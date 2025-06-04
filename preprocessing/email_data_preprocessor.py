# -*- coding: utf-8 -*-
import json
import os
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Any

from agents.wbs_analyze_agent.core.vector_db import VectorDBHandler 

class EmailDataPreprocessor:
    def __init__(self, settings):
        self.settings = settings
        self.email_db_handler: Optional[VectorDBHandler] = None

    def _initialize_email_db_handler(self, user_email_for_db_name: str):
        """특정 사용자의 이메일 데이터에 대한 VectorDBHandler를 초기화합니다."""
        safe_user_email = user_email_for_db_name.replace("@", "_").replace(".", "_")
        
        email_specific_db_base_path = os.path.join(self.settings.VECTOR_DB_PATH_ENV, "email_store")
        os.makedirs(email_specific_db_base_path, exist_ok=True)

        self.email_db_handler = VectorDBHandler(
            db_base_path=email_specific_db_base_path,
            collection_name_prefix="email_data",
            project_id=safe_user_email,
        )
        print(f"Email VectorDB Handler initialized for user: {user_email_for_db_name} -> collection: {self.email_db_handler.collection_name}")

    def _generate_email_id(self, email_data: Dict, author_email: str) -> str:
        """이메일 데이터에 대한 고유 ID 생성"""
        identifier_str = f"{author_email}_{email_data.get('conversation_id', '')}_{email_data.get('date', '')}_{email_data.get('subject', '')}_{email_data.get('sender','')}"
        return hashlib.md5(identifier_str.encode('utf-8')).hexdigest()

    def _filter_and_prepare_emails(
        self,
        raw_email_data_list: List[Dict],
        target_author_email: str,
        target_date_str: Optional[str] = None
    ) -> List[Dict]:
        """
        주어진 사용자와 날짜에 해당하는 이메일만 필터링하고 VectorDB 저장 형식으로 준비합니다.
        """
        print(f"Filtering email data for author: {target_author_email}, target date: {target_date_str}")
        
        prepared_emails = []
        target_dt = None
        if target_date_str:
            try:
                target_dt = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            except ValueError:
                print(f"Warning: Invalid target_date format '{target_date_str}'. Ignoring date filter for emails.")

        for user_email_block in raw_email_data_list:
            author_in_block = user_email_block.get("author")
            if author_in_block == target_author_email:
                for email in user_email_block.get("emails", []):
                    email_date_str = email.get("date", "")
                    email_dt = None
                    if email_date_str: # 날짜 정보가 있는 경우에만 파싱 시도
                        try:
                            # ISO 형식 (YYYY-MM-DDTHH:MM:SSZ 등) 우선 처리
                            if "T" in email_date_str:
                                email_dt = datetime.fromisoformat(email_date_str.replace("Z", "+00:00")).date()
                            else: # YYYY-MM-DD 형식 또는 기타 간단한 형식
                                email_dt = datetime.strptime(email_date_str, "%Y-%m-%d").date()
                        except ValueError:
                            print(f"Warning: Could not parse date '{email_date_str}' for an email. Skipping date filter for this email.")
                    
                    if target_dt and (not email_dt or email_dt != target_dt): # 날짜 필터링
                        continue

                    email_doc = {
                        "id": self._generate_email_id(email, author_in_block),
                        "text_for_embedding": f"Subject: {email.get('subject', '')}\nContent: {email.get('content', '')[:1000]}",
                        "metadata": {
                            "author": author_in_block,
                            "sender": email.get("sender"),
                            "receiver": email.get("receiver"),
                            "subject": email.get("subject"),
                            "date": email.get("date"),
                            "conversation_id": email.get("conversation_id"),
                            "attachment_list": email.get("attachment_list", []),
                            "type": "email"
                        }
                    }
                    prepared_emails.append(email_doc)
        
        print(f"Found {len(prepared_emails)} emails matching criteria for author '{target_author_email}'.")
        return prepared_emails

    def _upsert_emails_to_vector_db(self, email_documents: List[Dict]):
        """ 준비된 이메일 문서들을 VectorDB에 임베딩하고 저장(upsert)합니다. """
        if not self.email_db_handler:
            print("Error: Email DB Handler not initialized. Cannot upsert data.")
            return

        if not email_documents:
            print("No email documents to upsert to VectorDB.")
            return

        texts_to_embed = [doc["text_for_embedding"] for doc in email_documents]
        metadatas = [doc["metadata"] for doc in email_documents]
        ids = [doc["id"] for doc in email_documents]

        try:
            print(f"Upserting {len(texts_to_embed)} email documents to VectorDB collection: {self.email_db_handler.collection_name}")
            self.email_db_handler.add_texts_with_metadata(texts=texts_to_embed, metadatas=metadatas, ids=ids)
            print("Email documents successfully upserted/updated in VectorDB.")
        except Exception as e:
            print(f"Error upserting email documents to VectorDB: {e}")

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        print("EmailDataPreprocessor __call__ invoked.")
        
        email_data_json_path = state.get("email_data_json_path")
        author_email_for_analysis = state.get("author_email_for_analysis")
        target_date_str = state.get("target_date_str")

        if not all([email_data_json_path, author_email_for_analysis]):
            error_msg = "Missing required parameters in state for EmailDataPreprocessor: email_data_json_path, author_email_for_analysis must be provided."
            print(f"Error: {error_msg}")
            state["email_preprocessing_status"] = "error"
            state["email_preprocessing_error_message"] = error_msg
            state["processed_email_events_for_llm"] = []
            return state

        self._initialize_email_db_handler(author_email_for_analysis)

        try:
            with open(email_data_json_path, 'r', encoding='utf-8') as f:
                raw_email_data_list = json.load(f)
        except FileNotFoundError:
            error_msg = f"Email data file not found at {email_data_json_path}"
            state["email_preprocessing_status"] = "error"; state["email_preprocessing_error_message"] = error_msg; state["processed_email_events_for_llm"] = []
            print(f"Error: {error_msg}"); return state
        except json.JSONDecodeError:
            error_msg = f"Could not decode JSON from {email_data_json_path}"
            state["email_preprocessing_status"] = "error"; state["email_preprocessing_error_message"] = error_msg; state["processed_email_events_for_llm"] = []
            print(f"Error: {error_msg}"); return state
        
        email_documents_for_db = self._filter_and_prepare_emails(
            raw_email_data_list=raw_email_data_list,
            target_author_email=author_email_for_analysis,
            target_date_str=target_date_str
        )
        
        self._upsert_emails_to_vector_db(email_documents_for_db)
        
        llm_email_info = []
        # VectorDB에서 검색하는 대신, 필터링된 목록에서 LLM에 전달할 정보 요약 (최대 15개)
        for doc in email_documents_for_db[:15]: 
            meta = doc["metadata"]
            llm_email_info.append({
                "sender": meta.get("sender"), "receiver": meta.get("receiver"),
                "subject": meta.get("subject"), "date": meta.get("date"),
                "content_summary": doc["text_for_embedding"][:200] + "...",
                "conversation_id": meta.get("conversation_id"),
                "attachments": meta.get("attachment_list")
            })

        state["processed_email_events_for_llm"] = llm_email_info
        state["email_preprocessing_status"] = "success"
        state["email_preprocessing_error_message"] = None
        print("EmailDataPreprocessor __call__ completed successfully.")
        return state
