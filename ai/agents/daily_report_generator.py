import os
from datetime import datetime
import json
from typing import Dict, List, Any, Optional

from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser 

from core import config
from ai.graphs.state_definition import LangGraphState
from ai.tools.wbs_data_retriever import WBSDataRetriever

class DailyReportGenerator:
    """
    LangGraph 워크플로우와 통합된 일일 보고서 생성기
    분석된 Teams, Docs, Git, Email, Project 데이터를 종합하여 JSON 형식의 보고서 생성
    """
    
    # wbs_retriever_tool 인자를 추가하여 초기화 시 전달받도록 수정
    def __init__(self, wbs_retriever_tool_instance: WBSDataRetriever = None): # wbs_retriever_tool을 인자로 받도록 수정
        self.llm = ChatOpenAI(
            model=config.DEFAULT_MODEL,  # gpt-4o 사용
            temperature=0.3,
            openai_api_key=config.OPENAI_API_KEY
        )
        
        # wbs_retriever_tool을 인스턴스 변수로 저장
        self.wbs_retriever_tool = wbs_retriever_tool_instance 

        # 프롬프트 템플릿 로드
        prompt_file_path = os.path.join(config.PROMPTS_BASE_DIR, "daily_report_prompt.md")
        with open(prompt_file_path, "r", encoding="utf-8") as f:
            prompt_content = f.read()

        self.prompt = PromptTemplate(
            template=prompt_content,
            input_variables=[
                "user_name", "user_id", "target_date",
                "wbs_data", "docs_analysis", "teams_analysis", 
                "git_analysis", "email_analysis", "project_id", "project_name", "project_description", "project_period",
                "retrieved_readme_info", "docs_daily_reflection", "teams_daily_reflection", 
                "git_daily_reflection", "email_daily_reflection",
                "non_assigned_wbs_matches" # 이 변수는 이제 초기 프롬프트에는 사용되지 않을 수 있습니다.
                                           # 하지만 최종 리포트의 매핑된 null-project_id 활동을 위한 플레이스홀더로 유지합니다.
            ]
        )
        self.parser = JsonOutputParser()

        # WBS 검색 쿼리 생성을 위한 프롬프트 및 파서
        query_gen_prompt_path = os.path.join(config.PROMPTS_BASE_DIR, "wbs_query_generation_prompt.md")
        with open(query_gen_prompt_path, "r", encoding="utf-8") as f:
            query_gen_content = f.read()
        
        self.wbs_query_gen_prompt = PromptTemplate(
            template=query_gen_content,
            input_variables=["user_activity_data"]
        )
        self.str_parser = StrOutputParser() # 문자열 출력을 위한 파서

        # task_id가 null인 활동을 매칭하기 위한 전용 프롬프트 및 파서 (재도입)
        match_null_task_wbs_prompt_path = os.path.join(config.PROMPTS_BASE_DIR, "wbs_match_null_task_prompt.md")
        with open(match_null_task_wbs_prompt_path, "r", encoding="utf-8") as f:
            match_null_task_wbs_content = f.read()

        self.wbs_match_null_task_prompt = PromptTemplate(
            template=match_null_task_wbs_content,
            input_variables=["projects","relevant_wbs_data", "unmatched_activities"]
        )


    def generate_daily_report(self, state: LangGraphState) -> LangGraphState:
        print(f"DailyReportGenerator: 사용자 '{state.get('user_name')}' ({state.get('user_id')})의 {state.get('target_date')} 보고서 생성 시작...")
                    
        try:
            # --- 1단계: 초기 보고서 생성 (state의 할당된 WBS 데이터만 바탕으로) ---
            # LLM은 project_id는 채우지만, task_id는 매칭되지 않으면 null로 채웁니다.
            prompt_data = {
                "projects": state.get("projects", []),
                "user_name": state.get("user_name", "사용자"),
                "user_id": state.get("user_id", "알 수 없음"),
                "target_date": state.get("target_date", datetime.now().strftime('%Y-%m-%d')),
                "wbs_data": str(state.get("wbs_data", "WBS 데이터 없음")),
                "docs_analysis": str(state.get("documents_analysis_result", "문서 분석 결과 없음")),
                "teams_analysis": str(state.get("teams_analysis_result", "Teams 분석 결과 없음")),
                "git_analysis": str(state.get("git_analysis_result", "Git 분석 결과 없음")),
                "email_analysis": str(state.get("email_analysis_result", "이메일 분석 결과 없음")),
                "retrieved_readme_info": str(state.get("retrieved_readme_info", "README 정보 없음")),
                "docs_daily_reflection": str(state.get("documents_analysis_result", {}).get("daily_reflection", "")),
                "teams_daily_reflection": str(state.get("teams_analysis_result", {}).get("daily_reflection", "")),
                "git_daily_reflection": str(state.get("git_analysis_result", {}).get("daily_reflection", "")),
                "email_daily_reflection": str(state.get("email_analysis_result", {}).get("daily_reflection", "")),
            }
            
            chain = self.prompt | self.llm | self.parser
            print("DailyReportGenerator: 1차 보고서 생성 중...")
            first_pass_report = chain.invoke(prompt_data)
            
            # --- 2단계: 1차 보고서에서 task_id가 null인 활동 추출 ---
            activities_with_null_task: List[Dict[str, Any]] = []
            if first_pass_report and first_pass_report.get("daily_report", {}).get("contents"):
                for idx, content_item in enumerate(first_pass_report["daily_report"]["contents"]):
                    if content_item.get("task_id") is None and content_item.get("project_id"):
                        activities_with_null_task.append({
                            "original_index": idx, # 원본 배열의 인덱스 저장
                            "project_id": content_item.get("project_id"), # 해당 활동의 project_id
                            "text": content_item.get("text"),
                            "evidence_content": content_item.get("evidence", [{}])[0].get("content", "") # 첫 번째 evidence의 content
                        })
            
            print(f"DailyReportGenerator: Task ID가 null인 활동 {len(activities_with_null_task)}개 발견.")

            # --- 3단계: null task_id 활동에 대해 WBS 검색 및 재매칭 시도 ---
            if activities_with_null_task and self.wbs_retriever_tool:
                all_retrieved_wbs_for_rematch: List[Dict[str, Any]] = []
                
                # 각 null task 활동에 대해 개별적으로 쿼리를 생성하고 검색을 수행합니다.
                for activity in activities_with_null_task:
                    activity_text_for_query = f"{activity.get('text', '')} {activity.get('evidence_content', '')}".strip()
                    if not activity_text_for_query:
                        continue

                    # LLM에게 검색 쿼리 작성 요청 (활동별로)
                    generated_query_text = ""
                    try:
                        print(f"DailyReportGenerator: LLM에게 Task ID null 활동 '{activity_text_for_query[:30]}...'에 대한 검색 쿼리 생성 요청 중...")
                        query_gen_chain = self.wbs_query_gen_prompt | self.llm | self.str_parser
                        generated_query_text = query_gen_chain.invoke({"user_activity_data": activity_text_for_query})
                        print(f"DailyReportGenerator: 생성된 쿼리: '{generated_query_text}'")
                    except Exception as e:
                        print(f"DailyReportGenerator: WBS 검색 쿼리 생성 중 오류 발생: {e}")
                        generated_query_text = "" 
                    
                    if generated_query_text.strip():
                        # 해당 활동의 project_id를 사용하여 WBS 검색
                        print(f"DailyReportGenerator: 프로젝트 ID '{activity['project_id']}' 내에서 WBS 데이터 하이브리드 검색 시작...")
                        relevant_wbs_data = self.wbs_retriever_tool.retrieve_relevant_wbs_data_hybrid(
                            query_text=generated_query_text, 
                            project_ids=[int(activity["project_id"])], # <--- 해당 활동의 project_id로 필터링
                            limit=3 # 각 활동별로 적절한 개수만 검색
                        )
                        if relevant_wbs_data:
                            all_retrieved_wbs_for_rematch.extend(relevant_wbs_data)
                            print(f"DailyReportGenerator: 프로젝트 '{activity['project_id']}'에서 {len(relevant_wbs_data)}개의 관련 WBS 데이터 발견.")
                    else:
                        print(f"DailyReportGenerator: 유효한 검색 쿼리가 생성되지 않아 활동 '{activity_text_for_query[:30]}...'에 대한 WBS 검색 건너뜀.")

                if all_retrieved_wbs_for_rematch:
                    print(f"DailyReportGenerator: 총 {len(all_retrieved_wbs_for_rematch)}개의 WBS 데이터로 LLM 재매칭 시도.")
                    
                    # LLM 재매칭을 위한 프롬프트 데이터 구성
                    rematch_prompt_data = {
                        "projects": state.get("projects", []),
                        "relevant_wbs_data": json.dumps(all_retrieved_wbs_for_rematch, ensure_ascii=False),
                        "unmatched_activities": json.dumps(activities_with_null_task, ensure_ascii=False) 
                    }
                    
                    wbs_rematch_chain = self.wbs_match_null_task_prompt | self.llm | self.parser 
                    
                    try:
                        rematch_results = wbs_rematch_chain.invoke(rematch_prompt_data)
                        
                        # 재매칭된 결과를 1차 보고서에 반영
                        if rematch_results and rematch_results.get("matched_contents"):
                            for match_item in rematch_results["matched_contents"]:
                                original_idx = match_item.get("original_index")
                                if original_idx is not None and 0 <= original_idx < len(first_pass_report["daily_report"]["contents"]):
                                    original_item = first_pass_report["daily_report"]["contents"][original_idx]

                                    original_item["project_id"] = match_item.get("project_id", original_item.get("project_id"))
                                    original_item["project_name"] = match_item.get("project_name", original_item.get("project_name"))
                                    original_item["task_id"] = match_item.get("task_id")
                                    original_item["task"] = match_item.get("task")

                                    # evidence 배열 업데이트
                                    if "evidence" in match_item and isinstance(match_item["evidence"], list):
                                        original_item["evidence"] = match_item["evidence"]

                                    print(f"DailyReportGenerator: {original_idx}번 활동 전체 업데이트 완료.")

                            print(f"DailyReportGenerator: {len(rematch_results['matched_contents'])}개의 활동에 대한 WBS Task 정보 업데이트 완료.")
                        else:
                            print("DailyReportGenerator: LLM 재매칭 결과 매칭된 활동 없음.")

                    except Exception as e:
                        print(f"DailyReportGenerator: LLM 재매칭 중 오류 발생: {e}")
                else:
                    print("DailyReportGenerator: 관련 WBS 데이터를 찾지 못하여 재매칭 건너뜀.")
            else:
                print("DailyReportGenerator: Task ID가 null인 활동이 없거나 WBS Retriever 툴 없음. 재매칭 건너뜜.")
                


            # 최종 보고서 결과 (업데이트된 first_pass_report)를 state에 저장
            state["comprehensive_report"] = first_pass_report
            print("Daily 보고서 생성 및 WBS Task 매칭 업데이트 완료.")
            print(json.dumps(first_pass_report, ensure_ascii=False))
        except Exception as e:
            print(f"DailyReportGenerator: 보고서 생성 또는 WBS Task 매칭 중 최종 오류 발생: {e}")
            state["comprehensive_report"] = {
                "error": "보고서 생성 실패",
                "message": str(e)
            }
            current_error = state.get("error_message", "")
            state["error_message"] = (current_error + f"\n DailyReportGenerator 최종 오류: {e}").strip()
        
        return state 


    def __call__(self, state: LangGraphState) -> LangGraphState:
        """
        다른 analyzer들과 동일한 호출 패턴 지원
        """
        return self.generate_daily_report(state)
