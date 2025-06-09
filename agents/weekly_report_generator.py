import os
import sys
import json
from typing import Dict, List, Any
from datetime import datetime, timedelta

# LangChain 및 OpenAI 관련 라이브러리 임포트
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# core.config 모듈을 임포트하기 위해 상위 디렉토리 경로 추가
# 이 스크립트가 'agents' 폴더 내에 위치한다고 가정합니다.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
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
        prompt_file_path = os.path.join(config.PROMPTS_BASE_DIR, "weekly_report_prompt.md")
        
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

    def load_daily_reports(self, user_name: str, start_date_str: str, end_date_str: str, reports_dir: str) -> List[Dict[str, Any]]:
        """
        지정된 기간과 사용자에 해당하는 일일 보고서 파일들을 로드합니다.
        
        Args:
            user_name (str): 보고서를 생성할 사용자 이름.
            start_date_str (str): 보고서 시작일 (YYYY-MM-DD).
            end_date_str (str): 보고서 종료일 (YYYY-MM-DD).
            reports_dir (str): 일일 보고서 파일이 저장된 디렉토리 경로.

        Returns:
            List[Dict[str, Any]]: 로드된 일일 보고서 데이터의 리스트.
        """
        daily_reports = []
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            file_name = f"daily_report_{user_name}_{date_str}.json"
            file_path = os.path.join(reports_dir, file_name)
            
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        report_data = json.load(f)
                        daily_reports.append(report_data)
                        print(f"성공적으로 파일을 로드했습니다: {file_name}")
                except json.JSONDecodeError:
                    print(f"경고: JSON 파싱 오류가 발생했습니다: {file_name}")
                except Exception as e:
                    print(f"경고: 파일을 읽는 중 오류가 발생했습니다: {file_name}, 오류: {e}")
            else:
                print(f"정보: 해당 파일이 존재하지 않습니다: {file_name}")

            current_date += timedelta(days=1)
            
        return daily_reports

    def generate_weekly_report(self, user_name: str, user_id: str, start_date: str, end_date: str, daily_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        일일 보고서 목록을 기반으로 주간 보고서를 생성합니다.
        
        Args:
            user_name (str): 사용자 이름.
            user_id (str): 사용자 ID.
            start_date (str): 주간 보고서 시작일.
            end_date (str): 주간 보고서 종료일.
            daily_reports (List[Dict[str, Any]]): 분석할 일일 보고서 데이터 리스트.

        Returns:
            Dict[str, Any]: 생성된 주간 보고서 결과 (JSON 형식).
        """
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
                # 일일 보고서 목록을 JSON 문자열로 변환하여 전달
                "daily_reports": json.dumps(daily_reports, ensure_ascii=False, indent=2)
            }
            
            # LangChain 체인 구성 및 실행
            chain = self.prompt | self.llm | self.parser
            
            print("WeeklyReportGenerator: LLM을 통한 주간 보고서 생성 중...")
            report_result = chain.invoke(prompt_data)
            
            print(f"WeeklyReportGenerator: 주간 보고서 생성 완료 - 제목: {report_result.get('report_title', '제목 없음')}")
            return report_result
            
        except Exception as e:
            print(f"WeeklyReportGenerator: 주간 보고서 생성 중 오류 발생: {e}")
            return {
                "error": "주간 보고서 생성 실패",
                "message": str(e)
            }
