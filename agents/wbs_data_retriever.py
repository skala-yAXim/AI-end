# agents/wbs_data_retriever_agent.py
import sys
import os
from typing import Optional, Dict, Any, List

from qdrant_client import QdrantClient 
# langchain_core.embeddings.Embeddings는 현재 WBS 조회 도구에서 직접 사용 안 함

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core import config # config.DEFAULT_VECTOR_DB_BASE_PATH 등 사용 가능성
from core.state_definition import LangGraphState
# 이전 core.vector_db_retriever.retrieve_wbs_data 대신 새로운 도구 사용
from tools.wbs_retriever_tool import get_project_task_items_tool, get_tasks_by_assignee_tool

class WBSDataRetriever:
    """
    LangGraph 노드로서 tools/wbs_retriever_tools.py의 함수를 사용하여
    VectorDB에서 WBS 데이터를 조회하여 State에 저장합니다.
    """
    def __init__(self, qdrant_client: QdrantClient): # QdrantClient를 받지만, wbs_retriever_tools가 자체적으로 핸들러 생성
        """
        QdrantClient를 인자로 받지만, 현재 WBS 조회 도구들은 자체적으로 DB 핸들러를 생성합니다.
        이 qdrant_client는 향후 다른 방식의 직접 조회가 필요할 경우를 위해 유지할 수 있습니다.
        """
        self.qdrant_client_param = qdrant_client # 파라미터로 받은 클라이언트 (현재 직접 사용 X)
        if not qdrant_client:
             print("WBSDataRetriever 경고: QdrantClient 인스턴스가 제공되지 않았습니다. WBS 도구는 자체 클라이언트를 생성합니다.")
        print("WBSDataRetriever: 초기화 완료. WBS 조회는 tools/wbs_retriever_tools.py의 함수를 사용합니다.")

    def load_wbs_data(self, state: LangGraphState) -> LangGraphState:
        project_id = state.get("project_id")
        user_name_for_task_filter = state.get("user_name") # WBS 작업 필터링용 user_name

        if not project_id:
            error_msg = "WBSDataRetriever (load_wbs_data): project_id가 State에 제공되지 않았습니다."
            print(error_msg)
            state["wbs_data"] = None
            current_error = state.get("error_message", "")
            state["error_message"] = (current_error + "\n" + error_msg).strip() if current_error else error_msg
            return state
            
        print(f"WBSDataRetriever (load_wbs_data): 프로젝트 '{project_id}'의 WBS 데이터 로딩 시작 (tools 사용)...")
        
        task_list: List[Dict] = []
        db_base_path_for_tool = None # 또는 config.DEFAULT_VECTOR_DB_BASE_PATH

        # 담당자 필터링 조건 결정 (user_id 우선, 없으면 user_name)
        assignee_filter_identifier = user_name_for_task_filter

        if assignee_filter_identifier:
            print(f"담당자 '{assignee_filter_identifier}' 기준으로 WBS 작업 필터링 시도.")
            task_list = get_tasks_by_assignee_tool(
                project_id=project_id,
                assignee_name_to_filter=assignee_filter_identifier,
                db_base_path=db_base_path_for_tool,
            )
        else:
            print("담당자 필터링 없이 프로젝트의 모든 WBS 작업 조회 시도.")
            task_list = get_project_task_items_tool(
                project_id=project_id,
                db_base_path=db_base_path_for_tool,
            )
        
        # State에 저장할 wbs_data 구조 구성
        # get_project_task_items_tool은 task_list만 반환하므로, project_summary 등은 없음.
        if task_list: # 작업 목록이 비어있지 않은 경우
            wbs_data_for_state = {
                "project_id": project_id,
                "project_summary": f"'{project_id}' 프로젝트의 WBS 작업 목록입니다. (요약 정보는 현재 제공되지 않음)", # 임시 요약
                "task_list": task_list
            }
            state["wbs_data"] = wbs_data_for_state
            print(f"WBSDataRetriever (load_w_bs_data): WBS 데이터 로드 완료. 작업 수: {len(task_list)} (필터링 적용됨)")
        else:
            state["wbs_data"] = { # 데이터가 없더라도 기본 구조는 유지
                "project_id": project_id,
                "project_summary": "해당 조건으로 조회된 WBS 작업이 없습니다.",
                "task_list": []
            }
            not_found_msg = f"프로젝트 '{project_id}'에 대한 WBS 작업을 찾을 수 없거나 조회 중 오류 발생 (필터: {assignee_filter_identifier or '없음'})."
            current_error = state.get("error_message", "")
            state["error_message"] = (current_error + "\n" + not_found_msg).strip() if current_error else not_found_msg
            print(f"WBSDataRetriever (load_wbs_data): {not_found_msg}")
            
        return state

    def __call__(self, state: LangGraphState) -> LangGraphState:
        return self.load_wbs_data(state)
