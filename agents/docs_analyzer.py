# agents/docs_analyzer.py
import os
import sys
from typing import Dict, Any, Optional

from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI
# from langchain_core.embeddings import Embeddings # retriever 직접 사용 안 함
# from langchain_community.embeddings import HuggingFaceEmbeddings # retriever 직접 사용 안 함
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import config 
from core.state_definition import LangGraphState 
from tools.vector_db_retriever import retrieve_documents

class DocsAnalyzer:
    def __init__(self, qdrant_client: QdrantClient): # embeddings_model 제거
        self.qdrant_client = qdrant_client
        # self.embeddings_model = embeddings_model # 제거
            
        self.llm = ChatOpenAI(
            model=config.DEFAULT_MODEL,
            temperature=0.2,
            max_tokens=2000,
            openai_api_key=config.OPENAI_API_KEY
        )
        
        prompt_file_path = os.path.join(config.PROMPTS_BASE_DIR, "docs_analyze_prompt.md")
        try:
            with open(prompt_file_path, "r", encoding="utf-8") as f:
                prompt_template_str = f.read()
            self.prompt = PromptTemplate.from_template(prompt_template_str)
        except FileNotFoundError:
            print(f"DocsAnalyzer: 오류 - 프롬프트 파일을 찾을 수 없습니다: {prompt_file_path}")
            self.prompt = PromptTemplate.from_template(
                "사용자 ID {user_id} (이름: {user_name})의 다음 문서들을 분석하여 WBS({wbs_data})와 관련된 주요 내용을 요약하고, 관련 작업 매칭 결과를 JSON으로 반환해주세요:\n\n{documents}\n\n분석 기준일: {target_date}"
            ) # user_id 사용 명시
        self.parser = JsonOutputParser()

    def _count_unique_documents(self, retrieved_docs_list: list) -> int:
        """문서 리스트에서 고유한 문서의 개수를 계산합니다."""
        unique_filenames = set()
        
        for doc_item in retrieved_docs_list:
            metadata = doc_item.get("metadata", {})
            filename = metadata.get("filename", metadata.get("title", "Unknown Document"))
            unique_filenames.add(filename)
        
        return len(unique_filenames)
    
    def _analyze_docs_data_internal(
        self,
        user_id: str,
        user_name: Optional[str],
        target_date: str,
        wbs_data: Optional[dict],
        retrieved_docs_list: list,
        docs_quality_result: Optional[dict] = None,
        project_name: Optional[str] = None,
        project_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        print(f"DocsAnalyzer: 사용자 ID '{user_id}'의 문서 {len(retrieved_docs_list)}개 분석 시작.")
        
        # Unique 문서 개수 계산
        unique_count = self._count_unique_documents(retrieved_docs_list)

        # 문서가 아예 없으면 요약 없이 종료
        if not retrieved_docs_list:
            return {
                "user_id": user_id,
                "user_name": user_name or user_id,
                "date": target_date,
                "type": ["docs"],
                "source_collection": config.COLLECTION_DOCUMENTS,
                "matched_tasks": [],
                "unmatched_tasks": [],
                "summary": "분석할 관련 문서를 찾지 못했습니다.",
                "error": None,
                "retrieved_count": 0
            }

        # 문서 내용을 텍스트로 정리
        documents_text_parts = []
        for doc_item in retrieved_docs_list:
            metadata = doc_item.get("metadata", {})
            filename = metadata.get("filename", metadata.get("title", "Unknown Document"))
            title = doc_item.get("title", "")
            author = metadata.get("author", user_id)  # 작성자 없으면 user_id 사용
            
            documents_text_parts.append(f"파일명: {filename}\n작성자: {author}\n제목:\n{title}...\n---")

        documents_text = "\n\n".join(documents_text_parts)
        wbs_data_str = str(wbs_data) if wbs_data else "WBS 정보 없음"

        # 프롬프트로 넘길 입력값 구성 
        chain = (
            {
                "documents": lambda x: x["documents_text"],
                "wbs_data": lambda x: x["wbs_info"],
                "user_id": lambda x: x["in_user_id"],
                "user_name": lambda x: x["in_user_name"],
                "target_date": lambda x: x["in_target_date"],
                "docs_quality_result": lambda x: x["docs_quality_result"],
                "total_tasks": lambda x: x["in_total_tasks"],
                "project_name": lambda x: x["project_name"],
                "project_description": lambda x: x["project_description"],
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
                "docs_quality_result": docs_quality_result,
                "in_total_tasks": unique_count,
                "project_name": project_name,
                "project_description": project_description,
            })
            return result
        
        except Exception as e:
            print(f"DocsAnalyzer: LLM 분석 중 오류 발생: {e}")
            return {
                "user_id": user_id,
                "user_name": user_name or user_id,
                "date": target_date,
                "type": ["docs"],
                "source_collection": config.COLLECTION_DOCUMENTS,
                "error": str(e),
                "retrieved_count": len(retrieved_docs_list)
            }

    def analyze_documents(self, state: LangGraphState) -> LangGraphState:
        print(f"DocsAnalyzer: 사용자 ID '{state.get('user_id')}'의 문서 분석 시작...")
        
        user_id = state.get("user_id")
        user_name = state.get("user_name") # 표시용으로 사용 가능
        target_date = state.get("target_date")
        wbs_data = state.get("wbs_data")
        quality_result = state.get("documents_quality_result", {})
        
        project_name = state.get("project_name")
        project_description = state.get("project_description")        
        
        if not user_id:
            error_msg = "DocsAnalyzer: user_id가 State에 제공되지 않아 분석을 건너뜁니다."
            print(error_msg)
            analysis_result = {"error": error_msg, "type": "docs"}
        elif not target_date: # 날짜 필터링 필수
            error_msg = "EmailAnalyzerAgent: target_date가 State에 제공되지 않아 분석을 건너뜁니다."
            print(error_msg); analysis_result = {"error": error_msg, "type": "Email"}
        else:
            retrieved_docs_list = retrieve_documents(
                qdrant_client=self.qdrant_client,
                user_id=user_id,
                target_date_str=target_date,
            )
            state["retrieved_documents"] = retrieved_docs_list

            analysis_result = self._analyze_docs_data_internal(
                user_id=user_id,
                user_name=user_name, # LLM 프롬프트용
                target_date=target_date, # 분석 컨텍스트용 날짜
                wbs_data=wbs_data,
                retrieved_docs_list=retrieved_docs_list,
                docs_quality_result=quality_result,
                project_name = project_name,
                project_description = project_description
            )
        
        return {"documents_analysis_result": analysis_result}

    def __call__(self, state: LangGraphState) -> LangGraphState:
        return self.analyze_documents(state)
