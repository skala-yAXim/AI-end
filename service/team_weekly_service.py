from datetime import date, timedelta
from typing import List
from dotenv import load_dotenv

from ai.graphs.state_definition import TeamWeeklyLangGraphState
from ai.graphs.team_weekly_graph import create_team_weekly_graph
from api.api_client import APIClient
from schemas.project_info import ProjectInfo
from schemas.team_info import TeamInfo

def run_team_weekly_workflow(team_info: TeamInfo, weekly_reports: List[str], start_date: str, end_date: str):
    """
    주간 업무 보고서 생성 프로세스를 실행하는 메인 함수입니다.
    """
    
    initial_state = TeamWeeklyLangGraphState(
        team_name=team_info.name,
        team_id=team_info.id,
        team_description=team_info.description,
        team_members=team_info.members,
        start_date=start_date,
        end_date=end_date,
        project_id=team_info.projects[0].id,
        wbs_data=None,
        weekly_reports_data=weekly_reports,
        team_weekly_report_result=None,
        error_message="",
        last_week_progress=team_info.projects[0].progress,
        project_name=team_info.projects[0].name,
        project_start_date=team_info.projects[0].start_date,
        project_end_date=team_info.projects[0].end_date,
        weekly_input_template=team_info.weekly_template,
    )
    
    # --- 실행 ---
    try:
        app = create_team_weekly_graph()

        print("\n--- LangGraph 워크플로우 실행 시작 ---")
        final_state = app.invoke(initial_state)
        print("--- LangGraph 워크플로우 실행 완료 ---\n")

        print("최종 분석 결과 (State 내용):")
        
        team_weekly_report_result = final_state.get("team_weekly_report_result")
        
        return team_weekly_report_result
    except Exception as e:
        print(f"\n[오류] 예기치 않은 오류가 발생했습니다: {e}")

def team_weekly_report_service():
    load_dotenv()
    print("환경 변수 로드 시도 완료.")
    
    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    end_date_str = end_date.isoformat()
    start_date_str = start_date.isoformat()
    
    start_date_str = "2025-06-06"
    end_date_str = "2025-06-12"
    
    client = APIClient()
    response = client.get_teams_info()
    print(response)
    
    for team in response:
        print(team.name)
        
        projects = [
            ProjectInfo(
                    id = proj.id,
                    name = proj.name,
                    start_date = proj.start_date,
                    end_date = proj.end_date,
                    description = proj.description,
                    progress = proj.progress or 0
                )
                for proj in team.projects
        ]
        
        team_info = TeamInfo(
            id = team.id,
            name = team.name,
            description = team.description,
            members = [member.name for member in team.members],
            projects = projects,
            weekly_template = team.weekly_template
        )
        
        weekly_reports = client.get_team_user_weekly_reports(
            team_id=team_info.id,
            start_date=start_date_str,
            end_date=end_date_str
        )
        
        team_weekly_report = run_team_weekly_workflow(team_info, weekly_reports, start_date_str, end_date_str)
        
        if team_weekly_report:
            client.submit_team_weekly_report(
                team_id=team_info.id,
                start_date=start_date_str,
                end_date=end_date_str,
                report_content=team_weekly_report
            )