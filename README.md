# AI 기반 업무 자동화 및 분석 플랫폼

## 1. 프로젝트 개요

본 프로젝트는 FastAPI를 기반으로 구축된 모델 서빙 서버로, LangChain과 LangSmith를 활용하여 다양한 AI 에이전트를 통해 업무 자동화 및 분석 기능을 제공. Microsoft Graph API와 Git API를 통해 수집된 데이터를 바탕으로, 업무 분배, 코드 분석, 이메일 분석, 팀 대화 맥락 추출, 개인 일일 및 주간 보고서 생성 등의 기능을 수행.

## 2. 주요 기능

본 플랫폼은 다음과 같은 6가지 핵심 AI 에이전트를 포함합니다:

1.  **업무 분할 및 역할 관리 에이전트 (WBS/일정 분석)**:
    * WBS(Work Breakdown Structure) 또는 일정 관련 문서를 분석하여 업무를 분할하고 역할을 제안합니다.
2.  **Git 코드 분석 에이전트**:
    * Git 저장소의 코드 변경 이력, 커밋 메시지, 이슈, PR 등을 분석하여 코드 품질, 개발 진행 상황 등을 파악합니다.
3.  **이메일 내용 분석 에이전트**:
    * 수신된 이메일의 내용을 분석하여 주요 정보, 요청 사항, 감정 등을 추출합니다.
4.  **팀 대화 기반 맥락 추출 에이전트**:
    * Microsoft Teams 채팅 및 게시물 내용을 분석하여 대화의 주요 맥락, 결정 사항, 주요 논의 주제 등을 추출합니다.
5.  **문서 내용 분석 에이전트**:
    * 개인별 문서 파일들을 분석하여 문서의 퀄리티와 진척도 주요 논의 내용 등을 추출합니다.
6.  **아웃룩(팀즈) 일정 분석 에이전트**:
    * 아웃룩을 확인해서 일정 분석을 진행할 수 있도록 추출합니다.
7.  **개인 Daily 보고서 생성 에이전트**:
    * 개인의 하루 활동(이메일, 코드 커밋, 팀즈 활동 등)을 종합하여 일일 보고서를 자동 생성합니다.
8.  **개인 Weekly 보고서 생성 에이전트**:
    * 생성된 개인별 일일 보고서들을 기반으로 주간 업무 요약 보고서를 생성합니다.
9.  **팀 Weekly 보고서 생성 에이전트**:
    * 생성된 개인 weekly 보고서들을 기반으로 팀 전체의 주간 업무 요약 보고서를 생성합니다.

  

### 개인 Daily 보고서 Agent 흐름 
![image](https://github.com/user-attachments/assets/515beee1-a3cb-4e67-adc5-9e78a2ab0b93)



### 개인 Weekly 보고서 Agent 흐름
![image](https://github.com/user-attachments/assets/8adff976-d24c-4e06-891e-226590a11e0a)



### 팀 Weekly 보고서 Agent 흐름
![image](https://github.com/user-attachments/assets/c99ad3a5-b6b8-4f13-bccd-ec27b85c1fcc)



## 3. 기술 스택

* **Backend Framework**: FastAPI
* **AI/LLM Orchestration**: LangChain
* **LLM Observability**: LangSmith
* **Vector Database**: (미정 - Chroma, FAISS, Pinecone 등 유연하게 선택 가능하도록 설계)
* **Data Sources**:
    * Microsoft Graph API (Teams 채팅, Outlook 이메일, Teams 게시물)
    * Git API (Commits, Issues, PRs)
* **Programming Language**: Python
* **Task Queue (Optional)**: Celery (비동기 작업 처리용)
* **Database (Optional)**: PostgreSQL/MySQL (보고서 및 메타데이터 저장용)

## 4. 폴더 구조

```bash
.
├── app/
│   ├── init.py
│   ├── main.py                 # FastAPI 애플리케이션 초기화
│   ├── api/
│   │   ├── init.py
│   │   └── v1/
│   │       ├── init.py
│   │       ├── endpoints/
│   │       │   ├── init.py
│   │       │   ├── agents.py       # AI 에이전트 관련 API
│   │       │   ├── data_ingestion.py # 데이터 수집 API
│   │       │   └── reports.py      # 보고서 생성/조회 API
│   │       └── schemas.py          # Pydantic 스키마 (요청/응답 모델)
│   ├── core/
│   │   ├── init.py
│   │   ├── config.py             # 환경 설정 (API 키 등)
│   │   ├── dependencies.py       # 공통 의존성 주입
│   │   └── langchain_setup.py    # LangChain 및 LangSmith 설정
│   ├── services/
│   │   ├── init.py
│   │   ├── graph_service.py      # Microsoft Graph API 연동 서비스
│   │   ├── git_service.py        # Git API 연동 서비스
│   │   ├── vector_db_service.py  # Vector DB 연동 인터페이스
│   │   └── report_service.py     # 보고서 생성 및 관리 서비스
│   ├── agents/
│   │   ├── init.py
│   │   ├── base_agent.py         # 기본 에이전트 클래스
│   │   ├── wbs_analyzer_agent.py
│   │   ├── git_code_analyzer_agent.py
│   │   ├── email_content_analyzer_agent.py
│   │   ├── team_context_extractor_agent.py
│   │   ├── daily_report_generator_agent.py
│   │   └── weekly_report_generator_agent.py
│   ├── models/                   # DB 모델 (SQLAlchemy 등)
│   │   └── init.py
│   └── utils/                    # 유틸리티 함수
│       └── init.py
├── tests/                        # 테스트 코드
│   └── init.py
├── .env.example                  # 환경 변수 예시 파일
├── requirements.txt              # Python 패키지 의존성
└── README.md                     # 프로젝트 설명 파일
```

## 5. 설치 및 실행

### 5.1. 사전 준비 사항

* Python 3.9 이상
* pip (Python 패키지 관리자)
* Git
* (선택) Docker

### 5.2. 설치 과정

1.  **저장소 복제**:
    ```bash
    git clone <repository_url>
    cd <repository_name>
    ```

2.  **가상 환경 생성 및 활성화**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate    # Windows
    ```

3.  **필수 패키지 설치**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **환경 변수 설정**:
    `.env.example` 파일을 복사하여 `.env` 파일을 생성하고, 필요한 API 키 및 설정을 입력합니다.
    ```bash
    cp .env.example .env
    ```
    **`.env` 파일 예시**:
    ```env
    PROJECT_NAME="AI Workflow Automation Platform"
    API_V1_STR="/api/v1"

    # LangSmith (필수)
    LANGCHAIN_API_KEY="your_langsmith_api_key"
    LANGCHAIN_TRACING_V2="true"
    LANGCHAIN_ENDPOINT="[https://api.smith.langchain.com](https://api.smith.langchain.com)"
    LANGCHAIN_PROJECT="your_project_name_for_langsmith" # 예: "ai-workflow-dev"

    # Microsoft Graph API (필수)
    MS_GRAPH_CLIENT_ID="your_ms_graph_client_id"
    MS_GRAPH_CLIENT_SECRET="your_ms_graph_client_secret"
    MS_GRAPH_TENANT_ID="your_ms_graph_tenant_id"

    # Git API (필수)
    GIT_TOKEN="your_git_personal_access_token"
    GIT_REPO_URL="https_or_ssh_link_to_your_repo" # 분석 대상 Git 저장소

    # Vector DB (선택 - 사용하는 DB에 따라 설정)
    # 예: Qdrant
    # QDRANT_URL="http://localhost:6333"
    # QDRANT_API_KEY="your_qdrant_api_key_if_any"

    # Backend Server (보고서 전송용)
    BACKEND_SERVER_URL="http://your_backend_server_url/api"
    BACKEND_SERVER_API_KEY="your_backend_api_key"

    # 기타 설정
    # OPENAI_API_KEY="your_openai_api_key" # LangChain에서 사용할 LLM의 API 키
    ```

### 5.3. 애플리케이션 실행

```bash
uvicorn app.main:app --reload
```

--reload` 옵션은 개발 중에 코드가 변경될 때마다 서버를 자동으로 재시작합니다.

## 6. API 엔드포인트 (예시)

* **Agent Trigger**: `POST /api/v1/agents/{agent_name}/run`
* **Data Ingestion**:
    * `POST /api/v1/data/ingest/msteams`
    * `POST /api/v1/data/ingest/outlook`
    * `POST /api/v1/data/ingest/git`
* **Report Generation**:
    * `POST /api/v1/reports/daily`
    * `POST /api/v1/reports/weekly`
* **Report Retrieval**: `GET /api/v1/reports/{report_id}`

(세부적인 API 명세는 Swagger UI (`/docs` 또는 `/redoc`)를 통해 확인할 수 있습니다.)

## 7. VectorDB 선택 가이드

본 프로젝트는 특정 VectorDB에 종속되지 않도록 `services/vector_db_service.py`에 인터페이스를 정의하여 유연성을 확보하는 것을 목표로 합니다. 다음은 고려할 수 있는 몇 가지 VectorDB 옵션입니다:

* **ChromaDB**: 오픈소스, 사용 용이, 로컬 실행 가능. 소규모 프로젝트나 빠른 프로토타이핑에 적합.
* **FAISS**: Facebook AI에서 개발, 고성능, GPU 지원. 대규모 데이터셋 처리에 유리.
* **Pinecone**: 완전 관리형 서비스, 사용 편의성 및 확장성 우수. 운영 부담을 줄이고 싶을 때 적합.
* **Weaviate**: 오픈소스, GraphQL API 지원, 다양한 모듈(QA, 요약 등) 통합.
* **Qdrant**: 오픈소스, Rust 기반으로 성능 우수, 필터링 기능 강력.

선택 시 데이터 규모, 성능 요구사항, 운영 편의성, 비용 등을 종합적으로 고려하십시오.

## 8. LangSmith 연동

LangSmith는 LLM 애플리케이션의 디버깅, 모니터링, 테스트를 위한 플랫폼입니다.
`.env` 파일에 `LANGCHAIN_API_KEY` 등 관련 환경 변수를 설정하면 LangChain 실행 시 자동으로 LangSmith와 연동되어 추적 정보를 기록합니다. 이를 통해 에이전트의 실행 흐름, LLM과의 상호작용, 발생 오류 등을 쉽게 파악하고 개선할 수 있습니다.

## 9. Backend 서버 연동

생성된 보고서 및 기타 필요한 데이터는 `.env` 파일에 설정된 `BACKEND_SERVER_URL`로 전송됩니다. `report_service.py` 또는 각 에이전트 내에서 해당 서버로 HTTP 요청을 보내는 로직을 구현해야 합니다.

---

**참고**: 이 `README.md`는 프로젝트의 시작점이며, 개발 진행 상황에 따라 지속적으로 업데이트되어야 합니다.
