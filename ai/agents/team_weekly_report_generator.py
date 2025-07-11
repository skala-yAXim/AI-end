import os
import json

# LangChain 및 OpenAI 관련 라이브러리 임포트
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from ai.graphs.state_definition import TeamWeeklyLangGraphState
from core import config

class TeamWeeklyReportGenerator:
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
        
        self.reports_input_dir = os.path.join(config.PROJECT_ROOT_DIR, "outputs", "weekly_reports")
        
        # 주간 보고서 프롬프트 템플릿 파일 경로 설정
        prompt_file_path = os.path.join(config.PROMPTS_BASE_DIR, "team_weekly_report_prompt.md")
        
        # 프롬프트 템플릿 파일 로드
        try:
            with open(prompt_file_path, "r", encoding="utf-8") as f:
                prompt_template_str = f.read()
        except FileNotFoundError:
            print(f"오류: 프롬프트 파일을 찾을 수 없습니다. 경로: {prompt_file_path}")
            # 프롬프트 파일이 없으면 실행이 불가능하므로 예외 발생
            raise
            
        self.prompt = PromptTemplate.from_template(prompt_template_str)
        self.parser = JsonOutputParser()

    def load_weekly_reports(self, state: TeamWeeklyLangGraphState) -> TeamWeeklyLangGraphState:
        """
        모든 팀 멤버의 주간 보고서를 로드합니다.
        파일명 형식: weekly_report_{user_name}_{start_date}_to_{end_date}.json
        """
        start_date_str = state.get("start_date")
        end_date_str = state.get("end_date")
        team_members = state.get("team_members")

        weekly_reports = []

        for user_name in team_members:
            file_name = f"weekly_report_{user_name}_{start_date_str}_to_{end_date_str}.json"
            file_path = os.path.join(self.reports_input_dir, file_name)

            print(f"파일 경로: {file_path}")

            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        report_data = json.load(f)
                        weekly_reports.append({
                            "user_name": user_name,
                            "report": report_data
                        })
                        print(f"성공적으로 파일을 로드했습니다: {file_name}")
                except json.JSONDecodeError:
                    print(f"경고: JSON 파싱 오류가 발생했습니다: {file_name}")
                except Exception as e:
                    print(f"경고: 파일을 읽는 중 오류가 발생했습니다: {file_name}, 오류: {e}")
            else:
                print(f"정보: 해당 파일이 존재하지 않습니다: {file_name}")

        state["weekly_reports_data"] = weekly_reports
        return state


    def generate_team_weekly_report(self, state: TeamWeeklyLangGraphState) -> TeamWeeklyLangGraphState:
        """
        일일 보고서 목록을 기반으로 주간 보고서를 생성합니다.
        """
        team_id = state.get("team_id")
        team_name = state.get("team_name")
        team_description = state.get("team_description")
        start_date = state.get("start_date")
        end_date = state.get("end_date")
        team_members = state.get("team_members")
        wbs_data = state.get("wbs_data")
        weekly_reports = state.get("weekly_reports_data")
        projects = state.get("projects")
        weekly_input_template = state.get("weekly_input_template")

        print(f"WeeklyReportGenerator: 사용자 '{team_name}' ({team_id})의 {start_date} ~ {end_date} 주간 보고서 생성 시작...")
        
        if not weekly_reports:
            print("TeamWeeklyReportGenerator: 분석할 개인 주간 보고서가 없습니다. 생성을 중단합니다.")
            return {
                "error": "보고서 생성 실패",
                "message": "분석할 개인 주간 보고서 데이터가 없습니다."
            }
            
        try:
            # LLM에 전달할 프롬프트 데이터 구성
            prompt_data = {
                "team_id": team_id,
                "team_name": team_name,
                "team_description": team_description,
                "team_members": team_members,
                "start_date": start_date,
                "end_date": end_date,
                # 주간 보고서 목록을 JSON 문자열로 변환하여 전달
                "weekly_reports": json.dumps(weekly_reports, ensure_ascii=False, indent=2),
                "wbs_data": json.dumps(wbs_data, ensure_ascii=False, indent=2),
                "projects": projects,
                "weekly_input_template": weekly_input_template,
            }
            
            # LangChain 체인 구성 및 실행
            chain = self.prompt | self.llm | self.parser
            
            print("TeamWeeklyReportGenerator: LLM을 통한 주간 보고서 생성 중...")
            report_result = chain.invoke(prompt_data)
            
            print(f"TeamWeeklyReportGenerator: 주간 보고서 생성 완료 - 제목: {report_result.get('report_title', '제목 없음')}")
            
            state["team_weekly_report_result"] = report_result
            
            return state
            
        except Exception as e:
            print(f"TeamWeeklyReportGenerator: 주간 보고서 생성 중 오류 발생: {e}")
            return {
                "error": "주간 보고서 생성 실패",
                "message": str(e)
            }