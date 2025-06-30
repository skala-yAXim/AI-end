import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool

from pydantic.v1 import BaseModel

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

        
        # --- Agent 및 Prompt 설정 ---
        prompt_path = os.path.join(config.PROMPTS_BASE_DIR, "daily_report_prompt.md")
        template = open(prompt_path, "r", encoding="utf-8").read()
        agent_prompt = PromptTemplate.from_template(template)

        agent = create_tool_calling_agent(
            llm=self.llm,
            tools=[wbs_retrieve_tool],
            prompt=agent_prompt
        )

        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=[wbs_retrieve_tool],
            verbose=True, # Agent의 작동 과정을 로그로 확인하려면 True로 설정
            max_iterations=1,
            # early_stopping_method="generate"
            # handle_parsing_errors=True # LLM의 출력 파싱 오류 발생 시 대처
        )

    def generate_daily_report(self, state: LangGraphState) -> LangGraphState:
        """
        Agent를 호출하여 일일 보고서를 생성하고 LangGraph 상태를 업데이트합니다.
        """
        print(f"DailyReportGenerator: {state.get('user_name')} 님의 보고서 생성을 시작합니다 (Agent 방식).")
    
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

        # Agent에게 전달할 입력 데이터를 구성합니다.
        # 이전 코드의 'first_data'와 동일한 정보를 포함합니다.
        agent_input_data = {
            "user_name": state.get("user_name"),
            "user_id": state.get("user_id"),
            "target_date": state.get("target_date", datetime.now().strftime("%Y-%m-%d")),
            "projects": str(state.get("projects", [])),
            "wbs_data": state.get("wbs_data", []), # 전체 WBS 데이터도 컨텍스트로 제공
            "docs_analysis": str(filtered_results.get("documents_analysis_result") or "Docs 결과 없음"),
            "teams_analysis": str(filtered_results.get("teams_analysis_result") or "Teams 결과 없음"),
            "git_analysis": str(filtered_results.get("git_analysis_result") or "Git 결과 없음"),
            "email_analysis": str(filtered_results.get("email_analysis_result") or "Email 결과 없음"),
            "retrieved_readme_info": state.get("retrieved_readme_info", ""),
            "docs_daily_reflection": state.get("documents_analysis_result", {}).get("daily_reflection", ""),
            "teams_daily_reflection": state.get("teams_analysis_result", {}).get("daily_reflection", ""),
            "git_daily_reflection": state.get("git_analysis_result", {}).get("daily_reflection", ""),
            "email_daily_reflection": state.get("email_analysis_result", {}).get("daily_reflection", ""),
        }

        print("DailyReportGenerator: Agent 실행 중...")

        result = self.agent_executor.invoke(agent_input_data)

        print("result : ")
        print(result)
        

        print("보고서 결과 : ")
        raw_output = result["output"]
        parsed_result = json.loads(raw_output)

        print(parsed_result)
        
        if not result:
            raise ValueError("Agent가 유효한 보고서를 생성하지 못했습니다.")
        

        state["comprehensive_report"] = parsed_result
        print("DailyReportGenerator: 보고서 생성 완료.")
        return state

    def __call__(self, state: LangGraphState) -> LangGraphState:
        return self.generate_daily_report(state)