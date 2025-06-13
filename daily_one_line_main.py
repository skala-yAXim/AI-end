import os
import json
import argparse
from typing import List

# 아래 두 모듈은 'core' 폴더에 있다고 가정합니다.
# core.state, core.graph 파일이 없다면 아래의 코드 블록들을 참고하여 생성해주세요.
from core.state_definition import ProgressSummaryState
from daily_one_line_graph import create_progress_summary_graph


def run_progress_summary_pipeline():
    """
    데일리 보고서와 WBS를 기반으로 진척도 요약을 생성하는 파이프라인을 실행합니다.
    """
    parser = argparse.ArgumentParser(description="데일리 보고서 기반 진척도 요약을 생성합니다.")
    parser.add_argument("--date", type=str, default="2025-06-13", help="현재 날짜 (YYYY-MM-DD)")
    parser.add_argument("--project-id", type=str, default="project_sample_001", help="프로젝트 ID")
    parser.add_argument("--user-name", type=str, default="조민서", help="보고서를 생성할 사용자 이름")
    parser.add_argument("--user-id", type=str, default="G-12345", help="사용자의 고유 ID")
    parser.add_argument("--target-date", type=str, default="2025-06-05", help="분석한 데일리 보고서의 날짜 (YYYY-MM-DD)")
    args = parser.parse_args()

    # --- 설정값 ---
    # 프로젝트 루트 디렉토리 설정 (이 파일이 있는 위치 기준)
    project_root = os.path.abspath(os.path.dirname(__file__))
    
    # 데일리 보고서 파일들이 저장된 디렉토리 경로
    REPORTS_INPUT_DIR = os.path.join(project_root, 'outputs')
    # 출력 디렉토리
    SUMMARY_OUTPUT_DIR = os.path.join(project_root, 'outputs', 'progress_summaries')
    
    # 출력 디렉토리가 없으면 생성
    os.makedirs(SUMMARY_OUTPUT_DIR, exist_ok=True)
    
    # 분석할 데일리 보고서 파일 경로
    daily_report_filename = f"daily_report_{args.user_name}_{args.target_date}.json"
    daily_report_filepath = os.path.join(REPORTS_INPUT_DIR, daily_report_filename)
    
    # daily_report = _prepare_daily_report(daily_report_filepath)

    print("--- 진척도 요약 파이프라인 시작 ---")
    print(f"대상 날짜: {args.date}")
    print(f"입력 파일: {os.path.abspath(daily_report_filepath)}")
    print(f"출력 디렉토리: {os.path.abspath(SUMMARY_OUTPUT_DIR)}")
    print("-" * 30)
    
    # 파이프라인 초기 상태 정의
    initial_state = ProgressSummaryState(
        date=args.date,
        project_id=args.project_id,
        user_name=args.user_name,
        user_id=args.user_id,
        target_date=args.target_date,
        daily_report_path=daily_report_filepath,
        daily_report=None, 
        wbs_data=None,
        progress_summary=None,
        error_message=""
    )
    
    # --- 실행 ---
    try:
        # LangGraph 애플리케이션 생성
        app = create_progress_summary_graph()
        
        print("\n--- LangGraph 워크플로우 실행 시작 ---")
        # 초기 상태를 입력으로 워크플로우 실행
        final_state = app.invoke(initial_state)
        print("--- LangGraph 워크플로우 실행 완료 ---\n")

        print("최종 분석 결과 (State 내용):")

        if final_state.get("error_message"):
            print(f"\n[실패] 파이프라인 실행 중 오류 발생: {final_state['error_message']}")
        else:
            summary = final_state.get("progress_summary")
            print(f"\n[성공] 생성된 진척도 요약:\n>> {summary}")
            
            # 결과를 JSON 파일로 저장
            output_filename = f"progress_summary_{args.user_name}_{args.target_date}.json"
            output_filepath = os.path.join(SUMMARY_OUTPUT_DIR, output_filename)
            
            result_data = {
                "date": args.target_date,
                "project_id": args.project_id,
                "summary": summary,
                "source_report": daily_report_filename
            }
            
            with open(output_filepath, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=4)
                
            print(f"\n요약 결과가 다음 경로에 저장되었습니다:\n{os.path.abspath(output_filepath)}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n[오류] 예기치 않은 오류가 발생했습니다: {e}")

if __name__ == '__main__':
    run_progress_summary_pipeline()
