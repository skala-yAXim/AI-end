# agents/docs_analyzer.py
# LangGraph Agent용 Docs 분석기 (Qdrant + LLM 기반)
import os
import sys
from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI
from langchain.embeddings import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from qdrant_client.models import Filter, FieldCondition, MatchAny
from typing import Dict, Any, Optional

# Add parent directory to path for config import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import OPENAI_API_KEY, DEFAULT_MODEL, PROMPTS_DIR, DATA_DIR, EMBEDDING_MODEL, DOCS_COLLECTION

class State(Dict):
    user_id: Optional[str]
    user_name: Optional[str]
    target_date: Optional[str]
    wbs_data: Optional[Dict]
    docs_analysis_result: Optional[Dict]

class DocsAnalyzer:
    """LangGraph Agent용 Docs 분석기"""
    
    def __init__(self, qdrant_vectorstore=None):
        # Qdrant DB 초기화
        if qdrant_vectorstore is None:
            client = QdrantClient(host="localhost", port=6333)
            self.db = QdrantVectorStore(
                client=client,
                collection_name=DOCS_COLLECTION,
                embedding=HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
            )
        else:
            self.db = qdrant_vectorstore
            
        # LLM 초기화
        self.llm = ChatOpenAI(
            model=DEFAULT_MODEL,
            temperature=0.2,
            max_tokens=2000
        )
        
        # 프롬프트 템플릿 로드
        with open(os.path.join(PROMPTS_DIR, "docs_analyze_prompt.md"), "r", encoding="utf-8") as f:
            self.prompt_template_str = f.read()
        
        self.prompt = PromptTemplate.from_template(self.prompt_template_str)
        self.parser = JsonOutputParser()

    def analyze_docs_data(
            self,
            user_id: str,
            user_name: str,  
            target_date: str, 
            wbs_data: dict
        ) -> Dict[str, Any]:
        """
        문서 데이터를 분석하여 특정 사용자의 문서 기반 업무 수행을 요약합니다.
        
        :param user_id: 분석할 사용자 ID
        :param user_name: 사용자 이름 (문서 작성자명과 매칭)  
        :param target_date: 분석 기준 날짜 (YYYY-MM-DD 형식)
        :param wbs_data: WBS 작업 데이터
        :return: 분석 결과 딕셔너리
        """

        # 문서는 작성자 기준으로 필터링 (날짜 제한 없음)
        # author 필드가 리스트일 수 있으므로 다양한 경우 고려
        filter_ = Filter(
                should=[  # OR 조건으로 변경
                    FieldCondition(
                        key="metadata.author",
                        match=MatchAny(any=[user_name, user_id])
                    ),
                    FieldCondition(
                        key="metadata.author",
                        match=MatchAny(any=[f'["{user_name}"]', f'["{user_id}"]'])  # 리스트 형태
                    ),
                    FieldCondition(
                        key="metadata.filename",
                        match=MatchAny(any=[user_name])  # 파일명에서도 검색
                    )
                ]
            )
        
        # 사용자 관련 문서 검색 (LangChain retriever 사용)
        retriever = self.db.as_retriever(search_kwargs={"filter": filter_, "k": 20})
        docs = retriever.invoke(f"사용자 {user_name}의 문서")
        
        print(f"사용자 '{user_name}' ({user_id})의 문서 {len(docs)}개 발견")
        
        # 문서 내용 결합
        documents_text = "\n\n".join([
            f"파일명: {doc.metadata.get('filename', 'Unknown')}\n내용: {doc.page_content}"
            for doc in docs
        ])
        
        # Chain 생성 (Agent 대신)
        chain = (
            {
                "documents": lambda x: documents_text,
                "wbs_data": lambda x: x["wbs_data"],
                "user_id": lambda x: x["user_id"],
                "user_name": lambda x: x["user_name"],
                "target_date": lambda x: x["target_date"]
            }
            | self.prompt 
            | self.llm 
            | self.parser
        )

        try:
            result = chain.invoke({
                "user_id": user_id,
                "user_name": user_name,
                "wbs_data": wbs_data,
                "target_date": target_date
            })
            return result
        except Exception as e:
            print(f"분석 중 오류 발생: {e}")
            return {
                "user_id": user_id,
                "date": target_date,
                "type": ["docs"],
                "matched_tasks": [],
                "unmatched_tasks": [],
                "error": str(e)
            }
        
    def __call__(self, state: State) -> Dict[str, Any]:
        """State를 입력받아 분석 결과 반환하는 callable 메서드"""
        analysis_result = self.analyze_docs_data(
            user_id=state["user_id"],
            user_name=state["user_name"],
            target_date=state["target_date"],
            wbs_data=state["wbs_data"]
        )
        return analysis_result
    
    def analyze_documents(self, state: State) -> State:
        """LangGraph Agent 호출용 메서드"""
        analysis_result = self.analyze_docs_data(
            user_id=state["user_id"],
            user_name=state["user_name"],
            target_date=state["target_date"],
            wbs_data=state["wbs_data"]
        )
        return {
            **state,
            "docs_analysis_result": analysis_result
        }
