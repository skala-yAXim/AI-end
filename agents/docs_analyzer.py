# agents/docs_analyzer.py
# LangGraph Agent용 Docs 분석기 (Qdrant + LLM 기반)
import os
import sys
from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from qdrant_client.models import Filter, FieldCondition, MatchAny

# Add parent directory to path for config import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import OPENAI_API_KEY, DEFAULT_MODEL, PROMPTS_DIR, DATA_DIR

client = QdrantClient(host="localhost", port=6333)
db = QdrantVectorStore(
        client=client,
        collection_name="docs-collection",
        embedding=OpenAIEmbeddings(model="text-embedding-3-small")
    )   

llm = ChatOpenAI(
        model=DEFAULT_MODEL,
        temperature=0.2,
        max_tokens=2000
    )

with open(os.path.join(PROMPTS_DIR, "docs_analyze_prompt.md"), "r", encoding="utf-8") as f:
    prompt_template_str = f.read()

prompt = PromptTemplate.from_template(prompt_template_str)
parser = JsonOutputParser()

def analyze_docs_data(
        user_id: str,
        user_name: str,  
        target_date: str, 
        wbs_data: dict,
        collection_name: str = "docs-collection"
    ) -> str:
    """
    문서 데이터를 분석하여 특정 사용자의 문서 기반 업무 수행을 요약합니다.
    
    :param user_id: 분석할 사용자 ID
    :param user_name: 사용자 이름 (문서 작성자명과 매칭)  
    :param target_date: 분석 기준 날짜 (YYYY-MM-DD 형식)
    :param wbs_data: WBS 작업 데이터
    :param collection_name: Qdrant 컬렉션 이름
    :return: 분석 결과 요약 문자열
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
    retriever = db.as_retriever(search_kwargs={"filter": filter_, "k": 20})
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
        | prompt 
        | llm 
        | parser
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
