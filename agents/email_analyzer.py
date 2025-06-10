# agents/email_analyzer.py
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
from tools.vector_db_retriever import retrieve_emails

class EmailAnalyzerAgent:
    def __init__(self, qdrant_client: QdrantClient):
        self.qdrant_client = qdrant_client
        
        self.llm_client = ChatOpenAI(
            model=config.DEFAULT_MODEL, temperature=0.1,
            openai_api_key=config.OPENAI_API_KEY, max_tokens=2000
        )
        # self.wbs_data_handler 제거

        prompt_file_path = os.path.join(config.PROMPTS_BASE_DIR, "email_analyze_prompt.md")
        try:
            with open(prompt_file_path, 'r', encoding='utf-8') as f: 
                prompt_template_str = f.read()
            # 예상 프롬프트 변수: {user_id}, {user_name}, {target_date}, {email_data}, {wbs_data}
            self.prompt = PromptTemplate.from_template(prompt_template_str)
        except FileNotFoundError:
            print(f"EmailAnalyzerAgent: 오류 - 프롬프트 파일을 찾을 수 없습니다: {prompt_file_path}")
            self.prompt_template_str = "사용자 ID {user_id} (이름: {user_name})의 {target_date} 이메일 내역({email_data})과 WBS 업무({wbs_data})를 분석하여, 업무 매칭 결과와 진행 상황을 JSON 형식으로 요약해줘."
            self.prompt = PromptTemplate.from_template(self.prompt_template_str)
            
        self.parser = JsonOutputParser()

    def _prepare_email_data_for_llm(self, retrieved_emails_list: List[Dict], target_date_str: Optional[str]) -> str:
        date_info = f"({target_date_str} 기준)" if target_date_str else "(최근 활동 기준)"
        if not retrieved_emails_list: 
            return f"### 이메일 데이터 {date_info}:\n분석할 이메일 내역이 없습니다."
        
        # LLM 컨텍스트 길이 고려하여 최대 30건, 각 메일 내용도 일부만
        parts = [f"### 이메일 데이터 {date_info} (최대 {min(len(retrieved_emails_list), 30)}건 표시):"]
        for item in retrieved_emails_list[:30]: 
            meta = item.get("metadata", {})
            content = item.get("page_content", "")[:300] # 내용 일부
            subject = meta.get("subject", meta.get("title", "제목 없음"))
            from_addr = meta.get("sender", "알 수 없음") # 실제 Qdrant 필드명: sender
            to_addrs_val = meta.get("receiver", meta.get("recipients", [])) # 실제 Qdrant 필드명: receiver 또는 recipients
            to_addrs_str = ", ".join(to_addrs_val) if isinstance(to_addrs_val, list) else str(to_addrs_val)
            timestamp = meta.get("date", "날짜 정보 없음") # 실제 Qdrant 필드명: date
            parts.append(f"- 제목: {subject}\n  발신: {from_addr}\n  수신: {to_addrs_str}\n  날짜: {timestamp}\n  내용 일부: {content}...\n---")
        return "\n".join(parts)

    def _analyze_emails_internal(
        self, 
        user_id: str, 
        user_name: Optional[str],
        wbs_data: Optional[Dict], 
        target_date: str, # target_date는 필수
        retrieved_emails_list: List[Dict]
    ) -> Dict[str, Any]:
        print(f"EmailAnalyzerAgent: 사용자 ID '{user_id}'의 이메일 {len(retrieved_emails_list)}개 분석 시작 (대상일: {target_date}).")

        if not retrieved_emails_list:
            print(f"EmailAnalyzerAgent: 사용자 ID '{user_id}'에 대한 분석할 이메일이 없습니다 (대상일: {target_date}).")
            return {"summary": "분석할 관련 이메일을 찾지 못했습니다.", "matched_tasks": [], "unmatched_tasks": [], "error": "No emails to analyze"}
            
        wbs_data_str = json.dumps(wbs_data, ensure_ascii=False, indent=2) if wbs_data else "WBS 정보 없음"
        email_data_str = self._prepare_email_data_for_llm(retrieved_emails_list, target_date)
        
        chain = self.prompt | self.llm_client | self.parser
        
        try:
            llm_input = {
                "user_id": user_id,
                "target_user": user_name,
                "target_date": target_date,
                "email_data": email_data_str, # 프롬프트의 {email_data} 변수
                "wbs_data": wbs_data_str,     # 프롬프트의 {wbs_data} 변수
                "total_tasks": len(retrieved_emails_list)
            }
            analysis_result = chain.invoke(llm_input)
            return analysis_result # LLM 순수 결과만 반환
        except Exception as e:
            print(f"EmailAnalyzerAgent: LLM 이메일 분석 중 오류: {e}")
            return {"summary": "이메일 분석 중 오류 발생", "error": str(e)}

    def analyze_emails(self, state: LangGraphState) -> LangGraphState:
        print(f"EmailAnalyzerAgent: 사용자 ID '{state.get('user_id')}'의 이메일 분석 시작 (날짜: {state.get('target_date')})...")
        
        user_id = state.get("user_id")
        user_name = state.get("user_name")
        target_date = state.get("target_date")
        wbs_data = state.get("wbs_data")
        
        analysis_result = {} # 기본값 초기화
        if not user_id:
            error_msg = "EmailAnalyzerAgent: user_id가 State에 제공되지 않아 분석을 건너뜁니다."
            print(error_msg)
            analysis_result = {"error": error_msg, "summary": "사용자 ID 누락"}
        elif not target_date: # Emails는 날짜 필터링 필수
            error_msg = "EmailAnalyzerAgent: target_date가 State에 제공되지 않아 분석을 건너뜁니다."
            print(error_msg)
            analysis_result = {"error": error_msg, "summary": "대상 날짜 누락"}
        else:
            retrieved_list = retrieve_emails(
                qdrant_client=self.qdrant_client, 
                user_id=user_id, 
                target_date_str=target_date
            )
            state["retrieved_emails"] = retrieved_list # 필요시 저장

            analysis_result = self._analyze_emails_internal(
                user_id, user_name, wbs_data, target_date, retrieved_list
            )
        
        state["email_analysis_result"] = analysis_result
        return state

    def __call__(self, state: LangGraphState) -> LangGraphState:
        return self.analyze_emails(state)

