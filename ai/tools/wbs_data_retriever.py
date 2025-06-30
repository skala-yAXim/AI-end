from typing import Dict, List, Any, Optional
import json

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Filter, FieldCondition, MatchValue, IsNullCondition, MatchText
)

from langchain.retrievers import EnsembleRetriever
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from ai.graphs.state_definition import LangGraphState
from ai.tools.wbs_retriever_tool import get_project_task_items_tool, get_tasks_by_assignee_tool
from core import config
from ai.utils.embed_query import embed_query 

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
        self.qdrant_client_param = qdrant_client 
        self.collection_name = config.COLLECTION_WBS_DATA

        if not qdrant_client:
             print("WBSDataRetriever 경고: QdrantClient 인스턴스가 제공되지 않았습니다. WBS 도구는 자체 클라이언트를 생성합니다.")
        print("WBSDataRetriever: 초기화 완료. WBS 조회는 tools/wbs_retriever_tools.py의 함수를 사용합니다.")

    def load_wbs_data(self, state: LangGraphState) -> LangGraphState:
        projects = state.get("projects")
        project_ids = [project.id for project in projects]
        user_name_for_task_filter = state.get("user_name") # WBS 작업 필터링용 user_name

        if not projects:
            error_msg = "WBSDataRetriever (load_wbs_data): project가 State에 제공되지 않았습니다."
            print(error_msg)
            state["wbs_data"] = None
            current_error = state.get("error_message", "")
            state["error_message"] = (current_error + "\n" + error_msg).strip() if current_error else error_msg
            return state
        
        tasks: Dict[str, List[Dict]] = {}
        
        for project_id in project_ids:
            print(f"WBSDataRetriever (load_wbs_data): 프로젝트 '{project_id}'의 WBS 데이터 로딩 시작 (tools 사용)...")
        
            task_list: List[Dict] = []

            # 담당자 필터링 조건 결정 (user_id 우선, 없으면 user_name)
            assignee_filter_identifier = user_name_for_task_filter

            if assignee_filter_identifier:
                print(f"담당자 '{assignee_filter_identifier}' 기준으로 WBS 작업 필터링 시도.")
                task_list = get_tasks_by_assignee_tool(
                    project_id=project_id,
                    assignee_name_to_filter=assignee_filter_identifier,
                )
            else:
                print("담당자 필터링 없이 프로젝트의 모든 WBS 작업 조회 시도.")
                task_list = get_project_task_items_tool(
                    project_id=project_id,
                )
            
            tasks[project_id] = task_list
            print(f"WBSDataRetriever (load_w_bs_data): WBS 데이터 로드 완료. 작업 수: {len(task_list)} (필터링 적용됨)")
        
        # State에 저장할 wbs_data 구조 구성
        # get_project_task_items_tool은 task_list만 반환하므로, project_summary 등은 없음.
        if tasks: # 작업 목록이 비어있지 않은 경우
            state["wbs_data"] = tasks
        else:
            state["wbs_data"] = {}
            not_found_msg = f"프로젝트 '{project_ids}'에 대한 WBS 작업을 찾을 수 없거나 조회 중 오류 발생 (필터: {assignee_filter_identifier or '없음'})."
            current_error = state.get("error_message", "")
            state["error_message"] = (current_error + "\n" + not_found_msg).strip() if current_error else not_found_msg
            print(f"WBSDataRetriever (load_wbs_data): {not_found_msg}")
            
        return state

    def __call__(self, state: LangGraphState) -> LangGraphState:
        return self.load_wbs_data(state)

    def retrieve_relevant_wbs_data_hybrid(
        self, 
        query_text: str, 
        project_ids: Optional[List[int]] = None, 
        limit: int = 5
    ) -> Optional[List[Dict[str, Any]]]:
        
        print(f"WBSDataRetriever: 하이브리드 검색 시작 - 쿼리: '{query_text[:50]}', 프로젝트 ID(s): '{project_ids or '모든 프로젝트'}'")
        
        if not query_text.strip():
            print("WBSDataRetriever: 쿼리 텍스트가 없어 검색을 수행할 수 없습니다.")
            return None

        try:
            project_filter = Filter(
                should=[
                    FieldCondition(key="project_id", match=MatchValue(value=pid))
                    for pid in project_ids
                ]
            )

            if not self.qdrant_client_param:
                print("WBSDataRetriever 오류: Qdrant 클라이언트가 초기화되지 않았습니다.")
                return None
            
            # === Dense 검색 ===
            dense_vector = embed_query(query_text)
            dense_results = self.qdrant_client_param.search(
                collection_name=self.collection_name,
                query_vector=dense_vector,
                query_filter=project_filter,
                limit=20,
                with_payload=True
            )
            dense_docs = [
                {"source": "dense", "score": r.score, "payload": r.payload}
                for r in dense_results
            ]
            # print(f"Dense 검색 결과: {dense_docs}")


            # === Sparse 검색 ===
            keyword_filter = FieldCondition(
                key="original_data",
                match=MatchText(text=query_text)
            )

            project_filter = Filter(
                should=[
                    FieldCondition(key="project_id", match=MatchValue(value=pid))
                    for pid in project_ids
                ]
            )

            final_filter = Filter(must=[keyword_filter, project_filter])

            sparse_results, _ = self.qdrant_client_param.scroll(
                collection_name=self.collection_name,
                scroll_filter=final_filter,
                limit=20,
                with_payload=True
            )

            sparse_docs = [
                {"source": "sparse", "score": 1.0, "payload": r.payload}
                for r in sparse_results
            ]
            # print(f"Sparse 검색 결과: {sparse_docs}")
            # 병합
            merged = {}
            for r in dense_docs + sparse_docs:
                task_id = r["payload"].get("task_id")
                if task_id:
                    merged[task_id] = r

            ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:limit]

            print(f"WBSDataRetriever: 하이브리드 검색 최종 결과 {len(ranked)}개의 관련 WBS 데이터 발견.")

            print("검색 결과 값은 아래와 같습니다. : ")
            # print([r["payload"] for r in ranked])
            return [r["payload"] for r in ranked]

        except Exception as e:
            print(f"WBSDataRetriever: 하이브리드 WBS 데이터 조회 중 오류 발생: {e}")
            return None
