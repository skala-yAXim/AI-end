# agents/docs_quality_analyzer.py
import os
import sys
from typing import Dict, Any, List

from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import config 
from core.state_definition import LangGraphState 
from tools.wbs_matcher import WBSMatcher


class DocsQualityAnalyzer:
    def __init__(self, qdrant_client: QdrantClient):
        self.qdrant_client = qdrant_client
        self.wbs_matcher = WBSMatcher(qdrant_client)
        self.llm = ChatOpenAI(
            model=config.DEFAULT_MODEL,
            temperature=0.2,
            max_tokens=1000,
            openai_api_key=config.OPENAI_API_KEY
        )
        self.parser = JsonOutputParser()
        self.similarity_threshold = 0.2  # 유사도 임계값 조정
        
        # 품질 평가 프롬프트 로드
        prompt_file_path = os.path.join(config.PROMPTS_BASE_DIR, "docs_quality_analyze_prompt.md")
        try:
            with open(prompt_file_path, "r", encoding="utf-8") as f:
                prompt_template_str = f.read()
            self.prompt = PromptTemplate.from_template(prompt_template_str)
        except FileNotFoundError:
            # 기본 프롬프트
            self.prompt = PromptTemplate.from_template(
                "Deliverable: {deliverable}\n"
                "파일: {filename}\n"
                "내용: {page_content}\n\n"
                "품질을 평가하여 JSON으로 반환:\n"
                '{{"deliverable": "{deliverable}", "title": "{title}", "reason": "간결한 평가", "LLM_reference": "상세 근거"}}'
            )

    def analyze_document_quality(self, state: LangGraphState) -> LangGraphState:
        user_id = state.get("user_id")
        project_id = state.get("project_id")
        
        if not user_id:
            state["quality_analysis_result"] = {"error": "user_id 없음", "type": "quality"}
            return state
        
        # 1단계: WBS-문서 매칭
        matched_result = self.wbs_matcher.match_documents_to_wbs(user_id=user_id, project_id=project_id)
        
        if matched_result.get("error"):
            state["quality_analysis_result"] = {"error": matched_result["error"], "type": "quality"}
            return state
        
        # 2단계: 고유사도 청크 추출
        quality_results = self._evaluate_quality(matched_result)
        state["quality_analysis_result"] = quality_results
        return state
    
    def extract_high_similarity_chunks(self, matched_docs: List[Dict]) -> List[Dict]:
        """유사도 임계값 이상의 청크만 추출하고 파일별로 그룹화 (.docx, .xlsx만)"""
        # 유사도 필터링 + 파일 형식 필터링
        high_similarity_chunks = []
        allowed_extensions = ['.docx', '.xlsx']
        
        for doc in matched_docs:
            similarity = doc.get("similarity_score", 0)
            filename = doc.get("metadata", {}).get("filename", "")
            
            # 파일 확장자 확인
            file_extension = None
            for ext in allowed_extensions:
                if filename.lower().endswith(ext):
                    file_extension = ext
                    break
            
            # 유사도 및 파일 형식 조건 모두 충족
            if similarity >= self.similarity_threshold and file_extension:
                high_similarity_chunks.append(doc)
        
        # 파일별로 그룹화
        file_groups = {}
        for chunk in high_similarity_chunks:
            filename = chunk.get("metadata", {}).get("filename", "Unknown")
            if filename not in file_groups:
                file_groups[filename] = []
            file_groups[filename].append(chunk)
        
        # 각 파일별로 대표 청크 선택 (최고 유사도)
        representative_chunks = []
        for filename, chunks in file_groups.items():
            # 유사도 높은 순으로 정렬하고 첫 번째를 대표로 선택
            chunks.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
            best_chunk = chunks[0]
            
            # 같은 파일의 모든 청크 내용을 합쳐서 대표 청크에 추가
            combined_content = "\n".join([chunk.get("page_content", "") for chunk in chunks])
            best_chunk["combined_content"] = combined_content
            best_chunk["chunk_count"] = len(chunks)
            
            representative_chunks.append(best_chunk)
        
        return representative_chunks[:3]  # 최대 3개 파일
    
    def _evaluate_quality(self, matched_result: Dict[str, Any]) -> Dict[str, Any]:
        """품질 평가 실행"""
        matched_deliverables = matched_result.get("matched_deliverables", {})
        all_deliverables = matched_result.get("all_deliverables", [])
        deliverable_info = matched_result.get("deliverable_info", {})
        
        evaluated_deliverables = []
        unmatched_deliverables = []
        
        for deliverable in all_deliverables:
            docs = matched_deliverables.get(deliverable, [])
            
            if not docs:
                # 매칭되지 않은 deliverable
                unmatched_deliverables.append(deliverable)
                continue
                
            # 고유사도 청크 추출 (.docx, .xlsx만)
            high_similarity_chunks = self.extract_high_similarity_chunks(docs)
            
            if not high_similarity_chunks:
                unmatched_deliverables.append(deliverable)
                continue
            
            # 각 청크별 품질 평가
            chunk_evaluations = []
            for chunk in high_similarity_chunks:
                evaluation = self._evaluate_single_chunk(deliverable, chunk)
                if evaluation:
                    chunk_evaluations.append(evaluation)
            
            if chunk_evaluations:
                # task 정보 추가
                task_info = deliverable_info.get(deliverable, {})
                evaluated_deliverables.append({
                    "task_id": task_info.get("task_id", ""),
                    "task_name": task_info.get("task_name", ""),
                    "deliverable": deliverable,
                    "chunks": chunk_evaluations
                })
            else:
                unmatched_deliverables.append(deliverable)
        
        return {
            "evaluated_deliverables": evaluated_deliverables,
            "unmatched_deliverables": unmatched_deliverables
        }
    
    def _evaluate_single_chunk(self, deliverable: str, chunk: Dict) -> Dict[str, Any]:
        """단일 청크(파일) 품질 평가"""
        filename = chunk.get("metadata", {}).get("filename", "Unknown")
        
        # 합쳐진 내용이 있으면 사용, 없으면 기본 page_content 사용
        if "combined_content" in chunk:
            page_content = chunk["combined_content"]
        else:
            page_content = chunk.get("page_content", "")
        
        if not page_content.strip():
            return None
            
        chain = self.prompt | self.llm | self.parser
        
        result = chain.invoke({
            "deliverable": deliverable,
            "filename": filename,
            "page_content": page_content[:800],
            "title": filename  # 파일명만 사용
        })
        
        # 요청된 형식에 맞게 결과 정리
        clean_result = {
            "title": filename,
            "reason": result.get("reason", "N/A"),
            "LLM_reference": result.get("LLM_reference", "N/A"),
            "similarity_score": chunk.get("similarity_score", 0)
        }
        
        return result

    def __call__(self, state: LangGraphState) -> LangGraphState:
        return self.analyze_document_quality(state)
