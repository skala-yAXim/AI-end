# core/vector_db_retriever.py
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Union, Set, Tuple
import json 

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, DatetimeRange, MatchText
from utils.embed_query import embed_query 
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
    scroll_limit: int = DEFAULT_SCROLL_LIMIT,
    include_readmes: bool = True
) -> Union[List[Dict], Tuple[List[Dict], str]]:
    """
    Git 활동 로그 전체를 scroll로 한 번에 조회합니다.
    include_readmes=True시 해당 사용자가 참여한 저장소들의 README 정보도 함께 반환합니다.
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
        
        # README 조회가 필요한 경우
        if include_readmes:
            # 내가 참여한 저장소 목록 추출
            repo_names = set()
            for activity in formatted_event_docs:
                repo_name = activity.get("metadata", {}).get("repo_name")
                if repo_name:
                    repo_names.add(repo_name)
            
            print(f"VectorDBRetriever: 참여 저장소 {len(repo_names)}개 발견: {repo_names}")
            
            # 해당 저장소들의 README 조회
            readme_info = _get_readmes_by_repo_names(qdrant_client, repo_names)
            return formatted_event_docs, readme_info
        
        return formatted_event_docs
        
    except Exception as e:
        print(f"VectorDBRetriever: Git 활동 조회 중 오류: {e}")
        return [] if not include_readmes else ([], "README 조회 실패")

def _get_readmes_by_repo_names(qdrant_client: QdrantClient, repo_names: Set[str]) -> str:
    """참여한 저장소들의 README 조회"""
    if not repo_names:
        return "README 정보 없음"
    
    try:
        # config에서 정의된 README 컬렉션 이름 사용
        readme_collection_name = config.COLLECTION_GIT_README
        
        # 존재하는 컬렉션 찾기
        collections = qdrant_client.get_collections()
        existing_collections = [c.name for c in collections.collections]
        
        if readme_collection_name in existing_collections:
            readme_collection = readme_collection_name
            print(f"VectorDBRetriever: README 컬렉션 발견: {readme_collection}")
        else:
            print(f"VectorDBRetriever: README 컬렉션({readme_collection_name})을 찾을 수 없음. 더미 데이터 반환.")
            dummy_contents = []
            for repo_name in repo_names:
                dummy_contents.append(f"=== {repo_name} README ===\n프로젝트: {repo_name}\n설명: README 컬렉션을 찾을 수 없습니다.\n")
            return "\n".join(dummy_contents)
        
        # README 컬렉션이 있으면 조회
        readme_contents = []
        for repo_name in repo_names:
            try:
                points, _ = qdrant_client.scroll(
                    collection_name=readme_collection,
                    scroll_filter=Filter(must=[
                        FieldCondition(
                            key="repo_name",
                            match=MatchValue(value=repo_name)
                        )
                    ]),
                    limit=1,
                    with_payload=True,
                    with_vectors=False
                )
                
                if points:
                    content = points[0].payload.get("page_content", "")
                    readme_contents.append(f"=== {repo_name} README ===\n{content}\n")
                    print(f"VectorDBRetriever: {repo_name} README 조회 완료")
                else:
                    print(f"VectorDBRetriever: {repo_name} README 없음")
                    
            except Exception as e:
                print(f"VectorDBRetriever: README 조회 오류 ({repo_name}): {e}")
        
        return "\n".join(readme_contents) if readme_contents else "README 정보 없음"
        
    except Exception as e:
        print(f"VectorDBRetriever: README 컬렉션 확인 중 오류: {e}")
        # 오류 발생 시 더미 데이터 반환
        dummy_contents = []
        for repo_name in repo_names:
            dummy_contents.append(f"=== {repo_name} README ===\n프로젝트: {repo_name}\n설명: README 조회 중 오류가 발생했습니다.\n")
        return "\n".join(dummy_contents)


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


def retrieve_documents_content(
    qdrant_client: QdrantClient,
    document_list: List[Dict],   # file_id, filename 등 포함된 문서 리스트
    queries: List[str],          # LLM이 뽑은 중요 평가 항목 키워드
    top_k: int = 5
) -> List[Dict]:
    """
    문서 리스트와 평가 항목(queries)을 기반으로,
    해당 문서에 속한 page_content에서 의미 있는 chunk들을 hybrid 방식으로 추출
    """

    target_file_names = [doc["filename"] for doc in document_list]
    print(f"VectorDBRetriever: 타겟 파일들: {target_file_names}")

    # 파일 필터: 문서 리스트에 포함된 파일명으로 필터링
    file_conditions = []
    for filename in target_file_names:
        file_conditions.append(
            FieldCondition(key="filename", match=MatchValue(value=filename))
        )
    
    # OR 조건으로 파일 필터 생성
    from qdrant_client.models import Filter
    file_filter = Filter(should=file_conditions)  # should = OR 조건

    retrieved_docs_content = []
    seen_ids = set()
    print(f"VectorDBRetriever: {len(document_list)}개의 문서에서 {len(queries)}개의 쿼리로 검색 시작...")
    for query in queries:
        print(f"VectorDBRetriever: '{query}' 쿼리로 검색 중...")
        try:
            vector = embed_query(query)  # 의미 벡터 임베딩 함수
            
            # Qdrant 검색 (필터 매개변수명 수정)
            results = qdrant_client.search(
                collection_name=config.COLLECTION_DOCUMENTS,
                query_vector=vector,
                limit=top_k,
                with_payload=True,
                query_filter=file_filter,  # filter → query_filter로 변경
                search_params={"hnsw_ef": 128}
            )
            
            for r in results:
                if r.id not in seen_ids:
                    retrieved_docs_content.append({
                        "id": str(r.id),
                        "filename": r.payload.get("filename"),
                        "chunk_id": r.payload.get("chunk_id"),
                        "page_content": r.payload.get("page_content"),
                        "score": r.score
                    })
                    seen_ids.add(r.id)
                    
        except Exception as e:
            print(f"VectorDBRetriever: '{query}' 검색 중 오류: {e}")
            continue

    print(f"VectorDBRetriever: 총 {len(retrieved_docs_content)}개 청크 추출 완료")
    return retrieved_docs_content