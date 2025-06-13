import requests
import json
from datetime import date

class APIClient:
    """
    리포트 생성 API와의 통신을 담당하는 클라이언트 클래스
    """
    def __init__(self, base_url="http://localhost:8088/"):
        """
        클라이언트 초기화

        :param base_url: API 서버의 기본 URL
        """
        self.base_url = base_url

    def submit_user_daily_report(self, user_id: int, start_date: str, end_date: str, report_content: dict) -> dict:
        """
        리포트 데이터를 API 서버에 전송합니다.

        :param user_id: 사용자 ID (e.g., 1)
        :param start_date: 보고서 시작일 (e.g., "2025-06-02")
        :param end_date: 보고서 종료일 (e.g., "2025-06-08")
        :param report_content: 보고서 내용에 해당하는 딕셔너리
        :return: 서버로부터 받은 응답 (JSON 파싱된 딕셔너리)
        :raises: requests.exceptions.RequestException: 요청 실패 시
        """
        # API 엔드포인트 URL 구성
        api_url = f"{self.base_url}reports/user/daily" # API 경로를 명시적으로 수정했습니다. 실제 경로에 맞게 변경하세요.

        try:
            # 1. 보고서 내용(dict)을 JSON 형식의 문자열로 변환합니다.
            report_json_string = json.dumps(report_content, ensure_ascii=False)

            # 2. API DTO 형식에 맞춰 페이로드를 구성합니다.
            payload = {
                "userId": user_id,
                "startDate": start_date,
                "endDate": end_date,
                "report": report_json_string
            }

            print(f"--- 리포트 전송 요청: {api_url} ---")
            print(f"전송 데이터: \n{json.dumps(payload, indent=2, ensure_ascii=False)}")

            # 3. POST 요청을 전송합니다. `json` 파라미터는 자동으로 Content-Type을 application/json으로 설정합니다.
            response = requests.post(api_url, json=payload, timeout=10)

            # 4. 응답 상태 코드가 2xx가 아닐 경우 예외를 발생시킵니다.
            response.raise_for_status()

            print("\n--- 요청 성공 ---")
            print(f"상태 코드: {response.status_code}")
            return response.json()

        except requests.exceptions.HTTPError as e:
            # 서버에서 4xx, 5xx 에러 코드를 반환한 경우
            print(f"\n--- HTTP 오류 발생: {e.response.status_code} ---")
            print(f"응답 내용: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            # 네트워크 연결 문제, 타임아웃 등 요청 관련 오류
            print(f"\n--- 요청 실패: {e} ---")
            raise

# --- 사용 예시 ---
if __name__ == '__main__':
    # API 클라이언트 인스턴스 생성
    client = APIClient(base_url="http://localhost:8088/")

    # 전송할 리포트 원본 데이터 (딕셔너리)
    report_dict_content = {
        "report_title": "주간 업무 보고",
        "completed_tasks": [
            {"task_id": "T-101", "desc": "API 클라이언트 개발"},
            {"task_id": "T-102", "desc": "단위 테스트 작성"}
        ],
        "in_progress": 1,
        "notes": "다음 주에는 성능 테스트 예정"
    }

    try:
        # 메서드 호출
        response_data = client.submit_user_daily_report(
            user_id=1,
            start_date="2025-06-02",
            end_date="2025-06-02",
            report_content=report_dict_content
        )
        print("\n--- 최종 처리 성공 ---")
        print("서버로부터 받은 데이터:")
        print(response_data)

    except Exception as e:
        print(f"\n--- 최종 처리 중 오류 발생 ---")
        print(e)