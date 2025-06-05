# report_generate_main.py (옵션 1: 기존 Agent 래핑)

import os
import sys
import json
from agents.docs_analyzer import DocsAnalyzer
from agents.teams_analyzer import TeamsAnalyzer
from agents.report_generator import DailyReportGenerator

# 기존 Agent들을 위한 imports
from core.utils import Settings
from tools.wbs_data_handler import WBSDataHandler
from preprocessing.email_data_preprocessor import EmailDataPreprocessor
from preprocessing.git_data_preprocessor import GitDataPreprocessor
from agents.email_analyzer import EmailAnalyzerAgent
from agents.git_analyzer import GitAnalyzerAgent

from config import DATA_DIR

def setup_legacy_components():
    """기존 Agent들을 위한 설정"""
    settings_instance = Settings()
    default_vector_db_base_path = os.path.join("db", "vector_store_test")
    settings_instance.VECTOR_DB_PATH_ENV = os.getenv("VECTOR_DB_PATH", default_vector_db_base_path)
    os.makedirs(settings_instance.VECTOR_DB_PATH_ENV, exist_ok=True)
    
    return settings_instance

def run_email_analysis(user_id, user_name, target_date, settings):
    """Email 분석 실행"""
    try:
        # 핸들러들 초기화
        wbs_handler = WBSDataHandler(settings=settings)
        email_preprocessor = EmailDataPreprocessor(settings=settings)
        
        # EmailAnalyzerAgent 초기화
        email_agent = EmailAnalyzerAgent(
            settings=settings,
            wbs_data_handler=wbs_handler,
            email_data_preprocessor=email_preprocessor
        )
        
        # 이메일 데이터 파일 경로
        email_data_file = os.path.join(DATA_DIR, "email_export", "email_data.json")
        if not os.path.exists(email_data_file):
            print(f"경고: 이메일 데이터 파일이 없습니다: {email_data_file}")
            return {"user_id": user_id, "date": target_date, "type": "email", "matched_tasks": [], "unmatched_tasks": [], "error": "이메일 데이터 파일 없음"}
        
        # 분석 실행
        result = email_agent.analyze(
            email_data_json_path=email_data_file,
            author_email_for_analysis=user_id,
            wbs_assignee_name=user_name,
            project_id_for_wbs="project_sample_001",
            target_date_str=target_date
        )
        
        return result if result else {"user_id": user_id, "date": target_date, "type": "email", "matched_tasks": [], "unmatched_tasks": []}
        
    except Exception as e:
        print(f"이메일 분석 중 오류: {e}")
        return {"user_id": user_id, "date": target_date, "type": "email", "matched_tasks": [], "unmatched_tasks": [], "error": str(e)}

def run_git_analysis(user_id, user_name, target_date, settings):
    """Git 분석 실행"""
    try:
        # 핸들러들 초기화
        git_preprocessor = GitDataPreprocessor(settings=settings)
        wbs_handler = WBSDataHandler(settings=settings)
        
        # GitAnalyzerAgent 초기화
        git_agent = GitAnalyzerAgent(
            settings=settings,
            project_id_for_wbs="project_sample_001",
            git_data_preprocessor=git_preprocessor,
            wbs_data_handler=wbs_handler
        )
        
        # Git 데이터 파일 경로
        git_data_file = os.path.join(DATA_DIR, "git_export", "git_data.json")
        if not os.path.exists(git_data_file):
            print(f"경고: Git 데이터 파일이 없습니다: {git_data_file}")
            return {"user_id": user_id, "date": target_date, "type": "git", "matched_tasks": [], "unmatched_tasks": [], "error": "Git 데이터 파일 없음"}
        
        # 분석 실행
        result = git_agent.analyze(
            git_data_json_path=git_data_file,
            author_email_for_report=user_id,
            wbs_assignee_name=user_name,
            repo_name="skala-yAXim/AI-end",
            target_date_str=target_date
        )
        
        return result if result else {"user_id": user_id, "date": target_date, "type": "git", "matched_tasks": [], "unmatched_tasks": []}
        
    except Exception as e:
        print(f"Git 분석 중 오류: {e}")
        return {"user_id": user_id, "date": target_date, "type": "git", "matched_tasks": [], "unmatched_tasks": [], "error": str(e)}

def main():
    # WBS 데이터 로드
    with open(os.path.join(DATA_DIR, "wbs_analyze_data.json"), "r", encoding="utf-8") as f:
        raw_wbs = f.read()

    # 분석 대상 사용자 정보
    user_id = "sermadl1014@yasim2861.onmicrosoft.com"
    user_name = "김세은"
    target_date = "2025-05-29"
    wbs_data = json.dumps(raw_wbs, ensure_ascii=False, indent=2)

    # State 객체 생성
    state = {
        "user_id": user_id,
        "user_name": user_name,
        "target_date": target_date,
        "wbs_data": wbs_data
    }

    print(f"=== {user_name}님의 {target_date} 종합 Daily 보고서 생성 시작 ===")
    
    # 기존 Agent들을 위한 설정
    settings = setup_legacy_components()
    
    # 1. Docs 분석 실행
    print("\n1. 문서 분석 중...")
    docs_analyzer = DocsAnalyzer()
    docs_result = docs_analyzer(state)
    state["docs_analysis_result"] = docs_result
    print(f"문서 분석 완료: {len(docs_result.get('matched_tasks', []))}개 매칭, {len(docs_result.get('unmatched_tasks', []))}개 미매칭")
    
    # 2. Teams 분석 실행
    print("\n2. Teams 분석 중...")
    teams_analyzer = TeamsAnalyzer()
    teams_result = teams_analyzer(state)
    state["teams_analysis_result"] = teams_result
    print(f"Teams 분석 완료: {len(teams_result.get('matched_tasks', []))}개 매칭, {len(teams_result.get('unmatched_tasks', []))}개 미매칭")
    
    # 3. Email 분석 실행
    print("\n3. 이메일 분석 중...")
    email_result = run_email_analysis(user_id, user_name, target_date, settings)
    state["email_analysis_result"] = email_result
    print(f"이메일 분석 완료: {len(email_result.get('matched_tasks', []))}개 매칭, {len(email_result.get('unmatched_tasks', []))}개 미매칭")
    
    # 4. Git 분석 실행
    print("\n4. Git 분석 중...")
    git_result = run_git_analysis(user_id, user_name, target_date, settings)
    state["git_analysis_result"] = git_result
    print(f"Git 분석 완료: {len(git_result.get('matched_tasks', []))}개 매칭, {len(git_result.get('unmatched_tasks', []))}개 미매칭")
    
    # 5. 종합 Daily 보고서 생성
    print("\n5. 종합 Daily 보고서 생성 중...")
    report_generator = DailyReportGenerator()
    final_report = report_generator.generate_daily_report(state)
    
    if final_report.get("success"):
        print("\n=== 종합 Daily 보고서 생성 완료 ===")
        print(f"생성 시간: {final_report.get('generated_at')}")
        
        # 결과 출력
        print("\n=== 최종 보고서 내용 ===")
        print(final_report["final_report"]["json_content"])
        
        # 파일로 저장
        output_filename = f"daily_report_{user_name}_{target_date.replace('-', '')}.json"
        output_path = os.path.join("outputs", output_filename)
        
        os.makedirs("outputs", exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_report["final_report"]["json_content"])
        
        print(f"\n종합 보고서가 {output_path}에 저장되었습니다.")
        
    else:
        print("보고서 생성 중 오류가 발생했습니다.")
        print(final_report)

if __name__ == "__main__":
    main()