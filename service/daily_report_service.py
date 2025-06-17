# main.py
from datetime import date
import os
import tempfile
from typing import List
from dotenv import load_dotenv
from pprint import pprint
import json

import requests

from service.run_wbs_analyzer import run_wbs_agent
from api.dto.response.team_info_response import FileInfo
from schemas.user_info import ProjectInfo, UserInfo 

from api.api_client import APIClient
from ai.graphs.daily_graph import create_analysis_graph 
from ai.graphs.state_definition import LangGraphState

from langchain.globals import set_llm_cache
set_llm_cache(None)

def run_analysis_workflow(user_info: UserInfo, target_date: str = date.today().isoformat()):

    # TODO github_email state 지우기
    initial_state = LangGraphState(
        user_id=user_info.id,
        user_name=user_info.name,
        github_email=user_info.email,
        target_date=target_date,
        wbs_data=None, # 초기 WBS 데이터는 None
        comprehensive_report=None, # 일일 보고서 결과
        project_id=user_info.projects[0].id,
        project_name=user_info.projects[0].name,
        project_description=user_info.projects[0].description,
        project_period=f"{user_info.projects[0].start_date} ~ {user_info.projects[0].end_date}",
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
                "project_id": wbs_data_from_state.get("project_id", user_info.projects[0].id),
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
                output_filename = f"daily_report_{user_info.name}_{target_date}.json"
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
        
        return comprehensive_report

    except ConnectionError as ce:
        print(f"DB 연결 오류 발생: {ce}")
    except Exception as e:
        import traceback
        print(f"워크플로우 실행 중 예상치 못한 오류 발생: {e}")
        traceback.print_exc()

def download_wbs(project_id: str, files: List[FileInfo]):
    for file in files:
        tmp_path = None
        try:
            # 파일 다운로드 요청
            response = requests.get(file.file_url)
            response.raise_for_status()

            # 임시 파일로 저장
            file_ext = os.path.splitext(file.original_file_name)[-1].lower()
            if file_ext in [".xls", ".xlsx"]:
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.original_file_name)[-1]) as tmp_file:
                    tmp_file.write(response.content)
                    tmp_path = tmp_file.name

                print(f"[다운로드 완료] 임시 파일 경로: {tmp_path}")

                # Agent 실행
                success_status = run_wbs_agent(
                    project_id=project_id,
                    wbs_file_path=tmp_path
                )

                if success_status:
                    print(f"[성공] WBS agent 실행 성공 - 파일: {file.original_file_name}")
                else:
                    print(f"[실패] WBS agent 실행 실패 - 파일: {file.original_file_name}")

        except requests.RequestException as e:
            print(f"[에러] 파일 다운로드 중 오류 발생 - 파일: {file.original_file_name} | 에러: {e}")
        except Exception as e:
            print(f"[에러] 예기치 못한 오류 발생 - 파일: {file.original_file_name} | 에러: {e}")
        finally:
            # 임시 파일 삭제
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
                print(f"[삭제 완료] {tmp_path}")

        
def daily_report_service():
    load_dotenv()
    print("환경 변수 로드 시도 완료.")
    
    client = APIClient()
    result = client.get_teams_info()
    
    target_date = date.today().isoformat()
    target_date = "2025-06-02"
    
    for team in result:
        print(team.name)
        for proj in team.projects:
            for file in proj.files:
                download_wbs(proj.id, [file])

        projects = [
            ProjectInfo(
                id = proj.id,
                name = proj.name,
                start_date = proj.start_date,
                end_date = proj.end_date,
                description = proj.description
            )
            for proj in team.projects
        ]
        for member in team.members:
            if not member.id == 0:
                user_info = UserInfo(
                    id=member.id,
                    name=member.name,
                    email=member.email,
                    team_id=team.id,
                    team_name=team.name,
                    projects=projects
                )
                daily_report = run_analysis_workflow(user_info, target_date)
                
                if daily_report:
                    client.submit_user_daily_report(user_id=member.id, target_date=target_date, report_content=daily_report)
