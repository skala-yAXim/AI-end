# agents/teams_analyzer.py
# LangGraph Agent용 Teams 분석기 (ChromaDB + LLM 기반)
import os
import sys
from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain.tools.retriever import create_retriever_tool
from langchain.agents import create_openai_functions_agent, AgentExecutor
from qdrant_client.models import Filter, FieldCondition, MatchAny, DatetimeRange

# Add parent directory to path for config import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import OPENAI_API_KEY, DEFAULT_MODEL, PROMPTS_DIR, DATA_DIR

client = QdrantClient(host="localhost", port=6333)
db = QdrantVectorStore(
        client=client,
        collection_name="teams-posts",
        embedding=OpenAIEmbeddings(model="text-embedding-3-small")
    )   

llm = ChatOpenAI(
        model=DEFAULT_MODEL,
        temperature=0.2,
        max_tokens=2000
    )

with open(os.path.join(PROMPTS_DIR, "teams_analyzer_prompt.md"), "r", encoding="utf-8") as f:
    prompt_template_str = f.read()

prompt = PromptTemplate.from_template(prompt_template_str)
parser = JsonOutputParser()

def analyze_teams_data(
        user_id:str,
        user_name:str,  
        target_date:str, 
        wbs_data:dict,
        collection_name:str = "teams-posts"
    ) -> str:
    """
    Teams 데이터를 분석하여 특정 사용자의 활동을 요약합니다.
    
    :param user_id: 분석할 사용자 ID
    :param target_date: 분석할 날짜 (YYYY-MM-DD 형식)
    :param collection_name: Qdrant 컬렉션 이름
    :return: 분석 결과 요약 문자열
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
    
    retriever = db.as_retriever(search_kwargs={"filter": filter_})

    retriever_tool = create_retriever_tool(
        retriever=retriever,
        name="teams_search_tool",
        description="특정 사용자의 Teams 게시글에서 필요한 업무 활동 정보를 검색합니다."
    )

    agent = create_openai_functions_agent(
        llm=llm,
        tools=[retriever_tool],
        prompt=prompt  # ← 프롬프트 하나만 넣는다
    )

    agent_executor = AgentExecutor(agent=agent, tools=[retriever_tool], verbose=True)

    return agent_executor.invoke({
        "user_id": user_id,
        "user_name": user_name,
        "wbs_data": wbs_data,
        "target_date": target_date
    })
    