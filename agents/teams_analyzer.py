# agents/teams_analyzer.py
# LangGraph Agent용 Teams 분석기 (Qdrant + LLM 기반)
import os
import sys
from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI
from langchain.embeddings import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain.tools.retriever import create_retriever_tool
from langchain.agents import create_openai_functions_agent, AgentExecutor
from qdrant_client.models import Filter, FieldCondition, MatchAny, DatetimeRange
from typing import Dict, Any, Optional

# Add parent directory to path for config import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import OPENAI_API_KEY, DEFAULT_MODEL,FAST_MODEL, PROMPTS_DIR, DATA_DIR, EMBEDDING_MODEL, TEAMS_COLLECTION

class State(Dict):
    user_id: Optional[str]
    user_name: Optional[str]
    target_date: Optional[str]
    wbs_data: Optional[Dict]
    teams_analysis_result: Optional[Dict]

class TeamsAnalyzer:
    """LangGraph Agent용 Teams 분석기"""
    
    def __init__(self, qdrant_vectorstore=None):
        # Qdrant DB 초기화
        if qdrant_vectorstore is None:
            client = QdrantClient(host="localhost", port=6333)
            self.db = QdrantVectorStore(
                client=client,
                collection_name=TEAMS_COLLECTION,
                embedding=HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
            )
        else:
            self.db = qdrant_vectorstore
            
        # LLM 초기화
        self.llm = ChatOpenAI(
            model=FAST_MODEL,
            temperature=0.2,
            max_tokens=2000
        )
        
        # 프롬프트 템플릿 로드
        with open(os.path.join(PROMPTS_DIR, "teams_analyzer_prompt.md"), "r", encoding="utf-8") as f:
            self.prompt_template_str = f.read()
        
        self.prompt = PromptTemplate.from_template(self.prompt_template_str)
        self.parser = JsonOutputParser()

    def analyze_teams_data(
            self,
            user_id: str,
            user_name: str,  
            target_date: str, 
            wbs_data: dict
        ) -> Dict[str, Any]:
        """
        Teams 데이터를 분석하여 특정 사용자의 활동을 요약합니다.
        
        :param user_id: 분석할 사용자 ID
        :param user_name: 사용자 이름
        :param target_date: 분석할 날짜 (YYYY-MM-DD 형식)
        :param wbs_data: WBS 작업 데이터
        :return: 분석 결과 딕셔너리
        """

        start_str = f"{target_date}T00:00:00Z"
        end_str = f"{target_date}T23:59:59Z"

        filter_ = Filter(
                must=[
                    FieldCondition(
                        key="metadata.author",
                        match=MatchAny(
                            any=[user_id, "Jira Cloud"])
                    ),
                    FieldCondition(
                        key="metadata.date",
                        range=DatetimeRange(
                            gte=start_str,
                            lte=end_str
                        )
                    )
                ]
            )
        
        retriever = self.db.as_retriever(search_kwargs={"filter": filter_})
        posts = retriever.invoke(f"사용자 {user_name}의 게시물")
        print(f"사용자 '{user_name}' ({user_id})의 문서 {len(posts)}개 발견")
        
        # 게시물 내용 결합
        posts_text = "\n\n".join([
            f"작성자: {post.metadata.get('author', 'Unknown')}\n내용: {post.page_content}"
            for post in posts
        ])
        
        # Chain 생성 (Agent 대신)
        chain = (
            {
                "posts": lambda x: posts_text,
                "wbs_data": lambda x: x["wbs_data"],
                "user_id": lambda x: x["user_id"],
                "user_name": lambda x: x["user_name"],
                "target_date": lambda x: x["target_date"],
                "agent_scratchpad": lambda x: ""
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
        analysis_result = self.analyze_teams_data(
            user_id=state["user_id"],
            user_name=state["user_name"],
            target_date=state["target_date"],
            wbs_data=state["wbs_data"]
        )
        return analysis_result
    
    def analyze_teams(self, state: State) -> State:
        """LangGraph Agent 호출용 메서드"""
        analysis_result = self.analyze_teams_data(
            user_id=state["user_id"],
            user_name=state["user_name"],
            target_date=state["target_date"],
            wbs_data=state["wbs_data"]
        )
        return {
            **state,
            "teams_analysis_result": analysis_result
        }
