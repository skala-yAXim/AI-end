import os
from pathlib import Path
from dotenv import load_dotenv

# 기본 경로 설정
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = os.path.join(BASE_DIR, "data")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

# 필요한 디렉터리 생성
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PROMPTS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# API 키 설정
load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
HUGGINGFACEHUB_API_TOKEN = os.environ.get("HUGGINGFACEHUB_API_TOKEN", "")
# 모델 설정
DEFAULT_MODEL = "gpt-4o"
FAST_MODEL = "gpt-4o"
EMBEDDING_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

# Qdrant DB Collection 설정
DOCS_COLLECTION = "docs-collection"
TEAMS_COLLECTION = "teams-posts"