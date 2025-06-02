import argparse
import os
import sys
import json

from wbs_analyze_agent.core.vector_db import VectorDBHandler
from wbs_analyze_agent.core.config import Settings # API 키 등 설정 로드

def print_results(results: dict, query_description: str):
    """ChromaDB 조회 결과를 보기 좋게 출력하는 함수"""
    print(f"\n--- {query_description} ---")
    if results and results.get('ids') and len(results['ids']) > 0:
        print(f"총 {len(results['ids'])}개의 항목을 찾았습니다.")
        for i in range(min(3, len(results['ids']))): # 최대 3개 항목 미리보기
            print(f"  결과 #{i+1}:")
            if results.get('documents') and len(results['documents']) > i:
                print(f"    문서 (일부): {results['documents'][i]}...")
            if results.get('metadatas') and len(results['metadatas']) > i:
                meta = results['metadatas'][i]
                print(f"    메타데이터:")
                print(f"      - project_id: {meta.get('project_id')}")
                print(f"      - output_type: {meta.get('output_type')}")
                print(f"      - wbs_hash: {meta.get('wbs_hash', 'N/A')[:10]}...")
                if meta.get('original_data'):
                    try:
                        original_data_dict = json.loads(meta['original_data'])
                        print(f"      - 원본 데이터 (일부 키):")
                        for key, value in list(original_data_dict.items()): # 원본 데이터의 처음 3개 키-값 쌍
                            if isinstance(value, list) or isinstance(value, dict):
                                print(f"        - {key}: (복합 데이터)")
                            else:
                                print(f"        - {key}: {str(value)}")
                    except json.JSONDecodeError:
                        print(f"        - 원본 데이터 (파싱 불가): {meta['original_data']}...")
            print("-" * 20)
        if len(results['ids']) > 3:
            print(f"... 외 {len(results['ids']) - 3}개의 추가 항목이 있습니다.")
    else:
        print("해당 조건으로 조회된 데이터가 없습니다.")

def main():
    parser = argparse.ArgumentParser(description="WBS 적재 데이터 검증 스크립트")
    parser.add_argument("--project_id", required=True, help="검증할 프로젝트의 고유 ID")
    parser.add_argument("--db_path", help="VectorDB가 저장된 기본 경로 (선택 사항, 없으면 config의 기본값 사용)")
    parser.add_argument("--collection_prefix", default="wbs_data", help="컬렉션 이름 접두사 (기본값: wbs_data)")
    # 특정 항목 조회를 위한 선택적 인자들
    parser.add_argument("--task_id_to_check", help="조회할 특정 작업 ID (선택 사항)")
    parser.add_argument("--assignee_to_check", help="조회할 특정 담당자 이름 (선택 사항)")


    args = parser.parse_args()

    print("--- WBS 적재 데이터 검증 시작 ---")
    print(f"프로젝트 ID: {args.project_id}")
    
    try:
        # 설정 로드 (API 키 필요 - VectorDBHandler 내 임베딩 함수 초기화 시)
        app_settings = Settings()
        
        db_path_to_use = args.db_path or app_settings.VECTOR_DB_PATH_ENV or app_settings.DEFAULT_VECTOR_DB_BASE_PATH
        print(f"VectorDB 기본 경로: {db_path_to_use}")

        # VectorDB 핸들러 초기화
        # VectorDBHandler는 db_base_path 아래에 project_id와 collection_prefix를 조합한 경로에 DB를 생성/관리함
        # 따라서 db_base_path만 정확히 지정해주면 됨.
        db_handler = VectorDBHandler(
            db_base_path=db_path_to_use, # 이 경로 아래에 컬렉션별 폴더가 생김
            collection_name_prefix=args.collection_prefix, # agent.py에서 사용한 것과 동일해야 함
            project_id=args.project_id,
            embedding_api_key=app_settings.OPENAI_API_KEY
        )
        
        # 1. 프로젝트 개요 조회
        overview_results = db_handler.collection.get(
            where={"$and": [
                {"project_id": args.project_id},
                {"output_type": "project_overview"}
            ]},
            include=["documents", "metadatas"]
        )
        print_results(overview_results, f"'{args.project_id}' 프로젝트 개요 (output_type='project_overview')")

        # 2. 작업 항목 조회 (일반적인 task_item 조회)
        task_item_results = db_handler.collection.get(
            where={"$and": [
                {"project_id": args.project_id},
                {"output_type": "task_item"}
            ]},
            limit=100, # 너무 많으면 출력이 길어지므로 일부만
            include=["documents", "metadatas"]
        )
        print_results(task_item_results, f"'{args.project_id}' 프로젝트 작업 항목 샘플 (output_type='task_item', 최대 5개)")

        # 3. 특정 작업 ID로 조회 (인자가 주어졌을 경우)
        if args.task_id_to_check:
            specific_task_results = db_handler.collection.get(
                where={"$and": [
                    {"project_id": args.project_id},
                    {"output_type": "task_item"},
                    {"task_id": args.task_id_to_check} # 메타데이터 필터링
                ]},
                limit=1, 
                include=["documents", "metadatas"]
            )
            print_results(specific_task_results, f"'{args.project_id}' 프로젝트 특정 작업 ID '{args.task_id_to_check}' 조회")

        # 4. 담당자별 작업 부하 조회 (특정 담당자, 인자가 주어졌을 경우)
        if args.assignee_to_check:
            assignee_workload_results = db_handler.collection.get(
                where={"$and": [
                    {"project_id": args.project_id},
                    {"output_type": "assignee_workload_detail"},
                    {"assignee_name": args.assignee_to_check} # 메타데이터 필터링
                ]},
                include=["documents", "metadatas"]
            )
            print_results(assignee_workload_results, f"'{args.project_id}' 프로젝트 담당자 '{args.assignee_to_check}' 작업 부하 조회")

        # 5. 지연된 작업 조회
        delayed_task_results = db_handler.collection.get(
            where={"$and": [
                {"project_id": args.project_id},
                {"output_type": "delayed_task"}
            ]},
            limit=5, # 일부만 조회
            include=["documents", "metadatas"]
        )
        print_results(delayed_task_results, f"'{args.project_id}' 프로젝트 지연된 작업 샘플 (output_type='delayed_task', 최대 5개)")

        print("\n--- 데이터 검증 완료 ---")

    except ValueError as e:
        print(f"검증 스크립트 실행 중 설정 오류: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"검증 스크립트 실행 중 파일 관련 오류: {e}")
        sys.exit(1)
    except RuntimeError as e: # DB 핸들러 초기화 등에서 발생 가능
        print(f"검증 스크립트 실행 중 런타임 오류: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"검증 스크립트 실행 중 예상치 못한 오류 발생: {e}")
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
