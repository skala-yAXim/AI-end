# test_runner.py (최종 수정본)

import os
import json
import sys
import pandas as pd
from datetime import datetime, timedelta

COLLECTION_NAME_GIT_ACTIVITIES = "Git-Activities"
COLLECTION_NAME_GIT_README = "Git-Readme"
TEST_USER_EMAIL = "minsuh3203@yasim2861.onmicrosoft.com"  # 분석할 사용자의 Git 이메일
TEST_USER_NAME = "조민서"              # 리포트에 표시될 사용자 이름
TEST_TARGET_DATE = "2025-06-05"       # 분석할 날짜 (YYYY-MM-DD 형식)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if not os.getenv("OPENAI_API_KEY"):
    print("오류: OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
    print("터미널에서 'export OPENAI_API_KEY=your_key'를 실행하거나 .env 파일을 설정해주세요.")
    sys.exit(1)

from qdrant_client import QdrantClient, models
from agents.git_analyzer import GitAnalyzerAgent

LangGraphState = dict

def main():
    """메인 테스트 실행 함수"""
    print("--- Git Analyzer Agent 테스트 시작 (localhost:6333 연결) ---")
    
    # 1. 실제 Qdrant 클라이언트 초기화
    try:
        qdrant_client = QdrantClient(host="localhost", port=6333)
        qdrant_client.get_collections() 
        print("Qdrant DB (localhost:6333) 연결 성공.")
    except Exception as e:
        print(f"오류: Qdrant DB (localhost:6333)에 연결할 수 없습니다. Qdrant 서버가 실행 중인지 확인해주세요.")
        print(f"에러 상세: {e}")
        sys.exit(1)
    
    # 2. GitAnalyzerAgent 인스턴스 생성
    # 에이전트가 초기화되면서 자체적으로 './prompts/git_analyze_prompt.md' 파일을 로드합니다.
    git_agent = GitAnalyzerAgent(qdrant_client=qdrant_client)
    
    # 3. LangGraph State 시뮬레이션
    initial_state = LangGraphState({
        "github_email": TEST_USER_EMAIL,
        "user_name": TEST_USER_NAME,
        "target_date": TEST_TARGET_DATE,
        "wbs_data": {
            "project_name": "AI-end-Test",
            "taks": [
                {"task_id": "T01", "task_name": "로그인 기능 개발", "assignee": TEST_USER_NAME, "status": "진행중"},
                {"task_id": "T02", "task_name": "백엔드 API 연동", "assignee": TEST_USER_NAME, "status": "예정"}
            ]
        }
    })
    
    print(f"\n--- 에이전트 실행 (State: {json.dumps(initial_state, indent=2, ensure_ascii=False)}) ---")
    
    # 4. 에이전트 호출
    result_state = git_agent(initial_state)
    
    # 5. 결과 출력
    print("\n--- 에이전트 실행 완료 ---")
    git_analysis_result = result_state.get("git_analysis_result")
    
    if git_analysis_result:
        print("최종 분석 결과 (git_analysis_result):")
        print(json.dumps(git_analysis_result, indent=2, ensure_ascii=False))
        
        json_string = json.dumps(git_analysis_result, ensure_ascii=False, indent=2)
        output_filename = f"git_analysis_{TEST_USER_NAME}_{TEST_TARGET_DATE}.json"
        output_path = os.path.join("./outputs", output_filename)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_string)
    else:
        print("분석 결과가 없습니다.")

if __name__ == "__main__":
    main()