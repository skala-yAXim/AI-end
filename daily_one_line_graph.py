import json
import os
from typing import List, Dict, Any

# LangChain 관련 라이브러리를 설치해야 합니다.
# pip install langchain langchain-openai langgraph
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from qdrant_client import QdrantClient

from core.state_definition import ProgressSummaryState
from agents.wbs_data_retriever import WBSDataRetriever
from agents.progress_summary_agent import ProgressSummaryAgent
from core import config

qdrant_client_instance = None

def initialize_global_clients():
    global qdrant_client_instance
    if qdrant_client_instance is None:
        try:
            qdrant_client_instance = QdrantClient(
                host=config.QDRANT_HOST, 
                port=config.QDRANT_PORT
            )
            print("Qdrant 클라이언트 초기화 성공.")
        except Exception as e:
            print(f"Qdrant 클라이언트 초기화 실패: {e}")
            raise 
    return qdrant_client_instance

def load_wbs_node(state: ProgressSummaryState) -> ProgressSummaryState:
    print("\n--- WBS 데이터 로딩 노드 실행 (WBSDataRetrieverAgent) ---")
    if not qdrant_client_instance:
        state["error_message"] = (state.get("error_message","") + "\n WBS 로딩 실패: Qdrant 클라이언트 미초기화").strip()
        print("WBS 로딩 실패: Qdrant 클라이언트가 초기화되지 않았습니다.")
        state["wbs_data"] = None # 명시적으로 wbs_data를 None으로 설정
        return state

    wbs_retriever_agent = WBSDataRetriever(qdrant_client=qdrant_client_instance)
    updated_state = wbs_retriever_agent(state) 
    if updated_state.get("wbs_data") and updated_state.get("wbs_data", {}).get("task_list"):
        print("WBS 데이터 로딩 완료.")
    else:
        print(f"WBS 데이터 로딩 실패 또는 작업 목록 없음.") # 오류 메시지는 agent 내부에서 state에 추가
    return updated_state

# --- Graph Nodes ---

def load_daily_report(state: ProgressSummaryState) -> ProgressSummaryState:
    """
    지정된 경로에서 데일리 보고서 JSON 파일을 로드하여 상태에 추가하는 노드.
    사용자께서 요청하신 '상태값에 적재하는 함수'의 역할을 합니다.
    """
    print("--- [Node] 데일리 보고서 로드 ---")
    report_path = state["daily_report_path"]
    print(f"보고서 경로: {report_path}")
    
    try:
        if not os.path.exists(report_path):
            raise FileNotFoundError(f"데일리 보고서 파일을 찾을 수 없습니다: {report_path}")
            
        with open(report_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        
        state["daily_report"] = content
        print("결과: 데일리 보고서 로드 성공")
    except Exception as e:
        print(f"오류: {e}")
        state["error_message"] = f"데일리 보고서 로드 실패: {e}"
    
    return state

def generate_progress_summary(state: ProgressSummaryState) -> ProgressSummaryState:
   
    print("\n--- [Node] 진척도 요약 생성 ---")
    if state.get("error_message"):
        print("이전 노드에서 오류가 발생하여 요약 생성을 건너뜁니다.")
        return state
    
    # Qdrant 클라이언트 인스턴스 확인
    if not qdrant_client_instance:
        error_msg = "요약 생성 실패: Qdrant 클라이언트가 초기화되지 않았습니다."
        state["error_message"] = (state.get("error_message","") + f"\n{error_msg}").strip()
        print(error_msg)
        return state
        
    # 에이전트 인스턴스 생성 및 실행
    summary_agent = ProgressSummaryAgent(qdrant_client=qdrant_client_instance)
    updated_state = summary_agent(state)
    
    if updated_state.get("progress_summary"):
        print("결과: 진척도 요약 생성 완료.")
    # 에이전트 내부에서 오류 메시지를 state에 이미 추가했으므로 별도 처리는 생략
        
    return updated_state

# --- LangGraph 그래프 생성 ---
def create_progress_summary_graph():
    initialize_global_clients()
    if not qdrant_client_instance:
        raise ConnectionError("Qdrant 클라이언트 초기화에 실패하여 그래프를 생성할 수 없습니다.")

    """
    데일리 보고서 기반 진척도 요약 생성을 위한 LangGraph 워크플로우를 생성합니다.
    """
    workflow = StateGraph(ProgressSummaryState)

    # 1. 노드(작업 단위)들을 그래프에 추가합니다.
    workflow.add_node("load_daily_report", load_daily_report)
    workflow.add_node("load_wbs_node", load_wbs_node)
    workflow.add_node("generate_summary", generate_progress_summary)

    # 2. 노드 간의 작업 순서(흐름)를 정의합니다.
    workflow.set_entry_point("load_daily_report") # 시작점
    workflow.add_edge("load_daily_report", "load_wbs_node")
    workflow.add_edge("load_wbs_node", "generate_summary")
    workflow.add_edge("generate_summary", END) # 종료점

    # 3. 그래프를 컴파일하여 실행 가능한 애플리케이션으로 만듭니다.
    app = workflow.compile()
    print("\n--- 진척도 요약 그래프 생성 완료 ---\n")
    return app
