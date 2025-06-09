import os
import json
import argparse

# weekly_report_generator 모듈에서 WeeklyReportGenerator 클래스를 임포트합니다.
# 이 스크립트는 프로젝트의 루트 디렉토리에서 실행되는 것을 가정합니다.
from core.state_definition import WeeklyLangGraphState
from weekly_graph import create_weekly_graph

def run_weekly_workflow():
    """
    주간 업무 보고서 생성 프로세스를 실행하는 메인 함수입니다.
    """
    # 명령줄 인자를 파싱하여 사용자 정보를 받을 수 있도록 설정합니다.
    parser = argparse.ArgumentParser(description="사용자의 주간 업무 보고서를 생성합니다.")
    parser.add_argument("--user-name", type=str, default="조민서", help="보고서를 생성할 사용자 이름")
    parser.add_argument("--user-id", type=str, default="G-12345", help="사용자의 고유 ID")
    parser.add_argument("--start-date", type=str, default="2025-06-02", help="보고서 시작일 (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default="2025-06-06", help="보고서 종료일 (YYYY-MM-DD)")
    args = parser.parse_args()

    # --- 설정값 ---
    USER_NAME = args.user_name
    USER_ID = args.user_id
    START_DATE = args.start_date
    END_DATE = args.end_date
    
    # 프로젝트 루트 디렉토리 설정
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    
    # 보고서 파일들이 저장된 디렉토리 경로
    REPORTS_INPUT_DIR = os.path.join(project_root, 'outputs')
    # 출력 디렉토리
    REPORTS_OUTPUT_DIR = os.path.join(project_root, 'outputs', 'weekly_reports')
    
    # 출력 디렉토리가 없으면 생성
    os.makedirs(REPORTS_OUTPUT_DIR, exist_ok=True)
    
    print("--- 주간 보고서 생성 시작 ---")
    print(f"대상 사용자: {USER_NAME} ({USER_ID})")
    print(f"대상 기간: {START_DATE} ~ {END_DATE}")
    print(f"일일 보고서 입력 디렉토리: {os.path.abspath(REPORTS_INPUT_DIR)}")
    print(f"주간 보고서 출력 디렉토리: {os.path.abspath(REPORTS_OUTPUT_DIR)}")
    print("-" * 30)
    
    initial_state = WeeklyLangGraphState(
        user_name=USER_NAME,
        user_id=USER_ID,
        start_date=START_DATE,
        end_date=END_DATE,
        project_id="project_sample_001",
        wbs_data=None,
        daily_reports_data=None,
        weekly_report_result=None,
        error_message=""
    )
    
    # --- 실행 ---
    try:
        app = create_weekly_graph()
        
        print(f"DEBUG: initial_state: {initial_state}")

        print("\n--- LangGraph 워크플로우 실행 시작 ---")
        final_state = app.invoke(initial_state)
        print("--- LangGraph 워크플로우 실행 완료 ---\n")

        print("최종 분석 결과 (State 내용):")
        
        weekly_report_result = final_state.get("weekly_report_result")
        if weekly_report_result:
            if weekly_report_result and not weekly_report_result.get("error"):
                print("주간 보고서 생성 성공!")
                
                output_filename = f"weekly_report_{USER_NAME}_{START_DATE}_to_{END_DATE}.json"
                output_filepath = os.path.join(REPORTS_OUTPUT_DIR, output_filename)
                
                with open(output_filepath, "w", encoding="utf-8") as f:
                    json.dump(weekly_report_result, f, ensure_ascii=False, indent=4)
                    
                print(f"\n[성공] 주간 보고서가 다음 경로에 저장되었습니다:\n{os.path.abspath(output_filepath)}")
                
                # 생성된 보고서 내용 미리보기 출력
                print("\n--- 생성된 주간 보고서 내용 미리보기 ---")
                print(json.dumps(weekly_report_result, ensure_ascii=False, indent=2))
                print("---------------------------------------\n")
            else:
                print(f"\n[실패] 주간 보고서 생성에 실패했습니다: {weekly_report_result['message']}")
        else:
            print("\n[알림] 주간 보고서를 생성할 데이터가 없어 작업을 종료합니다.")
    except Exception as e:
        print(f"\n[오류] 예기치 않은 오류가 발생했습니다: {e}")

if __name__ == '__main__':
    # 이 스크립트가 직접 실행될 때 main 함수를 호출합니다.
    run_weekly_workflow()