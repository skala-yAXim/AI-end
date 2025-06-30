# core/state_definition.py
from typing import Dict, Any, Optional, List

from schemas.project_info import ProjectInfo

class LangGraphState(Dict):
    """
    LangGraph 워크플로우 전체에서 사용될 공유 상태 객체 정의.
    각 필드는 Optional로 선언하여 특정 노드에서만 사용될 수 있음을 명시합니다.
    """
    # --- 기본 입력 정보 ---
    user_id: Optional[str] = None # 분석 대상 사용자 ID
    user_email: Optional[str] = None # 분석 대상 사용자 이메일
    user_name: Optional[str] = None # 분석 대상 사용자 이름 (WBS 담당자명, LLM 프롬프트 표시용 등)
    target_date: Optional[str] = None # 분석 기준 날짜 (YYYY-MM-DD 형식). Documents를 제외한 모든 분석에서 사용.
    projects: Optional[List[ProjectInfo]]
    project_id: Optional[int] = None # 분석 대상 프로젝트 ID (WBS 등)

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

class TeamWeeklyLangGraphState(Dict):
    team_id: str
    team_name: str
    team_description: str
    start_date: str
    end_date: str
    team_members: List[str]
    # TODO project 여러개 들어오게끔 수정
    project_id: int
    project_name: str
    project_description: str
    project_period: str
    wbs_data: Optional[Dict] = None
    weekly_reports_data: Optional[List[Dict]] = None
    team_weekly_report_result: Optional[Dict] = None
    error_message: Optional[str] = None
    last_week_progress: Optional[Dict] = None
    project_name: Optional[str] = None
    project_start_date: Optional[str] = None
    project_end_date: Optional[str] = None

class WeeklyLangGraphState(Dict):
    user_name: str
    user_id: str
    start_date: str
    end_date: str
    # TODO project 여러개 들어오게끔 수정
    project_id: int
    project_name: str
    project_description: str
    project_period: str
    wbs_data: Optional[Dict] = None
    daily_reports_data: Optional[List[str]] = None
    weekly_report_result: Optional[Dict] = None
    error_message: Optional[str] = None


class ProgressSummaryState(Dict):
    user_name: Optional[str] = None 
    github_email: Optional[str] = None 
    target_date: Optional[str] = None 
    date: str
    # TODO project 여러개 들어오게끔 수정
    project_id: int
    daily_report_path: str
    daily_report: Dict[str, Any]
    wbs_data: List[Dict[str, Any]]
    progress_summary: str
    error_message: str
