# agents/git_analyzer.py
import os
import sys
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import config
from core.state_definition import LangGraphState
from tools.vector_db_retriever import retrieve_git_activities

class GitAnalyzerAgent:
    def __init__(self, qdrant_client: QdrantClient):
        self.qdrant_client = qdrant_client
        
        self.llm_client = ChatOpenAI(
            model=config.DEFAULT_MODEL, temperature=0.1,
            openai_api_key=config.OPENAI_API_KEY, max_tokens=2500
        )
        # self.wbs_data_handler 제거

        prompt_file_path = os.path.join(config.PROMPTS_BASE_DIR, "git_analyze_prompt.md")
        try:
            with open(prompt_file_path, 'r', encoding='utf-8') as f: 
                prompt_template_str = f.read()
            # 예상 프롬프트 변수: {author_identifier}, {wbs_assignee_name}, {target_date_str}, {git_info_str_for_llm}, {wbs_tasks_str_for_llm}
            self.prompt = PromptTemplate.from_template(prompt_template_str)
        except FileNotFoundError:
            print(f"GitAnalyzerAgent: 오류 - 프롬프트 파일을 찾을 수 없습니다: {prompt_file_path}")
            self.prompt_template_str = """
사용자 식별자 {author_identifier} (WBS 담당자명: {wbs_assignee_name})의 모든 레포지토리에 대한 Git 활동({git_info_str_for_llm})을 {target_date_str} 기준으로 분석하고, 
관련 WBS 작업({wbs_tasks_str_for_llm})과의 연관성을 파악하여 JSON 형식으로 상세 리포트를 작성해주세요. 
리포트에는 주요 활동 요약, WBS 매칭된 작업, 매칭되지 않은 작업, 할당되지 않은 Git 활동 목록을 포함해야 합니다.
"""
            self.prompt = PromptTemplate.from_template(self.prompt_template_str)
        
        self.parser = JsonOutputParser()

    def _prepare_git_data_for_llm(self, retrieved_git_activities: List[Dict], target_date_str: Optional[str]) -> str:
        date_info = f"({target_date_str} 기준)" if target_date_str else "(최근 활동 기준)"
        display_count = min(len(retrieved_git_activities), 30)  # 최대 30건만 출력

        parts = [f"### 전체 Git 활동 요약 {date_info} (최대 {display_count}건):"]

        if display_count == 0:
            parts.append("활동 내역이 없습니다.")
            return "\n".join(parts)

        for item in retrieved_git_activities[:display_count]:
            meta = item.get("metadata", {})
            repo = meta.get("repo_name", "N/A")
            sha_or_id = meta.get("sha", meta.get("id", "N/A"))[:7]
            author = meta.get("author", "N/A")
            event_date = meta.get("date", "N/A")
            event_type = meta.get("type", "N/A")
            message = item.get("page_content", meta.get("message", "N/A"))[:300]

            parts.append(f"- [{event_type}] 레포: {repo}, ID: {sha_or_id} (작성자: {author}, 날짜: {event_date})")
            parts.append(f"  메시지: {message}")

        return "\n".join(parts)


    def _analyze_git_internal(
    self, 
    git_author_id: str,  # Git 분석에 사용된 실제 ID (github_email or user_id)
    wbs_user_name: Optional[str],  # WBS 컨텍스트 및 LLM 프롬프트용 user_name
    wbs_data: Optional[Dict], 
    target_date: str, 
    retrieved_activities: List[Dict]  # 단일 List로 처리됨
    ) -> Dict[str, Any]:
        total_count = len(retrieved_activities)
        print(f"GitAnalyzerAgent: 사용자 식별자 '{git_author_id}' Git 활동 분석. 총 {total_count}건 (대상일: {target_date}).")
        
        if total_count == 0:
            print(f"GitAnalyzerAgent: 사용자 식별자 '{git_author_id}'에 대한 분석할 Git 활동이 없습니다 (대상일: {target_date}).")
            return {
                "summary": "분석할 관련 Git 활동을 찾지 못했습니다.",
                "matched_tasks": [],
                "unmatched_tasks": [],
                "unassigned_git_activities": [],
                "error": "No Git activities to analyze"
            }

        wbs_data_str = json.dumps(wbs_data, ensure_ascii=False, indent=2) if wbs_data else "WBS 정보 없음"
        git_data_str = self._prepare_git_data_for_llm(retrieved_activities, target_date)

        chain = self.prompt | self.llm_client | self.parser

        try:
            llm_input = {
                "author_email": git_author_id,
                "wbs_assignee_name": wbs_user_name,
                "target_date_str": target_date,
                "git_info_str_for_llm": git_data_str,
                "wbs_tasks_str_for_llm": wbs_data_str
            }
            analysis_result = chain.invoke(llm_input)
            return analysis_result
        except Exception as e:
            print(f"GitAnalyzerAgent: LLM Git 분석 중 오류: {e}")
            return {"summary": "Git 활동 분석 중 오류 발생", "error": str(e)}

    def analyze_git(self, state: LangGraphState) -> LangGraphState:
        git_identifier = state.get("github_email", state.get("user_id"))
        print(f"GitAnalyzerAgent: 사용자 식별자 '{git_identifier}' Git 활동 분석 시작 (날짜: {state.get('target_date')})...")
        
        user_name_for_context = state.get("user_name")
        target_date = state.get("target_date")
        wbs_data = state.get("wbs_data")

        analysis_result = {} # 기본값 초기화
        if not git_identifier:
            error_msg = "Git 분석용 식별자(github_email/user_id) 누락"; print(f"GitAnalyzerAgent: {error_msg}")
            analysis_result = {"error": error_msg, "summary": "사용자 식별자 누락"}
        elif not target_date: # Git 활동은 날짜 필터링 필수
            error_msg = "GitAnalyzerAgent: target_date가 State에 제공되지 않아 분석을 건너뜁니다."
            print(error_msg)
            analysis_result = {"error": error_msg, "summary": "대상 날짜 누락"}
        else:
            retrieved_dict = retrieve_git_activities(
                qdrant_client=self.qdrant_client, 
                git_author_identifier=git_identifier, 
                target_date_str=target_date
                # scroll_limit은 retriever 내부 기본값 사용 또는 여기서 지정
            )

            state["retrieved_git_activities"] = retrieved_dict # 필요시 저장

            analysis_result = self._analyze_git_internal(
                git_identifier, user_name_for_context, wbs_data, target_date, retrieved_dict
            )
        
        state["git_analysis_result"] = analysis_result
        return state

    def __call__(self, state: LangGraphState) -> LangGraphState:
        return self.analyze_git(state)
