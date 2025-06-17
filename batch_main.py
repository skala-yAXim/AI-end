# main.py (최소 수정 버전)
import os
import sys
from dotenv import load_dotenv
from pprint import pprint
import json 
from datetime import datetime
import time
import schedule

# 현재 디렉토리를 sys.path에 추가 (graph.py가 루트에 있다고 가정)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from graph import create_analysis_graph 
from core.state_definition import LangGraphState

from langchain.globals import set_llm_cache
set_llm_cache(None)

# 하드코딩된 사용자 데이터
HARDCODED_USERS = [
    {
        'user_id': 4,
        'user_name': '조민서',
        'project_id': 'project_sample_001',
        'github_email': 'minsuh3203@gmail.com',
        'project_name': '개인 업무 관리 AI 프로젝트',
        'project_description': 'AI 기술로 자동 수집·분석하여 객관적이고 정확한 개인 업무 성과 보고서를 자동 생성하는 시스템'
    },
   {
        'user_id': 7,
        'user_name': "노건표",
        'project_id': 'project_sample_001',
        'github_email': 'kproh99@naver.com',
        'project_name': '개인 업무 관리 AI 프로젝트',
        'project_description': 'AI 기술로 자동 수집·분석하여 객관적이고 정확한 개인 업무 성과 보고서를 자동 생성하는 시스템'
    },
]

def run_analysis_workflow(user_config=None):
    """
    단일 사용자 분석 워크플로우 실행
    user_config가 None이면 기존 하드코딩된 값 사용
    """
    load_dotenv()
    print("환경 변수 로드 시도 완료.")
    
    input_user_id = user_config['user_id']
    input_user_name = user_config['user_name']
    input_github_email = user_config.get('github_email', user_config['user_id'])
    input_target_date = datetime.now().strftime('%Y-%m-%d')  # 매번 오늘 날짜로
    input_project_id = user_config['project_id']
    input_project_name = user_config['project_name']
    input_project_description = user_config.get('project_description', '')

    print(f"\n분석 실행 파라미터:")
    print(f"  User ID (기본 식별자): {input_user_id}")
    print(f"  User Name (표시용): {input_user_name}")
    print(f"  GitHub Email (Git 분석용, 없으면 User ID 사용): {input_github_email if input_github_email else '(user_id 사용)'}")
    print(f"  Target Date: {input_target_date}")
    print(f"  Project ID (WBS용): {input_project_id}")
    print(f"  Project Name: {input_project_name}")
    
    initial_state = LangGraphState(
        user_id=input_user_id,
        user_name=input_user_name,
        github_email=input_user_id,
        target_date=input_target_date,
        project_id=input_project_id,
        docs_quality_analysis_result=None,
        documents_analysis_result=None,
        email_analysis_result=None,
        git_analysis_result=None,
        teams_analysis_result=None,
        wbs_data=None,
        comprehensive_report=None,
        project_name=input_project_name,
        project_description=input_project_description,
        error_message="" 
    )

    try:
        app = create_analysis_graph()

        print("\n--- LangGraph 워크플로우 실행 시작 ---")
        final_state = app.invoke(initial_state)
        print("--- LangGraph 워크플로우 실행 완료 ---\n")

        # 배치 모드에서는 상세 출력 생략, 단일 모드에서만 출력
        if user_config is None:
            print("최종 분석 결과 (State 내용):")
            
            print("\n=== WBS 데이터 (wbs_data) ===")
            wbs_data_from_state = final_state.get("wbs_data")
            if wbs_data_from_state and isinstance(wbs_data_from_state, dict):
                wbs_summary_display = {
                    "project_id": wbs_data_from_state.get("project_id", input_project_id),
                    "project_summary_available": "Yes (placeholder)" if wbs_data_from_state.get("project_summary") else "No (or placeholder)",
                    "task_count": len(wbs_data_from_state.get("task_list", []))
                }
                pprint(wbs_summary_display)
                if wbs_data_from_state.get("task_list"):
                     print(f"  (샘플 작업 1: {wbs_data_from_state['task_list'][0].get('task_name', 'N/A')})" if len(wbs_data_from_state['task_list']) > 0 else "  (작업 목록 비어있음)")
            else:
                print("WBS 데이터가 로드되지 않았거나 유효한 형식이 아닙니다.")
                
            print("\n=== 문서 퀄리티 분석 결과 (documents_quality_analysis_result) ===")
            if final_state.get("documents_quality_analysis_result"):
                pprint(final_state.get("documents_quality_analysis_result"))
            else:
                print("문서 분석 결과가 없습니다.")

            print("\n=== 문서 분석 결과 (documents_analysis_result) ===")
            if final_state.get("documents_analysis_result"):
                pprint(final_state.get("documents_analysis_result"))
            else:
                print("문서 분석 결과가 없습니다.")

            print("\n=== 이메일 분석 결과 (email_analysis_result) ===")
            if final_state.get("email_analysis_result"):
                pprint(final_state.get("email_analysis_result"))
            else:
                print("이메일 분석 결과가 없습니다.")

            print("\n=== Git 활동 분석 결과 (git_analysis_result) ===")
            if final_state.get("git_analysis_result"):
                pprint(final_state.get("git_analysis_result"))
            else:
                print("Git 활동 분석 결과가 없습니다.")

            print("\n=== Teams 활동 분석 결과 (teams_analysis_result) ===")
            if final_state.get("teams_analysis_result"):
                pprint(final_state.get("teams_analysis_result"))
            else:
                print("Teams 활동 분석 결과가 없습니다.")

        # 일일 보고서 결과 처리 및 저장
        print("\n=== Daily 보고서 (comprehensive_report) ===")
        comprehensive_report = final_state.get("comprehensive_report")
        if comprehensive_report:
            if comprehensive_report and not comprehensive_report.get("error"):
                print("Daily 보고서 생성 성공!")

                # 파일 저장
                json_string = json.dumps(comprehensive_report, ensure_ascii=False, indent=2)
                output_filename = f"daily_report_{input_user_name}_{input_target_date}.json"
                output_path = os.path.join("outputs", output_filename)
                os.makedirs("outputs", exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(json_string)
                print(f"보고서 파일 저장: {output_path}")
                
                # 배치 모드에서는 상세 출력 생략
                if user_config is None:
                    pprint(comprehensive_report)
                    
                return {"status": "success", "output_file": output_path, "report": comprehensive_report}
            else:
                print("Daily 보고서 생성 실패")
                if user_config is None:
                    pprint(comprehensive_report)
                return {"status": "failed", "error": comprehensive_report.get("error", "Unknown error")}
        else:
            print("Daily 보고서가 생성되지 않았습니다.")
            return {"status": "failed", "error": "No report generated"}

        if final_state.get("error_message") and final_state.get("error_message").strip():
            print("\n--- 워크플로우 실행 중 발생한 전체 오류 메시지 ---")
            print(final_state["error_message"])
        elif user_config is None:
            print("\n--- 워크플로우 실행 중 보고된 주요 오류 없음 ---")

    except ConnectionError as ce:
        print(f"DB 연결 오류 발생: {ce}")
        return {"status": "error", "error": f"DB 연결 오류: {ce}"}
    except Exception as e:
        import traceback
        print(f"워크플로우 실행 중 예상치 못한 오류 발생: {e}")
        if user_config is None:
            traceback.print_exc()
        return {"status": "error", "error": str(e)}


def run_batch():
    """하드코딩된 사용자들로 배치 실행"""
    try:
        print(f"\n[{datetime.now()}] 배치 작업 시작 - 총 {len(HARDCODED_USERS)}명")
        
        success_count = 0
        for i, user in enumerate(HARDCODED_USERS, 1):
            print(f"[{i}/{len(HARDCODED_USERS)}] {user['user_name']} 분석 중...")
            try:
                result = run_analysis_workflow(user)
                if result['status'] == 'success':
                    print(f"✅ {user['user_name']} 완료")
                    success_count += 1
                else:
                    print(f"❌ {user['user_name']} 실패: {result.get('error', 'Unknown')}")
            except Exception as e:
                print(f"❌ {user['user_name']} 오류: {e}")
        
        print(f"[{datetime.now()}] 배치 완료 - 성공: {success_count}/{len(HARDCODED_USERS)}명")
    except Exception as e:
        print(f"배치 작업 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def run_scheduler():
    print("스케줄러 시작!")
    
    schedule.every(10).minutes.do(run_batch)
    print("스케줄 등록 완료")

    print("첫 번째 배치를 즉시 실행합니다...")
    try:
        run_batch()
        print("✅ 첫 번째 배치 실행 완료!")
    except Exception as e:
        print(f"❌ 첫 번째 배치 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        print("하지만 스케줄러는 계속 실행됩니다...")
    
    print("while 루프 진입!")
    try:
        while True:
            print(f"루프 실행 중... {datetime.now().strftime('%H:%M:%S')}")
            schedule.run_pending()
            time.sleep(30)
    except Exception as e:
        print(f"루프 중 오류: {e}")

if __name__ == "__main__":
    print(sys.argv)
    if len(sys.argv) > 1 and sys.argv[1] == "schedule":
        # 스케줄러 모드
        run_scheduler()
    elif len(sys.argv) > 1 and sys.argv[1] == "batch":
        # 배치 한 번만 실행
        run_batch()
    else:
        # 기존 단일 사용자 모드
        run_analysis_workflow()