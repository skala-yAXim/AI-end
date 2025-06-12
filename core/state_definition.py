# core/state_definition.py
from typing import Dict, Any, Optional, List

class LangGraphState(Dict):
    """
    LangGraph 워크플로우 전체에서 사용될 공유 상태 객체 정의.
    각 필드는 Optional로 선언하여 특정 노드에서만 사용될 수 있음을 명시합니다.
    """
    # --- 기본 입력 정보 ---
    user_id: Optional[str] = None # 분석 대상 사용자 ID (이메일 형식 또는 내부 ID). Docs, Teams, Email 분석의 기본 키.
    user_name: Optional[str] = None # 분석 대상 사용자 이름 (WBS 담당자명, LLM 프롬프트 표시용 등)
    github_email: Optional[str] = None # Git 활동 분석 시 사용할 GitHub 이메일. 없으면 user_id를 Git author로 간주.
    target_date: Optional[str] = None # 분석 기준 날짜 (YYYY-MM-DD 형식). Documents를 제외한 모든 분석에서 사용.
    project_id: Optional[str] = None # 분석 대상 프로젝트 ID (WBS 등)

    # --- 데이터 조회 및 분석 결과 ---
    wbs_data: Optional[Dict] = None 

    documents_analysis_result: Optional[Dict] = None
    documents_quality_result: Optional[Dict] = None # 문서 품질 분석 결과 (DocsAnalyzerAgent에서 사용)
    email_analysis_result: Optional[Dict] = None
    git_analysis_result: Optional[Dict] = None
    teams_analysis_result: Optional[Dict] = None

    # --- 종합 분석 결과 ---
    comprehensive_report: Optional[Dict] = None

    # --- 오류 및 상태 관리 ---
    error_message: Optional[str] = None
    current_step: Optional[str] = None

    # --- 각 분석기별 중간 데이터 (디버깅 또는 세부 분석용, 선택적) ---
    retrieved_documents: Optional[List[Dict]] = None
    retrieved_emails: Optional[List[Dict]] = None
    retrieved_git_activities: Optional[Dict[str, List[Dict]]] = None
    retrieved_readme_info: Optional[str] = None
    retrieved_teams_posts: Optional[List[Dict]] = None

class TeamWeeklyLangGraphState(Dict):
    team_id: str
    team_name: str
    team_description: str
    start_date: str
    end_date: str
    team_members: List[str]
    project_id: str
    wbs_data: Optional[Dict] = None
    weekly_reports_data: Optional[List[Dict]] = None
    team_weekly_report_result: Optional[Dict] = None
    error_message: Optional[str] = None
    

class WeeklyLangGraphState(Dict):
    user_name: str
    user_id: str
    start_date: str
    end_date: str
    project_id: str
    wbs_data: Optional[Dict] = None
    daily_reports_data: Optional[List[Dict]] = None
    weekly_report_result: Optional[Dict] = None
    error_message: Optional[str] = None

