"""
작성자 : 노건표
작성일 : 2025-06-01
작성내용 : 리팩토링 ( WBS 파일을 분석하고 VectorDB에 적재하는 에이전트 )
WBSAnalysisAgent 클래스 : WBS 파일을 분석하고 VectorDB에 적재하는 에이전트.
parameters:
    project_id (str): 프로젝트 ID
    wbs_file_path (str): WBS 파일 경로
    prompt_file_path (str): 프롬프트 파일 경로
    vector_db_base_path (Optional[str]): VectorDB 기본 경로 (기본값: None)

run_ingestion_pipeline : WBS 파일을 분석하고 VectorDB에 적재하는 메인 파이프라인.
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.utils import Settings
from .core import file_processor
from .core.llm_interface import LLMInterface
from .core.vector_db import VectorDBHandler
from typing import Optional
import os

class WBSAnalysisAgent:

    def __init__(self, project_id: str, wbs_file_path: str, prompt_file_path: str, 
                 vector_db_base_path: Optional[str] = None):

        if not all([project_id, wbs_file_path, prompt_file_path]):
            raise ValueError("project_id, wbs_file_path, prompt_file_path는 필수 인자입니다.")

        self.project_id = project_id
        self.wbs_file_path = os.path.abspath(wbs_file_path) # 절대 경로로 변환
        self.prompt_file_path = os.path.abspath(prompt_file_path) # 절대 경로로 변환

        # 설정 로드 (API 키 등)
        self.settings = Settings() # Settings 클래스 인스턴스화 시 API 키 등 유효성 검사

        # LLM 인터페이스 초기화
        prompt_template_string = LLMInterface.load_prompt_from_file(self.prompt_file_path)
        self.llm_interface = LLMInterface(
            api_key=self.settings.OPENAI_API_KEY,
            model_name=self.settings.OPENAI_MODEL_NAME,
            prompt_template_str=prompt_template_string
        )

        # VectorDB 핸들러 초기화
        db_path_to_use = vector_db_base_path or self.settings.VECTOR_DB_PATH_ENV or self.settings.DEFAULT_VECTOR_DB_BASE_PATH
        # vector_db_base_path 아래에 프로젝트별/컬렉션별로 실제 DB 파일이 생성됨
        self.db_handler = VectorDBHandler(
            db_base_path=db_path_to_use, # 실제 DB 파일이 저장될 최상위 경로
            collection_name_prefix="wbs_data", # 컬렉션 이름 접두사
            project_id=self.project_id,
        )
        
        print(f"WBSAnalysisAgent 초기화 완료: Project ID '{self.project_id}', WBS File '{self.wbs_file_path}'")

    def run_ingestion_pipeline(self):
        print(f"\n=== WBS 데이터 적재 파이프라인 시작: 프로젝트 '{self.project_id}' ===")
        
        # 1. WBS 파일 존재 여부 확인
        if not os.path.exists(self.wbs_file_path):
            print(f"오류: WBS 파일을 찾을 수 없습니다 - {self.wbs_file_path}")
            return False # 실패로 처리

        try:
            # 2. 현재 WBS 파일의 해시 계산
            current_wbs_hash = file_processor.calculate_file_hash(self.wbs_file_path)
            print(f"현재 WBS 파일 해시: {current_wbs_hash[:10]}...")

            # 3. DB에 저장된 이전 해시 조회
            stored_hash = self.db_handler.get_stored_wbs_hash()
            print(f"DB에 저장된 이전 해시: {stored_hash[:10] if stored_hash else '없음'}")

            # 4. 해시 비교하여 변경 여부 확인
            if current_wbs_hash == stored_hash and stored_hash is not None:
                print(f"WBS 데이터 변경 없음 (해시 동일). 프로젝트 '{self.project_id}' 적재 작업을 건너뜁니다.")
                print("=== 파이프라인 완료 (변경 없음) ===")
                return True # 성공 (변경 없음)

            # 5. 변경되었거나 첫 실행 시, 기존 데이터 삭제 (해당 프로젝트에 대해서만)
            print(f"WBS 데이터 변경 감지 또는 첫 실행. 프로젝트 '{self.project_id}'의 기존 VectorDB 데이터 삭제 중...")
            self.db_handler.clear_project_data()

            # 6. WBS 파일 읽고 JSON으로 변환
            print(f"WBS 파일 '{self.wbs_file_path}' 읽고 JSON으로 변환 중...")
            wbs_json_content = file_processor.read_wbs_to_json_text(self.wbs_file_path)
            # print(f"WBS JSON 내용 (일부): {wbs_json_content[:300]}...") # 디버깅 시

            # 7. LLM으로 분석 요청
            print("LLM을 통해 WBS 데이터 분석 중...")
            llm_analysis_result = self.llm_interface.analyze_wbs_with_llm(wbs_json_content)

            if not llm_analysis_result or not isinstance(llm_analysis_result, dict) or \
               not any(llm_analysis_result.get(key) for key in ["project_summary", "task_list"]):
                print("오류: LLM으로부터 유효한 분석 결과를 받지 못했습니다. 파이프라인을 중단합니다.")
                # print(f"LLM 응답 내용: {llm_analysis_result}") # 디버깅 시
                return False # 실패

            # 8. 분석 결과를 VectorDB에 저장
            print("LLM 분석 결과를 VectorDB에 저장 중...")
            self.db_handler.store_llm_analysis_results(llm_analysis_result, current_wbs_hash)
            
            print(f"프로젝트 '{self.project_id}'의 WBS 데이터 분석 및 적재 성공!")
            print("=== 파이프라인 성공적으로 완료 ===")
            return True # 성공

        except FileNotFoundError as e_fnf:
            print(f"파일 관련 오류 발생: {e_fnf}")
            return False
        except ValueError as e_val:
            print(f"값 또는 설정 관련 오류 발생: {e_val}")
            return False
        except RuntimeError as e_rt:
            print(f"실행 중 심각한 오류 발생: {e_rt}")
            return False
        except Exception as e:
            import traceback
            print(f"WBS 적재 파이프라인 실행 중 예상치 못한 오류 발생: {e}")
            print(traceback.format_exc()) # 상세 스택 트레이스 출력
            return False
