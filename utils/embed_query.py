from sentence_transformers import SentenceTransformer
from typing import List
from core.config import EMBEDDING_MODEL

def embed_query(query: str) -> List[float]:
    """
    입력 쿼리를 의미 벡터로 임베딩하여 Qdrant 검색에 사용 가능하도록 변환
    """
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    
    return embedding_model.encode(query).tolist()
