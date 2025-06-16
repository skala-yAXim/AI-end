from qdrant_client import QdrantClient
from core import config
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from core.state_definition import ProgressSummaryState
import os
from langchain_core.output_parsers import StrOutputParser

class ProgressSummaryAgent:

    def __init__(self , qdrant_client: QdrantClient):
        self.qdrant_client = qdrant_client
        
        self.llm_client = ChatOpenAI(
            model=config.DEFAULT_MODEL, temperature=0.9,
            openai_api_key=config.OPENAI_API_KEY, max_tokens=2500
        )

        prompt_file_path = os.path.join(config.PROMPTS_BASE_DIR, "daily_one_line_prompt.md")
        with open(prompt_file_path, 'r', encoding='utf-8') as f: 
                prompt_template_str = f.read()
        self.prompt = PromptTemplate.from_template(prompt_template_str)


    def generate(self, state: ProgressSummaryState) -> ProgressSummaryState:
        
        user_name = state.get("user_name")
        target_date = state.get("target_date")
        wbs_data = state.get("wbs_data")
        daily_report = state.get("daily_report")

        if not daily_report or not wbs_data:
            return "요약 생성에 필요한 데이터(데일리 보고서 또는 WBS)가 부족합니다."

        chain = self.prompt | self.llm_client | StrOutputParser()


        try:
            llm_input = {
                "wbs_assignee_name": user_name,
                "target_date": target_date,
                "wbs_data": wbs_data,
                "daily_report": daily_report,
            }
            analysis_result = chain.invoke(llm_input)
            print("Llm 분석 결과 : " + analysis_result)
            state["progress_summary"] = analysis_result
            return state
        except Exception as e:
            print(f"ProgressSummaryAgent: LLM Git 분석 중 오류: {e}")
            return {"summary": "Git 활동 분석 중 오류 발생", "error": str(e)}

    def __call__(self, state: ProgressSummaryState) -> ProgressSummaryState:
        return self.generate(state)
