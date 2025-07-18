from typing import List
import requests
from api.dto.request.report_fetch_request import DailyReportFetchRequest, WeeklyReportFetchRequest
from api.dto.response.team_info_response import FileInfo, ProjectInfo, TeamInfoResponse, UserInfo
from core.config import API_AUTHORIZATION, API_BASE_URL, API_KEY
from api.dto.request.report_create_request import DailyReportCreateRequest, TeamWeeklyReportCreateRequest, WeeklyReportCreateRequest

# --- API 클라이언트 ---
class APIClient:
    """
    리포트 생성 API와의 통신을 담당하는 클라이언트 클래스
    """
    def __init__(self):
        """
        클라이언트 초기화
        :param base_url: API 서버의 기본 URL
        """
        self.base_url = f"{API_BASE_URL}/api-for-ai"
        
        if not API_BASE_URL:
            raise ValueError("API base_url이 제공되지 않았습니다.")
        
        self.headers = {API_AUTHORIZATION: API_KEY}

    def submit_user_daily_report(self, user_id: int, target_date: str, report_content: dict) -> dict:
        """사용자 일간 리포트를 제출합니다."""
        request_dto = DailyReportCreateRequest(
            user_id=user_id,
            date=target_date,
            report=report_content
        )

        payload = request_dto.to_payload()
        url = f"{self.base_url}/report/daily"

        response = requests.post(url, json=payload, timeout=10, headers=self.headers)

        print("[요청 결과] 상태 코드:", response.status_code)
        
        return response


    def submit_user_weekly_report(self, user_id: int, start_date: str, end_date: str, report_content: dict) -> dict:
        """사용자 주간 리포트를 제출합니다."""
        request_dto = WeeklyReportCreateRequest(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            report=report_content
        )
        
        payload = request_dto.to_payload()
        url = f"{self.base_url}/report/user-weekly"

        response = requests.post(url, json=payload, timeout=10, headers=self.headers)

        print("[요청 결과] 상태 코드:", response.status_code)
        
        return response

    def submit_team_weekly_report(self, team_id: int, start_date: str, end_date: str, report_content: dict) -> dict:
        """사용자 주간 리포트를 제출합니다."""
        request_dto = TeamWeeklyReportCreateRequest(
            team_id=team_id,
            start_date=start_date,
            end_date=end_date,
            report=report_content
        )
        
        payload = request_dto.to_payload()
        url = f"{self.base_url}/report/team-weekly"

        response = requests.post(url, json=payload, timeout=10, headers=self.headers)
        
        print(response.text)

        print("[요청 결과] 상태 코드:", response.status_code)
        
        return response
    
    def get_teams_info(self) -> List[TeamInfoResponse]:
        """팀 정보 조회"""
        url = f"{self.base_url}/team-info"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()

        teams_data = response.json()
        return [self._parse_team(team) for team in teams_data]

    def get_user_daily_reports(self, user_id: int, start_date: str, end_date: str) -> List[str]:
        """사용자 일간 리포트 조회"""
        request_dto = DailyReportFetchRequest(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        
        url = f"{self.base_url}/user-daily"
        payload = request_dto.to_payload()
        response = requests.post(url, json=payload, headers=self.headers, timeout=10)
        response.raise_for_status()
        reports_list = response.json()
        daily_reports = [report["report"] for report in reports_list]
        
        return daily_reports

    def get_team_user_weekly_reports(self, team_id: int, start_date: str, end_date: str) -> List[str]:
        """팀 사용자 주간 리포트 조회"""
        request_dto = WeeklyReportFetchRequest(
            team_id=team_id,
            start_date=start_date,
            end_date=end_date
        )
        
        url = f"{self.base_url}/user-weekly"
        payload = request_dto.to_payload()
        response = requests.post(url, json=payload, headers=self.headers, timeout=10)
        response.raise_for_status()
        reports_list = response.json()
        weekly_reports = [report["report"] for report in reports_list]
        
        return weekly_reports
    
    def _parse_project(self, proj: dict) -> ProjectInfo:
        files = [FileInfo(
            id=f["id"],
            created_at=f["createdAt"],
            updated_at=f["updatedAt"],
            original_file_name=f["originalFileName"],
            file_url=f["fileUrl"],
            file_size=f["fileSize"]
        ) for f in proj.get("files", [])]

        return ProjectInfo(
            id=proj["id"],
            created_at=proj["createdAt"],
            updated_at=proj["updatedAt"],
            name=proj["name"],
            start_date=proj["startDate"],
            end_date=proj["endDate"],
            description=proj["description"],
            status=proj["status"],
            progress=proj["progress"] or 0,
            files=files
        )

    def _parse_team(self, team: dict) -> TeamInfoResponse:
        members = [UserInfo(**member) for member in team.get("members", [])]
        projects = [self._parse_project(p) for p in team.get("projects", [])]

        return TeamInfoResponse(
            id=team["id"],
            name=team["name"],
            description=team["description"],
            weekly_template=team["weeklyTemplate"],
            members=members,
            projects=projects
        )
