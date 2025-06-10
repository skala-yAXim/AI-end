# core/vector_db_retriever.py
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
import json 

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, DatetimeRange

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core import config 

# scroll API 사용 시 한 번에 가져올 기본 최대 문서 수
DEFAULT_SCROLL_LIMIT = 50

def _format_qdrant_points(points: List[Any], field_name: str = "page_content") -> List[Dict]:
    """ 구조 변환 : Qdrant PointStruct 리스트를 Dict 리스트로 변환. """
    formatted_docs = []
    for point in points:
        payload = point.payload if point.payload else {}
        page_content = payload.get(field_name, "")
        
        # payload에서 page_content로 사용된 키를 제외한 나머지를 metadata로 구성
        metadata_from_payload = {k: v for k, v in payload.items() if k not in field_name}
        
        formatted_doc = {
            "page_content": page_content,
            "metadata": metadata_from_payload,
            "id": str(point.id), 
        }
        formatted_docs.append(formatted_doc)
    return formatted_docs

def _format_qdrant_points_for_documents(points: List[Any]) -> List[Dict]:
    formatted_docs = []
    for point in points:
        payload = point.payload if point.payload else {}
        title = payload.get("title", "")
        metadata = {k: v for k, v in payload.items() if k not in ["title", "page_content"]}
        
        formatted_docs.append({
            "page_content": title,
            "metadata": metadata,
            "id": str(point.id),
        })
    return formatted_docs

def _create_date_filter(target_date_str: str, date_field_in_db: str = "date") -> Optional[FieldCondition]:
    """주어진 날짜를 기준으로 1일 필터. """
    if not target_date_str:
        return None
    try:
        date_obj = datetime.strptime(target_date_str, "%Y-%m-%d")
        start_datetime_utc = datetime(date_obj.year, date_obj.month, date_obj.day, 0, 0, 0, tzinfo=timezone.utc)
        end_datetime_utc = datetime(date_obj.year, date_obj.month, date_obj.day, 23, 59, 59, 999999, tzinfo=timezone.utc)
        
        return FieldCondition(
            key=date_field_in_db, 
            range=DatetimeRange(
                gte=start_datetime_utc.isoformat().replace("+00:00", "Z"),
                lte=end_datetime_utc.isoformat().replace("+00:00", "Z")
            )
        )
    except ValueError:
        print(f"VectorDBRetriever: 경고 - 잘못된 날짜 형식: {target_date_str}. 날짜 필터링을 건너뜁니다.")
        return None

# --- Documents ---
def retrieve_documents(
    qdrant_client: QdrantClient,
    user_id: str,
    target_date_str: Optional[str] = None,
    scroll_limit: int = DEFAULT_SCROLL_LIMIT
) -> List[Dict]:
    """
    'Documents' 컬렉션에서 특정 사용자의 문서를 검색합니다. (scroll API 사용)
    필터: author 필드를 user_id로 필터링. 날짜 필터링.
    """
    print(f"VectorDBRetriever: '{config.COLLECTION_DOCUMENTS}' 컬렉션 scroll 검색 중 (author: {user_id}, limit: {scroll_limit})")
    
    must_conditions = [
        FieldCondition(key="author", match=MatchValue(value=user_id))
    ]
    date_filter_condition = _create_date_filter(target_date_str, "last_modified") 
    if date_filter_condition:
        must_conditions.append(date_filter_condition)

    qdrant_final_filter = Filter(must=must_conditions)

    try:
        points, _next_offset = qdrant_client.scroll(
            collection_name=config.COLLECTION_DOCUMENTS,
            scroll_filter=qdrant_final_filter,
            limit=scroll_limit,
            with_payload=True,
            with_vectors=False # 당장에는 벡터 자체는 제거. 차후에는 변경가능.
        )
        formatted_docs = _format_qdrant_points_for_documents(points)
        print(f"VectorDBRetriever: '{config.COLLECTION_DOCUMENTS}'에서 {len(formatted_docs)}개 문서 발견 (author: {user_id}).")
        return formatted_docs
    except Exception as e:
        print(f"VectorDBRetriever: Documents 검색 중 오류 (scroll API): {e}")
        return []


# --- Emails ---
def retrieve_emails(
    qdrant_client: QdrantClient,
    # embeddings_model: Embeddings,
    user_id: str, 
    target_date_str: Optional[str] = None,
    scroll_limit: int = DEFAULT_SCROLL_LIMIT
) -> List[Dict]:
    """
    'Emails' 컬렉션에서 특정 사용자의 이메일을 검색합니다. (scroll API 사용)
    필터: author 필드가 user_id와 일치. metadata.date로 날짜 필터링.
    """
    print(f"VectorDBRetriever: '{config.COLLECTION_EMAILS}' 컬렉션 scroll 검색 중 (user_id: {user_id}, 날짜: {target_date_str or '전체'}, limit: {scroll_limit})")
    
    must_conditions = [
        FieldCondition(key="author", match=MatchValue(value=user_id))
    ]

    
    date_filter_condition = _create_date_filter(target_date_str, "date") 
    if date_filter_condition:
        must_conditions.append(date_filter_condition)

    qdrant_final_filter = Filter(must=must_conditions)

    try:
        points, _next_offset = qdrant_client.scroll(
            collection_name=config.COLLECTION_EMAILS,
            scroll_filter=qdrant_final_filter,
            limit=scroll_limit,
            with_payload=True,
            with_vectors=False
        )
        formatted_docs = _format_qdrant_points(points)
        print(f"VectorDBRetriever: '{config.COLLECTION_EMAILS}'에서 {len(formatted_docs)}개 이메일 발견.")
        return formatted_docs
    except Exception as e:
        print(f"VectorDBRetriever: Emails 검색 중 오류 (scroll API): {e}")
        return []

# --- Git ---
def retrieve_git_activities(
    qdrant_client: QdrantClient,
    git_author_identifier: str,
    target_date_str: Optional[str],
    scroll_limit: int = DEFAULT_SCROLL_LIMIT
) -> List[Dict]:
    """
    Git 활동 로그 전체를 scroll로 한 번에 조회합니다.
    author, 날짜 기준 필터링만 수행하며, event_type별 분리는 하지 않습니다.
    """
    print(f"VectorDBRetriever: Git 활동 전체 조회 (author: {git_author_identifier}, date: {target_date_str})")
    
    must_conditions = [
        FieldCondition(
            key="author",
            match=MatchValue(value=git_author_identifier)
        )
    ]
    
    date_filter_condition = _create_date_filter(target_date_str, "date")
    if date_filter_condition:
        must_conditions.append(date_filter_condition)
    
    qdrant_filter = Filter(must=must_conditions)

    try:
        points, _ = qdrant_client.scroll(
            collection_name=config.COLLECTION_GIT_ACTIVITIES,
            scroll_filter=qdrant_filter,
            limit=scroll_limit,
            with_payload=True,
            with_vectors=False
        )
        formatted_event_docs = _format_qdrant_points(points)
        print(f"VectorDBRetriever: Git 활동 {len(formatted_event_docs)}개 조회 완료.")
        return formatted_event_docs
    except Exception as e:
        print(f"VectorDBRetriever: Git 활동 조회 중 오류: {e}")
        return []


# --- Teams Posts ---
def retrieve_teams_posts(
    qdrant_client: QdrantClient,
    # embeddings_model: Embeddings,
    user_id: str, 
    target_date_str: Optional[str] = None,
    scroll_limit: int = DEFAULT_SCROLL_LIMIT
) -> List[Dict]:
    """
    'Teams-Posts' 컬렉션에서 특정 사용자의 Teams 메시지/게시물을 검색합니다. (scroll API 사용)
    필터: metadata.user_id 필드를 State의 user_id로 필터링. metadata.date로 날짜 필터링.
    """
    print(f"VectorDBRetriever: '{config.COLLECTION_TEAMS_POSTS}' 컬렉션 scroll 검색 중 (user_id: {user_id}, 날짜: {target_date_str or '전체'}, limit: {scroll_limit})")
    must_conditions = [
        FieldCondition(key="user_id", match=MatchValue(value=user_id)) # 실제 Teams 사용자 ID 필드명
    ]
    
    date_filter_condition = _create_date_filter(target_date_str, "date") # 실제 Teams 게시물 날짜 필드명
    if date_filter_condition:
        must_conditions.append(date_filter_condition)

    qdrant_filter = Filter(must=must_conditions)

    try:
        points, _next_offset = qdrant_client.scroll(
            collection_name=config.COLLECTION_TEAMS_POSTS,
            scroll_filter=qdrant_filter,
            limit=scroll_limit,
            with_payload=True,
            with_vectors=False
        )
        formatted_docs = _format_qdrant_points(points)
        print(f"VectorDBRetriever: '{config.COLLECTION_TEAMS_POSTS}'에서 {len(formatted_docs)}개 Teams 게시물 발견.")
        return formatted_docs
    except Exception as e:
        print(f"VectorDBRetriever: Teams 게시물 검색 중 오류 (scroll API): {e}")
        return []


# --- WBS Data ---
def retrieve_wbs_data(
    qdrant_client: QdrantClient,
    project_id: Optional[str] = None,
    scroll_limit: int = DEFAULT_SCROLL_LIMIT
) -> List[Dict]:
    """
    'WBSData' 컬렉션에서 WBS 정보를 검색합니다. (scroll API 사용)
    필터: project_id가 있으면 해당 프로젝트만, 없으면 전체 조회
    """
    print(f"VectorDBRetriever: '{config.COLLECTION_WBS_DATA}' 컬렉션 scroll 검색 중 (project_id: {project_id or '전체'}, limit: {scroll_limit})")
    
    must_conditions = []
    if project_id:
        must_conditions.append(
            FieldCondition(key="project_id", match=MatchValue(value=project_id))
        )
    
    # project_id가 없으면 필터 없이 전체 조회
    qdrant_filter = Filter(must=must_conditions) if must_conditions else None
    
    try:
        points, _next_offset = qdrant_client.scroll(
            collection_name=config.COLLECTION_WBS_DATA,
            scroll_filter=qdrant_filter,
            limit=scroll_limit,
            with_payload=True,
            with_vectors=False
        )
        formatted_docs = _format_qdrant_points(points, "deliverables")
        print(f"VectorDBRetriever: '{config.COLLECTION_WBS_DATA}'에서 {len(formatted_docs)}개 WBS 데이터 발견.")
        return formatted_docs
    except Exception as e:
        print(f"VectorDBRetriever: WBS 데이터 검색 중 오류 (scroll API): {e}")
        return []


def retrieve_documents_for_wbs_matching(
    qdrant_client: QdrantClient,
    user_id: str,
    deliverable_keywords: Optional[List[str]] = None,
    scroll_limit: int = DEFAULT_SCROLL_LIMIT
) -> List[Dict]:
    """
    WBS 매칭을 위한 특화된 문서 검색입니다.
    기본 retrieve_documents와 동일하지만, deliverable_keywords 힌트를 활용할 수 있습니다.
    """
    print(f"VectorDBRetriever: WBS 매칭용 문서 검색 (author: {user_id}, keywords: {deliverable_keywords or '전체'}, limit: {scroll_limit})")
    
    must_conditions = [
        FieldCondition(key="author", match=MatchValue(value=user_id))
    ]
    
    # 향후 deliverable_keywords를 활용한 고급 필터링 추가 가능
    # 현재는 기본 문서 검색과 동일하게 동작
    
    qdrant_final_filter = Filter(must=must_conditions)
    
    try:
        points, _next_offset = qdrant_client.scroll(
            collection_name=config.COLLECTION_DOCUMENTS,
            scroll_filter=qdrant_final_filter,
            limit=scroll_limit,
            with_payload=True,
            with_vectors=False
        )
        # WBS 매칭용이므로 전체 page_content 포함하여 반환
        formatted_docs = _format_qdrant_points(points, "page_content")
        print(f"VectorDBRetriever: WBS 매칭용 문서 {len(formatted_docs)}개 발견 (author: {user_id}).")
        return formatted_docs
    except Exception as e:
        print(f"VectorDBRetriever: WBS 매칭용 문서 검색 중 오류 (scroll API): {e}")
        return []
