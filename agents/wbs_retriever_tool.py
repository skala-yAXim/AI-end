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

from wbs_analyze_agent.core.vector_db import VectorDBHandler # 실제 환경에 맞게 경로 수정 필요
from wbs_analyze_agent.core.config import Settings # 실제 환경에 맞게 경로 수정 필요


def get_project_task_items_tool(
    project_id: str,
    db_base_path: Optional[str] = None,
    collection_prefix: str = "wbs_data",
    limit_results: Optional[int] = None
) -> List[Dict]:
    print(f"--- WBS 작업 항목 조회 도구 실행 (전체 작업): 프로젝트 ID '{project_id}' ---")
    retrieved_tasks: List[Dict] = []

    try:
        app_settings = Settings()
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
        
        print(f"컬렉션 '{db_handler.collection_name}'에서 작업 항목 조회 중...")
        results = db_handler.collection.get(**query_params)

        if results and results.get('metadatas'):
            for meta in results['metadatas']:
                if 'original_data' in meta:
                    try:
                        task_data = json.loads(meta['original_data'])
                        retrieved_tasks.append(task_data)
                    except json.JSONDecodeError:
                        print(f"경고: 메타데이터의 original_data 파싱 실패 - {meta.get('id', 'N/A')}")
            print(f"총 {len(retrieved_tasks)}개의 작업 항목을 성공적으로 조회했습니다.")
        else:
            print("해당 조건으로 조회된 작업 항목이 없습니다.")

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
    assignee_name: str,
    db_base_path: Optional[str] = None,
    collection_prefix: str = "wbs_data",
    limit_results: Optional[int] = None
) -> List[Dict]:
    print(f"--- WBS 작업 항목 조회 도구 실행 (담당자별): 프로젝트 ID '{project_id}', 담당자 '{assignee_name}' ---")

    retrieved_tasks: List[Dict] = []

    if not assignee_name:
        print("오류: 담당자 이름(assignee_name)은 필수입니다.")
        return retrieved_tasks

    try:
        app_settings = Settings()
        db_path_to_use = db_base_path or app_settings.VECTOR_DB_PATH_ENV or app_settings.DEFAULT_VECTOR_DB_BASE_PATH
        print(f"VectorDB 기본 경로 사용: {db_path_to_use}")

        db_handler = VectorDBHandler(
            db_base_path=db_path_to_use,
            collection_name_prefix=collection_prefix,
            project_id=project_id,
            embedding_api_key=app_settings.OPENAI_API_KEY
        )

        # VectorDB에서 필터링을 위해 'assignee' 필드가 메타데이터의 최상위 키로 존재해야 합니다.
        # 이 부분은 위의 주석에서 설명된 것처럼 `VectorDBHandler`의 데이터 저장 로직에서 처리되어야 합니다.
        query_params = {
            "where": {
                "$and": [
                    {"project_id": project_id},
                    {"output_type": "task_item"},
                    {"assignee": assignee_name} # 'assignee' 메타데이터 필드로 필터링
                ]
            },
            "include": ["metadatas"] # 원본 데이터는 메타데이터 내 'original_data'에 저장되어 있음
        }
        if limit_results is not None and limit_results > 0:
            query_params["limit"] = limit_results

        print(f"컬렉션 '{db_handler.collection_name}'에서 담당자 '{assignee_name}'의 작업 항목 조회 중...")
        results = db_handler.collection.get(**query_params)

        if results and results.get('metadatas'):
            for meta_item in results['metadatas']: # 변수명 변경 (meta -> meta_item)
                if 'original_data' in meta_item:
                    try:
                        task_data = json.loads(meta_item['original_data'])
                        # VectorDB 필터가 정확히 동작했다면, task_data.get('assignee')는 assignee_name과 일치할 것입니다.
                        # 필요하다면 여기서 추가 검증: if task_data.get('assignee') == assignee_name:
                        retrieved_tasks.append(task_data)
                    except json.JSONDecodeError:
                        print(f"경고: 메타데이터의 original_data 파싱 실패 - {meta_item.get('id', 'N/A')}")
            print(f"총 {len(retrieved_tasks)}개의 작업 항목을 성공적으로 조회했습니다 (담당자: {assignee_name}).")
        else:
            print(f"해당 조건으로 조회된 작업 항목이 없습니다 (담당자: {assignee_name}).")
            print("    - `VectorDBHandler`에서 `task_item` 저장 시 메타데이터에 'assignee' 필드가 올바르게 추가되었는지 확인하세요.")
            print("    - 담당자 이름이 정확한지, 해당 담당자에게 할당된 작업이 실제로 존재하는지 확인하세요.")


    except ValueError as e: 
        print(f"오류: 도구 실행 중 설정 문제 발생 - {e}")
    except RuntimeError as e: 
        print(f"오류: 도구 실행 중 런타임 문제 발생 - {e}")
    except Exception as e:
        import traceback
        print(f"오류: 담당자별 WBS 작업 항목 조회 중 예상치 못한 문제 발생 - {e}")
        print(traceback.format_exc())

    return retrieved_tasks


if __name__ == "__main__":
    try:
        Settings() 
        print(".env 설정 로드 확인됨 (또는 OPENAI_API_KEY가 환경 변수에 직접 설정됨).")
    except ValueError as e:
        print(f"주의: .env 파일 또는 OPENAI_API_KEY 환경 변수 설정 문제 가능성 - {e}")
        print("테스트 실행을 위해 OPENAI_API_KEY='your_api_key_here' 와 같은 임시 설정이 필요할 수 있습니다.")
        print("또한, VECTOR_DB_PATH_ENV 또는 DEFAULT_VECTOR_DB_BASE_PATH가 설정되어 있어야 합니다.")

    example_project_id = "project_sample_002" 
    example_db_path = None 
    example_assignee_name = "김용준" 

    print(f"\n=== '{example_project_id}' 프로젝트 전체 작업 항목 조회 테스트 ===")
    task_items_all = get_project_task_items_tool(
        project_id=example_project_id,
        db_base_path=example_db_path,
        limit_results=5
    )

    if task_items_all:
        print(f"\n'{example_project_id}' 프로젝트에서 조회된 전체 작업 항목 (최대 5개):")
        for i, task in enumerate(task_items_all):
            print(f"\n [작업 항목 #{i+1}]")
            print(f" ID: {task.get('task_id', 'N/A')}")
            print(f" 이름: {task.get('task_name', 'N/A')}")
            print(f" 담당자: {task.get('assignee', 'N/A')}") 
            print(f" 상태: {task.get('status', 'N/A')}")
            print(f" 시작일: {task.get('start_date', 'N/A')}")
            print(f" 종료일/마감일: {task.get('end_date') or task.get('due_date', 'N/A')}")
            print(f" 진행도(%): {task.get('progress_percentage', 'N/A')}")
            print(f" 산출물: {task.get('deliverables', 'N/A')}")
    else:
        print(f"\n'{example_project_id}' 프로젝트에서 전체 작업 항목을 찾을 수 없거나 조회 중 오류가 발생했습니다.")

    print(f"\n=== '{example_project_id}' 프로젝트, 담당자 '{example_assignee_name}' 작업 항목 조회 테스트 ===")
    tasks_by_assignee = get_tasks_by_assignee_tool(
        project_id=example_project_id,
        assignee_name=example_assignee_name,
        db_base_path=example_db_path,
        limit_results=100
    )

    if tasks_by_assignee:
        print(f"\n'{example_project_id}' 프로젝트, 담당자 '{example_assignee_name}'에게 할당된 작업 항목:")
        for i, task in enumerate(tasks_by_assignee):
            print(f"\n  [담당자 작업 항목 #{i+1}]")
            print(f"    ID: {task.get('task_id', 'N/A')}")
            print(f"    이름: {task.get('task_name', 'N/A')}")
            print(f"    담당자: {task.get('assignee', 'N/A')}") 
    else:
        print(f"\n'{example_project_id}' 프로젝트에서 담당자 '{example_assignee_name}'의 작업 항목을 찾을 수 없거나 조회 중 오류가 발생했습니다.")
        print("    - VectorDB에 데이터가 올바르게 적재되었는지, 특히 'assignee' 메타데이터 필드가 정확한지 확인해주세요 (위의 주석 참고).")
        print("    - 담당자 이름이 정확한지 확인해주세요.")

    print("\n--- 모든 조회 테스트 완료 ---")
