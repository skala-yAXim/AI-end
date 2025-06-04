"""
작성자 : 노건표
작성일 : 2025-06-01 
작성내용 : WBS 작업 항목 조회 Tool 구현

get_project_task_items_tool : VectorDB에서 특정 프로젝트 ID에 해당하는 모든 작업 항목(task_item)을 조회.
이 함수는 'tool calling' 방식으로 사용될 수 있도록 설계됨.
이 함수들은 VectorDB에서 데이터를 조회하고, 조회된 데이터를 원본 데이터 딕셔너리 형태로 반환.

업데이트 내역:

작성자 : 노건표
작성일 : 2025-06-01
작성내용 : WBS 작업 항목 조회 Tool 구현
get_tasks_by_assignee_tool : VectorDB에서 특정 프로젝트 ID와 담당자 이름에 해당하는 작업 항목(task_item)을 조회.

"""
import json
from typing import List, Dict, Optional
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.utils import Settings 
from agents.wbs_analyze_agent.core.vector_db import VectorDBHandler

import json
from typing import List, Dict, Optional # Union 제거됨

def get_project_task_items_tool(
    project_id: str,
    db_base_path: Optional[str] = None,
    collection_prefix: str = "wbs_data",
    limit_results: Optional[int] = None
) -> List[Dict]:
    """
    지정된 프로젝트 ID에 해당하는 모든 작업 항목(task_item)을 VectorDB에서 조회합니다.
    """
    print(f"--- WBS 작업 항목 조회 도구 실행 (전체 작업): 프로젝트 ID '{project_id}' ---")
    retrieved_tasks: List[Dict] = []

    try:
        app_settings = Settings() # 수정된 Settings 클래스명 사용
        db_path_to_use = db_base_path or app_settings.VECTOR_DB_PATH_ENV or app_settings.DEFAULT_VECTOR_DB_BASE_PATH
        print(f"VectorDB 기본 경로 사용: {db_path_to_use}")

        db_handler = VectorDBHandler(
            db_base_path=db_path_to_use,
            collection_name_prefix=collection_prefix,
            project_id=project_id,
            embedding_api_key=app_settings.OPENAI_API_KEY
        )

        query_params = {
            "where": {
                "$and": [
                    {"project_id": project_id},
                    {"output_type": "task_item"}
                ]
            },
            "include": ["metadatas"]
        }
        if limit_results is not None and limit_results > 0:
             query_params["limit"] = limit_results

        print(f"컬렉션 '{db_handler.collection_name}'에서 작업 항목 조회 중 (최대 {limit_results if limit_results else '전체'}건)...")
        results = db_handler.collection.get(**query_params)

        if results and results.get('metadatas'):
            for meta in results['metadatas']:
                if 'original_data' in meta:
                    try:
                        task_data = json.loads(meta['original_data'])
                        retrieved_tasks.append(task_data)
                    except json.JSONDecodeError:
                        print(f"경고: 메타데이터의 original_data 파싱 실패 - {meta.get('id', 'N/A')}")
            print(f"VectorDB에서 총 {len(retrieved_tasks)}개의 작업 항목을 가져왔습니다 (Python 후처리 필터링 전).")
        else:
            print("해당 조건으로 VectorDB에서 조회된 작업 항목이 없습니다.")

    except ValueError as e:
        print(f"오류: 도구 실행 중 설정 문제 발생 - {e}")
    except RuntimeError as e:
        print(f"오류: 도구 실행 중 런타임 문제 발생 - {e}")
    except Exception as e:
        import traceback
        print(f"오류: WBS 작업 항목 조회 중 예상치 못한 문제 발생 - {e}")
        print(traceback.format_exc())

    return retrieved_tasks


def get_tasks_by_assignee_tool(
    project_id: str,
    assignee_name_to_filter: str,
    db_base_path: Optional[str] = None,
    collection_prefix: str = "wbs_data",
    initial_fetch_limit: Optional[int] = None
) -> List[Dict]:
    """
    지정된 프로젝트 ID의 모든 작업 항목을 가져온 후,
    Python 단에서 담당자 이름(리스트 또는 단일 문자열, 또는 단일 문자열 내 포함)을 기준으로 후처리 필터링합니다.
    """
    print(f"--- WBS 작업 항목 조회 및 후처리 필터링 (담당자별): 프로젝트 ID '{project_id}', 필터링 담당자 '{assignee_name_to_filter}' ---")

    if not assignee_name_to_filter:
        print("오류: 필터링할 담당자 이름(assignee_name_to_filter)은 필수입니다.")
        return []

    all_project_tasks = get_project_task_items_tool(
        project_id=project_id,
        db_base_path=db_base_path,
        collection_prefix=collection_prefix,
        limit_results=initial_fetch_limit
    )

    if not all_project_tasks:
        print(f"프로젝트 '{project_id}'에 대한 작업 항목을 찾을 수 없습니다. 담당자 필터링을 진행할 수 없습니다.")
        return []

    filtered_tasks: List[Dict] = []
    print(f"가져온 {len(all_project_tasks)}개 작업 항목에 대해 담당자 '{assignee_name_to_filter}'(으)로 후처리 필터링 시작...")

    for task_data in all_project_tasks:
        assignee_field_value = task_data.get('assignee')

        if assignee_field_value is None:
            continue

        # 담당자 필드가 단일 문자열인 경우: 필터링할 이름이 포함되어 있는지 확인
        if isinstance(assignee_field_value, str):
            if assignee_name_to_filter in assignee_field_value: # 수정된 부분: 정확한 일치에서 포함(contains)으로 변경
                filtered_tasks.append(task_data)
        # 담당자 필드가 리스트인 경우: 필터링할 이름이 리스트의 멤버인지 확인
        elif isinstance(assignee_field_value, list):
            if assignee_name_to_filter in assignee_field_value:
                filtered_tasks.append(task_data)
        else:
            print(f"경고: 작업 ID '{task_data.get('task_id', 'N/A')}'의 담당자 필드가 문자열 또는 리스트가 아닙니다 (타입: {type(assignee_field_value)}, 값: {assignee_field_value}). 필터링에서 제외됩니다.")

    print(f"후처리 필터링 완료. 담당자 '{assignee_name_to_filter}'에게 할당된 작업 {len(filtered_tasks)}건을 찾았습니다.")
    return filtered_tasks


if __name__ == "__main__":
    try:
        Settings() # 수정된 Settings 클래스명 사용
        print(".env 설정 로드 확인됨 (또는 OPENAI_API_KEY가 환경 변수에 직접 설정됨).")
    except ValueError as e:
        print(f"주의: .env 파일 또는 OPENAI_API_KEY 환경 변수 설정 문제 가능성 - {e}")
    except NameError: 
        print("치명적 오류: Settings 클래스를 임포트하거나 정의할 수 없습니다. 경로를 확인하세요.")
        sys.exit(1)


    example_project_id = "project_sample_002" 
    example_db_path = None 
    example_assignee_to_filter = "김용준" 

    # --- 담당자별 작업 조회 (후처리 필터링 방식) 테스트 ---
    print(f"\n=== '{example_project_id}' 프로젝트, 담당자 '{example_assignee_to_filter}' 작업 항목 조회 테스트 (후처리 필터링 방식) ===")
    tasks_for_specific_assignee = get_tasks_by_assignee_tool(
        project_id=example_project_id,
        assignee_name_to_filter=example_assignee_to_filter,
        db_base_path=example_db_path,
        collection_prefix="wbs_data",
        initial_fetch_limit=None
    )

    if tasks_for_specific_assignee:
        print(f"\n'{example_project_id}' 프로젝트에서 담당자 '{example_assignee_to_filter}'(으)로 필터링된 작업 항목:")
        for i, task in enumerate(tasks_for_specific_assignee):
            print(f"\n  [필터링된 작업 항목 #{i+1}]")
            print(f"    ID: {task.get('task_id', 'N/A')}")
            print(f"    이름: {task.get('task_name', 'N/A')}")
            print(f"    담당자 (원본 데이터): {task.get('assignee', 'N/A')}")
            print(f"    상태: {task.get('status', 'N/A')}")
    else:
        print(f"\n'{example_project_id}' 프로젝트에서 담당자 '{example_assignee_to_filter}'의 작업 항목을 찾을 수 없거나 조회 중 오류가 발생했습니다.")

