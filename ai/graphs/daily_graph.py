from qdrant_client import QdrantClient
from langgraph.graph import StateGraph, END
from typing import List

from core import config
from ai.graphs.state_definition import LangGraphState

from ai.tools.wbs_data_retriever import WBSDataRetriever
from ai.agents.docs_analyzer import DocsAnalyzer
from ai.agents.docs_quality_analyzer import DocsQualityAnalyzer
from ai.agents.email_analyzer import EmailAnalyzerAgent
from ai.agents.git_analyzer import GitAnalyzerAgent
from ai.agents.teams_analyzer import TeamsAnalyzer
from ai.agents.daily_report_generator import DailyReportGenerator

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

def load_wbs_node(state: LangGraphState) -> LangGraphState:
    print("\n--- WBS 데이터 로딩 노드 실행 (WBSDataRetrieverAgent) ---")
    if not qdrant_client_instance:
        state["error_message"] = (state.get("error_message","") + "\n WBS 로딩 실패: Qdrant 클라이언트 미초기화").strip()
        print("WBS 로딩 실패: Qdrant 클라이언트가 초기화되지 않았습니다.")
        state["wbs_data"] = None # 명시적으로 wbs_data를 None으로 설정
        return state
        
    # WBSDataRetrieverAgent는 __init__에서 qdrant_client를 받지만,
    # tools/wbs_retriever_tools.py의 함수들은 자체적으로 DB 핸들러를 생성함.
    # 따라서 여기서 전달하는 qdrant_client_instance는 현재 WBS 조회에는 직접 사용되지 않을 수 있음.
    wbs_retriever_agent = WBSDataRetriever(qdrant_client=qdrant_client_instance)
    updated_state = wbs_retriever_agent(state) 
    if updated_state.get("wbs_data") and updated_state.get("wbs_data", {}).get("task_list"):
        print("WBS 데이터 로딩 완료.")
    else:
        print(f"WBS 데이터 로딩 실패 또는 작업 목록 없음.") # 오류 메시지는 agent 내부에서 state에 추가
    return updated_state

# (Docs, Email, Git, Teams 노드는 이전과 동일하게 qdrant_client_instance를 사용)
def analyze_docs_node(state: LangGraphState) -> LangGraphState:
    print("\n--- 문서 분석 노드 실행 ---")
    if not qdrant_client_instance:
        state["error_message"] = (state.get("error_message","") + "\n 문서 분석 실패: Qdrant 클라이언트 미초기화").strip()
        state["documents_analysis_result"] = {"error": "Qdrant client not initialized"}
        return state
    docs_analyzer = DocsAnalyzer(qdrant_client=qdrant_client_instance)
    return docs_analyzer(state)

def analyze_emails_node(state: LangGraphState) -> LangGraphState:
    print("\n--- 이메일 분석 노드 실행 ---")
    if not qdrant_client_instance:
        state["error_message"] = (state.get("error_message","") + "\n 이메일 분석 실패: Qdrant 클라이언트 미초기화").strip()
        state["email_analysis_result"] = {"error": "Qdrant client not initialized"}
        return state
    email_analyzer = EmailAnalyzerAgent(qdrant_client=qdrant_client_instance)
    return email_analyzer(state)

def analyze_git_node(state: LangGraphState) -> LangGraphState:
    print("\n--- Git 활동 분석 노드 실행 ---")
    if not qdrant_client_instance:
        state["error_message"] = (state.get("error_message","") + "\n Git 분석 실패: Qdrant 클라이언트 미초기화").strip()
        state["git_analysis_result"] = {"error": "Qdrant client not initialized"}
        return state
    git_analyzer = GitAnalyzerAgent(qdrant_client=qdrant_client_instance)
    return git_analyzer(state)

def analyze_teams_node(state: LangGraphState) -> LangGraphState:
    print("\n--- Teams 활동 분석 노드 실행 ---")
    if not qdrant_client_instance:
        state["error_message"] = (state.get("error_message","") + "\n Teams 분석 실패: Qdrant 클라이언트 미초기화").strip()
        state["teams_analysis_result"] = {"error": "Qdrant client not initialized"}
        return state
    teams_analyzer = TeamsAnalyzer(qdrant_client=qdrant_client_instance)
    return teams_analyzer(state)


def analyze_docs_quality_node(state: LangGraphState) -> LangGraphState:
    print("\n--- 문서 품질 분석 노드 실행 ---")
    if not qdrant_client_instance:
        state["error_message"] = (state.get("error_message","") + "\n 문서 품질 분석 실패: Qdrant 클라이언트 미초기화").strip()
        state["documents_quality_result"] = {"error": "Qdrant client not initialized"}
        return state
    docs_quality_analyzer = DocsQualityAnalyzer(qdrant_client=qdrant_client_instance)
    return docs_quality_analyzer.analyze_document_quality(state)

def generate_report_node(state: LangGraphState) -> LangGraphState:
    print("\n--- Daily 보고서 생성 노드 실행 ---")
    try:
        if not qdrant_client_instance:
            error_msg = "보고서 생성 실패: Qdrant 클라이언트 미초기화. WBS 툴을 생성할 수 없습니다."
            print(error_msg)
            state["error_message"] = (state.get("error_message","") + f"\n {error_msg}").strip()
            state["comprehensive_report"] = {
                "report_metadata": {"success": False, "error": error_msg},
                "report_content": {"error": "보고서 생성 실패"}
            }
            return state

        # WBSDataRetriever 인스턴스를 DailyReportGenerator에 전달
        # DailyReportGenerator는 이 인스턴스를 통해 Qdrant 클라이언트에 직접 접근합니다.
        wbs_retriever_tool_instance = WBSDataRetriever(qdrant_client=qdrant_client_instance)

        report_generator = DailyReportGenerator(wbs_retriever_tool_instance=wbs_retriever_tool_instance) 
        
        updated_state = report_generator.generate_daily_report(state)
        print("Daily 보고서 생성 완료.")
        return updated_state
    except Exception as e:
        print(f"Daily 보고서 생성 실패: {e}")
        state["error_message"] = (state.get("error_message","") + f"\n 보고서 생성 실패: {e}").strip()
        state["comprehensive_report"] = {
            "report_metadata": {"success": False, "error": str(e)},
            "report_content": {"error": "보고서 생성 실패"}
        }
        return state


def fan_out(_: LangGraphState) -> List[str]:
    return ["analyze_git", "analyze_emails", "analyze_teams", "analyze_docs_quality"]

def create_analysis_graph():
    initialize_global_clients()
    if not qdrant_client_instance:
        raise ConnectionError("Qdrant 클라이언트 초기화에 실패하여 그래프를 생성할 수 없습니다.")

    workflow = StateGraph(LangGraphState)

    workflow.add_node("load_wbs", load_wbs_node)
    workflow.add_node("analyze_docs_quality", analyze_docs_quality_node)
    workflow.add_node("analyze_docs", analyze_docs_node)
    workflow.add_node("analyze_git", analyze_git_node)
    workflow.add_node("analyze_emails", analyze_emails_node)
    workflow.add_node("analyze_teams", analyze_teams_node)
    workflow.add_node("generate_report", generate_report_node)

    workflow.set_entry_point("load_wbs")

    workflow.add_conditional_edges("load_wbs", fan_out, ["analyze_git", "analyze_emails", "analyze_teams", "analyze_docs_quality"])
    workflow.add_edge("analyze_docs_quality", "analyze_docs")

    # super-step 병렬 실행 구조를 만들어, 모든 노드가 실행되어야 `generate_report`로 넘어감
    workflow.add_edge(["analyze_git", "analyze_emails", "analyze_teams", "analyze_docs"], "generate_report")
    workflow.add_edge("generate_report", END)

    app = workflow.compile()
    print("LangGraph 애플리케이션 컴파일 완료.")
    return app

if __name__ == "__main__":
    print("graph.py 직접 실행 - 그래프 생성 테스트")
    try:
        test_app = create_analysis_graph()
        print(f"테스트 그래프 생성 성공: {test_app}")
    except Exception as e:
        print(f"그래프 생성 중 오류: {e}")

