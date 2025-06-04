# -*- coding: utf-8 -*-
import os
import sys
import json

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

from core.utils import Settings
from tools.wbs_data_handler import WBSDataHandler 
from preprocessing.email_data_preprocessor import EmailDataPreprocessor
from agents.email_analyzer import EmailAnalyzerAgent 

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

def main():
    print("Email Analyzer - Test Run (Assuming all prerequisite files exist)")

    settings_instance = Settings()
    default_vector_db_base_path = os.path.join(PROJECT_ROOT, "db", "vector_store_test")
    settings_instance.VECTOR_DB_PATH_ENV = os.getenv("VECTOR_DB_PATH", default_vector_db_base_path)
    # VECTOR_DB_PATH_ENV 디렉토리는 여전히 생성할 수 있습니다. VectorDB 핸들러가 사용할 수 있도록.
    os.makedirs(settings_instance.VECTOR_DB_PATH_ENV, exist_ok=True)
    print(f"Using VECTOR_DB_PATH_ENV: {settings_instance.VECTOR_DB_PATH_ENV}")

    # 이메일 데이터 경로 - 이 파일은 반드시 존재해야 합니다.
    email_data_file = os.path.join(PROJECT_ROOT, "data", "email_export", "email_data.json")
    if not os.path.exists(email_data_file):
        print(f"Error: Email data file not found at {email_data_file}. Please create it.")
        sys.exit(1) # 파일이 없으면 종료

    # 이메일 프롬프트 파일 경로 - 이 파일은 반드시 존재해야 합니다.
    email_prompt_file_path = os.path.join(PROJECT_ROOT, "prompts", "email_analyze_prompt.md")
    if not os.path.exists(email_prompt_file_path):
        print(f"Error: Email prompt file not found at {email_prompt_file_path}. Please create it.")
        sys.exit(1) # 파일이 없으면 종료


    # --- 테스트 파라미터 ---
    test_author_email = "qkdrkzx@yasim2861.onmicrosoft.com" # 분석 대상 사용자
    test_wbs_assignee_name = "김용준" # WBS에서 필터링할 담당자 이름
    test_project_id_for_wbs = "project_sample_001" 
    test_target_date = "2025-05-28" 

    print(f"\n--- Running Email Analysis Test ---")
    print(f"Analysis for User Email: {test_author_email}")
    print(f"WBS Assignee Name: {test_wbs_assignee_name}")
    print(f"WBS Project ID: {test_project_id_for_wbs}")
    print(f"Target Date: {test_target_date}")
    
    # 핸들러들 초기화
    wbs_handler = WBSDataHandler(settings=settings_instance)
    email_preprocessor = EmailDataPreprocessor(settings=settings_instance)
    
    # EmailAnalyzerAgent 초기화
    email_agent = EmailAnalyzerAgent(
        settings=settings_instance,
        wbs_data_handler=wbs_handler,
        email_data_preprocessor=email_preprocessor
    )

    # 분석 실행
    analysis_output = email_agent.analyze(
        email_data_json_path=email_data_file,
        author_email_for_analysis=test_author_email,
        wbs_assignee_name=test_wbs_assignee_name,
        project_id_for_wbs=test_project_id_for_wbs,
        target_date_str=test_target_date
    )

    if analysis_output:
        print("\n--- Email Analysis Test Complete ---")
        # print(json.dumps(analysis_output, indent=2, ensure_ascii=False)) # 결과 상세 출력
        assert "user_id" in analysis_output, "user_id missing"
        assert "type" in analysis_output and analysis_output["type"] == "Email", "type missing or incorrect"
        assert "matched_tasks" in analysis_output, "matched_tasks missing"
        print("JSON structure basic validation passed for email analysis.")
    else:
        print("\n--- Email Analysis Test Failed ---")

    print(f"\nReviewed the email data file used: {email_data_file}")
    print(f"Reviewed the email prompt file used: {email_prompt_file_path}")

if __name__ == "__main__":
    main()
