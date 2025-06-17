"""
작성자 : 노건표
작성일 : 2025-06-01 
작성내용 : 리팩토링 ( WBS 분석 에이전트 실행을 담당하는 클래스 )

def run_wbs_agent(project_id: str, 
                        wbs_file_path: str, 
                        prompt_file_path: str, 
                        db_base_path: Optional[str] = None):
parameters:
    project_id (str): 프로젝트 ID
    wbs_file_path (str): WBS 파일 경로
    prompt_file_path (str): 프롬프트 파일 경로
    db_base_path (Optional[str]): VectorDB 기본 경로 (기본값: None)

업데이트 내역:
작성자 : 노건표
작성일 : 2025-06-04
작성내용 : Qdrant로 벡터DB를 사용하였기에 test 코드 수정.
"""
import os
import sys
from typing import Optional

from agents.wbs_analyze_agent.agent import WBSAnalysisAgent
from core.utils import Settings 
from langchain.globals import set_llm_cache

# LangChain 캐시 비활성화 (LLM 호출 시 항상 최신 응답을 받기 위함)
set_llm_cache(None)

def run_wbs_agent(project_id: str, 
                        wbs_file_path: str):
    
    prompt_file_path = "prompts/wbs_prompt.md"

    print("--- WBS 적재 에이전트 실행 ---")
    print(f"프로젝트 ID: {project_id}")
    print(f"WBS 파일 경로: {wbs_file_path}")
    print(f"프롬프트 파일 경로: {prompt_file_path}")

    # 파일 경로를 절대 경로로 변환
    wbs_file_abs = os.path.abspath(wbs_file_path)
    prompt_file_abs = os.path.abspath(prompt_file_path)

    if not os.path.exists(wbs_file_abs):
        print(f"오류: WBS 파일을 찾을 수 없습니다 - {wbs_file_abs}")
        return False
    if not os.path.exists(prompt_file_abs):
        print(f"오류: 프롬프트 파일을 찾을 수 없습니다 - {prompt_file_abs}")
        return False

    try:
        agent = WBSAnalysisAgent(
            project_id=project_id,
            wbs_file_path=wbs_file_abs,
            prompt_file_path=prompt_file_abs
        )
        
        success = agent.run_ingestion_pipeline()

        if success:
            print("--- 에이전트 실행 완료 (성공) ---")
        else:
            print("--- 에이전트 실행 완료 (실패 또는 문제 발생) ---")
        return success

    except ValueError as e: # 주로 설정 관련 에러 (예: API 키 없음)
        print(f"에이전트 초기화 또는 실행 중 설정 오류: {e}")
        return False
    except FileNotFoundError as e:
        print(f"에이전트 실행 중 파일 관련 오류: {e}")
        return False
    except Exception as e:
        import traceback
        print(f"에이전트 실행 중 예상치 못한 심각한 오류 발생: {e}")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    
    # 예시: 기본값 사용
    project_id_example = "project_sample_001"
    wbs_file_example = "data/wbs/[야심]_300. WBS_v0.2.xlsx" # 실제 파일 경로로 수정 필요
    # wbs_file_example = "data/wbs/WBS_스마트팩토리챗봇1.xlsx" # 실제 파일 경로로 수정 필요

    print(f"예시 실행: 프로젝트 ID '{project_id_example}'")
    
    # 필요한 경우 .env 파일이 올바르게 로드되었는지 확인
    # (Settings 클래스 초기화 시 OPENAI_API_KEY 등이 필요할 수 있음)
    try:
        Settings() 
        print(".env 설정 로드 확인됨 (또는 OPENAI_API_KEY가 환경 변수에 직접 설정됨).")
    except ValueError as e:
        print(f"주의: .env 파일 또는 OPENAI_API_KEY 환경 변수 설정 문제 가능성 - {e}")
        print("      계속 진행하지만, API 키가 필요한 작업에서 오류가 발생할 수 있습니다.")

    # 함수 호출
    success_status = run_wbs_agent(
        project_id=project_id_example,
        wbs_file_path=wbs_file_example
    )

    if success_status:
        sys.exit(0) # 성공 시 종료 코드 0
    else:
        sys.exit(1) # 실패 시 종료 코드 1
