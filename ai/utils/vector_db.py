from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct, Distance, VectorParams, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer # 직접 SentenceTransformer 사용
import json
from typing import Dict, List, Any, Optional, Union
import uuid
import numpy
import traceback # 디버깅을 위해 추가

from core.config import COLLECTION_WBS_DATA, QDRANT_HOST
# 임베딩 모델 정보
DEFAULT_SENTENCE_TRANSFORMER_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

class VectorDBHandler:
    """VectorDB(Qdrant) 관련 처리를 담당하는 클래스 (SentenceTransformer 임베딩 전용, 차원 동적 로드)"""

    def __init__(self, project_id: str, collection_name_prefix: str = COLLECTION_WBS_DATA,
                 sentence_transformer_model_name: str = DEFAULT_SENTENCE_TRANSFORMER_MODEL, **kwargs):
        if not project_id:
            raise ValueError("VectorDBHandler 초기화: project_id가 필요합니다.")

        if 'embedding_api_key' in kwargs:
            print(f"경고: 'embedding_api_key' 인자가 VectorDBHandler에 전달되었으나, SentenceTransformer 전용 모드에서는 사용되지 않고 무시됩니다.")

        self.project_id = project_id
        self.collection_name = f"{collection_name_prefix}"

        try:
            self.client = QdrantClient(host=QDRANT_HOST, port=6333)
        except Exception as e:
            raise RuntimeError(f"Qdrant 클라이언트 초기화 실패 : {e}")

        self.embedding_model_name = sentence_transformer_model_name
        self.embedding_model = None  # 임베딩 모델은 필요할 때 초기화
        self.embedding_dim = 384    # 임베딩 차원도 필요할 때 설정

        try:
            collection_exists = False
            current_config_dim = -1 # 컬렉션 차원 초기화
            try:
                collection_info = self.client.get_collection(collection_name=self.collection_name)
                if collection_info:
                    vectors_config = collection_info.config.params.vectors
                    if isinstance(vectors_config, models.VectorParams):
                        current_config_dim = vectors_config.size
                    elif isinstance(vectors_config, dict):
                        default_vector_config = vectors_config.get('') or vectors_config.get(models.DEFAULT_VECTOR_NAME)
                        if default_vector_config:
                            current_config_dim = default_vector_config.size
                        elif vectors_config: # 명명된 벡터만 있는 경우 첫 번째 것을 기준으로 함
                            first_named_vector_config = next(iter(vectors_config.values()))
                            current_config_dim = first_named_vector_config.size
                    
                    if current_config_dim != -1 and current_config_dim != self.embedding_dim:
                         print(f"경고: 기존 컬렉션 '{self.collection_name}'의 벡터 차원({current_config_dim})이 현재 모델('{self.embedding_model_name}')의 임베딩 차원({self.embedding_dim})과 다릅니다. "
                               "데이터 일관성 문제가 발생할 수 있습니다. 컬렉션을 재 생성하거나 모델 설정을 확인하세요.")
                collection_exists = True
            except Exception as e:
                error_str = str(e).lower()
                if "not found" in error_str or "status_code=404" in error_str or "not_found" in error_str or "NOT_FOUND" in str(e).upper() :
                     collection_exists = False
                else:
                    raise RuntimeError(f"Qdrant 컬렉션 '{self.collection_name}' 정보 조회 실패: {e}")

            if not collection_exists:
                print(f"Qdrant 컬렉션 '{self.collection_name}' 생성 중 (벡터 크기: {self.embedding_dim}, 거리 함수: COSINE)...")
                self.client.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.embedding_dim, distance=Distance.COSINE)
                )
                print(f"Qdrant 컬렉션 '{self.collection_name}' 생성 완료.")
            else:
                print(f"Qdrant 컬렉션 '{self.collection_name}'이 이미 존재합니다. 설정된 벡터 차원: {current_config_dim if current_config_dim != -1 else '확인 안됨'}.")

        except Exception as e:
            raise RuntimeError(f"Qdrant 컬렉션 '{self.collection_name}' 처리 중 오류: {e}")

        print(f"VectorDBHandler(Qdrant, SentenceTransformer) 초기화 완료. , 컬렉션: {self.collection_name}, 임베딩 모델: {self.embedding_model_name} (차원: {self.embedding_dim})")

    def _initialize_embedding_model(self):
        """임베딩 모델을 초기화합니다. 필요할 때만 호출됩니다."""
        if self.embedding_model is None:
            try:
                print(f"SentenceTransformer 모델 '{self.embedding_model_name}' 로드 중...")
                self.embedding_model = SentenceTransformer(self.embedding_model_name)
                self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
                print(f"SentenceTransformer 모델 로드 완료. 모델 '{self.embedding_model_name}'의 임베딩 차원은 {self.embedding_dim}입니다.")
            except Exception as model_load_e:
                raise ValueError(
                    f"SentenceTransformer 모델 '{self.embedding_model_name}' 로드 또는 차원 확인에 실패했습니다. "
                    f"모델 이름이 정확한지, 모델 파일이 올바르게 다운로드되었는지 확인하세요. 원본 오류: {model_load_e}"
                )
                
    def initialize_embedding_model(self):
        """외부에서 호출 가능한 임베딩 모델 초기화 메서드"""
        self._initialize_embedding_model()

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """텍스트 리스트를 임베딩 벡터 리스트(List[List[float]])로 변환합니다."""
        if not texts:
            return []
            
        # 임베딩 모델이 초기화되지 않았다면 초기화
        if self.embedding_model is None:
            self._initialize_embedding_model()
            
        try:
            raw_embeddings: numpy.ndarray = self.embedding_model.encode(texts, convert_to_numpy=True)

            if not isinstance(raw_embeddings, numpy.ndarray):
                 raise ValueError(f"SentenceTransformer.encode 결과가 예상치 못한 타입입니다 (numpy.ndarray 기대): {type(raw_embeddings)}")

            embeddings_as_lists: List[List[float]] = []
            if raw_embeddings.ndim == 1:
                embeddings_as_lists.append(raw_embeddings.tolist())
            elif raw_embeddings.ndim == 2:
                for emb_vector in raw_embeddings:
                    embeddings_as_lists.append(emb_vector.tolist())
            else:
                raise ValueError(f"SentenceTransformer.encode 결과가 예상치 못한 차원의 NumPy 배열입니다: {raw_embeddings.ndim}D")

            return embeddings_as_lists
        except Exception as e:
            print(f"텍스트 임베딩 중 오류 (모델: {self.embedding_model_name}): {e}")
            traceback.print_exc()
            raise

    def get_stored_wbs_hash(self) -> Optional[str]:
        """DB에서 현재 프로젝트의 저장된 WBS 파일 해시를 조회합니다."""
        try:
            scroll_filter = Filter(
                must=[
                    FieldCondition(key="project_id", match=MatchValue(value=self.project_id)),
                ]
            )
            results, _next_page_offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=1,
                with_payload=True,
                with_vectors=False
            )
            if results:
                payload = results[0].payload
                if payload and isinstance(payload, dict):
                    return payload.get('wbs_hash')
        except Exception as e:
            print(f"저장된 WBS 해시 조회 중 오류 또는 데이터 없음 (컬렉션: {self.collection_name}, 프로젝트 ID: {self.project_id}): {e}")
        return None

    def clear_project_data(self):
        """DB에서 현재 프로젝트 ID와 관련된 모든 데이터를 삭제합니다."""
        print(f"프로젝트 '{self.project_id}'의 데이터 삭제 시도 (컬렉션: {self.collection_name})...")
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(key="project_id", match=models.MatchValue(value=self.project_id))
                        ]
                    )
                ),
                wait=True
            )
            print(f"프로젝트 '{self.project_id}' 데이터 삭제 완료 (또는 해당 프로젝트 ID로 삭제할 데이터 없음).")
        except Exception as e:
            print(f"프로젝트 데이터 삭제 중 오류 (프로젝트: {self.project_id}, 컬렉션: {self.collection_name}): {e}")


    def _prepare_item_for_storage(self, item_dict: Dict[str, Any], item_type: str, wbs_hash: str,
                                 id_counter: int, assignee_name_for_workload: Optional[str] = None) -> Optional[tuple]:
        """단일 항목을 저장 가능한 형태(문서 텍스트, 페이로드, ID)로 준비합니다."""
        if not isinstance(item_dict, dict):
            print(f"경고: 저장할 {item_type} 항목이 딕셔너리가 아닙니다. 건너뜁니다: {item_dict}")
            return None

        doc_text_parts = [f"유형: {item_type}"]
        payload = {
            "project_id": self.project_id,
            "wbs_hash": wbs_hash,
            "original_data": json.dumps(item_dict, ensure_ascii=False, sort_keys=True)
        }

        task_id = item_dict.get('task_id')
        task_name = item_dict.get('task_name')
        assignee = item_dict.get('assignee')
        if task_name: doc_text_parts.append(f"작업명: {task_name}")
        if task_id: payload["task_id"] = str(task_id)
        if assignee: payload["assignee"] = str(assignee)
        if item_dict.get('deliverables'): payload["has_deliverables"] = True

        doc_text = ", ".join(filter(None, doc_text_parts))
        unique_id = str(uuid.uuid4())

        return doc_text, payload, unique_id


    def store_llm_analysis_results(self, llm_output_dict: Dict[str, Any], wbs_hash: str):
        """LLM 분석 결과를 청킹(항목별 분리)하여 VectorDB(Qdrant)에 저장합니다."""
        if not llm_output_dict or not isinstance(llm_output_dict, dict):
            print("저장할 LLM 분석 결과가 없거나 유효하지 않습니다.")
            return

        items_to_process: List[tuple] = []
        current_id_counter = 0

        print(f"LLM 분석 결과 VectorDB(Qdrant) 저장 준비 중 (컬렉션: {self.collection_name})...")

        
        task_list_data = llm_output_dict.get("task_list", [])
        if isinstance(task_list_data, list):
            for task_item in task_list_data:
                prepared_item = self._prepare_item_for_storage(task_item, "task_item", wbs_hash, current_id_counter)
                if prepared_item: items_to_process.append(prepared_item); current_id_counter += 1
        elif task_list_data is not None:
            print(f"경고: 'task_list' 데이터가 예상한 리스트 형태가 아닙니다: {type(task_list_data)}")

        if not items_to_process:
            print("LLM 분석 결과에서 VectorDB에 저장할 청크된 데이터가 없습니다.")
            return

        docs_to_embed = [item[0] for item in items_to_process]
        payloads = [item[1] for item in items_to_process]
        ids_for_points = [item[2] for item in items_to_process]

        print(f"텍스트 {len(docs_to_embed)}건 임베딩 진행 중 (모델: {self.embedding_model_name})...")
        try:
            vectors = self._get_embeddings(docs_to_embed)
        except Exception as e:
            print(f"임베딩 생성 중 심각한 오류 발생: {e}. 데이터 저장을 중단합니다.")
            return

        if not vectors or len(vectors) != len(items_to_process):
            print(f"오류: 임베딩 결과 수({len(vectors) if vectors else 0})와 처리할 항목 수({len(items_to_process)})가 일치하지 않거나 임베딩 결과가 없습니다. 데이터 저장을 중단합니다.")
            return

        points_to_add = []
        for i in range(len(ids_for_points)):
            if isinstance(vectors[i], list) and all(isinstance(x, float) for x in vectors[i]):
                if isinstance(payloads[i], dict):
                    points_to_add.append(PointStruct(id=ids_for_points[i], vector=vectors[i], payload=payloads[i]))
                else:
                    print(f"경고: ID {ids_for_points[i]}의 페이로드가 딕셔너리가 아닙니다 (타입: {type(payloads[i])}). 해당 포인트 저장 건너뜁니다.")
            else:
                print(f"경고: ID {ids_for_points[i]}의 벡터가 List[float] 형태가 아닙니다 (타입: {type(vectors[i])}). 해당 포인트 저장 건너뜁니다.")


        if points_to_add:
            print(f"VectorDB(Qdrant)에 새로운 포인트 {len(points_to_add)}개 추가/업데이트 중 (컬렉션: {self.collection_name})...")
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points_to_add,
                    wait=True
                )
                print(f"데이터 {len(points_to_add)}건 추가/업데이트 완료.")
            except Exception as e:
                print(f"VectorDB(Qdrant)에 데이터 추가/업데이트 중 오류 발생: {e}")
                if points_to_add:
                    print(f"  오류 발생 시 첫 번째 포인트 ID (샘플): {points_to_add[0].id}")
                    try:
                        payload_sample = str(points_to_add[0].payload)[:200] + "..." if points_to_add[0].payload else "None"
                        print(f"  오류 발생 시 첫 번째 포인트 페이로드 (샘플): {payload_sample}")
                    except Exception as log_e:
                        print(f"  페이로드 샘플 로깅 중 오류: {log_e}")
        else:
            print("VectorDB(Qdrant)에 저장할 유효한 포인트가 없습니다 (임베딩 실패, 데이터 형식 오류 또는 모든 항목이 필터링됨).")

    def add_texts_with_metadata(self, texts: List[str], metadatas: List[Dict], ids: List[str]):
        """제공된 텍스트, 메타데이터(페이로드), ID를 사용하여 VectorDB(Qdrant) 컬렉션에 포인트를 추가/업데이트합니다."""
        if not (texts and metadatas and ids):
            print("경고 (add_texts_with_metadata): 추가할 텍스트, 메타데이터 또는 ID 리스트 중 하나 이상이 비어있습니다. 작업을 중단합니다.")
            return

        if not (len(texts) == len(metadatas) == len(ids)):
            print("오류 (add_texts_with_metadata): 텍스트, 메타데이터, ID 리스트의 길이가 일치하지 않습니다. 작업을 중단합니다.")
            print(f"  Texts: {len(texts)}, Metadatas: {len(metadatas)}, IDs: {len(ids)}")
            return

        print(f"텍스트 {len(texts)}건 임베딩 진행 중 (add_texts_with_metadata, 모델: {self.embedding_model_name})...")
        try:
            vectors = self._get_embeddings(texts)
        except Exception as e:
            print(f"임베딩 생성 중 심각한 오류 발생 (add_texts_with_metadata): {e}. 데이터 저장을 중단합니다.")
            return

        if not vectors or len(vectors) != len(texts):
            print(f"오류 (add_texts_with_metadata): 임베딩 결과 수({len(vectors) if vectors else 0})와 텍스트 수({len(texts)})가 일치하지 않거나 임베딩 결과가 없습니다. 데이터 저장을 중단합니다.")
            return

        points_to_add = []
        for i in range(len(ids)):
            if not isinstance(vectors[i], list) or not all(isinstance(x, float) for x in vectors[i]):
                print(f"경고 (add_texts_with_metadata): ID {ids[i]}의 벡터가 List[float] 형태가 아닙니다 (타입: {type(vectors[i])}). 해당 포인트 저장 건너뜁니다.")
                continue
            if not isinstance(metadatas[i], dict):
                print(f"경고 (add_texts_with_metadata): ID {ids[i]}의 메타데이터(페이로드)가 딕셔너리가 아닙니다 (타입: {type(metadatas[i])}). 해당 포인트 저장 건너뜁니다.")
                continue

            points_to_add.append(
                PointStruct(id=ids[i], vector=vectors[i], payload=metadatas[i])
            )

        if points_to_add:
            print(f"VectorDB(Qdrant)에 새로운 포인트 {len(points_to_add)}개 추가/업데이트 중 (컬렉션: {self.collection_name}, via add_texts_with_metadata)...")
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points_to_add,
                    wait=True
                )
                print(f"데이터 {len(points_to_add)}건 추가/업데이트 완료 (via add_texts_with_metadata).")
            except Exception as e:
                print(f"VectorDB(Qdrant)에 데이터 추가/업데이트 중 오류 발생 (add_texts_with_metadata): {e}")
                if points_to_add:
                    print(f"  오류 발생 시 첫 번째 포인트 ID (샘플): {points_to_add[0].id}")
                    try:
                        payload_sample = str(points_to_add[0].payload)[:200] + "..." if points_to_add[0].payload else "None"
                        print(f"  오류 발생 시 첫 번째 포인트 페이로드 (샘플): {payload_sample}")
                    except Exception as log_e:
                        print(f"  페이로드 샘플 로깅 중 오류 (add_texts_with_metadata): {log_e}")
        else:
            print("VectorDB(Qdrant)에 저장할 유효한 포인트가 없습니다 (임베딩 실패, 데이터 형식 오류 또는 모든 항목이 필터링됨, via add_texts_with_metadata).")