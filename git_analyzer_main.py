# -*- coding: utf-8 -*-
import os
import sys
import json
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

from core.utils import Settings
from preprocessing.git_data_preprocessor import GitDataPreprocessor
from tools.wbs_data_handler import WBSDataHandler # WBS 핸들러 임포트
from agents.git_analyzer import GitAnalyzerAgent

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

def main():
    print("Git Analyzer Agent - Test Run with Refactored Code (including WBSDataHandler)")

    settings_instance = Settings()
    default_vector_db_base_path = os.path.join(PROJECT_ROOT, "db", "vector_store_test")
    settings_instance.VECTOR_DB_PATH_ENV = os.getenv("VECTOR_DB_PATH", default_vector_db_base_path)
    os.makedirs(settings_instance.VECTOR_DB_PATH_ENV, exist_ok=True)
    print(f"Using VECTOR_DB_PATH_ENV: {settings_instance.VECTOR_DB_PATH_ENV}")

    real_git_data_path = os.path.join(PROJECT_ROOT, "data", "git_export", "git_data.json")
    print(f"Attempting to use real git data from: {real_git_data_path}")

    test_author_email_for_report = "kproh99@naver.com" 
    test_wbs_assignee_name = "노건표" 
    test_repo_name = "skala-yAXim/AI-end" 
    test_project_id_for_wbs = "project_sample_001"
    test_target_date = "2025-06-02"

    print(f"\n--- Running Test ---")
    print(f"Report for User: {test_author_email_for_report}")
    print(f"WBS Assignee: {test_wbs_assignee_name}")
    print(f"Repository Filter: {test_repo_name}")
    print(f"Target Date: {test_target_date if test_target_date else 'All Recent'}")
    print(f"WBS Project ID: {test_project_id_for_wbs}")
    
    # 핸들러들 초기화
    git_preprocessor = GitDataPreprocessor(settings=settings_instance)
    wbs_handler = WBSDataHandler(settings=settings_instance) # WBS 핸들러 초기화

    # GitAnalyzerAgent 초기화 시 핸들러들 전달
    git_agent = GitAnalyzerAgent(
        settings=settings_instance, 
        project_id_for_wbs=test_project_id_for_wbs, # 컨텍스트용 ID 전달
        git_data_preprocessor=git_preprocessor,
        wbs_data_handler=wbs_handler # WBS 핸들러 전달
    )

    analysis_output = git_agent.analyze(
        git_data_json_path=real_git_data_path, 
        author_email_for_report=test_author_email_for_report,
        wbs_assignee_name=test_wbs_assignee_name,
        repo_name=test_repo_name,
        target_date_str=test_target_date
    )

    if analysis_output:
        print("\n--- Test Analysis Complete ---")
        assert "user_id" in analysis_output, "user_id missing"
        # LLM이 user_id를 채우도록 프롬프트에서 요청했으므로, LLM 결과에 따라 달라질 수 있음
        # 여기서는 LLM이 author_email_for_report 값으로 채웠다고 가정
        # assert analysis_output["user_id"] == test_author_email_for_report, "user_id mismatch" 
        assert "date" in analysis_output, "date missing"
        assert "type" in analysis_output and analysis_output["type"] == "Git", "type missing or incorrect"
        assert "matched_tasks" in analysis_output, "matched_tasks missing"
        assert "unmatched_tasks" in analysis_output, "unmatched_tasks missing"
        print("JSON structure basic validation passed.")
    else:
        print("\n--- Test Analysis Failed ---")

    print(f"Review the git data file used: {real_git_data_path}")

if __name__ == "__main__":
    main()
