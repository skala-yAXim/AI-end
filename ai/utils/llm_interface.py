
import os
import json
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

class LLMInterface:

    def __init__(self, api_key: str, model_name: str, prompt_template_str: str):
        if not api_key:
            raise ValueError("LLMInterface 초기화: OpenAI API 키가 필요합니다.")
        if not prompt_template_str:
            raise ValueError("LLMInterface 초기화: 프롬프트 템플릿 문자열이 필요합니다.")

        self.llm = ChatOpenAI(
            model_name=model_name,
            openai_api_key=api_key,
            temperature=0, # 일관된 출력을 위해 온도 조절
            # model_kwargs={"response_format": {"type": "json_object"}} # JSON 모드 활성화
        )
        try:
            self.prompt_template = PromptTemplate.from_template(prompt_template_str)
        except Exception as e:
            raise ValueError(f"프롬프트 템플릿 생성 실패: {e}\n템플릿 내용: {prompt_template_str[:200]}...")

        # LangChain 체인 구성 (입력 변수가 'wbs_data' 하나라고 가정)
        self.chain = (
            {"wbs_data": RunnablePassthrough()} 
            | self.prompt_template
            | self.llm
            | StrOutputParser() # LLM 응답을 문자열로 받음
        )
        print(f"LLMInterface 초기화 완료. 모델: {model_name}")

    @staticmethod
    def load_prompt_from_file(prompt_file_path: str) -> str:

        if not os.path.exists(prompt_file_path):
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {prompt_file_path}")
        try:
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"프롬프트 파일 읽기 오류 ({prompt_file_path}): {e}")
            raise

    def analyze_wbs_with_llm(self, wbs_json_data: str) -> Dict[str, Any]:
        if not wbs_json_data:
            print("경고: LLM 분석을 위한 WBS 데이터가 비어있습니다.")
            return self._default_llm_response()

        print("LLM에 WBS 데이터 전송 및 분석 요청 중...")
        prompt_preview = self.prompt_template.format(wbs_data=wbs_json_data)
        print(f"[DEBUG] Prompt 길이 (문자): {len(prompt_preview)}")

        try:
            response_str = self.chain.invoke(wbs_json_data)
            print("LLM 분석 완료. 응답 파싱 중...")
            # prompt_str = self.prompt_template.format(wbs_data=wbs_json_data)
            # response_str = self.llm.invoke(prompt_str)  # LangChain chain 안 거침

            # LLM 응답이 마크다운 코드 블록(```json ... ```)으로 감싸져 오는 경우가 있으므로 처리
            clean_response_str = response_str.strip()
            if clean_response_str.startswith("```json"):
                clean_response_str = clean_response_str[7:]
                if clean_response_str.endswith("```"):
                    clean_response_str = clean_response_str[:-3]
            clean_response_str = clean_response_str.strip()

            # JSON 응답 시작과 끝을 찾아 파싱 (더 견고한 방법 고려 가능)
            json_start = clean_response_str.find('{')
            json_end = clean_response_str.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_to_parse = clean_response_str[json_start:json_end]
                parsed_json = json.loads(json_to_parse)
                print("LLM 응답 파싱 성공.")
                return parsed_json
            else:
                print(f"LLM 응답에서 유효한 JSON 구조를 찾지 못했습니다. 응답 전문: {response_str}")
                return self._default_llm_response()
        except json.JSONDecodeError as e:
            error_context = clean_response_str if 'clean_response_str' in locals() else response_str
            print(f"LLM JSON 응답 파싱 오류: {e}")
            print(f"LLM 원본 응답 (파싱 시도 부분):\n{error_context}")
            return self._default_llm_response()
        except Exception as e:
            # API 연결 오류 등 LangChain/OpenAI 관련 예외 처리 포함
            print(f"LLM 처리 중 예상치 못한 오류 발생: {e}")
            # raise # 필요에 따라 에러를 다시 발생시켜 상위 호출부에서 처리
            return self._default_llm_response() # 또는 기본 응답 반환

    def _default_llm_response(self) -> Dict[str, Any]:
        """LLM 처리 실패 또는 유효하지 않은 응답 시 반환할 기본 구조입니다."""
        return {
            "project_summary": None, 
            "task_list": [], 
            "assignee_workload": {}, # 프롬프트 스키마에 따라 딕셔너리
            "delayed_tasks": []
        }
