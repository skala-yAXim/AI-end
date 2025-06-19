import os
from dotenv import load_dotenv

class Settings:

    # .env 파일 로드 시도 (실행 위치에 따라 여러 경로 시도)
    # 이 클래스가 임포트되는 시점에 .env를 로드합니다.
    _loaded_dotenv = False
    _potential_dotenv_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'), # 프로젝트 루트 경로의 .env
        os.path.join(os.getcwd(), '.env'), # 현재 작업 디렉토리
    ]
    for path in _potential_dotenv_paths:
        if os.path.exists(path):
            load_dotenv(path)
            _loaded_dotenv = True
            print(f".env 파일 로드 성공: {path}")
            break
    if not _loaded_dotenv:
        print("경고: .env 파일을 찾지 못했습니다. 환경 변수가 직접 설정되었는지 확인하세요.")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL_NAME: str = os.getenv("OPENAI_MODEL_NAME", "gpt-4o")
    
    # VectorDB 기본 경로 (프로젝트 루트를 기준으로 db/vector_store_wbs 로 가정)
    # 이 경로는 run_agent.py 등에서 오버라이드 될 수 있음
    _project_root_guess = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # core -> wbs_ingestion_agent -> project_root
    
    def __init__(self):
        if not self.OPENAI_API_KEY:
            # 이 에이전트는 OPENAI_API_KEY가 필수적이므로, 없으면 에러 발생
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다. .env 파일을 확인하거나 직접 설정해주세요.")
