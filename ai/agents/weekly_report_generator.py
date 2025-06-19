import os
import json
from datetime import datetime, timedelta

# LangChain 및 OpenAI 관련 라이브러리 임포트
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from ai.graphs.state_definition import WeeklyLangGraphState
from core import config
# from core.state_definition import LangGraphState # LangGraph와 직접 연동 시 필요

class WeeklyReportGenerator:
    """
    주어진 기간 동안의 일일 보고서들을 취합하여 주간 보고서를 생성합니다.
    보고서 생성 로직을 캡슐화하여 다른 곳에서 재사용할 수 있도록 합니다.
    """
    
    def __init__(self):
        """
        WeeklyReportGenerator를 초기화합니다.
        LLM, 프롬프트 템플릿, 출력 파서를 설정합니다.
        """
        self.llm = ChatOpenAI(
            model=config.DEFAULT_MODEL,
            temperature=0.2,
            openai_api_key=config.OPENAI_API_KEY
        )
        
        # 주간 보고서 프롬프트 템플릿 파일 경로 설정
        prompt_file_path = os.path.join(config.PROMPTS_BASE_DIR,"weekly_report_prompt.md")
        
        # 프롬프트 템플릿 파일 로드
        try:
            with open(prompt_file_path, "r", encoding="utf-8") as f:
                prompt_template_str = f.read()
        except FileNotFoundError:
            print(f"오류: 프롬프트 파일을 찾을 수 없습니다. 경로: {prompt_file_path}")
            # 프롬프트 파일이 없으면 실행이 불가능하므로 예외 발생
            raise
            
        # 예상 프롬프트 변수: {user_name}, {user_id}, {start_date}, {end_date}, {daily_reports}
        self.prompt = PromptTemplate.from_template(prompt_template_str)
        self.parser = JsonOutputParser()

    def generate_weekly_report(self, state: WeeklyLangGraphState) -> WeeklyLangGraphState:
        """
        일일 보고서 목록을 기반으로 주간 보고서를 생성합니다.
        """
        user_name = state.get("user_name")
        user_id = state.get("user_id")
        project_id = state.get("project_id")
        project_name = state.get("project_name")
        project_description = state.get("project_description")
        project_period = state.get("project_period")
        start_date = state.get("start_date")
        end_date = state.get("end_date")
        daily_reports = state.get("daily_reports_data")
        wbs_data = state.get("wbs_data")
        
        print(f"WeeklyReportGenerator: 사용자 '{user_name}' ({user_id})의 {start_date} ~ {end_date} 주간 보고서 생성 시작...")
        
        if not daily_reports:
            print("WeeklyReportGenerator: 분석할 일일 보고서가 없습니다. 생성을 중단합니다.")
            return {
                "error": "보고서 생성 실패",
                "message": "분석할 일일 보고서 데이터가 없습니다."
            }
            
        try:
            # LLM에 전달할 프롬프트 데이터 구성
            prompt_data = {
                "user_name": user_name,
                "user_id": user_id,
                "start_date": start_date,
                "end_date": end_date,
                "project_id": project_id,
                "project_name": project_name,
                "project_description": project_description,
                "project_period": project_period,
                "daily_reports": json.dumps(daily_reports or [], ensure_ascii=False, indent=2),
                "wbs_data": json.dumps(wbs_data, ensure_ascii=False, indent=2),
            }
            
            # LangChain 체인 구성 및 실행
            chain = self.prompt | self.llm | self.parser
            
            print("WeeklyReportGenerator: LLM을 통한 주간 보고서 생성 중...")
            report_result = chain.invoke(prompt_data)
            
            print(f"WeeklyReportGenerator: 주간 보고서 생성 완료 - 제목: {report_result.get('report_title', '제목 없음')}")
            
            state["weekly_report_result"] = report_result
            
            return state
            
        except Exception as e:
            print(f"WeeklyReportGenerator: 주간 보고서 생성 중 오류 발생: {e}")
            return {
                "error": "주간 보고서 생성 실패",
                "message": str(e)
            }
