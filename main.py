# main.py
import os
import sys
from dotenv import load_dotenv
from pprint import pprint
import json 

# 현재 디렉토리를 sys.path에 추가 (graph.py가 루트에 있다고 가정)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from graph import create_analysis_graph 
from core.state_definition import LangGraphState

from langchain.globals import set_llm_cache
set_llm_cache(None)

def run_analysis_workflow():
    load_dotenv()
    print("환경 변수 로드 시도 완료.")

    input_user_id = "minsuh3203@yasim2861.onmicrosoft.com" 
    input_user_name = "조민서" 
    input_github_email = "minsuh3203@gmail.com" 
    input_target_date = "2025-06-02" 
    input_project_id = "project_sample_001" # 테스트할 실제 프로젝트 ID

    print(f"\n분석 실행 파라미터:")
    print(f"  User ID (기본 식별자): {input_user_id}")
    print(f"  User Name (표시용): {input_user_name}")
    print(f"  GitHub Email (Git 분석용, 없으면 User ID 사용): {input_github_email if input_github_email else '(user_id 사용)'}")
    print(f"  Target Date: {input_target_date}")
    print(f"  Project ID (WBS용): {input_project_id}")
    
    initial_state = LangGraphState(
        user_id=input_user_id,
        user_name=input_user_name,
        github_email=input_user_id,
        target_date=input_target_date,
        project_id=input_project_id,
        documents_analysis_result=None,
        email_analysis_result=None,
        git_analysis_result=None,
        teams_analysis_result=None,
        wbs_data=None, # 초기 WBS 데이터는 None
        comprehensive_report=None, # 일일 보고서 결과
        error_message="" 
    )

    try:
        app = create_analysis_graph()

        print("\n--- LangGraph 워크플로우 실행 시작 ---")
        final_state = app.invoke(initial_state)
        print("--- LangGraph 워크플로우 실행 완료 ---\n")

        print("최종 분석 결과 (State 내용):")
        
        print("\n=== WBS 데이터 (wbs_data) ===")
        wbs_data_from_state = final_state.get("wbs_data")
        if wbs_data_from_state and isinstance(wbs_data_from_state, dict):
            # 새로운 WBS 도구는 project_summary를 직접 반환하지 않으므로, task_list 존재 유무로 판단
            wbs_summary_display = {
                "project_id": wbs_data_from_state.get("project_id", input_project_id),
                "project_summary_available": "Yes (placeholder)" if wbs_data_from_state.get("project_summary") else "No (or placeholder)",
                "task_count": len(wbs_data_from_state.get("task_list", []))
            }
            pprint(wbs_summary_display)
            if wbs_data_from_state.get("task_list"):
                 print(f"  (샘플 작업 1: {wbs_data_from_state['task_list'][0].get('task_name', 'N/A')})" if len(wbs_data_from_state['task_list']) > 0 else "  (작업 목록 비어있음)")

            # 전체 WBS 내용을 보려면 다음 주석 해제:
            # print("--- WBS 전체 내용 (task_list 위주) ---")
            # pprint({"project_id": wbs_data_from_state.get("project_id"), "task_list": wbs_data_from_state.get("task_list")})
            # print("--- WBS 전체 내용 끝 ---")
        else:
            print("WBS 데이터가 로드되지 않았거나 유효한 형식이 아닙니다.")

        print("\n=== 문서 분석 결과 (documents_analysis_result) ===")
        if final_state.get("documents_analysis_result"):
            pprint(final_state.get("documents_analysis_result"))
        else:
            print("문서 분석 결과가 없습니다.")

        # (이메일, Git, Teams 결과 출력은 이전과 동일)
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

        # 일일 보고서 결과 출력
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
                
                pprint(comprehensive_report)
            else:
                print("Daily 보고서 생성 실패")
                pprint(comprehensive_report)
        else:
            print("Daily 보고서가 생성되지 않았습니다.")

        if final_state.get("error_message") and final_state.get("error_message").strip():
            print("\n--- 워크플로우 실행 중 발생한 전체 오류 메시지 ---")
            print(final_state["error_message"])
        else:
            print("\n--- 워크플로우 실행 중 보고된 주요 오류 없음 ---")

    except ConnectionError as ce:
        print(f"DB 연결 오류 발생: {ce}")
    except Exception as e:
        import traceback
        print(f"워크플로우 실행 중 예상치 못한 오류 발생: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    run_analysis_workflow()
