import os
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from core import config
from ai.graphs.state_definition import LangGraphState

class DailyReportGenerator:
    """
    LangGraph 워크플로우와 통합된 일일 보고서 생성기
    분석된 Teams, Docs, Git, Email, Project 데이터를 종합하여 JSON 형식의 보고서 생성
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=config.DEFAULT_MODEL,  # gpt-4o 사용
            temperature=0.3,
            openai_api_key=config.OPENAI_API_KEY
        )
        
        # 프롬프트 템플릿 로드
        prompt_file_path = os.path.join(config.PROMPTS_BASE_DIR, "daily_report_prompt.md")
        with open(prompt_file_path, "r", encoding="utf-8") as f:
            prompt_content = f.read()

        self.prompt = PromptTemplate(
            template=prompt_content,
            input_variables=[
                "user_name", "user_id", "target_date",
                "wbs_data", "docs_analysis", "teams_analysis", 
                "git_analysis", "email_analysis", "project_id", "project_name", "project_description", "project_period",
                "retrieved_readme_info", "docs_daily_reflection", "teams_daily_reflection", 
                "git_daily_reflection", "email_daily_reflection"
            ]
        )
        self.parser = JsonOutputParser()

    def generate_daily_report(self, state: LangGraphState) -> LangGraphState:
        """
        종합 일일 보고서 생성 (LangGraph 노드 함수)
        """
        print(f"DailyReportGenerator: 사용자 '{state.get('user_name')}' ({state.get('user_id')})의 {state.get('target_date')} 보고서 생성 시작...")
        
        try:
            # state에서 직접 데이터 추출
            prompt_data = {
                "user_name": state.get("user_name", "사용자"),
                "user_id": state.get("user_id", "알 수 없음"),
                "target_date": state.get("target_date", datetime.now().strftime('%Y-%m-%d')),
                "wbs_data": str(state.get("wbs_data", "WBS 데이터 없음")),
                "docs_analysis": str(state.get("documents_analysis_result", "문서 분석 결과 없음")),
                "teams_analysis": str(state.get("teams_analysis_result", "Teams 분석 결과 없음")),
                "git_analysis": str(state.get("git_analysis_result", "Git 분석 결과 없음")),
                "email_analysis": str(state.get("email_analysis_result", "이메일 분석 결과 없음")),
                "project_id": str(state.get("project_id", "프로젝트 ID 없음")),
                "project_name": str(state.get("project_name", "프로젝트 이름 없음")),
                "project_description": str(state.get("project_description", "프로젝트 설명 없음")),
                "project_period": str(state.get("project_period", "프로젝트 기간 없음")),
                "retrieved_readme_info": str(state.get("retrieved_readme_info", "README 정보 없음")),
                "docs_daily_reflection": str(state.get("documents_analysis_result", {}).get("daily_reflection", "")),
                "teams_daily_reflection": str(state.get("teams_analysis_result", {}).get("daily_reflection", "")),
                "git_daily_reflection": str(state.get("git_analysis_result", {}).get("daily_reflection", "")),
                "email_daily_reflection": str(state.get("email_analysis_result", {}).get("daily_reflection", "")
)
            }
            
            # 체인 구성 및 실행
            chain = self.prompt | self.llm | self.parser
            
            print("DailyReportGenerator: LLM을 통한 보고서 생성 중...")
            report_result = chain.invoke(prompt_data)
            
            # 성공적인 보고서 생성 결과를 state에 직접 저장
            print(f"DailyReportGenerator: 보고서 생성 완료 - 제목: {report_result.get('report_title', '제목 없음')}")
            
        except Exception as e:
            print(f"DailyReportGenerator: 보고서 생성 중 오류 발생: {e}")
            state["comprehensive_report"] = {
                "error": "보고서 생성 실패",
                "message": str(e)
            }
            
            # 에러를 state의 error_message에도 추가
            current_error = state.get("error_message", "")
            state["error_message"] = (current_error + f"\n DailyReportGenerator 오류: {e}").strip()
        
        return {"comprehensive_report": report_result}

    def __call__(self, state: LangGraphState) -> LangGraphState:
        """
        다른 analyzer들과 동일한 호출 패턴 지원
        """
        return self.generate_daily_report(state)