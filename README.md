# LangGraph 기반 AI 에이전트를 활용한 보고서 생성 시스템

## 1. 기능 요약 (Features)

LangGraph 프레임워크 기반 시스템으로, 다양한 데이터 소스(WBS, Git, Email, Microsoft Teams, 문서 파일)를 분석하여 **프로젝트 진행 상황 보고서**를 자동 생성합니다.

### 주요 기능

- **WBS 분석 및 캐싱**  
  - 프로젝트 기준이 되는 WBS(Work Breakdown Structure)를 분석하고 캐싱
  - 다른 에이전트가 공통 기준으로 참조 가능

- **다중 데이터 소스 병렬 분석**
  - **Git Analyze Agent**: 커밋/PR/이슈/README 분석
  - **Email Analyze Agent**: 이메일 기반 업무 소통 추적
  - **Teams Analyze Agent**: 채팅/게시물 중심 협업 기록 추적
  - **Docs Analyze Agent**: 문서 변경 이력, 품질 분석

- **자동 일일 보고서 생성**
  - WBS 기준의 업무 내역 + 기타 진행사항 요약
  - 출처 및 증거 포함

- **RAG (Retrieval Augmented Generation) 지원**
  - 문서 및 WBS 분석 시 외부 문서 참조로 정확도 및 깊이 향상

---

## 2. 프로젝트 구조 (Project Structure)
```bash

your-repository-name/
├── .env                
├── .gitignore               
├── README.md               # 프로젝트 개요 및 사용 방법 안내
├── requirements.txt       
├── main.py                 # 메인 실행 스크립트 (Graph 실행 및 워크플로우 제어)
├── graph.py                # LangGraph 그래프 정의 파일
│
├── core/                   # 프로젝트 핵심 로직 및 공통 유틸리티
│   ├── __init__.py
│   └── utils.py            # 공통 헬퍼 함수, 설정 로더 등
│
├── agents/                 # 각 분석 에이전트 모듈
│   ├── __init__.py
│   ├── run_wbs_analyzer.py     # WBS 분석 에이전트
│   ├── git_analyzer.py     # Git 분석 에이전트 (로컬 데이터 처리)
│   ├── email_analyzer.py   # Email 분석 에이전트 (로컬 데이터 처리)
│   ├── teams_analyzer.py   # Teams 분석 에이전트 (로컬 데이터 처리)
│   ├── docs_analyzer.py    # 문서 분석 에이전트
│   └── report_generator.py # 일일 보고서 생성 에이전트
├── └── wbs_ingestion_agent/       # WBS 분석 및 적재 에이전트 패키지
│       ├── __init__.py
│       ├── core/                  # 핵심 로직 컴포넌트
│       │   ├── __init__.py
│       │   ├── config.py          # 설정 (API 키, DB 기본 경로 등)
│       │   ├── file_processor.py  # 파일 해시, WBS 데이터 읽기
│       │   ├── llm_interface.py   # LLM 연동 (프롬프트 로딩, API 호출, 응답 파싱)
│       │   └── vector_db.py       # VectorDB 핸들링 (연결, 저장, 조회, 삭제)
│       └── agent.py               # WBSAnalysisAgent 클래스 (핵심 로직 조합)
│
├── prompts/             # LLM 에이전트용 프롬프트 템플릿
│   ├── wbs_prompt.md
│   ├── git_analyze_prompt.md
│   ├── email_analyze_prompt.md
│   ├── teams_analyze_prompt.md
│   ├── docs_analyze_prompt.md
│   └── daily_report_prompt.md
│
├── tools/                # Tool 모듈
│   └── __init__.py
│
├── data/                # 분석용 입력 데이터 (샘플 또는 로컬 파일)
│   ├── wbs/             # WBS 파일 저장 위치
│   │   └── project_wbs.xlsx
│   ├── git_export/      # Git 데이터 export 파일 (e.g., JSON, CSV)
│   │   └── commits.json
│   ├── email_export/    # Email 데이터 export 파일 (e.g., mbox, JSON)
│   │   └── project_emails.json
│   ├── teams_export/    # Teams 데이터 export 파일 (e.g., JSON)
│   │   └── team_chats.json
│   └── project_documents/ # 분석 대상 문서 파일
│       ├── requirement_spec_v1.docx
│       └── design_doc_v2.pdf
│
├── db/                  # 로컬 데이터베이스 및 캐시 파일
    ├── wbs_cache.db     # WBS 분석 결과 캐시 
    └── vector_store/    # 문서 임베딩 VectorDB (ChromaDB)

```

---

## 3. 프로젝트 아키텍처 (System Architecture)

### WBS 분석 Architecture 
 ```mermaid
graph TD;
    WBSAnalyze --> WBSRetriever
```

### 개인 Daily 보고서 Architecture 
 ```mermaid
graph TD;
    WBSRetriever -->|병렬| GitAnalyze
    WBSRetriever -->|병렬| EmailAnalyze
    WBSRetriever -->|병렬| TeamsAnalyze
    WBSRetriever -->|병렬| DocsAnalyze
    GitAnalyze --> DailyReport
    EmailAnalyze --> DailyReport
    TeamsAnalyze --> DailyReport
    DocsAnalyze --> DailyReport
```

### 개인 Weekly 보고서 Architecture
 ```mermaid
graph TD;
    WBSRetriever -->|병렬| WeeklyReport
    DailyReport  -->|병렬| WeeklyReport
```

### 팀 Weekly 보고서 Architecture
 ```mermaid
graph TD;
    WBSRetriever -->|병렬| TeamWeeklyReport
    WeeklyReport -->|병렬| TeamWeeklyReport
```

흐름 요약:
WBS 분석 → 캐싱

병렬 데이터 분석 (Git, Email, Teams, Docs)

분석 결과 → 종합 보고서 생성

## 4. 설치 및 실행 방법 (Installation & Setup)

### 4.1. 사전 요구 사항

Python 3.8+

LangGraph, LangChain, ChromaDB 등

(초기 단계) API 접근 불필요

### 4.2. 설치

```bash
git clone https://github.com/your-username/your-repository-name.git
cd your-repository-name


# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate


# 패키지 설치
pip install -r requirements.txt
4.3. 실행


# WBS 분석 및 캐시 저장
python main.py --run_wbs_analyzer --wbs_file data/wbs/project_wbs.xlsx


# 일일 보고서 생성
python main.py --generate_report --date 2025-05-29
```

## 5. 설정 파일 (.env)

예시 설정값
```bash
# LLM API Keys
OPENAI_API_KEY="your_openai_api_key_here"
# GOOGLE_API_KEY="your_google_api_key_here"
# HUGGINGFACE_API_TOKEN="your_huggingface_token_here"

# Database Paths
CACHE_DB_PATH="db/wbs_cache.db"
VECTOR_DB_PATH="db/vector_store"

# Data Paths
WBS_DATA_DIR="data/wbs/"
GIT_DATA_PATH="data/git_export/commits.json"
EMAIL_DATA_PATH="data/email_export/project_emails.json"
TEAMS_DATA_PATH="data/teams_export/team_chats.json"
PROJECT_DOCS_DIR="data/project_documents/"

# Logging
LOG_LEVEL="INFO"
.env.example 참고하여 실제 값을 입력한 .env 생성 필요
```