from typing import List, Dict, Any
from ai.tools.wbs_retriever_tool import get_tasks_by_assignee_tool

class WBSDataHandler:
    def __init__(self, settings):
        self.settings = settings

    def _format_wbs_tasks_for_llm(self, tasks: List[Dict]) -> str:
        """WBS 작업 목록을 LLM 프롬프트용 문자열로 포맷합니다."""
        if not tasks:
            return "### 할당된 WBS 업무 목록:\n해당 담당자에게 할당된 WBS 작업을 찾을 수 없거나, WBS 데이터가 없습니다."
        
        formatted_tasks = ["### 할당된 WBS 업무 목록:"]
        for task in tasks:
            task_details = (
                f"- 작업명: {task.get('task_name', 'N/A')}\n"
                f"  ID: {task.get('task_id', 'N/A')}\n"
                f"  담당자: {task.get('assignee', 'N/A')}\n"
                f"  상태 (WBS 기준): {task.get('status', 'N/A')}\n"
                f"  산출물: {task.get('deliverable', 'N/A')}\n"
                f"  시작 예정: {task.get('start_date', 'N/A')}\n"
                f"  종료 예정: {task.get('end_date', 'N/A')}"
            )
            formatted_tasks.append(task_details)
        return "\n".join(formatted_tasks)

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:

        project_id_for_wbs = state.get("project_id_for_wbs")
        wbs_assignee_name = state.get("wbs_assignee_name")

        if not all([project_id_for_wbs, wbs_assignee_name]):
            error_msg = "Missing required parameters in state for WBSDataHandler: project_id_for_wbs, wbs_assignee_name must be provided."
            print(f"Error: {error_msg}")
            state["wbs_handling_status"] = "error"
            state["wbs_handling_error_message"] = error_msg
            state["raw_wbs_tasks"] = []
            state["wbs_tasks_str_for_llm"] = self._format_wbs_tasks_for_llm([]) # 빈 목록 포맷팅
            return state

        print(f"Retrieving WBS tasks for project '{project_id_for_wbs}' and assignee '{wbs_assignee_name}'...")
        try:
            assigned_wbs_tasks = get_tasks_by_assignee_tool(
                project_id=project_id_for_wbs,
                assignee_name_to_filter=wbs_assignee_name,
            )
            print(f"Retrieved {len(assigned_wbs_tasks)} WBS tasks for assignee '{wbs_assignee_name}'.")
            state["raw_wbs_tasks"] = assigned_wbs_tasks
            state["wbs_tasks_str_for_llm"] = self._format_wbs_tasks_for_llm(assigned_wbs_tasks)
            state["wbs_handling_status"] = "success"
            state["wbs_handling_error_message"] = None

        except Exception as e:
            error_msg = f"Error retrieving WBS tasks: {e}"
            print(error_msg)
            state["raw_wbs_tasks"] = []
            state["wbs_tasks_str_for_llm"] = self._format_wbs_tasks_for_llm([]) # 빈 목록 포맷팅
            state["wbs_handling_status"] = "error"
            state["wbs_handling_error_message"] = error_msg
        
        print("WBSDataHandler __call__ completed.")
        return state

