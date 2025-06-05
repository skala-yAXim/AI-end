from typing import Dict, Optional, List
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import AIMessage
from langchain_core.output_parsers import JsonOutputParser

import os
import json
from datetime import datetime
from config import DEFAULT_MODEL, FAST_MODEL, PROMPTS_DIR

class State(Dict):
    user_id: Optional[str]
    user_name: Optional[str]
    target_date: Optional[str]
    wbs_data: Optional[Dict]
    docs_analysis_result: Optional[Dict]
    teams_analysis_result: Optional[Dict]  
    git_analysis_result: Optional[Dict]
    email_analysis_result: Optional[Dict]
    final_report: Optional[Dict]

class DailyReportGenerator:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=DEFAULT_MODEL,  # gpt-4o 사용 (더 긴 컨텍스트 지원)
            temperature=0.2
        )
        
        # 프롬프트 템플릿 로드
        with open(os.path.join(PROMPTS_DIR, "daily_report_prompt.md"), "r", encoding="utf-8") as f:
            prompt_content = f.read()
        
        # JSON 구조의 중괄호를 LangChain 변수와 구분하기 위해 이스케이프 처리
        self.prompt_template = self._escape_json_braces(prompt_content)
        
        self.prompt = PromptTemplate(
            template=self.prompt_template,
            input_variables=[
                "user_name", "user_id", "target_date",
                "wbs_data", "docs_analysis", "teams_analysis", 
                "git_analysis", "email_analysis"
            ]
        )
        self.parser = JsonOutputParser()

    def _escape_json_braces(self, content: str) -> str:
        """
JSON 구조의 중괄호를 LangChain 변수와 구분하기 위해 이스케이프 처리
        """
        # LangChain 변수들을 임시 플레이스홀더로 교체
        variables = [
            "{user_name}", "{user_id}", "{target_date}", "{wbs_data}", 
            "{docs_analysis}", "{teams_analysis}", "{git_analysis}", "{email_analysis}"
        ]
        
        placeholders = {}
        for i, var in enumerate(variables):
            placeholder = f"__PLACEHOLDER_{i}__"
            placeholders[placeholder] = var
            content = content.replace(var, placeholder)
        
        # 모든 중괄호를 이스케이프 처리
        content = content.replace("{", "{{").replace("}", "}}")
        
        # 플레이스홀더를 다시 원래 변수로 교체
        for placeholder, var in placeholders.items():
            content = content.replace(placeholder, var)
        
        return content

    def generate_daily_report(self, state: State) -> Dict:
        """Daily 보고서 생성"""

        prompt_data = {
            "user_name": state.get("user_name"),
            "user_id": state.get("user_id"),
            "target_date": state.get("target_date"),
            "wbs_data": str(state.get("wbs_data")),
            "docs_analysis": str(state.get("docs_analysis_result", {})),
            "teams_analysis": str(state.get("teams_analysis_result", {})),
            "git_analysis": str(state.get("git_analysis_result", "{}")),
            "email_analysis": str(state.get("email_analysis_result", "{}"))
            }
        
        # 체인 구성 및 실행
        chain = self.prompt | self.llm | self.parser
        
        # 보고서 생성
        report_result = chain.invoke(prompt_data)
        
        return {
            "final_report": {
                "json_content": json.dumps(report_result, ensure_ascii=False, indent=2),
                "parsed_content": report_result
            },
            "success": True,
            "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
