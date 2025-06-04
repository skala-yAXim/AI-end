"""
작성자 : 노건표
작성일 : 2025-06-01
작성내용 : 리팩토링 ( VectorDB(ChromaDB) 관련 처리를 담당하는 클래스 )

사용법:
1. 인스턴스 생성: handler = VectorDBHandler(db_base_path, collection_name_prefix, project_id) # sentence_transformer_model_name은 기본값 사용
2. WBS 해시 조회: stored_hash = handler.get_stored_wbs_hash()
3. 프로젝트 데이터 삭제: handler.clear_project_data()
4. LLM 분석 결과 저장 : handler.store_llm_analysis_results(llm_analysis_results, wbs_hash)

업데이트 내역:
작성자 : 노건표
작성일 : 2025-06-04
작성내용 : Qdrant로 벡터DB를 사용하고, SentenceTransformer를 사용하여 텍스트 임베딩을 수행.
          기본 임베딩 모델을 'paraphrase-multilingual-MiniLM-L12-v2'로 변경.
          EMBEDDING_DIMENSIONS 딕셔너리를 사용하지 않고 항상 모델에서 차원을 동적으로 로드하도록 수정.
"""
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct, Distance, VectorParams, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer # 직접 SentenceTransformer 사용
import json
import os
from typing import Dict, List, Any, Optional, Union
import uuid
import numpy
import traceback # 디버깅을 위해 추가

# 임베딩 모델 정보
DEFAULT_SENTENCE_TRANSFORMER_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

class VectorDBHandler:
    """VectorDB(Qdrant) 관련 처리를 담당하는 클래스 (SentenceTransformer 임베딩 전용, 차원 동적 로드)"""

    def __init__(self, db_base_path: str, collection_name_prefix: str, project_id: str,
                 sentence_transformer_model_name: str = DEFAULT_SENTENCE_TRANSFORMER_MODEL, **kwargs):
        if not project_id:
            raise ValueError("VectorDBHandler 초기화: project_id가 필요합니다.")

        if 'embedding_api_key' in kwargs:
            print(f"경고: 'embedding_api_key' 인자가 VectorDBHandler에 전달되었으나, SentenceTransformer 전용 모드에서는 사용되지 않고 무시됩니다.")

        self.project_id = project_id
        safe_project_id = "".join(c if c.isalnum() else "_" for c in project_id)
        self.collection_name = f"{collection_name_prefix}_{safe_project_id}_revised"

        self.db_path = os.path.join(db_base_path, "qdrant_db")
        os.makedirs(self.db_path, exist_ok=True)

        try:
            self.client = QdrantClient(path=self.db_path)
        except Exception as e:
            raise RuntimeError(f"Qdrant 클라이언트 초기화 실패 (경로: {self.db_path}): {e}")

        self.embedding_model_name = sentence_transformer_model_name

        try:
            print(f"정보: 모델 '{self.embedding_model_name}'의 기본 차원을 동적으로 확인합니다...")
            temp_model = SentenceTransformer(self.embedding_model_name)
            self.embedding_dim = temp_model.get_sentence_embedding_dimension()
            print(f"모델 '{self.embedding_model_name}'의 기본 차원은 {self.embedding_dim}(으)로 확인되어 설정되었습니다.")
            del temp_model # 임시 모델 객체 메모리에서 해제
        except Exception as model_load_e:
            raise ValueError(
                f"SentenceTransformer 모델 '{self.embedding_model_name}' 로드 또는 차원 확인에 실패했습니다. "
                f"모델 이름이 정확한지, 모델 파일이 올바르게 다운로드되었는지 확인하세요. 원본 오류: {model_load_e}"
            )

        try:
            print(f"SentenceTransformer 모델 '{self.embedding_model_name}' 로드 중 (차원: {self.embedding_dim})...")
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            print("SentenceTransformer 모델 로드 완료.")
        except Exception as se_init_e:
            raise RuntimeError(f"SentenceTransformer 모델 ('{self.embedding_model_name}') 초기화 실패: {se_init_e}. "
                               "sentence-transformers 라이브러리가 올바르게 설치되었는지, 모델 이름이 정확한지 확인하세요.")

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

        print(f"VectorDBHandler(Qdrant, SentenceTransformer) 초기화 완료. DB 경로: {self.db_path}, 컬렉션: {self.collection_name}, 임베딩 모델: {self.embedding_model_name} (차원: {self.embedding_dim})")

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """텍스트 리스트를 임베딩 벡터 리스트(List[List[float]])로 변환합니다."""
        if not texts:
            return []
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
                    FieldCondition(key="output_type", match=MatchValue(value="project_overview"))
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
            "output_type": item_type,
            "original_data": json.dumps(item_dict, ensure_ascii=False, sort_keys=True)
        }

        if item_type == "project_overview":
            if "summary_text" in item_dict:
                doc_text_parts.append(f"요약: {item_dict['summary_text']}")
                payload["summary_text"] = item_dict['summary_text']
            if "total_tasks" in item_dict:
                doc_text_parts.append(f"총 작업 수: {item_dict['total_tasks']}")
                payload["total_tasks"] = item_dict['total_tasks']

        elif item_type == "task_item":
            task_id = item_dict.get('task_id')
            task_name = item_dict.get('task_name')
            assignee = item_dict.get('assignee')
            if task_name: doc_text_parts.append(f"작업명: {task_name}")
            if task_id: payload["task_id"] = str(task_id)
            if assignee: payload["assignee"] = str(assignee)
            if item_dict.get('deliverables'): payload["has_deliverables"] = True

        elif item_type == "assignee_workload_detail":
            assignee_name = assignee_name_for_workload
            if assignee_name:
                doc_text_parts.append(f"담당자: {assignee_name}")
                payload["assignee_name"] = assignee_name
            if item_dict.get('total_tasks') is not None:
                doc_text_parts.append(f"담당 작업 수: {item_dict.get('total_tasks')}")
                payload["total_tasks"] = item_dict.get('total_tasks')

        elif item_type == "delayed_task":
            task_id = item_dict.get('task_id')
            task_name = item_dict.get('task_name')
            if task_name: doc_text_parts.append(f"지연 작업명: {task_name}")
            if task_id: payload["task_id"] = str(task_id)
            if item_dict.get('due_date'): payload["due_date"] = item_dict.get('due_date')
        else:
            print(f"정보: 알 수 없는 item_type '{item_type}'입니다. 일반적인 처리를 시도합니다.")
            preview_data = {k: v for k, v in item_dict.items() if isinstance(v, (str, int, float, bool))}
            doc_text_parts.append(f"내용: {json.dumps(preview_data, ensure_ascii=False, indent=None)}")

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

        project_summary_data = llm_output_dict.get("project_summary")
        if isinstance(project_summary_data, dict):
            prepared_item = self._prepare_item_for_storage(project_summary_data, "project_overview", wbs_hash, current_id_counter)
            if prepared_item: items_to_process.append(prepared_item); current_id_counter +=1
        elif project_summary_data is not None:
            print(f"경고: 'project_summary' 데이터가 예상한 딕셔너리 형태가 아닙니다: {type(project_summary_data)}")

        task_list_data = llm_output_dict.get("task_list", [])
        if isinstance(task_list_data, list):
            for task_item in task_list_data:
                prepared_item = self._prepare_item_for_storage(task_item, "task_item", wbs_hash, current_id_counter)
                if prepared_item: items_to_process.append(prepared_item); current_id_counter += 1
        elif task_list_data is not None:
            print(f"경고: 'task_list' 데이터가 예상한 리스트 형태가 아닙니다: {type(task_list_data)}")

        assignee_workload_data = llm_output_dict.get("assignee_workload", {})
        if isinstance(assignee_workload_data, dict):
            for assignee_name, workload_details in assignee_workload_data.items():
                if isinstance(workload_details, dict):
                    prepared_item = self._prepare_item_for_storage(workload_details, "assignee_workload_detail", wbs_hash, current_id_counter, assignee_name_for_workload=assignee_name)
                    if prepared_item: items_to_process.append(prepared_item); current_id_counter +=1
                else:
                    print(f"경고: 담당자 '{assignee_name}'의 workload_details가 딕셔너리가 아닙니다. 건너뜁니다: {type(workload_details)}")
        elif assignee_workload_data is not None:
             print(f"경고: 'assignee_workload' 데이터가 예상한 딕셔너리 형태가 아닙니다: {type(assignee_workload_data)}")

        delayed_tasks_data = llm_output_dict.get("delayed_tasks", [])
        if isinstance(delayed_tasks_data, list):
            for delayed_task_item in delayed_tasks_data:
                prepared_item = self._prepare_item_for_storage(delayed_task_item, "delayed_task", wbs_hash, current_id_counter)
                if prepared_item: items_to_process.append(prepared_item); current_id_counter += 1
        elif delayed_tasks_data is not None:
            print(f"경고: 'delayed_tasks' 데이터가 예상한 리스트 형태가 아닙니다: {type(delayed_tasks_data)}")


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