"""
작성자 : 노건표
작성일 : 2025-06-01 
작성내용 : 리팩토링 ( VectorDB(ChromaDB) 관련 처리를 담당하는 클래스 ) 

사용법:
1. 인스턴스 생성: handler = VectorDBHandler(db_base_path, collection_name_prefix, project_id, embedding_api_key)
2. WBS 해시 조회: stored_hash = handler.get_stored_wbs_hash()
3. 프로젝트 데이터 삭제: handler.clear_project_data()
4. LLM 분석 결과 저장 : handler.store_llm_analysis_results(llm_analysis_results, wbs_hash)
"""
import chromadb
from chromadb.utils import embedding_functions
import json
import os
from typing import Dict, List, Any, Optional

class VectorDBHandler:
    """VectorDB(ChromaDB) 관련 처리를 담당하는 클래스"""

    def __init__(self, db_base_path: str, collection_name_prefix: str, project_id: str, embedding_api_key: str):
        if not project_id:
            raise ValueError("VectorDBHandler 초기화: project_id가 필요합니다.")
        
        self.project_id = project_id
        # 컬렉션 이름: prefix_projectid_revises (project_id의 특수문자 변경)
        safe_project_id = "".join(c if c.isalnum() else "_" for c in project_id)
        self.collection_name = f"{collection_name_prefix}_{safe_project_id}_revised"
        
        # DB 경로 설정 (db_base_path 아래에 컬렉션별 디렉토리 생성)
        # ChromaDB PersistentClient는 지정된 경로에 DB 파일을 저장합니다.
        self.db_path = os.path.join(db_base_path, self.collection_name) # 컬렉션별 경로 분리
        os.makedirs(self.db_path, exist_ok=True) # DB 경로 생성
        
        self.client = chromadb.PersistentClient(path=self.db_path)
        
        # 임베딩 함수 설정
        if not embedding_api_key:
            print("경고: OpenAI API 키가 없어 기본 임베딩 함수(SentenceTransformer)를 사용합니다. (VectorDBHandler)")
            # SentenceTransformer가 설치되어 있어야 함 (pip install sentence-transformers)
            try:
                self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2" # 또는 다른 경량 모델
                )
            except Exception as se_init_e:
                raise RuntimeError(f"SentenceTransformer 임베딩 함수 초기화 실패: {se_init_e}. "
                                   "OpenAI API 키를 제공하거나 sentence-transformers를 설치하세요.")
        else:
            try:
                self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                    api_key=embedding_api_key,
                    model_name="text-embedding-ada-002" # OpenAI의 표준 임베딩 모델
                )
            except Exception as openai_init_e:
                print(f"OpenAI 임베딩 함수 초기화 중 오류: {openai_init_e}. SentenceTransformer로 대체 시도합니다.")
                try:
                    self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
                except Exception as se_fallback_e:
                    raise RuntimeError(f"OpenAI 및 SentenceTransformer 임베딩 함수 초기화 모두 실패: {se_fallback_e}")

        # 컬렉션 가져오기 또는 생성
        try:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name, # 컬렉션 이름은 클라이언트 경로와 별개로 관리됨
                embedding_function=self.embedding_function
            )
        except Exception as e:
            raise RuntimeError(f"ChromaDB 컬렉션 '{self.collection_name}' 가져오기/생성 실패: {e}")

        print(f"VectorDBHandler 초기화 완료. DB 경로: {self.db_path}, 컬렉션: {self.collection_name}")

    def get_stored_wbs_hash(self) -> str | None:
        """DB에서 현재 프로젝트의 저장된 WBS 파일 해시를 조회합니다."""
        try:
            # project_overview 메타데이터를 가진 문서를 찾습니다.
            results = self.collection.get(
                where={"$and": [
                    {"project_id": self.project_id},
                    {"output_type": "project_overview"}
                ]},
                limit=1, # 해시는 하나만 저장되므로
                include=["metadatas"]
            )
            if results and results['metadatas'] and results['metadatas'][0]:
                return results['metadatas'][0].get('wbs_hash')
        except Exception as e:
            # 컬렉션이 비어있거나, project_id에 해당하는 데이터가 없을 때 등
            print(f"저장된 WBS 해시 조회 중 오류 또는 데이터 없음 (컬렉션: {self.collection_name}): {e}")
        return None

    def clear_project_data(self):
        """DB에서 현재 프로젝트 ID와 관련된 모든 데이터를 삭제합니다."""
        ids_to_delete = []
        offset = 0
        limit = 100 # 한 번에 가져올 ID 개수
        
        print(f"프로젝트 '{self.project_id}'의 오래된 데이터 삭제 시도 (컬렉션: {self.collection_name})...")
        while True:
            try:
                # where 필터를 사용하여 해당 project_id의 모든 문서를 가져옴
                results = self.collection.get(
                    where={"project_id": self.project_id},
                    limit=limit,
                    offset=offset,
                    include=[] # ID만 필요
                )
                if not results or not results['ids']: # 더 이상 ID가 없으면 종료
                    break
                
                ids_to_delete.extend(results['ids'])
                
                if len(results['ids']) < limit: # 가져온 ID 수가 limit보다 작으면 마지막 페이지
                    break
                offset += limit
            except Exception as e:
                print(f"오래된 데이터 ID 조회 중 오류 (프로젝트: {self.project_id}): {e}")
                break # 오류 발생 시 중단
            
        if ids_to_delete:
            print(f"프로젝트 '{self.project_id}'의 오래된 항목 {len(ids_to_delete)}개 삭제 중...")
            # ChromaDB는 한 번에 많은 ID를 삭제할 수 있지만, 너무 많으면 타임아웃 발생 가능성 고려
            max_batch_size = 500 # 배치 크기 조절 가능
            for i in range(0, len(ids_to_delete), max_batch_size):
                batch_ids = ids_to_delete[i:i + max_batch_size]
                try:
                    if batch_ids: # 빈 리스트가 아닐 때만 삭제 시도
                        self.collection.delete(ids=batch_ids)
                except Exception as e:
                    print(f"ID 배치 삭제 중 오류 (ID 일부: {batch_ids[:3]}...): {e}")
            print(f"프로젝트 '{self.project_id}' 데이터 삭제 완료.")
        else:
            print(f"프로젝트 '{self.project_id}'에 삭제할 기존 데이터가 없습니다.")
    
    def _prepare_item_for_storage(self, item_dict: Dict[str, Any], item_type: str, wbs_hash: str,
                                 id_counter: int, assignee_name_for_workload: Optional[str] = None) -> Optional[tuple]:
        """단일 항목을 저장 가능한 형태(문서 텍스트, 메타데이터, ID)로 준비합니다."""
        if not isinstance(item_dict, dict):
            print(f"경고: 저장할 {item_type} 항목이 딕셔너리가 아닙니다. 건너뜁니다: {item_dict}")
            return None

        doc_text_parts = [f"유형: {item_type}"]
        # 기본 메타데이터 구성
        meta = {
            "project_id": self.project_id,
            "wbs_hash": wbs_hash, # 현재 처리 중인 WBS 파일의 해시
            "output_type": item_type, # 이 청크의 데이터 유형
            "original_data": json.dumps(item_dict, ensure_ascii=False) # 원본 JSON 데이터 저장
        }
        identifier_for_id = None # ID 생성에 사용될 주요 식별자

        # item_type에 따라 문서 텍스트 및 추가 메타데이터 구성
        if item_type == "project_overview": # project_summary 딕셔너리 전체를 item_dict로 받음
            if "summary_text" in item_dict:
                 doc_text_parts.append(f"요약: {item_dict['summary_text']}")
                 meta["summary_text"] = item_dict['summary_text']
            if "total_tasks" in item_dict:
                 doc_text_parts.append(f"총 작업 수: {item_dict['total_tasks']}")
                 meta["total_tasks"] = item_dict['total_tasks']
            # project_summary 내 다른 필드들도 필요에 따라 추가 가능
            identifier_for_id = "summary"

        elif item_type == "task_item": # task_list 내부의 각 작업 항목
            task_id = item_dict.get('task_id')
            task_name = item_dict.get('task_name')
            assignee = item_dict.get('assignee')

            identifier_for_id = str(task_id) if task_id else str(task_name)
            # 예시:
            if task_name: doc_text_parts.append(f"작업명: {task_name}")
            if task_id: meta["task_id"] = str(task_id)
            if assignee: # 담당자 정보가 있다면 메타데이터에 명시적으로 추가
                meta["assignee"] = str(assignee) #

            if item_dict.get('deliverables'): meta["has_deliverables"] = True


        elif item_type == "assignee_workload_detail": # assignee_workload 내부의 각 담당자별 상세 정보
            assignee_name = assignee_name_for_workload # 외부에서 전달받은 담당자 이름
            # ... (이전 코드의 assignee_workload_detail 처리 로직과 유사하게 필드 추출 및 메타 추가) ...
            identifier_for_id = str(assignee_name)
            # 예시:
            if assignee_name: meta["assignee_name"] = assignee_name
            if item_dict.get('total_tasks') is not None: meta["total_tasks"] = item_dict.get('total_tasks')

        elif item_type == "delayed_task": # delayed_tasks 리스트 내부의 각 지연 작업 항목
            task_id = item_dict.get('task_id')
            task_name = item_dict.get('task_name')
            # ... (이전 코드의 delayed_task 처리 로직과 유사하게 필드 추출 및 메타 추가) ...
            identifier_for_id = str(task_id) if task_id else str(task_name)
            # 예시:
            if task_name: doc_text_parts.append(f"지연 작업명: {task_name}")
            if task_id: meta["task_id"] = str(task_id)
            if item_dict.get('due_date'): meta["due_date"] = item_dict.get('due_date')

        else: # 알 수 없는 유형 또는 일반적인 처리
            print(f"경고: 알 수 없는 item_type '{item_type}'입니다. 일반적인 처리를 시도합니다.")
            generic_name = item_dict.get('name', item_dict.get('id', f"item_{id_counter}"))
            identifier_for_id = str(generic_name)
            doc_text_parts.append(f"내용: {json.dumps(item_dict, ensure_ascii=False, indent=2)}")

        if identifier_for_id is None: # 식별자가 설정되지 않은 경우 (예: 빈 딕셔너리)
            identifier_for_id = f"unknown_item_{id_counter}"
        
        # 최종 문서 텍스트 생성
        doc_text = ", ".join(filter(None, doc_text_parts)) # 비어있지 않은 부분만 연결
        
        # 고유 ID 생성 (project_id + wbs_hash 일부 + item_type + 주요 식별자 + 카운터)
        # ID에 사용될 식별자 문자열 정리 (공백, 특수문자 등 처리)
        safe_identifier = "".join(c if c.isalnum() else "_" for c in str(identifier_for_id))
        # ID 길이 제한이 있을 수 있으므로, 너무 길어지지 않도록 주의 (ChromaDB는 보통 문제 없음)
        unique_id_str = f"{self.project_id}_{wbs_hash[:8]}_{item_type}_{safe_identifier}_{id_counter}"
        
        return doc_text, meta, unique_id_str[:255] # ID 길이 제한 (예: 255자)

    def store_llm_analysis_results(self, llm_output_dict: Dict[str, Any], wbs_hash: str):
        """LLM 분석 결과를 청킹하여 VectorDB에 저장합니다."""
        if not llm_output_dict or not isinstance(llm_output_dict, dict):
            print("저장할 LLM 분석 결과가 없거나 유효하지 않습니다.")
            return

        documents_to_add: List[str] = []
        metadatas_to_add: List[Dict] = []
        ids_to_add: List[str] = []
        current_id_counter = 0 # 각 항목에 대한 고유 ID 생성을 위한 카운터

        print(f"LLM 분석 결과 VectorDB 저장 준비 중 (컬렉션: {self.collection_name})...")

        # 1. project_summary 처리 (output_type: "project_overview")
        project_summary_data = llm_output_dict.get("project_summary")
        if isinstance(project_summary_data, dict):
            prepared_item = self._prepare_item_for_storage(project_summary_data, "project_overview", 
                                                           wbs_hash, current_id_counter)
            if prepared_item:
                documents_to_add.append(prepared_item[0])
                metadatas_to_add.append(prepared_item[1])
                ids_to_add.append(prepared_item[2])
                current_id_counter += 1
        elif project_summary_data is not None: # None이 아니지만 dict도 아닌 경우
            print(f"경고: 'project_summary' 데이터가 예상한 딕셔너리 형태가 아닙니다: {type(project_summary_data)}")

        # 2. task_list 처리 (각 항목은 output_type: "task_item")
        task_list_data = llm_output_dict.get("task_list", [])
        if isinstance(task_list_data, list):
            for task_item in task_list_data:
                prepared_item = self._prepare_item_for_storage(task_item, "task_item", 
                                                               wbs_hash, current_id_counter)
                if prepared_item:
                    documents_to_add.append(prepared_item[0])
                    metadatas_to_add.append(prepared_item[1])
                    ids_to_add.append(prepared_item[2])
                    current_id_counter += 1
        elif task_list_data is not None:
            print(f"경고: 'task_list' 데이터가 예상한 리스트 형태가 아닙니다: {type(task_list_data)}")

        # 3. assignee_workload 처리 (각 담당자별 정보는 output_type: "assignee_workload_detail")
        assignee_workload_data = llm_output_dict.get("assignee_workload", {})
        if isinstance(assignee_workload_data, dict):
            for assignee_name, workload_details in assignee_workload_data.items():
                prepared_item = self._prepare_item_for_storage(workload_details, "assignee_workload_detail",
                                                               wbs_hash, current_id_counter, 
                                                               assignee_name_for_workload=assignee_name)
                if prepared_item:
                    documents_to_add.append(prepared_item[0])
                    metadatas_to_add.append(prepared_item[1])
                    ids_to_add.append(prepared_item[2])
                    current_id_counter += 1
        elif assignee_workload_data is not None:
             print(f"경고: 'assignee_workload' 데이터가 예상한 딕셔너리 형태가 아닙니다: {type(assignee_workload_data)}")

        # 4. delayed_tasks 처리 (각 항목은 output_type: "delayed_task")
        delayed_tasks_data = llm_output_dict.get("delayed_tasks", [])
        if isinstance(delayed_tasks_data, list):
            for delayed_task_item in delayed_tasks_data:
                prepared_item = self._prepare_item_for_storage(delayed_task_item, "delayed_task",
                                                               wbs_hash, current_id_counter)
                if prepared_item:
                    documents_to_add.append(prepared_item[0])
                    metadatas_to_add.append(prepared_item[1])
                    ids_to_add.append(prepared_item[2])
                    current_id_counter += 1
        elif delayed_tasks_data is not None:
            print(f"경고: 'delayed_tasks' 데이터가 예상한 리스트 형태가 아닙니다: {type(delayed_tasks_data)}")
        
        # 준비된 데이터가 있을 경우 DB에 추가
        if documents_to_add:
            print(f"VectorDB에 새로운 항목 {len(documents_to_add)}개 추가 중 (컬렉션: {self.collection_name})...")
            try:
                # ChromaDB는 add 메서드에서 ID, 문서, 메타데이터 리스트를 받음
                # 배치 처리는 내부적으로 수행될 수 있으나, 너무 큰 배치는 메모리 문제 유발 가능
                # 여기서는 한 번에 모든 문서를 추가 시도
                self.collection.add(
                    ids=ids_to_add,
                    documents=documents_to_add,
                    metadatas=metadatas_to_add
                )
                print(f"데이터 {len(ids_to_add)}건 추가 완료.")
            except Exception as e:
                print(f"VectorDB에 데이터 추가 중 오류 발생: {e}")
                # 오류 발생 시 디버깅 정보 추가 (일부만)
                print(f"  오류 발생 시 ID (처음 3개): {ids_to_add[:3]}")
                if documents_to_add: print(f"  오류 발생 시 문서 (첫 번째): {documents_to_add[0][:200]}...")
                if metadatas_to_add: print(f"  오류 발생 시 메타데이터 (첫 번째): {str(metadatas_to_add[0])[:200]}...")
        else:
            print("LLM 분석 결과에서 VectorDB에 저장할 청크된 데이터가 없습니다.")

    def add_texts_with_metadata(self, texts: List[str], metadatas: List[Dict], ids: List[str]):
        """
        제공된 텍스트, 메타데이터, ID를 사용하여 VectorDB 컬렉션에 문서를 추가합니다.
        ChromaDB의 collection.add 메소드를 직접 사용합니다.
        'texts'는 ChromaDB의 'documents' 매개변수에 해당합니다.
        """
        if not (texts and metadatas and ids):
            print("경고 (add_texts_with_metadata): 추가할 텍스트, 메타데이터 또는 ID가 비어있습니다.")
            return
        
        if not (len(texts) == len(metadatas) == len(ids)):
            print("오류 (add_texts_with_metadata): 텍스트, 메타데이터, ID 리스트의 길이가 일치하지 않습니다.")
            print(f"  Texts: {len(texts)}, Metadatas: {len(metadatas)}, IDs: {len(ids)}")
            return

        try:
            print(f"VectorDB에 새로운 항목 {len(texts)}개 추가 중 (컬렉션: {self.collection_name}) via add_texts_with_metadata...")
            self.collection.add(
                ids=ids,
                documents=texts, # ChromaDB는 'documents' 인자를 사용합니다.
                metadatas=metadatas
            )
            print(f"데이터 {len(ids)}건 추가 완료 (via add_texts_with_metadata).")
        except Exception as e:
            print(f"VectorDB에 데이터 추가 중 오류 발생 (add_texts_with_metadata): {e}")
            print(f"  오류 발생 시 ID (처음 3개): {ids[:3]}")
            if texts: print(f"  오류 발생 시 문서 (첫 번째): {texts[0][:200]}...")
            if metadatas: print(f"  오류 발생 시 메타데이터 (첫 번째): {str(metadatas[0])[:200]}...")
            # 필요시 전체 스택 트레이스 출력
            # import traceback
            # traceback.print_exc()

