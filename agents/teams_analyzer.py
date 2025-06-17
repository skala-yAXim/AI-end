# agents/teams_analyzer.py
import os
import sys
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate

from core import config
from core.state_definition import LangGraphState
from tools.vector_db_retriever import retrieve_teams_posts

class TeamsAnalyzer:
    def __init__(self, qdrant_client: QdrantClient):
        self.qdrant_client = qdrant_client
            
        self.llm = ChatOpenAI(
            model=config.FAST_MODEL, temperature=0.2,
            max_tokens=2000, openai_api_key=config.OPENAI_API_KEY
        )
        # self.wbs_data_handler 제거
        
        prompt_file_path = os.path.join(config.PROMPTS_BASE_DIR, "teams_analyzer_prompt.md")
        try:
            with open(prompt_file_path, "r", encoding="utf-8") as f: 
                prompt_template_str = f.read()
            # 예상 프롬프트 변수: {user_id}, {user_name}, {target_date}, {posts}, {wbs_data}
            self.prompt = PromptTemplate.from_template(prompt_template_str)
        except FileNotFoundError:
            print(f"TeamsAnalyzer: 오류 - 프롬프트 파일을 찾을 수 없습니다: {prompt_file_path}")
            self.prompt_template_str = """
사용자 ID {user_id} (이름: {user_name})의 {target_date} Teams 활동 내역({posts})과 WBS 업무({wbs_data})를 분석하여, 
주요 대화 내용 요약, 업무 관련성, WBS 작업 매칭 결과를 JSON 형식으로 반환해주세요.
"""
            self.prompt = PromptTemplate.from_template(self.prompt_template_str)
            
        self.parser = JsonOutputParser()

    def _prepare_teams_posts_for_llm(self, retrieved_posts_list: List[Dict], target_date_str: Optional[str]) -> str:
        date_info = f"({target_date_str} 기준)" if target_date_str else "(최근 활동 기준)"
        if not retrieved_posts_list: 
            return f"### Teams 게시물 데이터 {date_info}:\n분석할 Teams 게시물이 없습니다."
        
        # LLM 컨텍스트 길이 고려하여 최대 30건, 각 게시물 내용도 일부만
        parts = [f"### Teams 게시물 데이터 {date_info} (최대 {min(len(retrieved_posts_list), 30)}건 표시):"]
        for item in retrieved_posts_list[:30]: 
            meta = item.get("metadata", {})
            content = item.get("page_content", "")[:500] # 내용 일부
            # 실제 Teams 작성자 ID 필드명 (예: user_id, author_id 등)
            author_display = meta.get("user_id", meta.get("author_name", meta.get("author_id", "익명"))) 
            timestamp = meta.get("date", "시간 정보 없음") # 실제 Qdrant 필드명: date
            channel = meta.get("channel_name", meta.get("channel", "알 수 없는 채널"))
            parts.append(f"- 작성자: {author_display}\n  채널: {channel}\n  시간: {timestamp}\n  내용: {content}...\n---")
        return "\n".join(parts)

    def _analyze_teams_data_internal(
            self, 
            user_id: str, # Teams 분석 대상 user_id
            user_name: Optional[str], # LLM 프롬프트용 user_name 
            target_date: str, # target_date는 필수
            wbs_data: Optional[dict],
            project_name: Optional[str],
            project_description: Optional[str],
            project_period: Optional[str],
            retrieved_posts_list: List[Dict]
        ) -> Dict[str, Any]:
        print(f"TeamsAnalyzer: 사용자 ID '{user_id}'의 Teams 게시물 {len(retrieved_posts_list)}개 분석 시작 (대상일: {target_date}).")

        if not retrieved_posts_list:
            print(f"TeamsAnalyzer: 사용자 ID '{user_id}'에 대한 분석할 Teams 게시물이 없습니다 (대상일: {target_date}).")
            return {
                "user_id": user_id,
                "date": target_date,
                "type": "Teams",
                "total_tasks": 0,
                "teams_analysis": {
                    "matched_tasks": [],
                    "unmatched_tasks": [],
                    "daily_reflection": {
                        "title": "🔍 오늘의 회고 및 개선점",
                        "content": "분석할 Teams 게시물이 없어 업무 현황을 파악할 수 없습니다."
                    }
                },
                "error": "No Teams posts to analyze"
            }

        wbs_data_str = json.dumps(wbs_data, ensure_ascii=False, indent=2) if wbs_data else "WBS 정보 없음"
        posts_data_str = self._prepare_teams_posts_for_llm(retrieved_posts_list, target_date)

        chain = self.prompt | self.llm | self.parser
        
        try:
            llm_input = {
                "user_id": user_id,
                "user_name": user_name or user_id,
                "target_date": target_date,
                "posts": posts_data_str, # 프롬프트의 {posts} 변수
                "wbs_data": wbs_data_str, # 프롬프트의 {wbs_data} 변수
                "project_name": project_name,
                "project_description": project_description,
                "project_period": project_period
            }
            result = chain.invoke(llm_input)
            return result # LLM 순수 결과만 반환
        except Exception as e:
            print(f"TeamsAnalyzer: LLM Teams 분석 중 오류: {e}")
            return {"summary": "Teams 활동 분석 중 오류 발생", "error": str(e)}

    def analyze_teams(self, state: LangGraphState) -> LangGraphState:
        print(f"TeamsAnalyzer: 사용자 ID '{state.get('user_id')}' Teams 활동 분석 시작 (날짜: {state.get('target_date')})...")
        
        user_id = state.get("user_id")
        user_name = state.get("user_name")
        target_date = state.get("target_date")
        wbs_data = state.get("wbs_data")
        project_name = state.get("project_name")
        project_description = state.get("project_description")
        project_period = state.get("project_period")

        analysis_result = {} # 기본값 초기화
        if not user_id:
            error_msg = "TeamsAnalyzer: user_id가 State에 제공되지 않아 분석을 건너뜁니다."
            print(error_msg)
            analysis_result = {"error": error_msg, "summary": "사용자 ID 누락"}
        elif not target_date: # Teams는 날짜 필터링 필수
            error_msg = "TeamsAnalyzer: target_date가 State에 제공되지 않아 분석을 건너뜁니다."
            print(error_msg)
            analysis_result = {"error": error_msg, "summary": "대상 날짜 누락"}
        else:
            retrieved_list = retrieve_teams_posts(
                qdrant_client=self.qdrant_client, 
                user_id=user_id, 
                target_date_str=target_date
                # scroll_limit은 retriever 내부 기본값 사용 또는 여기서 지정
            )
            state["retrieved_teams_posts"] = retrieved_list # 필요시 저장

            analysis_result = self._analyze_teams_data_internal(
                user_id, user_name, target_date, wbs_data, project_name, project_description, project_period, retrieved_list
            )
        
        return {"teams_analysis_result": analysis_result}

    def __call__(self, state: LangGraphState) -> LangGraphState:
        return {"teams_analysis_result": self.analyze_teams(state)["teams_analysis_result"]}