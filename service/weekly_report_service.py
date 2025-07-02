from datetime import date, timedelta
from typing import List
from dotenv import load_dotenv

from ai.graphs.state_definition import WeeklyLangGraphState
from ai.graphs.weekly_graph import create_weekly_graph
from api.api_client import APIClient
from schemas.user_info import ProjectInfo, UserInfo

def run_weekly_workflow(user_info: UserInfo, daily_reports: List[str], start_date: str, end_date: str):
    print("--- 주간 보고서 생성 시작 ---")
    
    initial_state = WeeklyLangGraphState(
        user_name=user_info.name,
        user_id=user_info.id,
        start_date=start_date,
        end_date=end_date,
        projects=user_info.projects,
        wbs_data=None,
        daily_reports_data=daily_reports,
        weekly_report_result=None,
        error_message=""
    )
    
    # --- 실행 ---
    try:
        app = create_weekly_graph()

        print("\n--- LangGraph 워크플로우 실행 시작 ---")
        final_state = app.invoke(initial_state)
        print("--- LangGraph 워크플로우 실행 완료 ---\n")

        print("최종 분석 결과 (State 내용):")
        
        weekly_report_result = final_state.get("weekly_report_result")
        
        return weekly_report_result
    except Exception as e:
        print(f"\n[오류] 예기치 않은 오류가 발생했습니다: {e}")


def weekly_report_service():
    load_dotenv()
    print("환경 변수 로드 시도 완료.")

    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    end_date_str = end_date.isoformat()
    start_date_str = start_date.isoformat()
    
    start_date_str = "2025-06-13"
    end_date_str = "2025-06-19"
    
    client = APIClient()
    team_info = client.get_teams_info()
    
    for team in team_info:
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
                
                daily_reports = client.get_user_daily_reports(user_id=user_info.id, start_date=start_date_str, end_date=end_date_str)
                
                weekly_report = run_weekly_workflow(user_info, daily_reports, start_date_str, end_date_str)
                
                if weekly_report:
                    client.submit_user_weekly_report(user_id=member.id, start_date=start_date_str, end_date=end_date_str, report_content=weekly_report)
