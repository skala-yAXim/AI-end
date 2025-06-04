import json
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from openai import OpenAI

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.utils import Settings 
from agents.wbs_analyze_agent.core.vector_db import VectorDBHandler 
from tools.wbs_retriever_tool import get_tasks_by_assignee_tool

PROMPT_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompts", "git_analyze_prompt.md"))

class GitAnalyzerAgent:
    def __init__(self, settings: Settings, project_id_for_wbs: str):
        self.settings = settings
        self.project_id_for_wbs = project_id_for_wbs # Used for WBS queries
        self.llm_client = OpenAI(api_key=self.settings.OPENAI_API_KEY)

        self.git_vector_db_path = os.path.join(self.settings.VECTOR_DB_PATH_ENV, "git_store")
        os.makedirs(self.git_vector_db_path, exist_ok=True)

        self.git_db_handler = None

    def _initialize_git_db_handler(self, repo_name: str):
        """Initializes VectorDBHandler for a specific repository."""
        safe_repo_name = repo_name.replace("/", "_").replace("-", "_") # Make repo name fs-friendly
        self.git_db_handler = VectorDBHandler(
            db_base_path=self.git_vector_db_path,
            collection_name_prefix="git_events", # Generic prefix
            project_id=safe_repo_name, # Using repo name as project_id for this DB
            embedding_api_key=self.settings.OPENAI_API_KEY
        )
        print(f"Git VectorDB Handler initialized for repo: {repo_name} -> collection: {self.git_db_handler.collection_name}")


    def _load_and_filter_git_data(
        self,
        git_data_content: Dict,
        author_email: str, # This is the author from the git_data.json file's top level
        repo_name_filter: str,
        target_date_str: Optional[str] = None
    ) -> Dict[str, List[Dict]]:
        print(f"Filtering Git data (source author: {author_email}) for repo: {repo_name_filter}, target date: {target_date_str}")

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
                    filtered_data["commits"].append(commit)

        for pr in git_data_content.get("pull_requests", []):
            if pr.get("repo") == repo_name_filter:
                pr_dt = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00")).date()
                if not target_dt or pr_dt == target_dt:
                    filtered_data["pull_requests"].append(pr)
        
        print(f"Found {len(filtered_data['commits'])} commits and {len(filtered_data['pull_requests'])} PRs matching criteria.")
        return filtered_data

    def _upsert_git_events_to_vector_db(self, git_events: Dict[str, List[Dict]], repo_name: str, author_email_from_file: str):
        """
        Embeds and stores git event texts (commit messages, PR titles/bodies) into the VectorDB.
        Uses upsert logic by relying on unique IDs. author_email_from_file is the one from git_data.json.
        """
        if not self.git_db_handler:
            print("Error: Git DB Handler not initialized. Call _initialize_git_db_handler first.")
            return

        texts_to_embed = []
        metadatas = []
        ids = []

        for commit in git_events.get("commits", []):
            texts_to_embed.append(f"Commit: {commit['message']}")
            commit_specific_author = commit.get("author_email", author_email_from_file) 
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
            pr_specific_author = pr.get("user_email", author_email_from_file) 
            metadatas.append({
                "type": "pull_request",
                "number": pr["number"],
                "repo": repo_name,
                "author": pr_specific_author, 
                "date": pr["created_at"], 
                "title": pr["title"],
                "state": pr["state"]
            })
            ids.append(f"pr_{repo_name.replace('/', '_')}_{pr['number']}")

        if texts_to_embed:
            try:
                print(f"Upserting {len(texts_to_embed)} Git events to VectorDB collection: {self.git_db_handler.collection_name}")
                self.git_db_handler.add_texts_with_metadata(texts=texts_to_embed, metadatas=metadatas, ids=ids)
                print("Git events successfully upserted/updated in VectorDB.")
            except Exception as e:
                print(f"Error upserting Git events to VectorDB: {e}")
        else:
            print("No new Git events to upsert to VectorDB for the given filters.")


    def _format_wbs_tasks_for_llm(self, tasks: List[Dict]) -> str:
        if not tasks:
            return "해당 담당자에게 할당된 WBS 작업을 찾을 수 없거나, WBS 데이터가 없습니다."
        formatted_tasks = ["### 할당된 WBS 업무 목록:"]
        for task in tasks:
            task_details = (
                f"- 작업명: {task.get('task_name', 'N/A')}\n"
                f"  ID: {task.get('task_id', 'N/A')}\n"
                f"  담당자: {task.get('assignee', 'N/A')}\n"
                f"  상태 (WBS 기준): {task.get('status', 'N/A')}\n"
                f"  산출물: {task.get('deliverable', 'N/A')}\n"
                f"  시작 예정: {task.get('start_date', 'N/A')}\n"
                f"  종료 예정: {task.get('end_date', 'N/A')}"
            )
            formatted_tasks.append(task_details)
        return "\n".join(formatted_tasks)

    def _prepare_git_data_for_llm_prompt(self, git_events: Dict[str, List[Dict]], target_date_str: Optional[str]) -> str:
        """Formats filtered Git data into a string for the LLM prompt."""
        date_info = f"({target_date_str} 기준)" if target_date_str else "(최근 활동 기준)"
        prompt_parts = [f"### Git 활동 기록 {date_info}:"]

        if git_events["commits"]:
            prompt_parts.append("\n**최근 커밋:**")
            for commit in git_events["commits"][:15]: 
                commit_date_obj = datetime.fromisoformat(commit['date'].replace("Z", "+00:00"))
                commit_date_formatted = commit_date_obj.strftime('%Y-%m-%d %H:%M')
                prompt_parts.append(f"- SHA: {commit['sha'][:7]} ({commit_date_formatted})\n  리포지토리: {commit.get('repo', 'N/A')}\n  메시지: {commit['message']}")
        else:
            prompt_parts.append(f"\n**최근 커밋:** {date_info} 내역 없음")

        if git_events["pull_requests"]:
            prompt_parts.append("\n**관련 Pull Requests:**")
            for pr in git_events["pull_requests"][:10]: 
                pr_date_obj = datetime.fromisoformat(pr['created_at'].replace("Z", "+00:00"))
                pr_date_formatted = pr_date_obj.strftime('%Y-%m-%d %H:%M')
                prompt_parts.append(f"- PR #{pr['number']} ({pr.get('repo', 'N/A')}): {pr['title']} ({pr_date_formatted}, 상태: {pr['state']})")
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

        print(f"\n--- Git Analyzer Agent Invoked ---")
        print(f"Report for User ID (Author Email): {author_email_for_report}, WBS Assignee: {wbs_assignee_name}, Repo: {repo_name}, Target Date: {target_date_str or 'All Recent'}")

        self._initialize_git_db_handler(repo_name)

        try:
            with open(git_data_json_path, 'r', encoding='utf-8') as f:
                git_data_content = json.load(f)
        except FileNotFoundError:
            print(f"Error: Git data file not found at {git_data_json_path}")
            return None
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {git_data_json_path}")
            return None
        
        author_email_from_file = git_data_content.get("author")
        if not author_email_from_file:
            print(f"Warning: 'author' field not found in {git_data_json_path}. Using report author as fallback for data processing.")
            author_email_from_file = author_email_for_report 

        filtered_git_events = self._load_and_filter_git_data(
            git_data_content,
            author_email_from_file, 
            repo_name,
            target_date_str
        )

        if self.git_db_handler:
             self._upsert_git_events_to_vector_db(filtered_git_events, repo_name, author_email_from_file)
        else:
            print("Skipping Git event upsert to VectorDB as handler is not available.")

        print(f"Retrieving WBS tasks for project '{self.project_id_for_wbs}' and assignee '{wbs_assignee_name}'...")
        try:
            assigned_wbs_tasks = get_tasks_by_assignee_tool(
                project_id=self.project_id_for_wbs,
                assignee_name_to_filter=wbs_assignee_name,
                db_base_path=self.settings.VECTOR_DB_PATH_ENV,
            )
            print(f"Retrieved {len(assigned_wbs_tasks)} WBS tasks for assignee '{wbs_assignee_name}'.")
        except Exception as e:
            print(f"Error retrieving WBS tasks: {e}")
            assigned_wbs_tasks = []
            
        wbs_tasks_str_for_llm = self._format_wbs_tasks_for_llm(assigned_wbs_tasks)
        git_info_str_for_llm = self._prepare_git_data_for_llm_prompt(filtered_git_events, target_date_str)
        
        current_time_iso = datetime.now(timezone.utc).isoformat()

        try:
            with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
        except FileNotFoundError:
            print(f"Error: Prompt file not found at {PROMPT_FILE_PATH}")
            return None
        
        # Populate the prompt template
        # Added 'git_data' key to provide flexibility for the prompt template placeholder
        prompt = prompt_template.format(
            author_email=author_email_for_report, 
            wbs_assignee_name=wbs_assignee_name,
            repo_name=repo_name,
            target_date_str=target_date_str if target_date_str else "전체 최근 활동",
            current_time_iso=current_time_iso,
            git_info_str_for_llm=git_info_str_for_llm,
            wbs_tasks_str_for_llm=wbs_tasks_str_for_llm
        )

        print("\n--- Sending prompt to LLM (details in prompt file) ---")
        # print(prompt) # Uncomment for debugging
        print("--- End of prompt ---")

        try:
            response = self.llm_client.chat.completions.create(
                model=self.settings.OPENAI_MODEL, 
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
                print("\n--- LLM Analysis Result (JSON) ---")
                print(json.dumps(analysis_result, indent=2, ensure_ascii=False))
                
                if not all(key in analysis_result for key in ["user_id", "date", "type", "matched_tasks", "unmatched_tasks"]):
                    print("Warning: LLM output might not fully match the requested JSON structure.")
                
                analysis_result["user_id"] = author_email_for_report 
                analysis_result["date"] = current_time_iso 
                analysis_result["type"] = "Git" 

                return analysis_result
            else:
                print("Error: LLM returned empty content.")
                return None

        except json.JSONDecodeError as je:
            print(f"Error decoding LLM JSON response: {je}")
            print(f"LLM Raw Output:\n{llm_output_content}") 
            return None
        except Exception as e:
            print(f"Error during LLM interaction: {e}")
            return None

if __name__ == "__main__":
    print("Git Analyzer Agent - Test Run with Real Data Path using core.utils.Settings")

    settings_instance = Settings()
    
    settings_instance.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Calculate project_root for path configurations within this test script
    current_script_path = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_script_path, "..")) 
    
    default_vector_db_base_path = os.path.join(project_root, "db", "vector_store_test")
    settings_instance.VECTOR_DB_PATH_ENV = os.getenv("VECTOR_DB_PATH", default_vector_db_base_path)
    os.makedirs(settings_instance.VECTOR_DB_PATH_ENV, exist_ok=True)

    real_git_data_path = os.path.join(project_root, "data", "git_export", "git_data.json")
    print(f"Attempting to use real git data from: {real_git_data_path}")

    # --- Test Parameters ---
    test_author_email_for_report = "kproh99@naver.com" 
    test_wbs_assignee_name = "노건표" 
    test_repo_name = "skala-yAXim/AI-end" 
    test_project_id_for_wbs = "project_sample_002" 
    test_target_date = "2025-06-02" 

    print(f"\n--- Running Test ---")
    print(f"Report for User: {test_author_email_for_report}")
    print(f"WBS Assignee: {test_wbs_assignee_name}")
    print(f"Repository Filter: {test_repo_name}")
    print(f"Target Date: {test_target_date if test_target_date else 'All Recent'}")
    print(f"WBS Project ID: {test_project_id_for_wbs}")
    
    print("\nNote: This test assumes WBS data for the assignee and project ID exists in the VectorDB.")

    # GitAnalyzerAgent 초기화 시 settings 인스턴스 전달
    git_agent = GitAnalyzerAgent(settings=settings_instance, project_id_for_wbs=test_project_id_for_wbs)

    analysis_output = git_agent.analyze(
        git_data_json_path=real_git_data_path, 
        author_email_for_report=test_author_email_for_report,
        wbs_assignee_name=test_wbs_assignee_name,
        repo_name=test_repo_name,
        target_date_str=test_target_date
    )

    if analysis_output:
        print("\n--- Test Analysis Complete ---")
        assert "user_id" in analysis_output, "user_id missing"
        assert analysis_output["user_id"] == test_author_email_for_report, "user_id mismatch"
        assert "date" in analysis_output, "date missing"
        assert "type" in analysis_output and analysis_output["type"] == "Git", "type missing or incorrect"
        assert "matched_tasks" in analysis_output, "matched_tasks missing"
        assert "unmatched_tasks" in analysis_output, "unmatched_tasks missing"
        print("JSON structure basic validation passed.")
    else:
        print("\n--- Test Analysis Failed ---")

    print(f"\nReview the git data file used: {real_git_data_path}")
    print(f"Review the prompt file used: {PROMPT_FILE_PATH}")
