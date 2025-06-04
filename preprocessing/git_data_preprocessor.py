# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

from agents.wbs_analyze_agent.core.vector_db import VectorDBHandler

class GitDataPreprocessor:
    
    def __init__(self, settings):

        self.settings = settings
        self.git_db_handler: Optional[VectorDBHandler] = None

    def _initialize_git_db_handler(self, repo_name: str):
        """특정 리포지토리에 대한 VectorDBHandler를 초기화합니다."""
        safe_repo_name = repo_name.replace("/", "_").replace("-", "_")
        repo_specific_db_base_path = os.path.join(self.settings.VECTOR_DB_PATH_ENV, "git_store")
        os.makedirs(repo_specific_db_base_path, exist_ok=True)

        self.git_db_handler = VectorDBHandler(
            db_base_path=repo_specific_db_base_path,
            collection_name_prefix="git_events",
            project_id=safe_repo_name,
        )
        print(f"Git VectorDB Handler initialized for repo: {repo_name} -> collection: {self.git_db_handler.collection_name} at path: {self.git_db_handler.db_path}")

    def _filter_git_data(
        self,
        git_data_content: Dict,
        author_email_from_json: str,
        repo_name_filter: str,
        target_date_str: Optional[str] = None
    ) -> Dict[str, List[Dict]]:
        """
        로드된 Git 데이터 (commits, pull_requests)를 주어진 조건에 따라 필터링합니다.
        """
        print(f"Filtering Git data (source author from JSON: {author_email_from_json}) for repo: {repo_name_filter}, target date: {target_date_str}")

        target_dt = None
        if target_date_str:
            try:
                target_dt = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            except ValueError:
                print(f"Warning: Invalid target_date format '{target_date_str}'. Expected YYYY-MM-DD. Ignoring date filter.")

        filtered_data = {"commits": [], "pull_requests": []}

        for commit in git_data_content.get("commits", []):
            if commit.get("repo") == repo_name_filter:
                commit_dt = datetime.fromisoformat(commit["date"].replace("Z", "+00:00")).date()
                if not target_dt or commit_dt == target_dt:
                    if "author_email" not in commit or not commit["author_email"]:
                        commit["author_email_resolved"] = author_email_from_json
                    else:
                        commit["author_email_resolved"] = commit["author_email"]
                    filtered_data["commits"].append(commit)

        for pr in git_data_content.get("pull_requests", []):
            if pr.get("repo") == repo_name_filter:
                pr_dt = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00")).date()
                if not target_dt or pr_dt == target_dt:
                    if "user_email" not in pr or not pr["user_email"]:
                        pr["user_email_resolved"] = author_email_from_json
                    else:
                        pr["user_email_resolved"] = pr["user_email"]
                    filtered_data["pull_requests"].append(pr)
        
        print(f"Found {len(filtered_data['commits'])} commits and {len(filtered_data['pull_requests'])} PRs matching criteria for repo '{repo_name_filter}'.")
        return filtered_data

    def _upsert_git_events_to_vector_db(self, git_events: Dict[str, List[Dict]], repo_name: str, author_email_from_json: str):
        """
        필터링된 Git 이벤트를 VectorDB에 임베딩하고 저장(upsert)합니다.
        """
        if not self.git_db_handler:
            print("Error: Git DB Handler not initialized. Cannot upsert data.")
            return

        texts_to_embed = []
        metadatas = []
        ids = []

        for commit in git_events.get("commits", []):
            texts_to_embed.append(f"Commit: {commit['message']}")
            commit_specific_author = commit.get("author_email_resolved", author_email_from_json)
            metadatas.append({
                "type": "commit",
                "sha": commit["sha"],
                "repo": repo_name,
                "author": commit_specific_author, 
                "date": commit["date"], 
                "message_summary": commit['message'][:100]
            })
            ids.append(f"commit_{commit['sha']}") 

        for pr in git_events.get("pull_requests", []):
            pr_content_for_embedding = f"PR Title: {pr['title']}\nPR Body: {pr.get('content', '')[:500]}"
            texts_to_embed.append(pr_content_for_embedding)
            pr_specific_author = pr.get("user_email_resolved", author_email_from_json)
            metadatas.append({
                "type": "pull_request",
                "number": pr["number"],
                "repo": repo_name,
                "author": pr_specific_author, 
                "date": pr["created_at"], 
                "title": pr["title"],
                "state": pr["state"]
            })
            safe_repo_name_for_id = repo_name.replace('/', '_').replace('-', '_')
            ids.append(f"pr_{safe_repo_name_for_id}_{pr['number']}")

        if texts_to_embed:
            try:
                print(f"Upserting {len(texts_to_embed)} Git events to VectorDB collection: {self.git_db_handler.collection_name}")
                self.git_db_handler.add_texts_with_metadata(texts=texts_to_embed, metadatas=metadatas, ids=ids)
                print("Git events successfully upserted/updated in VectorDB.")
            except Exception as e:
                print(f"Error upserting Git events to VectorDB: {e}")
        else:
            print(f"No new Git events to upsert to VectorDB for repo '{repo_name}' with the given filters.")

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        필요한 상태 값:
            - repo_name (str): 처리할 리포지토리의 이름.
            - git_data_json_path (str): Git 데이터 JSON 파일 경로.
            - author_email_for_report_context (str): 보고서 컨텍스트용 작성자 이메일 (fallback).
            - target_date_str (Optional[str]): 특정 날짜 필터 (YYYY-MM-DD).

        업데이트되는 상태 값:
            - filtered_git_events (Dict[str, List[Dict]]): 필터링된 Git 이벤트.
            - preprocessing_status (str): "success" 또는 "error".
            - preprocessing_error_message (Optional[str]): 오류 발생 시 메시지.
        """
        
        repo_name = state.get("repo_name")
        git_data_json_path = state.get("git_data_json_path")
        author_email_for_report_context = state.get("author_email_for_report_context")
        target_date_str = state.get("target_date_str") # Optional

        if not all([repo_name, git_data_json_path, author_email_for_report_context]):
            error_msg = "Missing required parameters in state for GitDataPreprocessor: repo_name, git_data_json_path, author_email_for_report_context must be provided."
            print(f"Error: {error_msg}")
            state["preprocessing_status"] = "error"
            state["preprocessing_error_message"] = error_msg
            state["filtered_git_events"] = {"commits": [], "pull_requests": []}
            return state

        self._initialize_git_db_handler(repo_name)

        try:
            with open(git_data_json_path, 'r', encoding='utf-8') as f:
                git_data_content = json.load(f)
        except FileNotFoundError:
            error_msg = f"Git data file not found at {git_data_json_path}"
            print(f"Error: {error_msg}")
            state["preprocessing_status"] = "error"
            state["preprocessing_error_message"] = error_msg
            state["filtered_git_events"] = {"commits": [], "pull_requests": []}
            return state
        except json.JSONDecodeError:
            error_msg = f"Could not decode JSON from {git_data_json_path}"
            print(f"Error: {error_msg}")
            state["preprocessing_status"] = "error"
            state["preprocessing_error_message"] = error_msg
            state["filtered_git_events"] = {"commits": [], "pull_requests": []}
            return state
        
        author_email_from_git_json = git_data_content.get("author")
        if not author_email_from_git_json:
            print(f"Warning: 'author' field not found in {git_data_json_path}. Using report author context ('{author_email_for_report_context}') as fallback for data processing.")
            author_email_from_git_json = author_email_for_report_context

        filtered_git_events = self._filter_git_data(
            git_data_content=git_data_content,
            author_email_from_json=author_email_from_git_json, 
            repo_name_filter=repo_name,
            target_date_str=target_date_str
        )

        if self.git_db_handler:
             self._upsert_git_events_to_vector_db(
                 git_events=filtered_git_events, 
                 repo_name=repo_name, 
                 author_email_from_json=author_email_from_git_json
            )
        else:
            # 이 경우는 _initialize_git_db_handler에서 문제가 발생하지 않는 한 드뭅니다.
            print("Warning: Git DB Handler was not available for upsert. This might indicate an issue in initialization.")
            
        state["filtered_git_events"] = filtered_git_events
        state["preprocessing_status"] = "success"
        state["preprocessing_error_message"] = None
        print("GitDataPreprocessor __call__ completed successfully.")
        return state
            
    def process_repo_data(
        self, 
        repo_name: str, 
        git_data_json_path: str, 
        author_email_for_report_context: str,
        target_date_str: Optional[str] = None
    ) -> Dict[str, List[Dict]]:
        """
        [기존 메소드 - 필요시 독립 실행 또는 테스트용으로 유지]
        지정된 리포지토리의 Git 데이터를 로드, 필터링하고 VectorDB에 저장한 후, 필터링된 데이터를 반환합니다.
        내부적으로 __call__을 호출하도록 변경하거나, 독립적인 로직을 유지할 수 있습니다.
        여기서는 __call__과 유사한 로직을 유지하되, 상태 객체 대신 직접 파라미터를 사용합니다.
        """
        print("GitDataPreprocessor process_repo_data invoked (standalone mode).")

        self._initialize_git_db_handler(repo_name)

        try:
            with open(git_data_json_path, 'r', encoding='utf-8') as f:
                git_data_content = json.load(f)
        except FileNotFoundError:
            print(f"Error: Git data file not found at {git_data_json_path}")
            return {"commits": [], "pull_requests": []}
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {git_data_json_path}")
            return {"commits": [], "pull_requests": []}
        
        author_email_from_git_json = git_data_content.get("author")
        if not author_email_from_git_json:
            print(f"Warning: 'author' field not found in {git_data_json_path}. Using report author context ('{author_email_for_report_context}') as fallback for data processing.")
            author_email_from_git_json = author_email_for_report_context

        filtered_git_events = self._filter_git_data(
            git_data_content=git_data_content,
            author_email_from_json=author_email_from_git_json, 
            repo_name_filter=repo_name,
            target_date_str=target_date_str
        )

        if self.git_db_handler:
             self._upsert_git_events_to_vector_db(
                 git_events=filtered_git_events, 
                 repo_name=repo_name, 
                 author_email_from_json=author_email_from_git_json
            )
        else:
            print("Skipping Git event upsert to VectorDB as handler is not available (should have been initialized).")
            
        return filtered_git_events
