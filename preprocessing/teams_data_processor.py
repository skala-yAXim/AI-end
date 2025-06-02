# preprocessing/teams_data_processor.py

import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import chromadb
from chromadb.config import Settings
from openai import OpenAI
import hashlib
import os
import sys

# Add parent directory to path for config import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import OPENAI_API_KEY, DATA_DIR

class TeamsDataProcessor:
    """Teams 채팅 데이터 전처리 및 ChromaDB 구축 클래스"""
    
    def __init__(self, data_path: str = None, chroma_db_path: str = "./chroma_db"):
        """
        초기화
        
        Args:
            data_path: teams_messages_data.json 파일 경로
            chroma_db_path: ChromaDB 저장 경로
        """
        self.data_path = data_path or os.path.join(DATA_DIR, "teams_messages_data.json")
        self.chroma_db_path = chroma_db_path
        
        # OpenAI 클라이언트 초기화
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        # ChromaDB 클라이언트 초기화
        self.chroma_client = chromadb.PersistentClient(path=chroma_db_path)
        
        # 기본 설정
        self.collection_name = "teams_messages"
        self.embedding_model = "text-embedding-3-small"
        
        print(f"📊 TeamsDataProcessor 초기화 완료")
        print(f"   - 데이터 경로: {self.data_path}")
        print(f"   - ChromaDB 경로: {self.chroma_db_path}")
    
    def load_raw_data(self) -> Dict[str, Any]:
        """
        원본 Teams 데이터 로드
        
        Returns:
            Dict: teams_messages_data.json 내용
        """
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            messages_count = len(data.get("teams_messages", []))
            print(f"✅ 원본 데이터 로드 완료: {messages_count}개 메시지")
            return data
            
        except FileNotFoundError:
            raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {self.data_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 파싱 오류: {e}")
    
    def clean_message_content(self, content: str) -> str:
        """
        메시지 내용에서 HTML 태그 제거 및 정규화
        
        Args:
            content: 원본 메시지 내용
            
        Returns:
            str: 정리된 텍스트
        """
        if not content:
            return ""
        
        # HTML 태그 제거
        clean_text = re.sub(r'<[^>]+>', '', content)
        
        # 특수 문자 정리 (필요시)
        clean_text = re.sub(r'\s+', ' ', clean_text)  # 여러 공백을 단일 공백으로
        clean_text = clean_text.strip()
        
        return clean_text
    
    def extract_metadata(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        메시지에서 메타데이터 추출
        
        Args:
            message: 원본 메시지 객체
            
        Returns:
            Dict: 추출된 메타데이터
        """
        # 기본 정보 추출
        message_id = message.get("id", "")
        created_datetime = message.get("createdDateTime", "")
        message_type = message.get("messageType", "message")
        chat_id = message.get("chatId", "")
        
        # 발신자 정보
        from_info = message.get("from", {})
        user_info = from_info.get("user", {})
        sender_id = user_info.get("id", "")
        sender_name = user_info.get("displayName", "")
        
        # 본문 내용
        body = message.get("body", {})
        content_type = body.get("contentType", "")
        raw_content = body.get("content", "")
        clean_content = self.clean_message_content(raw_content)
        
        # 답글 정보
        reply_to_id = message.get("replyToId")
        is_reply = reply_to_id is not None
        
        # 첨부파일 정보
        attachments = message.get("attachments", [])
        has_attachments = len(attachments) > 0
        attachment_types = [att.get("contentType", "") for att in attachments]
        
        # 멘션 정보
        mentions = message.get("mentions", [])
        has_mentions = len(mentions) > 0
        mentioned_users = [m.get("mentioned", {}).get("displayName", "") for m in mentions]
        
        # 반응 정보
        reactions = message.get("reactions", [])
        has_reactions = len(reactions) > 0
        reaction_types = [r.get("reactionType", "") for r in reactions]
        reaction_count = len(reactions)
        
        # 시간 정보 파싱
        parsed_datetime = None
        hour_of_day = None
        day_of_week = None
        
        if created_datetime:
            try:
                dt = datetime.fromisoformat(created_datetime.replace('Z', '+00:00'))
                parsed_datetime = dt
                hour_of_day = dt.hour
                day_of_week = dt.weekday()  # 0=월요일, 6=일요일
            except:
                pass
        
        return {
            "message_id": message_id,
            "created_datetime": created_datetime,
            "parsed_datetime": parsed_datetime,
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
            "message_type": message_type,
            "chat_id": chat_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "content_type": content_type,
            "raw_content": raw_content,
            "clean_content": clean_content,
            "is_reply": is_reply,
            "reply_to_id": reply_to_id,
            "has_attachments": has_attachments,
            "attachment_types": attachment_types,
            "has_mentions": has_mentions,
            "mentioned_users": mentioned_users,
            "has_reactions": has_reactions,
            "reaction_types": reaction_types,
            "reaction_count": reaction_count,
            "content_length": len(clean_content),
            "word_count": len(clean_content.split()) if clean_content else 0
        }
    
    def preprocess_messages(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        원본 메시지 데이터를 전처리
        
        Args:
            raw_data: load_raw_data()에서 반환된 데이터
            
        Returns:
            List[Dict]: 전처리된 메시지 리스트
        """
        messages = raw_data.get("teams_messages", [])
        processed_messages = []
        
        print(f"📝 메시지 전처리 시작: {len(messages)}개")
        
        for i, message in enumerate(messages):
            try:
                # 메타데이터 추출
                metadata = self.extract_metadata(message)
                
                # 임베딩용 텍스트 준비 (메시지 내용 + 컨텍스트)
                embedding_text = self._prepare_embedding_text(message, metadata)
                
                processed_message = {
                    "id": metadata["message_id"],
                    "text": embedding_text,
                    "clean_content": metadata["clean_content"],
                    "metadata": metadata,
                    "original_message": message  # 원본 메시지도 보관
                }
                
                processed_messages.append(processed_message)
                
                if (i + 1) % 5 == 0:
                    print(f"   진행률: {i+1}/{len(messages)}")
                    
            except Exception as e:
                print(f"⚠️  메시지 {i} 전처리 오류: {e}")
                continue
        
        print(f"✅ 전처리 완료: {len(processed_messages)}개 메시지")
        return processed_messages
    
    def _prepare_embedding_text(self, message: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """
        임베딩을 위한 텍스트 준비 (내용 + 컨텍스트 정보)
        
        Args:
            message: 원본 메시지
            metadata: 추출된 메타데이터
            
        Returns:
            str: 임베딩용 텍스트
        """
        text_parts = []
        
        # 메인 내용
        clean_content = metadata["clean_content"]
        if clean_content:
            text_parts.append(clean_content)
        
        # 발신자 정보 추가
        sender_name = metadata["sender_name"]
        if sender_name:
            text_parts.append(f"발신자: {sender_name}")
        
        # 메시지 타입 정보
        message_type = metadata["message_type"]
        if message_type == "post":
            text_parts.append("게시물")
        
        # 첨부파일 정보
        if metadata["has_attachments"]:
            attachment_types = metadata["attachment_types"]
            text_parts.append(f"첨부파일: {', '.join(attachment_types)}")
        
        # 멘션 정보
        if metadata["has_mentions"]:
            mentioned_users = metadata["mentioned_users"]
            text_parts.append(f"멘션: {', '.join(mentioned_users)}")
        
        # 시간 컨텍스트
        if metadata["hour_of_day"] is not None:
            hour = metadata["hour_of_day"]
            if 6 <= hour < 12:
                text_parts.append("오전 메시지")
            elif 12 <= hour < 18:
                text_parts.append("오후 메시지")
            elif 18 <= hour < 22:
                text_parts.append("저녁 메시지")
            else:
                text_parts.append("야간 메시지")
        
        return " | ".join(text_parts)
    
    def generate_embeddings(self, processed_messages: List[Dict[str, Any]], batch_size: int = 10) -> List[Dict[str, Any]]:
        """
        메시지들의 임베딩 생성
        
        Args:
            processed_messages: 전처리된 메시지 리스트
            batch_size: 배치 크기
            
        Returns:
            List[Dict]: 임베딩이 추가된 메시지 리스트
        """
        print(f"🔮 임베딩 생성 시작: {len(processed_messages)}개 메시지")
        
        # 배치별로 처리
        for i in range(0, len(processed_messages), batch_size):
            batch = processed_messages[i:i+batch_size]
            texts = [msg["text"] for msg in batch]
            
            try:
                # OpenAI API 호출
                response = self.openai_client.embeddings.create(
                    input=texts,
                    model=self.embedding_model
                )
                
                # 각 메시지에 임베딩 추가
                for j, embedding_data in enumerate(response.data):
                    processed_messages[i + j]["embedding"] = embedding_data.embedding
                
                print(f"   임베딩 완료: {i+1}-{min(i+batch_size, len(processed_messages))}/{len(processed_messages)}")
                
            except Exception as e:
                print(f"⚠️  배치 {i//batch_size + 1} 임베딩 생성 오류: {e}")
                # 오류 발생시 해당 배치는 건너뛰기
                for j in range(len(batch)):
                    processed_messages[i + j]["embedding"] = None
        
        # 임베딩 생성 성공한 메시지만 필터링
        valid_messages = [msg for msg in processed_messages if msg.get("embedding") is not None]
        
        print(f"✅ 임베딩 생성 완료: {len(valid_messages)}개 성공")
        return valid_messages
    
    def setup_chroma_collection(self) -> any:
        """
        ChromaDB 컬렉션 설정
        
        Returns:
            Collection: ChromaDB 컬렉션 객체
        """
        try:
            # 기존 컬렉션이 있으면 삭제 (재생성)
            try:
                existing_collection = self.chroma_client.get_collection(name=self.collection_name)
                self.chroma_client.delete_collection(name=self.collection_name)
                print(f"🗑️  기존 컬렉션 '{self.collection_name}' 삭제됨")
            except:
                pass  # 컬렉션이 없었음
            
            # 새 컬렉션 생성
            collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "Teams 메시지 벡터 저장소"}
            )
            
            print(f"✅ ChromaDB 컬렉션 '{self.collection_name}' 생성 완료")
            return collection
            
        except Exception as e:
            raise RuntimeError(f"ChromaDB 컬렉션 설정 실패: {e}")
    
    def store_to_chroma(self, messages_with_embeddings: List[Dict[str, Any]]) -> bool:
        """
        임베딩된 메시지를 ChromaDB에 저장
        
        Args:
            messages_with_embeddings: 임베딩이 포함된 메시지 리스트
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            collection = self.setup_chroma_collection()
            
            print(f"💾 ChromaDB 저장 시작: {len(messages_with_embeddings)}개 메시지")
            
            # 데이터 준비
            ids = []
            embeddings = []
            documents = []
            metadatas = []
            
            for msg in messages_with_embeddings:
                # ID 생성 (메시지 ID + 체크섬)
                msg_id = msg["id"]
                checksum = hashlib.md5(msg["text"].encode()).hexdigest()[:8]
                doc_id = f"{msg_id}_{checksum}"
                
                ids.append(doc_id)
                embeddings.append(msg["embedding"])
                documents.append(msg["clean_content"])  # 검색 시 반환될 텍스트
                metadatas.append({
                    "message_id": msg["metadata"]["message_id"],
                    "sender_name": msg["metadata"]["sender_name"],
                    "sender_id": msg["metadata"]["sender_id"],
                    "created_datetime": msg["metadata"]["created_datetime"],
                    "message_type": msg["metadata"]["message_type"],
                    "chat_id": msg["metadata"]["chat_id"],
                    "is_reply": msg["metadata"]["is_reply"],
                    "has_attachments": msg["metadata"]["has_attachments"],
                    "has_mentions": msg["metadata"]["has_mentions"],
                    "reaction_count": msg["metadata"]["reaction_count"],
                    "content_length": msg["metadata"]["content_length"],
                    "word_count": msg["metadata"]["word_count"],
                    "hour_of_day": msg["metadata"]["hour_of_day"],
                    "day_of_week": msg["metadata"]["day_of_week"]
                })
            
            # ChromaDB에 벌크 추가
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            
            print(f"✅ ChromaDB 저장 완료: {len(ids)}개 메시지")
            
            # 저장 확인
            count = collection.count()
            print(f"📊 컬렉션 내 총 문서 수: {count}")
            
            return True
            
        except Exception as e:
            print(f"❌ ChromaDB 저장 실패: {e}")
            return False
    
    def process_and_store(self) -> bool:
        """
        전체 파이프라인 실행: 로드 → 전처리 → 임베딩 → 저장
        
        Returns:
            bool: 전체 프로세스 성공 여부
        """
        try:
            print("🚀 Teams 데이터 처리 파이프라인 시작")
            print("=" * 50)
            
            # 1. 원본 데이터 로드
            raw_data = self.load_raw_data()
            
            # 2. 메시지 전처리
            processed_messages = self.preprocess_messages(raw_data)
            
            if not processed_messages:
                print("❌ 전처리된 메시지가 없습니다.")
                return False
            
            # 3. 임베딩 생성
            messages_with_embeddings = self.generate_embeddings(processed_messages)
            
            if not messages_with_embeddings:
                print("❌ 임베딩이 생성된 메시지가 없습니다.")
                return False
            
            # 4. ChromaDB 저장
            success = self.store_to_chroma(messages_with_embeddings)
            
            if success:
                print("=" * 50)
                print("🎉 Teams 데이터 처리 파이프라인 완료!")
                print(f"   - 처리된 메시지: {len(messages_with_embeddings)}개")
                print(f"   - ChromaDB 경로: {self.chroma_db_path}")
            
            return success
            
        except Exception as e:
            print(f"❌ 파이프라인 실행 실패: {e}")
            return False
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        ChromaDB 컬렉션 정보 조회
        
        Returns:
            Dict: 컬렉션 통계 정보
        """
        try:
            collection = self.chroma_client.get_collection(name=self.collection_name)
            
            count = collection.count()
            
            # 샘플 문서 조회
            sample_results = collection.peek(limit=3)
            
            info = {
                "collection_name": self.collection_name,
                "total_documents": count,
                "chroma_db_path": self.chroma_db_path,
                "sample_documents": {
                    "ids": sample_results.get("ids", []),
                    "documents": sample_results.get("documents", []),
                    "metadatas": sample_results.get("metadatas", [])
                }
            }
            
            return info
            
        except Exception as e:
            return {"error": f"컬렉션 정보 조회 실패: {e}"}


# 실행 예시 및 테스트
if __name__ == "__main__":
    # 프로세서 초기화
    processor = TeamsDataProcessor()
    
    # 전체 파이프라인 실행
    success = processor.process_and_store()
    
    if success:
        # 결과 확인
        info = processor.get_collection_info()
        print("\n📊 최종 결과:")
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print("💥 처리 실패")
