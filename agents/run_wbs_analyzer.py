import argparse
import os
import sys 

from wbs_analyze_agent.agent import WBSAnalysisAgent
from wbs_analyze_agent.core.config import Settings 

def main():
    parser = argparse.ArgumentParser(description="WBS 분석 및 VectorDB 적재 에이전트 실행 스크립트")
    parser.add_argument("--project_id", help="분석 대상 프로젝트의 고유 ID", default="project123")
    parser.add_argument("--wbs_file", help="분석할 WBS 엑셀 파일의 전체 또는 상대 경로", default="data/wbs/WBS_스마트팩토리챗봇1.xlsx")
    parser.add_argument("--prompt_file", help="LLM에 사용될 프롬프트 파일의 전체 또는 상대 경로", default="prompts/wbs_prompt.md")
    parser.add_argument("--db_path", help="VectorDB가 저장될 기본 경로 (선택 사항, 없으면 config의 기본값 사용)")
    
    args = parser.parse_args()

    print("--- WBS 적재 에이전트 실행 ---")
    print(f"프로젝트 ID: {args.project_id}")
    print(f"WBS 파일 경로: {args.wbs_file}")
    print(f"프롬프트 파일 경로: {args.prompt_file}")
    if args.db_path:
        print(f"VectorDB 기본 경로 (사용자 지정): {args.db_path}")
    else:
        # Settings에서 기본 DB 경로 가져오기 (참고용)
        try:
            s = Settings() # API 키 없으면 여기서 에러날 수 있음. .env 파일 로드 확인.
            default_db_path_from_config = s.VECTOR_DB_PATH_ENV or s.DEFAULT_VECTOR_DB_BASE_PATH
            print(f"VectorDB 기본 경로 (설정값): {default_db_path_from_config}")
        except ValueError as e:
            print(f"경고: 설정 로드 중 오류로 기본 DB 경로를 확인할 수 없습니다 - {e}")
            print("      .env 파일에 OPENAI_API_KEY가 설정되어 있는지 확인하세요.")
            # API 키가 없어도 db_path 인자가 주어지면 실행은 가능할 수 있으나,
            # VectorDBHandler에서 임베딩 함수 초기화 시 문제가 될 수 있음.

    # 파일 경로를 절대 경로로 변환 (상대 경로 입력 지원)
    wbs_file_abs = os.path.abspath(args.wbs_file)
    prompt_file_abs = os.path.abspath(args.prompt_file)
    db_path_abs = os.path.abspath(args.db_path) if args.db_path else None

    if not os.path.exists(wbs_file_abs):
        print(f"오류: WBS 파일을 찾을 수 없습니다 - {wbs_file_abs}")
        sys.exit(1)
    if not os.path.exists(prompt_file_abs):
        print(f"오류: 프롬프트 파일을 찾을 수 없습니다 - {prompt_file_abs}")
        sys.exit(1)

    try:
        # WBSAnalysisAgent 인스턴스 생성
        agent = WBSAnalysisAgent(
            project_id=args.project_id,
            wbs_file_path=wbs_file_abs,
            prompt_file_path=prompt_file_abs,
            vector_db_base_path=db_path_abs # None일 수 있음
        )
        
        # 에이전트 파이프라인 실행
        success = agent.run_ingestion_pipeline()

        if success:
            print("--- 에이전트 실행 완료 (성공) ---")
            sys.exit(0)
        else:
            print("--- 에이전트 실행 완료 (실패 또는 문제 발생) ---")
            sys.exit(1)

    except ValueError as e: # 주로 설정 관련 에러 (예: API 키 없음)
        print(f"에이전트 초기화 또는 실행 중 설정 오류: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"에이전트 실행 중 파일 관련 오류: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"에이전트 실행 중 예상치 못한 심각한 오류 발생: {e}")
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
