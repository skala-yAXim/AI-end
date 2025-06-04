"""
이메일-WBS 업무 분석기
============================
작성자: 김용준
기능: 이메일 데이터 분석 및 WBS 업무 매칭

업데이트 내역 :
작성자 : 노건표
작성일 : 2025-06-04
작성내용 : 코드 리팩토링 및 vectorDB 연결 및 전처리 추가.
"""
# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from openai import OpenAI

# from core.utils import Settings
# from preprocessing.email_data_preprocessor import EmailDataPreprocessor
# from git_analysis_service.wbs_data_handler import WBSDataHandler

PROMPT_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompts", "email_analyze_prompt.md"))

class EmailAnalyzerAgent:
    def __init__(self, settings, wbs_data_handler, email_data_preprocessor):
        self.settings = settings
        self.wbs_data_handler = wbs_data_handler
        self.email_data_preprocessor = email_data_preprocessor
        self.llm_client = OpenAI(api_key=self.settings.OPENAI_API_KEY)

        if not os.path.exists(PROMPT_FILE_PATH):
            print(f"Warning: Prompt file {PROMPT_FILE_PATH} not found. Please ensure it exists.")

    def _prepare_email_data_for_llm_prompt(self, processed_emails: List[Dict], target_date_str: Optional[str]) -> str:
        """필터링 및 처리된 이메일 데이터를 LLM 프롬프트용 문자열로 포맷합니다."""
        date_info = f"({target_date_str} 기준)" if target_date_str else "(최근 활동 기준)"
        prompt_parts = [f"### 이메일 데이터 {date_info}:"] # 프롬프트와 일치하도록 수정

        if not processed_emails:
            prompt_parts.append(f"\n{date_info}에 해당하는 이메일 내역이 없습니다.")
            return "\n".join(prompt_parts)

        email_data_json_str = json.dumps(processed_emails, ensure_ascii=False, indent=2)
        prompt_parts.append(email_data_json_str)
        
        return "\n".join(prompt_parts)

    def analyze(
        self,
        email_data_json_path: str, 
        author_email_for_analysis: str,
        wbs_assignee_name: str, 
        project_id_for_wbs: str,
        target_date_str: Optional[str] = None 
    ) -> Optional[Dict[str, Any]]:
        print(f"\n--- Email Analyzer Agent Invoked ---")
        print(f"Analysis for User Email: {author_email_for_analysis}, WBS Assignee: {wbs_assignee_name}, Target Date: {target_date_str or 'All Recent'}")

        current_state = {
            "email_data_json_path": email_data_json_path,
            "author_email_for_analysis": author_email_for_analysis,
            "target_date_str": target_date_str,
            "project_id_for_wbs": project_id_for_wbs,
            "wbs_assignee_name": wbs_assignee_name
        }

        current_state = self.email_data_preprocessor(current_state)
        if current_state.get("email_preprocessing_status") != "success":
            print(f"Email data preprocessing failed: {current_state.get('email_preprocessing_error_message')}")
            return None
        processed_email_events_for_llm = current_state.get("processed_email_events_for_llm", [])

        current_state = self.wbs_data_handler(current_state)
        if current_state.get("wbs_handling_status") != "success":
            print(f"WBS data handling failed: {current_state.get('wbs_handling_error_message')}")
        wbs_tasks_str_for_llm = current_state.get("wbs_tasks_str_for_llm", "WBS 정보를 가져오는 데 실패했습니다.")
        
        email_info_str_for_llm = json.dumps(processed_email_events_for_llm, ensure_ascii=False, indent=2)

        current_time_iso = datetime.now(timezone.utc).isoformat()

        try:
            with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
        except FileNotFoundError:
            print(f"Error: Prompt file not found at {PROMPT_FILE_PATH}.")
            return None
        
        # 프롬프트 포맷팅 시 target_user, target_date, email_data, wbs_data 사용
        prompt = prompt_template.format(
            target_user=author_email_for_analysis, # 프롬프트의 {target_user}와 매칭
            target_date=target_date_str if target_date_str else "전체 최근 활동", # 프롬프트의 {target_date}와 매칭
            email_data=email_info_str_for_llm, # 프롬프트의 {email_data}와 매칭 (JSON 문자열)
            wbs_data=wbs_tasks_str_for_llm, # 프롬프트의 {wbs_data}와 매칭 (이미 문자열)
        )

        print("\n--- Sending prompt to LLM for Email Analysis ---")
        # print(prompt) 
        print("--- End of prompt ---")

        try:
            response = self.llm_client.chat.completions.create(
                model=self.settings.OPENAI_MODEL_NAME,
                messages=[
                    # 시스템 메시지는 프롬프트 파일 자체에 포함시키는 것이 더 일반적일 수 있음
                    # 여기서는 프롬프트 파일이 사용자 지시사항에 집중한다고 가정
                    {"role": "system", "content": "당신은 특정 개인의 이메일 데이터를 분석하여 WBS 업무와 매칭하고 실제 업무 진행 상황을 파악하는 전문가입니다. 주어진 프롬프트를 정확히 따라 JSON 형식으로 응답하세요."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            
            llm_output_content = response.choices[0].message.content
            if llm_output_content:
                analysis_result = json.loads(llm_output_content)
                print("\n--- LLM Email Analysis Result (JSON from LLM) ---")
                print(json.dumps(analysis_result, indent=2, ensure_ascii=False))
                
                if not all(key in analysis_result for key in ["user_id", "date", "type", "matched_tasks", "unmatched_tasks"]):
                    print("Warning: LLM output for email analysis might not fully match the requested JSON structure from the prompt.")
                
                # 만약 LLM이 user_id 등을 채우지 않았다면 여기서 보충
                analysis_result.setdefault("user_id", author_email_for_analysis) # 프롬프트에서 이미 target_user로 전달
                analysis_result.setdefault("date", current_time_iso) # 프롬프트에서 현재 시간을 직접 넣도록 유도 가능
                analysis_result.setdefault("type", "Email")

                return analysis_result
            else:
                print("Error: LLM returned empty content for email analysis.")
                return None

        except json.JSONDecodeError as je:
            print(f"Error decoding LLM JSON response for email analysis: {je}")
            print(f"LLM Raw Output (first 500 chars):\n{llm_output_content[:500] if llm_output_content else 'No content'}") 
            return None
        except Exception as e:
            print(f"Error during LLM interaction for email analysis: {e}")
            return None
