# agents/docs_quality_analyzer.py
import os
from typing import Dict, Any, List, Optional

from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from core import config 
from ai.graphs.state_definition import LangGraphState 
from ai.tools.vector_db_retriever import retrieve_documents, retrieve_documents_content


class DocsQualityAnalyzer:
    def __init__(self, qdrant_client: QdrantClient):
        self.qdrant_client = qdrant_client
        self.llm = ChatOpenAI(
            model=config.DEFAULT_MODEL,
            temperature=0.2,
            max_tokens=2000,
            openai_api_key=config.OPENAI_API_KEY
        )
        
        self.json_parser = JsonOutputParser()
        self._load_prompts()
    
    def _load_prompts(self):
        """프롬프트 .md 파일들을 PromptTemplate 객체로 로드"""
        try:
            # 중요도 평가 프롬프트
            importance_path = os.path.join(config.PROMPTS_BASE_DIR, "docs_importance_evaluation_prompt.md")
            with open(importance_path, "r", encoding="utf-8") as f:
                importance_content = f.read()
            
            # 품질 평가 프롬프트
            quality_path = os.path.join(config.PROMPTS_BASE_DIR, "docs_quality_analyze_prompt.md")
            with open(quality_path, "r", encoding="utf-8") as f:
                quality_content = f.read()
            
            # PromptTemplate 객체 생성
            self.importance_prompt = PromptTemplate.from_template(importance_content)
            self.quality_prompt = PromptTemplate.from_template(quality_content)
            
        except FileNotFoundError as e:
            print(f"DocsQualityAnalyzer: 프롬프트 파일을 찾을 수 없음: {e}")

    def analyze_document_quality(self, state: LangGraphState) -> LangGraphState:
        """메인 문서 품질 분석 파이프라인"""
        user_id = state.get("user_id")
        target_date = state.get("target_date")
                
        if not user_id:
            return {
                "documents_quality_result": {"error": "user_id가 제공되지 않았습니다"},
                "retrieved_docs_list": []
            }

        # 문서 검색 (한 번만 실행)
        retrieved_docs_list = retrieve_documents(
            qdrant_client=self.qdrant_client,
            user_id=user_id,
            target_date_str=target_date,
        )
        
        if not retrieved_docs_list:
            print(f"DocsQualityAnalyzer: 사용자 ID '{user_id}'에 대한 분석할 문서가 없습니다 (대상일: {target_date}).")
            return {
                "documents_quality_result": {"error": "분석할 관련 문서를 찾지 못했습니다"},
                "retrieved_docs_list": []
            }

        print(f"DocsQualityAnalyzer: {len(retrieved_docs_list)}개 문서 발견")

        # 품질 분석 실행
        quality_results = self._analyze_quality_internal(retrieved_docs_list)

        # state에 retrieved_docs_list와 품질 분석 결과 모두 저장
        return {
            "documents_quality_result": quality_results,
            "retrieved_docs_list": retrieved_docs_list  # docs_analyzer에서 재사용
        }

    def _analyze_quality_internal(self, retrieved_docs_list: List[Dict]) -> Dict[str, Any]:
        """내부 품질 분석 로직"""
        try:
            # 1단계: 중요 문서 + 포함할 내용 선별
            important_docs, required_contents = self._get_important_documents_and_contents(retrieved_docs_list)
            
            if not important_docs:
                return {"error": "중요한 문서가 선별되지 않았습니다"}
            
            print(f"DocsQualityAnalyzer: 중요 문서: {important_docs}")
            print(f"DocsQualityAnalyzer: 필요 내용: {required_contents}")
            
            # 2단계: hybrid search로 관련 content 가져오기
            search_results = self._hybrid_search_for_quality(important_docs, required_contents)
            
            if not search_results:
                return {"error": "hybrid search 결과가 없습니다"}
            
            print(f"DocsQualityAnalyzer: hybrid search: {len(search_results)}개 chunk")
            
            # 3단계: 품질 평가
            quality_results = self._evaluate_quality_by_file(search_results)
            print(f"DocsQualityAnalyzer: 품질 평가: {len(quality_results)}개 문서")

            return {"evaluations": quality_results, "total_evaluated": len(quality_results)}
            
        except Exception as e:
            print(f"DocsQualityAnalyzer: 품질 분석 오류: {e}")
            return {"error": f"분석 중 오류 발생: {str(e)}"}

    def _get_important_documents_and_contents(self, retrieved_docs_list: List[Dict]) -> tuple[Optional[List[str]], Optional[Dict[str, List[str]]]]:
        """중요 문서와 포함할 내용 선별 (JSON parser 사용)"""
        
        # 지원되는 확장자 정의
        valid_extensions = {".docx", ".xlsx"}

        # 고유 문서 목록 생성 (파일명 기준으로 중복 제거)
        unique_docs = {}
        for doc in retrieved_docs_list:
            filename = doc.get("metadata", {}).get("filename")
            if filename and os.path.splitext(filename)[-1].lower() in valid_extensions:
                file_type = doc.get("metadata", {}).get("type", "Unknown")
                unique_docs[filename] = file_type
        
        if not unique_docs:
            print("DocsQualityAnalyzer: 지원되는 확장자(.docx, .xlsx)의 문서가 없습니다.")
            return None, None

        # 문서 목록 텍스트 생성
        doc_list = "\n".join([f"{i}. {filename} ({file_type})" 
                             for i, (filename, file_type) in enumerate(unique_docs.items(), 1)])
        
        try:
            # Chain 구성
            chain = (
                {
                    "doc_list": lambda x: x["input_doc_list"]
                }
                | self.importance_prompt
                | self.llm
                | self.json_parser
            )
            
            # Chain 실행
            result = chain.invoke({
                "input_doc_list": doc_list
            })
            
            print(f"DocsQualityAnalyzer: 중요도 분석 결과: {result}")
            
            # JSON에서 데이터 추출
            important_docs = result.get("important_docs", [])
            contents_dict = result.get("contents", {})
            
            # 결과 검증
            if not important_docs:
                print("DocsQualityAnalyzer: 중요 문서가 선별되지 않았습니다.")
                return None, None
            
            return important_docs, contents_dict

        except Exception as e:
            print(f"DocsQualityAnalyzer: 중요도 분석 JSON 파싱 오류: {e}")
            return None, None

    def _hybrid_search_for_quality(self, important_docs: List[str], required_contents: Dict[str, List[str]]) -> List[Dict]:
        """hybrid search로 품질 평가용 content 가져오기"""
        
        all_results = []
        
        for filename in important_docs:
            contents = required_contents.get(filename, ["문서 완성도"])
            
            try:
                # retrieve_documents_content 사용
                results = retrieve_documents_content(
                    qdrant_client=self.qdrant_client,
                    document_list=[{"filename": filename}],
                    queries=contents,
                    top_k=3  # 각 쿼리당 3개
                )
                
                all_results.extend(results)
                print(f"DocsQualityAnalyzer: {filename}: {len(results)}개 chunk 검색됨 (쿼리: {contents})")
                
            except Exception as e:
                print(f"DocsQualityAnalyzer: {filename} 검색 오류: {e}")
                continue
        
        return all_results

    def _evaluate_quality_by_file(self, search_results: List[Dict]) -> List[Dict]:
        """파일별로 chunk를 종합하여 품질 평가"""
        
        # 파일별로 chunk 그룹화
        file_chunks = {}
        for chunk in search_results:
            filename = chunk.get("filename") or chunk.get("metadata", {}).get("filename", "Unknown")
            if filename not in file_chunks:
                file_chunks[filename] = []
            file_chunks[filename].append(chunk)
        
        file_evaluations = []
        
        for filename, chunks in file_chunks.items():
            try:
                # 파일의 모든 chunk content 합치기
                combined_content = "\n\n".join([
                    f"[Chunk {i+1}]: {chunk.get('page_content', '')[:400]}"
                    for i, chunk in enumerate(chunks)
                ])
                
                # 품질 평가 Chain
                quality_evaluation_chain = (
                    {
                        "filename": lambda x: x["filename"],
                        "combined_content": lambda x: x["combined_content"]
                    }
                    | self.quality_prompt 
                    | self.llm
                    | self.json_parser 
                )

                result_json = quality_evaluation_chain.invoke({
                    "filename": filename,
                    "combined_content": combined_content
                })

                file_evaluations.append({
                    "filename": filename,
                    "evaluation": result_json,
                    "chunks_analyzed": len(chunks)
                })
                
                print(f"DocsQualityAnalyzer: {filename} 품질 평가 완료")
                
            except Exception as e:
                print(f"DocsQualityAnalyzer: {filename} 평가 오류: {e}")
                file_evaluations.append({
                    "filename": filename,
                    "evaluation": {"error": f"평가 중 오류 발생: {str(e)}"},
                    "chunks_analyzed": len(chunks)
                })

        return file_evaluations

    def __call__(self, state: LangGraphState) -> LangGraphState:
        return self.analyze_document_quality(state)