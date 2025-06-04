# -*- coding: utf-8 -*-
import json
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from openai import OpenAI

# from core.utils import Settings # 생성자에서 받음
# tools.wbs_retriever_tool은 WBSDataHandler 내부에서 사용됨


PROMPT_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompts", "git_analyze_prompt.md"))

class GitAnalyzerAgent:
    def __init__(self, settings, project_id_for_wbs: str, 
                 git_data_preprocessor, wbs_data_handler): # WBSDataHandler 주입
        """
        GitAnalyzerAgent를 초기화합니다.
        Args:
            settings (Settings): 설정 객체.
            project_id_for_wbs (str): WBS 데이터를 조회할 프로젝트 ID (WBSDataHandler로 전달).
            git_data_preprocessor (GitDataPreprocessor): Git 데이터 전처리 객체.
            wbs_data_handler (WBSDataHandler): WBS 데이터 처리 객체.
        """
        self.settings = settings
        # project_id_for_wbs는 WBSDataHandler가 상태를 통해 받으므로, agent에 직접 저장할 필요는 없을 수 있음
        # 하지만, 다른 용도로 필요하다면 유지 가능
        self.project_id_for_wbs_context = project_id_for_wbs 
        self.git_data_preprocessor = git_data_preprocessor
        self.wbs_data_handler = wbs_data_handler # WBS 핸들러 인스턴스 저장
        self.llm_client = OpenAI(api_key=self.settings.OPENAI_API_KEY)

    # _format_wbs_tasks_for_llm 메소드는 WBSDataHandler로 이동했으므로 여기서 삭제

    def _prepare_git_data_for_llm_prompt(self, git_events: Dict[str, List[Dict]], target_date_str: Optional[str]) -> str:
        """필터링된 Git 데이터를 LLM 프롬프트용 문자열로 포맷합니다. (기존 코드 유지)"""
        date_info = f"({target_date_str} 기준)" if target_date_str else "(최근 활동 기준)"
        prompt_parts = [f"### Git 활동 기록 {date_info}:"]

        if git_events.get("commits"):
            prompt_parts.append("\n**최근 커밋:**")
            for commit in git_events["commits"][:15]: 
                commit_date_obj = datetime.fromisoformat(commit['date'].replace("Z", "+00:00"))
                commit_date_formatted = commit_date_obj.strftime('%Y-%m-%d %H:%M')
                prompt_parts.append(f"- SHA: {commit['sha'][:7]} (작성자: {commit.get('author_email_resolved', 'N/A')}, 날짜: {commit_date_formatted})\n  메시지: {commit['message']}")
        else:
            prompt_parts.append(f"\n**최근 커밋:** {date_info} 내역 없음")

        if git_events.get("pull_requests"):
            prompt_parts.append("\n**관련 Pull Requests:**")
            for pr in git_events["pull_requests"][:10]: 
                pr_date_obj = datetime.fromisoformat(pr['created_at'].replace("Z", "+00:00"))
                pr_date_formatted = pr_date_obj.strftime('%Y-%m-%d %H:%M')
                prompt_parts.append(f"- PR #{pr['number']} (요청자: {pr.get('user_email_resolved', 'N/A')}): {pr['title']} ({pr_date_formatted}, 상태: {pr['state']})")
                if pr.get('content'):
                    pr_content_summary = pr['content'][:200].strip().replace('\r\n', ' ').replace('\n', ' ')
                    prompt_parts.append(f"  내용 요약: {pr_content_summary}...")
        else:
            prompt_parts.append(f"\n**관련 Pull Requests:** {date_info} 내역 없음")
        
        return "\n".join(prompt_parts)

    def analyze(
        self,
        git_data_json_path: str, 
        author_email_for_report: str,
        wbs_assignee_name: str,
        repo_name: str,         
        target_date_str: Optional[str] = None 
    ) -> Optional[Dict[str, Any]]:
        """
        Git 데이터와 WBS 데이터를 분석하여 LLM을 통해 종합적인 리포트를 생성합니다.
        """
        print(f"\n--- Git Analyzer Agent Invoked ---")
        print(f"Report for User ID (Author Email): {author_email_for_report}, WBS Assignee: {wbs_assignee_name}, Repo: {repo_name}, Target Date: {target_date_str or 'All Recent'}")

        # 초기 상태(state) 구성
        current_state = {
            "git_data_json_path": git_data_json_path,
            "author_email_for_report_context": author_email_for_report, # Git 전처리 시 fallback 용도
            "repo_name": repo_name,
            "target_date_str": target_date_str,
            "project_id_for_wbs": self.project_id_for_wbs_context, # WBS 핸들러용
            "wbs_assignee_name": wbs_assignee_name # WBS 핸들러용
        }

        # 1. Git 데이터 전처리 (GitDataPreprocessor 호출)
        current_state = self.git_data_preprocessor(current_state)
        
        if current_state.get("preprocessing_status") != "success":
            error_message = current_state.get("preprocessing_error_message", "Unknown Git preprocessing error")
            print(f"Git data preprocessing failed: {error_message}")
            # 오류 발생 시 분석 중단 또는 부분적 분석 진행 결정 가능
            return None # 여기서는 중단
        
        filtered_git_events = current_state.get("filtered_git_events", {"commits": [], "pull_requests": []})
        if not filtered_git_events or (not filtered_git_events.get("commits") and not filtered_git_events.get("pull_requests")):
            print(f"No Git events found for repo '{repo_name}' and date '{target_date_str}'. Analysis might be limited.")
            # 빈 Git 정보로 계속 진행할 수 있음

        # 2. WBS 데이터 조회 및 포맷팅 (WBSDataHandler 호출)
        current_state = self.wbs_data_handler(current_state)

        if current_state.get("wbs_handling_status") != "success":
            error_message = current_state.get("wbs_handling_error_message", "Unknown WBS data handling error")
            print(f"WBS data handling failed: {error_message}")
            # 오류 발생 시 분석 중단 또는 부분적 분석 진행 결정 가능
            # WBS 정보 없이 Git 정보만으로 분석을 시도할 수도 있음
            # 여기서는 WBS 정보가 없어도 LLM 프롬프트에는 "정보 없음"으로 전달됨
        
        wbs_tasks_str_for_llm = current_state.get("wbs_tasks_str_for_llm", "WBS 정보를 가져오는 데 실패했습니다.")
        
        # 3. LLM 프롬프트 준비
        git_info_str_for_llm = self._prepare_git_data_for_llm_prompt(filtered_git_events, target_date_str)
        current_time_iso = datetime.now(timezone.utc).isoformat()

        try:
            with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
        except FileNotFoundError:
            print(f"Error: Prompt file not found at {PROMPT_FILE_PATH}")
            return None
        
        prompt = prompt_template.format(
            author_email=author_email_for_report, 
            wbs_assignee_name=wbs_assignee_name,
            repo_name=repo_name,
            target_date_str=target_date_str if target_date_str else "전체 최근 활동",
            current_time_iso=current_time_iso,
            git_info_str_for_llm=git_info_str_for_llm,
            wbs_tasks_str_for_llm=wbs_tasks_str_for_llm # WBSDataHandler로부터 받은 포맷된 문자열
        )

        print("\n--- Sending prompt to LLM (details in prompt file) ---")
        # print(prompt) # 디버깅 시 프롬프트 내용 확인
        print("--- End of prompt ---")

        # 4. LLM 호출 및 결과 처리 (기존 코드 유지)
        try:
            response = self.llm_client.chat.completions.create(
                model=self.settings.OPENAI_MODEL_NAME, 
                messages=[
                    {"role": "system", "content": "You are a highly capable AI assistant specialized in analyzing project data and generating reports in a precise JSON format according to the user's instructions."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            
            llm_output_content = response.choices[0].message.content
            if llm_output_content:
                analysis_result = json.loads(llm_output_content)
                print("\n--- LLM Analysis Result (JSON from LLM) ---")
                print(json.dumps(analysis_result, indent=2, ensure_ascii=False))
                
                if not isinstance(analysis_result, dict) or not all(key in analysis_result for key in ["summary", "matched_tasks", "unmatched_tasks", "unassigned_git_activities"]):
                    print("Warning: LLM output might not fully match the requested JSON structure from the prompt's instructions.")
                
                return analysis_result
            else:
                print("Error: LLM returned empty content.")
                return None

        except json.JSONDecodeError as je:
            print(f"Error decoding LLM JSON response: {je}")
            print(f"LLM Raw Output (first 500 chars):\n{llm_output_content[:500] if llm_output_content else 'No content'}") 
            return None
        except Exception as e:
            print(f"Error during LLM interaction: {e}")
            return None
