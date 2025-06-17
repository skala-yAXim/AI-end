from dotenv import load_dotenv
from api.api_client import APIClient


if __name__ == '__main__':

    load_dotenv()


    # API 클라이언트 인스턴스 생성
    client = APIClient()

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
        result = client.get_teams_info()
        print(result)

    except Exception as e:
        print(f"\n--- 최종 처리 중 오류 발생: {e} ---")