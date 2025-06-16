from datetime import datetime
import os
from typing import List
import requests
from dotenv import load_dotenv
import json
from api.dto.response.team_info_response import FileInfo, ProjectInfo, TeamInfoResponse, UserInfo
from core.config import API_AUTHORIZATION, API_BASE_URL, API_KEY
from api.dto.request.report_create_request import ReportCreateRequest

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

    def _send_request(self, path: str, request_dto: ReportCreateRequest) -> dict:
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
            print(f"전송 데이터: \n{json.dumps(payload, indent=2, ensure_ascii=False)}")

            response = requests.post(api_url, json=payload, timeout=10)
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
        request_dto = ReportCreateRequest(
            userId=user_id,
            startDate=target_date,
            endDate=target_date,
            report=report_content
        )
        return self._send_request(path="reports/user/daily", request_dto=request_dto)

    def submit_user_weekly_report(self, user_id: int, start_date: str, end_date: str, report_content: dict) -> dict:
        """사용자 주간 리포트를 제출합니다."""
        request_dto = ReportCreateRequest(
            userId=user_id,
            startDate=start_date,
            endDate=end_date,
            report=report_content
        )
        return self._send_request(path="reports/user/weekly", request_dto=request_dto)

    def submit_team_weekly_report(self, team_id: int, start_date: str, end_date: str, report_content: dict) -> dict:
        """팀 주간 리포트를 제출합니다. (userId 필드를 team_id로 사용)"""
        request_dto = ReportCreateRequest(
            userId=team_id,
            startDate=start_date,
            endDate=end_date,
            report=report_content
        )
        return self._send_request(path="reports/team/weekly", request_dto=request_dto)
    
    def get_teams_info(self) -> List[TeamInfoResponse]:
        """팀 리스트를 가져옵니다."""
        url = f"{self.base_url}/api-for-ai/team-info"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        teams_data = response.json()
        result = []

        for team in teams_data:
            members = [
                UserInfo(
                    id=member["id"],
                    name=member["name"],
                    email=member["email"]
                )
                for member in team.get("members", [])
            ]

            projects = []
            for proj in team.get("projects", []):
                files = [
                    FileInfo(
                        id=f["id"],
                        created_at=f["createdAt"],
                        updated_at=f["updatedAt"],
                        original_file_name=f["originalFileName"],
                        file_url=f["fileUrl"],
                        file_size=f["fileSize"]
                    )
                    for f in proj.get("files", [])
                ]

                project_info = ProjectInfo(
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
                projects.append(project_info)

            team_info = TeamInfoResponse(
                id=team["id"],
                name=team["name"],
                description=team["description"],
                members=members,
                projects=projects
            )
            result.append(team_info)

        return result


# --- 사용 예시 ---
if __name__ == '__main__':

    load_dotenv()

    api_base_url = os.getenv("BASE_URL")

    # API 클라이언트 인스턴스 생성
    client = APIClient(base_url=api_base_url)

    # 전송할 리포트 원본 데이터 (딕셔너리)
    # report_dict_content = {
    #     "report_title": "일일 업무 보고",
    #     "completed_tasks": [
    #         {"task_id": "T-103", "desc": "요청 DTO 클래스 분리 리팩토링"}
    #     ],
    #     "notes": "클린 코드를 위한 구조 개선 완료"
    # }

    try:
        # 사용자 일간 리포트 제출 예시
        # response_data = client.submit_user_daily_report(
        #     user_id=1,
        #     target_date="2025-06-08",
        #     report_content=report_dict_content
        # )
        # print("\n--- 최종 처리 성공 ---")
        # print("서버로부터 받은 데이터:", response_data)
        result = client.get_teams()
        print(result)

    except Exception as e:
        print(f"\n--- 최종 처리 중 오류 발생: {e} ---")
