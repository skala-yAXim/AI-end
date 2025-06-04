import json
import re
import sys
import os
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import OPENAI_API_KEY, DATA_DIR

client = QdrantClient(
    host="localhost",
    port=6333
)

embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")

collection_name = "teams-posts"

if not client.collection_exists(collection_name):
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )

qdrant_store = QdrantVectorStore(
    client=client,
    collection_name=collection_name,
    embedding=embedding_model
)

def clean_html(raw_html):
    return re.sub(r'<[^>]+>', '', raw_html)

def extract_texts_from_json(json_data):
    docs = [] # VectorDB에 저장할 문서
    for post in json_data["posts"]:
        docs.append(parse_json(post))

        if post.get("replies", []):

            for reply in post["replies"]:
                docs.append(
                    parse_json(
                        data=reply, 
                        is_reply=True, 
                        post_content=post.get("content")
                    )
                )

    qdrant_store.add_texts(
        texts=[doc["text"] for doc in docs],
        metadatas=[doc["metadata"] for doc in docs]
    )

    return docs

def parse_json(data:dict, 
               is_reply:bool = False, 
               post_content:str = None) -> dict:
    """
    JSON 데이터를 파싱하여 텍스트와 메타데이터를 추출합니다.
    :param data: JSON 데이터
    :param is_reply: 댓글인지 여부
    :param post_content: 원본 게시글 내용 (댓글인 경우)
    :return: 파싱된 텍스트와 메타데이터를 포함하는 딕셔너리
    """
    
    text_parts = []

    if is_reply:
        text_parts.append("Reply to: " + clean_html(post_content))
        text_parts.append("Reply Content: " + clean_html(data["content"]))
    else:
        if data.get("subject"):
            text_parts.append(f"Subject: {data['subject']}")
        if data.get("content"):
                text_parts.append(clean_html(data["content"]))
        if data.get("application_content"):
            text_parts.extend(data["application_content"])

    if data.get("attachments"):
        for attachment in data["attachments"]:
            text_parts.append(f"Attachment: {attachment}")

    combined_text = "\n".join(text_parts)
    
    return {
            "text": combined_text.strip(),
            "metadata": {
                "author": data["author"],
                "date": data["date"],  # ISO 형식 문자열로 저장
                "source": "teams"
            }
        }

# 사용 예시
with open(DATA_DIR + "/teams_posts_data_week1.json", encoding="utf-8") as f:
    json_data = json.load(f)

parsed_docs = extract_texts_from_json(json_data)

# 출력 예시
for d in parsed_docs:
    print("-----")
    print("텍스트 내용:")
    print(d["text"])
    print("메타데이터:")
    print(d["metadata"])
    