import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.agents import AgentExecutor
from langchain.tools import tool
from langchain.agents import create_openai_functions_agent

from core import config
from ai.graphs.state_definition import LangGraphState
from ai.tools.wbs_data_retriever import WBSDataRetriever
from pydantic import BaseModel
from typing import Any

class DailyReportGenerator:
    """
    LangGraph 워크플로우용 일일 보고서 생성기
    - Agent를 사용하여 단일 프로세스로 활동 내역을 분석하고 WBS Task와 매핑하여 최종 보고서를 생성합니다.
    """
    def __init__(self, wbs_retriever_tool_instance: WBSDataRetriever = None):
        # LLM 설정
        self.llm = ChatOpenAI(
            model=config.DEFAULT_MODEL,
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
                "user_name", "user_id", "target_date", "wbs_data",
                "docs_analysis", "teams_analysis", "git_analysis", "email_analysis", 
                "projects", "docs_daily_reflection", "teams_daily_reflection", 
                "git_daily_reflection", "email_daily_reflection"
            ]
        )
        self.parser = JsonOutputParser()

        # WBS Retriever Tool 인스턴스 및 Tool 정의
        retriever = wbs_retriever_tool_instance

        @tool
        def wbs_retrieve_tool(query_text: str, project_ids: List[int], limit: int = 5) -> Optional[Dict[str, Any]]:
            """
            사용자 활동 내용(query_text)과 관련된 프로젝트 ID(project_ids)를 기반으로 
            WBS(Task) 정보를 검색하는 도구입니다.
            """
            raw_results = retriever.retrieve_relevant_wbs_data_hybrid(
                query_text=query_text,
                project_ids=project_ids,
                limit=limit
            )

            parsed_results = []
            for item in raw_results:
                try:
                    original = json.loads(item.get("original_data", "{}"))
                    parsed_results.append({
                        "task_id": item.get("task_id"),
                        "task_name": original.get("task_name"),
                        "assignee": original.get("assignee"),
                        "start_date": (original.get("start_date") or ""),
                        "end_date": (original.get("end_date") or ""),
                        "project_id": item.get("project_id")
                    })
                except json.JSONDecodeError:
                    continue  # JSON 파싱 실패한 항목은 건너뜀

            return {
                "summary": f"총 {len(parsed_results)}개의 WBS 작업이 검색되었습니다.",
                "tasks": parsed_results
            }

    def generate_daily_report(self, state: LangGraphState) -> LangGraphState:
        """
        Agent를 호출하여 일일 보고서를 생성하고 LangGraph 상태를 업데이트합니다.
        """
        print(f"DailyReportGenerator: {state.get('user_name')} 님의 보고서 생성을 시작합니다.")
    
        exclude_key = "daily_reflection"
        target_keys = [
            "documents_analysis_result",
            "git_analysis_result",
            "teams_analysis_result",
            "email_analysis_result"
        ]

        filtered_results = {}

        for key in target_keys:
            analysis_result = state.get(key)
            if analysis_result:
                filtered_results[key] = {k: v for k, v in analysis_result.items() if k != exclude_key}
            else:
                filtered_results[key] = {}
        
        try:
            # state에서 직접 데이터 추출
            input_data = {
                "user_name": state.get("user_name"),
                "user_id": state.get("user_id"),
                "target_date": state.get("target_date", datetime.now().strftime("%Y-%m-%d")),
                "projects": str(state.get("projects", [])),
                "wbs_data": state.get("wbs_data", []), # 전체 WBS 데이터도 컨텍스트로 제공
                "docs_analysis": str(filtered_results.get("documents_analysis_result") or "Docs 결과 없음"),
                "teams_analysis": str(filtered_results.get("teams_analysis_result") or "Teams 결과 없음"),
                "git_analysis": str(filtered_results.get("git_analysis_result") or "Git 결과 없음"),
                "email_analysis": str(filtered_results.get("email_analysis_result") or "Email 결과 없음"),
                "docs_daily_reflection": state.get("documents_analysis_result", {}).get("daily_reflection", ""),
                "teams_daily_reflection": state.get("teams_analysis_result", {}).get("daily_reflection", ""),
                "git_daily_reflection": state.get("git_analysis_result", {}).get("daily_reflection", ""),
                "email_daily_reflection": state.get("email_analysis_result", {}).get("daily_reflection", ""),
            }
            
            # 체인 구성 및 실행
            chain = self.prompt | self.llm | self.parser
            
            print("DailyReportGenerator: LLM을 통한 보고서 생성 중...")
            report_result = chain.invoke(input_data)
            
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
        return self.generate_daily_report(state)