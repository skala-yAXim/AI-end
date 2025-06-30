# agents/docs_analyzer.py
import os
from typing import Dict, Any, Optional, List

from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate

from core import config 
from ai.graphs.state_definition import LangGraphState 
from ai.tools.vector_db_retriever import retrieve_documents
from schemas.project_info import ProjectInfo

class DocsAnalyzer:
    def __init__(self, qdrant_client: QdrantClient):
        self.qdrant_client = qdrant_client
            
        self.llm = ChatOpenAI(
            model=config.DEFAULT_MODEL,
            temperature=0.2,
            max_tokens=2000,
            openai_api_key=config.OPENAI_API_KEY
        )
        
        self._load_prompt()
        self.parser = JsonOutputParser()

    def _load_prompt(self):
        """프롬프트 파일 로드"""
        prompt_file_path = os.path.join(config.PROMPTS_BASE_DIR, "docs_analyze_prompt.md")
        try:
            with open(prompt_file_path, "r", encoding="utf-8") as f:
                prompt_template_str = f.read()
            self.prompt = PromptTemplate.from_template(prompt_template_str)
        except FileNotFoundError:
            # 기본 프롬프트 설정
            self.prompt = PromptTemplate.from_template(
                "사용자 ID {user_id} (이름: {user_name})의 다음 문서들을 분석하여 WBS({wbs_data})와 관련된 주요 내용을 요약하고, 관련 작업 매칭 결과를 JSON으로 반환해주세요:\n\n{documents}\n\n분석 기준일: {target_date}"
            )

    def _get_retrieved_docs_list(self, state: LangGraphState) -> List[Dict]:
        """state에서 retrieved_docs_list를 가져오거나, 없으면 직접 검색"""
        retrieved_docs_list = state.get("retrieved_docs_list")
        
        if retrieved_docs_list:
            print(f"DocsAnalyzer: state에서 {len(retrieved_docs_list)}개 문서 재사용")
            return retrieved_docs_list
        
        # state에 없으면 직접 검색
        user_id = state.get("user_id")
        target_date = state.get("target_date")
        
        retrieved_docs_list = retrieve_documents(
            qdrant_client=self.qdrant_client,
            user_id=user_id,
            target_date_str=target_date,
        )
        
        return retrieved_docs_list

    def _count_unique_documents(self, retrieved_docs_list: List[Dict]) -> int:
        """문서 리스트에서 고유한 문서의 개수를 계산"""
        unique_filenames = set()
        
        for doc_item in retrieved_docs_list:
            metadata = doc_item.get("metadata", {})
            filename = metadata.get("filename", metadata.get("title", "Unknown Document"))
            unique_filenames.add(filename)
        
        return len(unique_filenames)

    def _format_documents_for_analysis(self, retrieved_docs_list: List[Dict], user_id: str) -> str:
        """문서 목록을 분석용 텍스트로 포맷팅"""
        if not retrieved_docs_list:
            return "분석할 문서가 없습니다."
        
        documents_text_parts = []
        for doc_item in retrieved_docs_list:
            metadata = doc_item.get("metadata", {})
            filename = metadata.get("filename", metadata.get("title", "Unknown Document"))
            title = doc_item.get("title", "")
            author = metadata.get("author", user_id)  # 작성자 없으면 user_id 사용
            
            documents_text_parts.append(
                f"파일명: {filename}\n작성자: {author}\n제목:\n{title}...\n---"
            )

        return "\n\n".join(documents_text_parts)
    
    def _analyze_docs_data_internal(
        self,
        user_id: str,
        user_name: Optional[str],
        target_date: str,
        wbs_data: Optional[dict],
        retrieved_docs_list: List[Dict],
        docs_quality_result: Optional[dict] = None,
        projects: List[ProjectInfo] = None,
    ) -> Dict[str, Any]:
        """내부 문서 분석 로직"""
        print(f"DocsAnalyzer: 사용자 ID '{user_id}'의 문서 {len(retrieved_docs_list)}개 분석 시작")
        
        # Unique 문서 개수 계산
        unique_count = self._count_unique_documents(retrieved_docs_list)

        # 문서가 없으면 기본 응답 반환
        if not retrieved_docs_list:
            return {
                "user_id": user_id,
                "user_name": user_name or user_id,
                "date": target_date,
                "type": "docs",
                "docs_analysis": {
                    "matched_docs": [],
                    "unmatched_docs": []
                },
                "daily_reflection": {
                    "content": [
                        "분석 대상 데이터가 없어 업무 분석을 수행할 수 없습니다."
                    ]
                },
                "total_tasks": 0
            }

        # 문서 내용을 텍스트로 정리
        documents_text = self._format_documents_for_analysis(retrieved_docs_list, user_id)
        wbs_data_str = str(wbs_data) if wbs_data else "WBS 정보 없음"

        # LLM Chain 구성
        chain = (
            {
                "documents": lambda x: x["documents_text"],
                "wbs_data": lambda x: x["wbs_info"],
                "user_id": lambda x: x["in_user_id"],
                "user_name": lambda x: x["in_user_name"],
                "target_date": lambda x: x["in_target_date"],
                "docs_quality_result": lambda x: x["docs_quality_result"],
                "total_tasks": lambda x: x["in_total_tasks"],
                "projects": lambda x: x["projects"]
            }
            | self.prompt
            | self.llm
            | self.parser
        )

        try:
            result = chain.invoke({
                "in_user_id": user_id,
                "in_user_name": user_name or user_id,
                "in_target_date": target_date,
                "wbs_info": wbs_data_str,
                "documents_text": documents_text,
                "docs_quality_result": docs_quality_result or {},
                "in_total_tasks": unique_count,
                "projects": projects
            })
            
            # 결과 검증 및 기본값 설정
            if not isinstance(result, dict):
                raise ValueError("LLM이 올바른 JSON을 반환하지 않았습니다.")
            
            return result
        
        except Exception as e:
            print(f"DocsAnalyzer: LLM 분석 중 오류 발생: {e}")

    def analyze_documents(self, state: LangGraphState) -> LangGraphState:
        """메인 문서 분석 메서드"""
        user_id = state.get("user_id")
        user_name = state.get("user_name")
        target_date = state.get("target_date")
        wbs_data = state.get("wbs_data")
        quality_result = state.get("documents_quality_result", {})
        projects = state.get("projects")
                
        # 필수 파라미터 검증
        if not user_id:
            error_msg = "DocsAnalyzer: user_id가 State에 제공되지 않아 분석을 건너뜁니다."
            print(error_msg)
            return {"documents_analysis_result": {"error": error_msg, "type": "docs"}}
        
        if not target_date:
            error_msg = "DocsAnalyzer: target_date가 State에 제공되지 않아 분석을 건너뜁니다."
            print(error_msg)
            return {"documents_analysis_result": {"error": error_msg, "type": "docs"}}

        # retrieved_docs_list 가져오기 (state에서 재사용 또는 직접 검색)
        retrieved_docs_list = self._get_retrieved_docs_list(state)

        # 문서 분석 실행
        analysis_result = self._analyze_docs_data_internal(
            user_id=user_id,
            user_name=user_name,
            target_date=target_date,
            wbs_data=wbs_data,
            retrieved_docs_list=retrieved_docs_list,
            docs_quality_result=quality_result,
            projects=projects
        )
        
        return {"documents_analysis_result": analysis_result}

    def __call__(self, state: LangGraphState) -> LangGraphState:
        return self.analyze_documents(state)