# core/config.py
import os
from dotenv import load_dotenv

load_dotenv() # .env 파일에서 환경 변수를 로드합니다.

# --- OpenAI 설정 ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o")
FAST_MODEL = os.getenv("FAST_MODEL", "gpt-4o") # 빠른 응답이 필요할 때 사용

# --- HuggingFace 임베딩 모델 ---
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

# --- Qdrant 설정 ---
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

# --- 컬렉션 이름 ---
COLLECTION_DOCUMENTS = "Documents"
COLLECTION_EMAILS = "Emails"
COLLECTION_GIT_ACTIVITIES = "Git-Activities"
COLLECTION_GIT_README = "Git-Readme"
COLLECTION_TEAMS_POSTS = "Teams-Posts"
COLLECTION_WBS_DATA = "WBSData" # WBS 데이터 저장용

# --- 경로 설정 ---
# 프로젝트 루트 디렉토리를 기준으로 설정.
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")) # core의 부모 디렉토리

PROMPTS_BASE_DIR = os.path.join(PROJECT_ROOT_DIR, "prompts")
DATA_DIR = os.path.join(PROJECT_ROOT_DIR, "data") # 원본 데이터 저장 경로 (필요시)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

