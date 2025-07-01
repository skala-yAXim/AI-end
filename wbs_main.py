from service.run_wbs_analyzer import run_wbs_agent 
from core.settings import Settings
import sys
if __name__ == "__main__":
    
    # 예시: 기본값 사용
    project_id_example = "project_sample_003"
    wbs_file_example = "./[yAXim]_300. WBS_v0.4.xlsx" # 실제 파일 경로로 수정 필요
    # wbs_file_example = "data/wbs/WBS_스마트팩토리챗봇1.xlsx" # 실제 파일 경로로 수정 필요

    print(f"예시 실행: 프로젝트 ID '{project_id_example}'")
    
    # 필요한 경우 .env 파일이 올바르게 로드되었는지 확인
    # (Settings 클래스 초기화 시 OPENAI_API_KEY 등이 필요할 수 있음)
    try:
        Settings() 
        print(".env 설정 로드 확인됨 (또는 OPENAI_API_KEY가 환경 변수에 직접 설정됨).")
    except ValueError as e:
        print(f"주의: .env 파일 또는 OPENAI_API_KEY 환경 변수 설정 문제 가능성 - {e}")
        print("      계속 진행하지만, API 키가 필요한 작업에서 오류가 발생할 수 있습니다.")

    # 함수 호출
    success_status = run_wbs_agent(
        project_id=project_id_example,
        wbs_file_path=wbs_file_example
    )

    if success_status:
        sys.exit(0) # 성공 시 종료 코드 0
    else:
        sys.exit(1) # 실패 시 종료 코드 1
