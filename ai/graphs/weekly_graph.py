from qdrant_client import QdrantClient
from ai.tools.wbs_data_retriever import WBSDataRetriever
from ai.agents.weekly_report_generator import WeeklyReportGenerator
from core import config
from ai.graphs.state_definition import WeeklyLangGraphState
from langgraph.graph import StateGraph, END

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

def load_wbs_node(state: WeeklyLangGraphState) -> WeeklyLangGraphState:
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

def load_daily_reports_node(state: WeeklyLangGraphState) -> WeeklyLangGraphState:
    print("\n--- 일일 보고서 로드 노드 실행 ---")
    try:
        generator = WeeklyReportGenerator()

        user_name = state.get("user_name")
        start_date = state.get("start_date")
        end_date = state.get("end_date")
        
        print(start_date, end_date, user_name, state.get("user_name"), state.get("project_id"))

        updated_state = generator.load_daily_reports(state)
        
        print("일일 보고서 로드 완료")
        
        return updated_state

    except Exception as e:
        print(f"일일 보고서 로드 실패: {e}")
        state["error_message"] = (state.get("error_message", "") + f"\n일일 보고서 로드 실패: {e}").strip()
        state["comprehensive_report"] = {
            "report_metadata": {"success": False, "error": str(e)},
            "report_content": {"error": "일일 보고서 로드 실패"}
        }

    return state


def generate_weekly_report_node(state: WeeklyLangGraphState) -> WeeklyLangGraphState:
    print("\n--- 주간 보고서 생성 및 저장 노드 실행 ---")
    try:
        generator = WeeklyReportGenerator()

        user_name = state.get("user_name")
        user_id = state.get("user_id")
        start_date = state.get("start_date")
        end_date = state.get("end_date")

        daily_reports_data = state.get("daily_reports_data")
        if not daily_reports_data:
            raise ValueError("일일 보고서 데이터가 없습니다.")

        updated_state = generator.generate_weekly_report(state)

        return updated_state

    except Exception as e:
        print(f"주간 보고서 생성 실패: {e}")
        state["error_message"] = (state.get("error_message", "") + f"\n주간 보고서 생성 실패: {e}").strip()
        state["weekly_report_result"] = {
            "report_metadata": {"success": False, "error": str(e)},
            "report_content": {"error": "주간 보고서 생성 실패"}
        }

    return state

def create_weekly_graph():
    initialize_global_clients()
    if not qdrant_client_instance:
        raise ConnectionError("Qdrant 클라이언트 초기화에 실패하여 그래프를 생성할 수 없습니다.")

    workflow = StateGraph(WeeklyLangGraphState)

    workflow.add_node("load_wbs", load_wbs_node)
    workflow.add_node("load_daily", load_daily_reports_node)
    workflow.add_node("generate_report", generate_weekly_report_node)

    workflow.set_entry_point("load_wbs")
    workflow.add_edge("load_wbs", "load_daily")
    workflow.add_edge("load_daily", "generate_report")
    workflow.add_edge("generate_report", END) 
    
    app = workflow.compile()
    print("LangGraph 애플리케이션 컴파일 완료.")
    return app

if __name__ == "__main__":
    print("graph.py 직접 실행 - 그래프 생성 테스트")
    try:
        test_app = create_weekly_graph()
        print(f"테스트 그래프 생성 성공: {test_app}")
    except Exception as e:
        print(f"그래프 생성 중 오류: {e}")