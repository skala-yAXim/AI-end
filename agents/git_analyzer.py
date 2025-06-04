# agents/git_analyzer.py

import json
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from openai import OpenAI

# Adjust path to import from sibling and parent directories based on README structure
# This assumes the script is run from the root of the project, or PYTHONPATH is set.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))) # If agents is a sub-sub-directory

from core.utils import Settings
from wbs_analyze_agent.core.vector_db import VectorDBHandler # For storing/retrieving git embeddings
from tools.wbs_retriever_tool import get_tasks_by_assignee_tool

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
        author_email: str,
        repo_name_filter: str, # To ensure we are processing data for the correct repo
        target_date_str: Optional[str] = None
    ) -> Dict[str, List[Dict]]:
        """
        Loads Git data from the provided dictionary content, filters by author, repo, and optionally date.
        The current git_data.json structure has a global author. We'll assume commits
        and PRs under this author are relevant if the repo matches.
        """
        print(f"Filtering Git data for author: {author_email}, repo: {repo_name_filter}, date: {target_date_str}")
        if git_data_content.get("author") != author_email:
            print(f"Warning: Top-level author in git_data ({git_data_content.get('author')}) does not match requested author ({author_email}).")
            # Depending on requirements, you might want to return empty or still process if commits have individual authors.
            # For this structure, we assume the top-level author is the one whose activities are listed.

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

    def _upsert_git_events_to_vector_db(self, git_events: Dict[str, List[Dict]], repo_name: str, author_email: str):
        """
        Embeds and stores git event texts (commit messages, PR titles/bodies) into the VectorDB.
        This fulfills the "vectorDB를 설계하고 동작하도록" part for git_data.
        """
        if not self.git_db_handler:
            print("Error: Git DB Handler not initialized. Call _initialize_git_db_handler first.")
            return

        texts_to_embed = []
        metadatas = []
        ids = []

        for commit in git_events.get("commits", []):
            texts_to_embed.append(f"Commit: {commit['message']}")
            metadatas.append({
                "type": "commit",
                "sha": commit["sha"],
                "repo": repo_name,
                "author": author_email, # Or specific commit author if available
                "date": commit["date"],
                "message_summary": commit['message'][:100] # Store a summary
            })
            ids.append(f"commit_{commit['sha']}")

        for pr in git_events.get("pull_requests", []):
            pr_content_for_embedding = f"PR Title: {pr['title']}\nPR Body: {pr.get('content', '')[:500]}" # Limit body length for embedding
            texts_to_embed.append(pr_content_for_embedding)
            metadatas.append({
                "type": "pull_request",
                "number": pr["number"],
                "repo": repo_name,
                "author": author_email, # Or PR creator if available
                "date": pr["created_at"],
                "title": pr["title"],
                "state": pr["state"]
            })
            ids.append(f"pr_{repo_name}_{pr['number']}")
        
        if texts_to_embed:
            try:
                print(f"Upserting {len(texts_to_embed)} Git events to VectorDB collection: {self.git_db_handler.collection_name}")
                self.git_db_handler.add_texts_with_metadata(texts=texts_to_embed, metadatas=metadatas, ids=ids)
                print("Git events successfully upserted to VectorDB.")
            except Exception as e:
                print(f"Error upserting Git events to VectorDB: {e}")
        else:
            print("No new Git events to upsert to VectorDB.")


    def _format_wbs_tasks_for_llm(self, tasks: List[Dict]) -> str:
        if not tasks:
            return "해당 담당자에게 할당된 WBS 작업을 찾을 수 없거나, WBS 데이터가 없습니다."
        formatted_tasks = ["### 할당된 WBS 업무 목록:"]
        for task in tasks:
            task_details = (
                f"- 작업명: {task.get('task_name', 'N/A')}\n"
                f"  ID: {task.get('task_id', 'N/A')}\n"
                f"  담당자: {task.get('assignee', 'N/A')}\n" # WBS retriever should provide this
                f"  상태: {task.get('status', 'N/A')}\n"
                f"  산출물: {task.get('deliverable', 'N/A')}\n"
                f"  시작 예정: {task.get('start_date', 'N/A')}\n"
                f"  종료 예정: {task.get('end_date', 'N/A')}"
            )
            formatted_tasks.append(task_details)
        return "\n".join(formatted_tasks)

    def _prepare_git_data_for_llm_prompt(self, git_events: Dict[str, List[Dict]]) -> str:
        """Formats filtered Git data into a string for the LLM prompt."""
        prompt_parts = ["### Git 활동 기록:"]

        if git_events["commits"]:
            prompt_parts.append("\n**최근 커밋:**")
            for commit in git_events["commits"][:15]: # Display latest 15 commits
                commit_date = datetime.fromisoformat(commit['date'].replace("Z", "+00:00")).strftime('%Y-%m-%d %H:%M')
                prompt_parts.append(f"- SHA: {commit['sha'][:7]} ({commit_date})\n  메시지: {commit['message']}")
        else:
            prompt_parts.append("\n**최근 커밋:** 해당 기간 내역 없음")

        if git_events["pull_requests"]:
            prompt_parts.append("\n**관련 Pull Requests:**")
            for pr in git_events["pull_requests"][:10]: # Display latest 10 PRs
                pr_date = datetime.fromisoformat(pr['created_at'].replace("Z", "+00:00")).strftime('%Y-%m-%d %H:%M')
                prompt_parts.append(f"- PR #{pr['number']}: {pr['title']} ({pr_date}, 상태: {pr['state']})")
                if pr.get('content'):
                    pr_content_summary = pr['content'][:200].strip().replace('\r\n', ' ').replace('\n', ' ') # Brief summary
                    prompt_parts.append(f"  내용 요약: {pr_content_summary}...")
        else:
            prompt_parts.append("\n**관련 Pull Requests:** 해당 기간 내역 없음")
        
        # Placeholder for issues if data becomes available
        # if git_events.get("issues"): ...

        return "\n".join(prompt_parts)

    def analyze(
        self,
        git_data_json_path: str, # Path to the git_data.json file
        author_email: str,      # Git author email (e.g., kproh99@naver.com)
        wbs_assignee_name: str, # Assignee name as it appears in WBS (e.g., "노건표" or "kproh99")
        repo_name: str,         # Repository name (e.g., "skala-yAXim/AI-end")
        target_date_str: Optional[str] = None # Optional: "YYYY-MM-DD"
    ) -> Optional[Dict[str, Any]]:
        """
        Analyzes Git data for a given author and repository, correlates with WBS tasks,
        and generates a progress summary using an LLM.
        """
        print(f"\n--- Git Analyzer Agent Invoked ---")
        print(f"Author Email: {author_email}, WBS Assignee: {wbs_assignee_name}, Repo: {repo_name}, Date: {target_date_str or 'Any'}")

        self._initialize_git_db_handler(repo_name) # Initialize DB handler for this specific repo

        # 1. Load and filter Git data from the provided JSON file
        try:
            with open(git_data_json_path, 'r', encoding='utf-8') as f:
                git_data_content = json.load(f)
        except FileNotFoundError:
            print(f"Error: Git data file not found at {git_data_json_path}")
            return None
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {git_data_json_path}")
            return None
            
        filtered_git_events = self._load_and_filter_git_data(
            git_data_content, author_email, repo_name, target_date_str
        )

        # 2. (Optional but per request) Upsert filtered Git events to its VectorDB
        # This makes the git data queryable for other purposes or future, more complex analyses.
        if self.git_db_handler: # Check if initialized
             self._upsert_git_events_to_vector_db(filtered_git_events, repo_name, author_email)
        else:
            print("Skipping Git event upsert to VectorDB as handler is not available.")

        # 3. Retrieve WBS tasks for the author
        # The project_id_for_wbs is set during agent initialization
        print(f"Retrieving WBS tasks for project '{self.project_id_for_wbs}' and assignee '{wbs_assignee_name}'...")
        try:
            # Using get_tasks_by_assignee_tool as it's more direct
            assigned_wbs_tasks = get_tasks_by_assignee_tool(
                project_id=self.project_id_for_wbs,
                assignee_name_to_filter=wbs_assignee_name,
                db_base_path=self.settings.VECTOR_DB_PATH_ENV, # Assuming WBS retriever uses the same base path system
                # collection_prefix="wbs_data" # Default in wbs_retriever_tool
            )
            print(f"Retrieved {len(assigned_wbs_tasks)} WBS tasks for assignee '{wbs_assignee_name}'.")
        except Exception as e:
            print(f"Error retrieving WBS tasks: {e}")
            assigned_wbs_tasks = []
            
        wbs_tasks_str_for_llm = self._format_wbs_tasks_for_llm(assigned_wbs_tasks)
        git_info_str_for_llm = self._prepare_git_data_for_llm_prompt(filtered_git_events)

        # 4. Construct the prompt for LLM
        # The user's example prompt: “너는 20년차 개발자 ~~ . 너가 해야할일은 위의 정보들만 가지고 현재 프로젝트 진행상황을 파악해야해. ~~”
        # Output: 1. 개인 수행 진행 업무. 2. 수행 리스트 업무 중 진행 된 내용 요약.
        prompt = f"""당신은 20년차 시니어 개발자이자 프로젝트 분석 전문가입니다. 당신의 임무는 제공된 WBS(업무분담구조)상의 할당된 작업 내역과 지정된 Git 저장소의 활동 기록을 면밀히 검토하여, 특정 담당자의 프로젝트 진행 상황을 분석하고 요약 보고서를 작성하는 것입니다.

        **분석 대상:**
        * 담당자 Git 이메일: {author_email}
        * 담당자 WBS 상 이름: {wbs_assignee_name}
        * Git 저장소: {repo_name}
        * 분석 기준일: {target_date_str if target_date_str else "전체 최근 활동"}

        **제공된 정보:**

        {wbs_tasks_str_for_llm}

        {git_info_str_for_llm}

        **요청 사항:**
        위의 정보를 바탕으로 다음 항목에 대해 상세히 분석하고, 그 결과를 JSON 형식으로 제공해주십시오. 각 항목의 내용은 구체적인 근거(WBS 작업명, 커밋 SHA, PR 번호 등)를 포함하여 작성해야 합니다.

        1.  **개인 수행 진행 업무 (individual_task_progress):**
            * 현재 WBS 상에서 담당자({wbs_assignee_name})가 맡아 진행 중인 주요 업무는 무엇입니까?
            * 각 WBS 업무 항목에 대해, Git 활동(커밋 메시지, PR 제목/내용)을 근거로 실제 어떤 작업이 얼마나 진행되었는지 상세히 연결하여 설명해주십시오. (예: 'WBS 작업 [작업명]'은(는) 커밋 [SHA] 및 PR #[번호]를 통해 '[기능 상세 설명]' 기능 개발이 진행 중/완료된 것으로 보입니다.)
            * 만약 WBS에는 있지만 Git 활동이 없는 경우, 해당 사항도 명시해주십시오.

        2.  **수행 리스트 업무 중 진행된 내용 요약 (completed_or_progressed_summary):**
            * 담당자가 완료했거나 상당 부분 진행하여 주요 성과가 있는 WBS 업무 항목들을 요약해주십시오.
            * 각 완료/진행 업무에 대한 핵심 변경 사항, 구현된 기능, 또는 주요 산출물을 Git 기록을 근거로 간략히 언급해주십시오.

        3.  **추가 관찰 및 제언 (additional_observations_and_suggestions) (선택 사항):**
            * WBS에 명시되지 않았지만 Git 활동으로 미루어보아 담당자가 수행한 것으로 보이는 추가 작업 사항이 있습니까? (예: 긴급 버그 수정, 기술 부채 해결, 리팩토링 등)
            * 업무 진행 패턴(예: 특정 유형의 작업에 집중, 여러 작업 병행 등), 잠재적 위험/이슈, 또는 프로젝트 효율성 증진을 위한 제언 등이 있다면 자유롭게 기술해주십시오.

        **출력 형식 (JSON):**
        ```json
        {{
        "report_for_author": "{wbs_assignee_name} ({author_email})",
        "repository": "{repo_name}",
        "analysis_date": "{target_date_str if target_date_str else 'Latest'}",
        "individual_task_progress": "...",
        "completed_or_progressed_summary": "...",
        "additional_observations_and_suggestions": "..."
        }}
        ```
        각 항목의 값은 명확하고 이해하기 쉬운 문장으로 작성해주십시오.
        """
        print("\n--- Sending prompt to LLM ---")
        # print(prompt) # Uncomment to see the full prompt
        print("--- End of prompt ---")

        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4o", # Or your preferred model like gpt-3.5-turbo
                messages=[
                    {"role": "system", "content": "당신은 요청받은 정보를 분석하여 JSON 형식으로 결과를 제공하는 유능한 AI 어시스턴트입니다."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}, # For models supporting JSON mode
                temperature=0.2, # Lower temperature for more factual, less creative output
            )
            
            llm_output_content = response.choices[0].message.content
            if llm_output_content:
                analysis_result = json.loads(llm_output_content)
                print("\n--- LLM Analysis Result (JSON) ---")
                print(json.dumps(analysis_result, indent=2, ensure_ascii=False))
                return analysis_result
            else:
                print("Error: LLM returned empty content.")
                return None

        except Exception as e:
            print(f"Error during LLM interaction: {e}")
            return None

if __name__ == "__main__":
    print("Git Analyzer Agent - Test Run")

    class DummySettings(Settings): 
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        if not OPENAI_API_KEY:
            print("Error: OPENAI_API_KEY environment variable not set.")
            sys.exit(1)
        
        current_script_path = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_script_path, "..")) # Up one level from 'agents'
        DEFAULT_VECTOR_DB_BASE_PATH = os.path.join(project_root, "db", "vector_store_test")
        VECTOR_DB_PATH_ENV = os.getenv("VECTOR_DB_PATH", DEFAULT_VECTOR_DB_BASE_PATH)
        print(f"Test Vector DB Path: {VECTOR_DB_PATH_ENV}")

    user_git_data_path = "data/git_export/git_data.json"
    print(f"Using user's git_data.json found at '{user_git_data_path}'")
    git_data_to_use = user_git_data_path
    test_author_email = "kproh99@naver.com"
    test_wbs_assignee_name = "노건표" 
    test_repo_name = "skala-yAXim/AI-end"
    test_project_id_for_wbs = "project_sample_002" 
    test_target_date = "2025-06-02"

    git_agent = GitAnalyzerAgent(project_id_for_wbs=test_project_id_for_wbs)

    analysis_output = git_agent.analyze(
        git_data_json_path=git_data_to_use,
        author_email=test_author_email,
        wbs_assignee_name=test_wbs_assignee_name,
        repo_name=test_repo_name,
        target_date_str=test_target_date
    )

    if analysis_output:
        print("\n--- Analysis Complete ---")
        # Output is already printed in JSON format within the analyze method
    else:
        print("\n--- Analysis Failed ---")

    # Clean up dummy file if created
    if git_data_to_use == dummy_git_data_path and os.path.exists(dummy_git_data_path):
        # os.remove(dummy_git_data_path)
        print(f"Kept dummy git data file for review: {dummy_git_data_path}")


