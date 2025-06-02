# agents/teams_analyzer.py
# LangGraph Agent용 Teams 분석기 (ChromaDB + LLM 기반)

import json
import os
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime
import chromadb
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser

# Add parent directory to path for config import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import OPENAI_API_KEY, DEFAULT_MODEL, PROMPTS_DIR

class TeamsAnalyzer:
    """LangGraph Agent용 Teams 채팅 분석기 (업무 중심)"""
    
    def __init__(self, chroma_db_path: str = "./chroma_db", model_name: str = DEFAULT_MODEL):
        """초기화"""
        self.chroma_db_path = chroma_db_path
        self.model_name = model_name
        
        # LLM 초기화
        self.llm = ChatOpenAI(api_key=OPENAI_API_KEY, model=model_name, temperature=0)
        self.parser = JsonOutputParser()
        
        # ChromaDB 연결
        try:
            self.chroma_client = chromadb.PersistentClient(path=chroma_db_path)
            self.collection = self.chroma_client.get_collection(name="teams_messages")
        except Exception as e:
            raise RuntimeError(f"ChromaDB 연결 실패: {e}")
        
        # 프롬프트 템플릿 로드
        self.prompt_template = self._load_prompt_template()
        self.chain = self.prompt_template | self.llm | self.parser
    
    def _load_prompt_template(self) -> PromptTemplate:
        """teams_analyze_prompt.md 프롬프트 로드"""
        prompt_path = os.path.join(PROMPTS_DIR, "teams_analyze_prompt.md")
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_content = f.read()
                
        # 프롬프트 템플릿 검증 및 생성
        template = PromptTemplate(
            template=prompt_content,
            input_variables=["user_id", "user_name", "teams_messages", "wbs_data", "analysis_date"]
                )
        return template
        
    
    def get_user_messages(self, user_id: str) -> List[Dict[str, Any]]:
        """ChromaDB에서 특정 사용자 메시지 조회"""
        try:
            # 표준 검색
            results = self.collection.get(
                where={"sender_id": user_id},
                include=["documents", "metadatas"]
            )
            
            if not results.get("documents"):
                # 전체 검색 후 필터링
                all_data = self.collection.get(include=["documents", "metadatas"])
                
                filtered_docs = []
                filtered_metas = []
                
                for i, metadata in enumerate(all_data.get("metadatas", [])):
                    if metadata.get("sender_id", "").strip() == user_id.strip():
                        filtered_docs.append(all_data["documents"][i])
                        filtered_metas.append(metadata)
                
                results = {"documents": filtered_docs, "metadatas": filtered_metas}
            
            # 메시지 데이터 구성
            messages = []
            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])
            
            for i, doc in enumerate(documents):
                metadata = metadatas[i] if i < len(metadatas) else {}
                
                message = {
                    "message_id": metadata.get("message_id", f"msg_{i}"),
                    "content": doc,
                    "sender_id": metadata.get("sender_id", ""),
                    "sender_name": metadata.get("sender_name", ""),
                    "created_datetime": metadata.get("created_datetime", ""),
                    "message_type": metadata.get("message_type", "message"),
                    "has_attachments": metadata.get("has_attachments", False),
                    "reaction_count": metadata.get("reaction_count", 0),
                    "is_reply": metadata.get("is_reply", False)
                }
                messages.append(message)
            
            # 시간순 정렬
            messages.sort(key=lambda x: x.get("created_datetime", ""))
            return messages
            
        except Exception:
            return []
    
    def analyze_user(self, user_id: str, wbs_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """개인별 업무 수행 분석 (LangGraph Agent 메인 함수)"""
        try:
            # 1. 사용자 메시지 검색
            user_messages = self.get_user_messages(user_id)
            
            if not user_messages:
                return {
                    "error": f"사용자 '{user_id}'의 메시지를 찾을 수 없습니다.",
                    "user_id": user_id
                }
            
            user_name = user_messages[0].get("sender_name", user_id)
            
            # 2. WBS 데이터 준비
            if wbs_data is None:
                wbs_data = {"task_details_and_dependencies": []}
            
            # 사용자 할당 WBS 작업 필터링
            user_wbs_tasks = []
            for task in wbs_data.get("task_details_and_dependencies", []):
                if task.get("assignee") == user_name:
                    user_wbs_tasks.append(task)
            
            # 3. 데이터 정리 (토큰 제한 방지)
            max_messages = 20  # 업무 메시지 중심으로 더 많이 분석
            formatted_messages = user_messages[:max_messages]
            
            # LLM 분석용 데이터 준비 (업무 관련 내용 중심)
            analysis_data = []
            for msg in formatted_messages:
                analysis_data.append({
                    "message_id": msg.get("message_id", ""),
                    "content": msg.get("content", "")[:300],  # 업무 내용을 위해 더 긴 텍스트
                    "created_datetime": msg.get("created_datetime", ""),
                    "message_type": msg.get("message_type", "message"),
                    "has_attachments": msg.get("has_attachments", False)
                })
            
            # 4. LLM 분석 실행
            analysis_date = datetime.now().strftime("%Y-%m-%d")
            
            llm_input = {
                "user_id": user_id,
                "user_name": user_name,
                "teams_messages": json.dumps(analysis_data, ensure_ascii=False, indent=2)[:3000],  # 업무 분석을 위해 더 많은 데이터
                "wbs_data": json.dumps(wbs_data, ensure_ascii=False, indent=2)[:2000],
                "analysis_date": analysis_date
            }
            
            try:
                result = self.chain.invoke(llm_input)
            except Exception as llm_error:
                # LLM 호출 실패시 기본 업무 분석 결과 반환
                return {
                    "summary": f"{user_name}님의 개인 업무 수행 진행 상황 분석 (기본 모드)",
                    "task_progress_analysis": {
                        "completed_tasks": [],
                        "in_progress_tasks": [{"task": "메시지 활동 확인됨", "current_status": "기본 분석", "progress_percentage": 50, "evidence_message_ids": [analysis_data[0].get("message_id", "")] if analysis_data else []}],
                        "pending_tasks": []
                    },
                    "wbs_task_matching": {
                        "assigned_wbs_tasks": [{"task_id": task.get("task_id", ""), "task_name": task.get("task_name", ""), "wbs_status": task.get("status", ""), "actual_progress_from_chat": "기본 분석 모드", "evidence_message_ids": []} for task in user_wbs_tasks[:3]]
                    },
                    "work_performance_summary": {
                        "total_tasks_mentioned": len(analysis_data),
                        "completion_rate": 0.0,
                        "key_achievements": ["Teams 활동 확인"],
                        "current_focus_areas": ["업무 커뮤니케이션"],
                        "upcoming_priorities": ["상세 분석 필요"]
                    },
                    "analysis_metadata": {
                        "user_id": user_id,
                        "user_name": user_name,
                        "analysis_mode": "basic_fallback",
                        "llm_error": str(llm_error)
                    }
                }
            
            # 5. 결과 후처리
            if isinstance(result, dict):
                # 메타데이터 추가
                result["analysis_metadata"] = {
                    "user_id": user_id,
                    "user_name": user_name,
                    "total_messages_analyzed": len(analysis_data),
                    "wbs_tasks_assigned": len(user_wbs_tasks),
                    "analysis_date": analysis_date,
                    "model_used": self.model_name,
                    "analysis_focus": "task_progress_oriented"
                }
                return result
            else:
                # 기본 구조로 래핑
                return {
                    "summary": f"{user_name}님의 업무 수행 분석 완료",
                    "user_id": user_id,
                    "user_name": user_name,
                    "analysis_date": analysis_date,
                    "raw_result": str(result)
                }
            
        except Exception as e:
            return {
                "error": f"업무 분석 실패: {str(e)}",
                "user_id": user_id,
                "analysis_date": datetime.now().strftime("%Y-%m-%d")
            }
    
    def get_available_users(self) -> List[Dict[str, str]]:
        """사용 가능한 사용자 목록 조회"""
        try:
            all_data = self.collection.get(include=["metadatas"])
            users = {}
            
            for metadata in all_data.get("metadatas", []):
                sender_id = metadata.get("sender_id", "")
                sender_name = metadata.get("sender_name", "")
                if sender_id and sender_name:
                    users[sender_id] = sender_name
            
            return [{"user_id": uid, "user_name": name} for uid, name in users.items()]
            
        except Exception:
            return []


# LangGraph 노드 함수
def teams_analyze_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph용 Teams 분석 노드"""
    try:
        # 상태에서 필요한 데이터 추출
        user_id = state.get("target_user_id") or state.get("user_id")
        wbs_data = state.get("wbs_data", {})
        chroma_db_path = state.get("chroma_db_path", "./chroma_db")
        
        if not user_id:
            return {
                **state, 
                "teams_analysis": {
                    "error": "target_user_id 또는 user_id가 지정되지 않았습니다."
                }
            }
        
        # Teams 분석 실행
        analyzer = TeamsAnalyzer(chroma_db_path=chroma_db_path)
        result = analyzer.analyze_user(user_id, wbs_data)
        
        return {**state, "teams_analysis": result}
        
    except Exception as e:
        return {
            **state, 
            "teams_analysis": {
                "error": f"Teams 분석 노드 실행 오류: {str(e)}"
            }
        }


# 단순 실행 함수
def analyze_user(user_id: str, wbs_data: Dict[str, Any] = None, chroma_db_path: str = "./chroma_db") -> Dict[str, Any]:
    """단순 사용자 분석 실행 함수"""
    try:
        analyzer = TeamsAnalyzer(chroma_db_path=chroma_db_path)
        return analyzer.analyze_user(user_id, wbs_data)
    except Exception as e:
        return {"error": f"분석 실행 오류: {str(e)}"}


# 사용 예시 및 테스트
if __name__ == "__main__":
    try:
        # 기본 테스트
        analyzer = TeamsAnalyzer("./chroma_db")
        
        # 사용 가능한 사용자 확인
        users = analyzer.get_available_users()
        
        if users:
            test_user = users[0]
            print(f"테스트 사용자: {test_user['user_name']} ({test_user['user_id']})")
            
            # 샘플 WBS 데이터
            sample_wbs = {
                "task_details_and_dependencies": [
                    {
                        "task_id": "TASK-001",
                        "task_name": "프로젝트 초기 설정",
                        "assignee": test_user["user_name"],
                        "status": "completed",
                        "progress_percentage": 100
                    },
                    {
                        "task_id": "TASK-002",
                        "task_name": "기능 개발",
                        "assignee": test_user["user_name"],
                        "status": "in_progress",
                        "progress_percentage": 60
                    }
                ]
            }
            
            # 분석 실행
            result = analyzer.analyze_user(test_user["user_id"], sample_wbs)
            
            print("\n=== 업무 수행 분석 결과 ===")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
        else:
            print("사용 가능한 사용자가 없습니다. teams_data_processor.py를 먼저 실행하세요.")
            
    except Exception as e:
        print(f"테스트 실행 오류: {e}")
