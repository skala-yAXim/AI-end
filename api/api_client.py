from datetime import datetime
import os
from typing import List
import requests
import json
from api.dto.response.team_info_response import FileInfo, ProjectInfo, TeamInfoResponse, UserInfo
from core.config import API_AUTHORIZATION, API_BASE_URL, API_KEY
from api.dto.request.report_create_request import DailyReportCreateRequest

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
        self.base_url = API_BASE_URL
        
        if not API_BASE_URL:
            raise ValueError("API base_url이 제공되지 않았습니다.")
        
        self.headers = {API_AUTHORIZATION: API_KEY}

    def _send_request(self, path: str, request_dto: DailyReportCreateRequest) -> dict:
        """
        내부용 요청 전송 헬퍼 메서드.
        :param path: API 요청 경로 (e.g., "reports/user/daily")
        :param request_dto: 전송할 데이터 DTO 객체
        :return: 서버 응답 (JSON 파싱된 딕셔너리)
        """
        api_url = f"{self.base_url}{path}"
        payload = request_dto.to_payload()

        try:
            print(f"--- 리포트 전송 요청: {api_url} ---")
            # print(f"전송 데이터: \n{json.dumps(payload, indent=2, ensure_ascii=False)}")

            response = requests.post(api_url, json=payload, timeout=10, headers=self.headers)
            response.raise_for_status()

            print("\n--- 요청 성공 ---")
            print(f"상태 코드: {response.status_code}")
            return response.json()

        except requests.exceptions.HTTPError as e:
            print(f"\n--- HTTP 오류 발생: {e.response.status_code} ---")
            print(f"응답 내용: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"\n--- 요청 실패: {e} ---")
            raise

    def submit_user_daily_report(self, user_id: int, target_date: str, report_content: dict) -> dict:
        """사용자 일간 리포트를 제출합니다."""
        request_dto = DailyReportCreateRequest(
            user_id=user_id,
            date = target_date,
            report=report_content
        )
        return self._send_request(path="/api-for-ai/report/daily", request_dto=request_dto)

    # def submit_user_weekly_report(self, user_id: int, start_date: str, end_date: str, report_content: dict) -> dict:
    #     """사용자 주간 리포트를 제출합니다."""
    #     request_dto = DailyReportCreateRequest(
    #         userId=user_id,
    #         date=start_date,
    #         report=report_content
    #     )
    #     return self._send_request(path="reports/user/weekly", request_dto=request_dto)

    # def submit_team_weekly_report(self, team_id: int, start_date: str, end_date: str, report_content: dict) -> dict:
    #     """팀 주간 리포트를 제출합니다. (userId 필드를 team_id로 사용)"""
    #     request_dto = ReportCreateRequest(
    #         userId=team_id,
    #         startDate=start_date,
    #         endDate=end_date,
    #         report=report_content
    #     )
    #     return self._send_request(path="reports/team/weekly", request_dto=request_dto)
    
    def get_teams_info(self) -> List[TeamInfoResponse]:
        """팀 정보 조회"""
        url = f"{self.base_url}/api-for-ai/team-info"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()

        teams_data = response.json()
        return [self._parse_team(team) for team in teams_data]
    
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
            files=files
        )

    def _parse_team(self, team: dict) -> TeamInfoResponse:
        members = [UserInfo(**member) for member in team.get("members", [])]
        projects = [self._parse_project(p) for p in team.get("projects", [])]

        return TeamInfoResponse(
            id=team["id"],
            name=team["name"],
            description=team["description"],
            members=members,
            projects=projects
        )
