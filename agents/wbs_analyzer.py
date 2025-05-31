import pandas as pd
import chromadb
import hashlib
import json
import os
from typing import Dict, List, Any, Optional

# LangChain 및 OpenAI 관련 임포트
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser # 문자열 출력을 위해
from langchain_core.runnables import RunnablePassthrough
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class WBSAnalyzerAgent:
    """
    WBS 파일을 분석하여 LLM으로 처리하고, 그 결과를 VectorDB(ChromaDB)에
    분석된 항목 단위로 청킹하여 저장(캐싱)하는 에이전트.
    LLM의 JSON 응답을 파싱하여 프롬프트에 정의된 구조에 따라 처리합니다.
    WBS 업데이트를 감지하여 기존 데이터를 처리합니다.
    """

    def __init__(self, project_id: str, wbs_file_path: str):
        self.project_id = project_id
        self.wbs_file_path = wbs_file_path
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.vector_db_path = os.getenv("VECTOR_DB_PATH", "db/vector_store_revised_prompt") # DB 경로 변경
        self.collection_name = f"wbs_analysis_{project_id.replace('.', '_')}_revised" # 프로젝트별 컬렉션 이름 + 버전 명시

        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        if not os.path.exists(self.wbs_file_path):
            raise FileNotFoundError(f"WBS 파일을 찾을 수 없습니다: {self.wbs_file_path}")

        self.client = chromadb.PersistentClient(path=self.vector_db_path)
        # OpenAI 임베딩 함수 설정
        try:
            self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                api_key=self.openai_api_key,
                model_name="text-embedding-ada-002"
            )
        except Exception as e:
            print(f"OpenAI 임베딩 함수 초기화 중 오류 발생: {e}")
            print("기본 임베딩 함수(SentenceTransformer)로 대체합니다. 결과의 질이 다를 수 있습니다.")
            # 대체 임베딩 함수 (SentenceTransformer가 설치되어 있어야 함)
            # pip install sentence-transformers
            try:
                self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2" # 또는 다른 사용 가능한 모델
                )
            except Exception as se:
                print(f"SentenceTransformer 임베딩 함수 초기화 실패: {se}")
                raise ValueError("적합한 임베딩 함수를 초기화할 수 없습니다. OpenAI API 키를 확인하거나 SentenceTransformer를 설치하세요.")


        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function
        )

        self.llm = ChatOpenAI(
            model_name=os.getenv("OPENAI_MODEL_NAME", "gpt-4o"), # 환경 변수 또는 기본값 사용
            openai_api_key=self.openai_api_key,
            temperature=0, # 일관된 출력을 위해 온도 조절
            model_kwargs={"response_format": {"type": "json_object"}}
        )
        # 사용자가 제공한 프롬프트 파일을 로드합니다.
        # 파일명은 'wbs_prompt.md'로 가정하고, 내용은 수정된 버전을 사용해야 합니다.
        self.prompt_template = self._load_prompt_template("prompts/wbs_prompt.md")


    def _load_prompt_template(self, prompt_path: str) -> PromptTemplate:
        # 스크립트 파일의 위치를 기준으로 상대 경로를 절대 경로로 변환 시도
        script_dir = os.path.dirname(os.path.abspath(__file__)) # 현재 파일의 절대 경로
        
        # 1. script_dir/../prompts/wbs_prompt.md (프로젝트 루트의 prompts 폴더)
        candidate_path1 = os.path.join(script_dir, '..', prompt_path)
        
        # 2. script_dir/prompts/wbs_prompt.md (스크립트와 같은 폴더 내의 prompts 폴더)
        candidate_path2 = os.path.join(script_dir, prompt_path)

        # 3. 현재 작업 디렉토리 기준 prompts/wbs_prompt.md
        candidate_path3 = os.path.join(os.getcwd(), prompt_path)

        # 4. 프로젝트 루트로 추정되는 경로 (script_dir/..) 기준
        project_root_prompts = os.path.join(os.path.dirname(script_dir), prompt_path)

        paths_to_try = [candidate_path1, candidate_path2, candidate_path3, project_root_prompts, prompt_path]

        for path_try in paths_to_try:
            abs_path_try = os.path.abspath(path_try)
            # print(f"프롬프트 파일 시도: {abs_path_try}") # 디버깅용
            if os.path.exists(abs_path_try):
                try:
                    with open(abs_path_try, 'r', encoding='utf-8') as f:
                        template_str = f.read()
                    print(f"프롬프트 파일 로드 성공: {abs_path_try}")
                    return PromptTemplate.from_template(template_str)
                except Exception as e:
                    print(f"프롬프트 파일 읽기 오류 ({abs_path_try}): {e}")
        
        raise FileNotFoundError(f"프롬프트 파일을 다음 경로들에서 찾을 수 없습니다: {', '.join(map(os.path.abspath, paths_to_try))}. 'prompts/wbs_prompt.md' 경로에 수정된 프롬프트 파일이 있는지 확인하세요.")


    def _calculate_hash(self) -> str:
        hasher = hashlib.sha256()
        try:
            with open(self.wbs_file_path, 'rb') as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            print(f"해시 계산 중 오류 발생: {e}")
            raise

    def _read_wbs_to_text(self) -> str:
        try:
            print(f"WBS 파일 읽는 중: {self.wbs_file_path}")
            # 엑셀 파일의 모든 시트를 읽어올 수 있도록 sheet_name=None 설정
            # 또는 특정 시트만 필요한 경우 해당 시트 이름이나 인덱스 지정
            excel_file = pd.ExcelFile(self.wbs_file_path)
            if not excel_file.sheet_names:
                raise ValueError("엑셀 파일에 시트가 없습니다.")
            
            # 첫 번째 시트를 사용하거나, 특정 시트 이름을 지정할 수 있습니다.
            # 여기서는 첫 번째 시트를 사용합니다.
            df = excel_file.parse(excel_file.sheet_names[0])

            # 날짜 필드가 문자열로 제대로 읽히도록 처리 (필요시)
            # 예: df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce').dt.strftime('%Y-%m-%d')
            # 프롬프트에서 원본 형식을 유지하라고 했으므로, 특별한 변환은 자제합니다.
            # 다만, pandas가 날짜를 datetime 객체로 자동 변환하는 경우가 있으므로,
            # 이를 다시 문자열로 바꿔주거나, to_json에서 date_format='iso' 등을 사용 고려.
            # 여기서는 to_json의 기본 동작에 맡기되, ensure_ascii=False로 유니코드 유지.

            print(f"WBS 파일 (시트: {excel_file.sheet_names[0]}) 상위 5개 행:\n{df.head()}")
            print("WBS 파일 읽기 완료. JSON으로 변환 중...")
            # orient='records'는 각 행을 JSON 객체로, 이들의 리스트로 변환합니다.
            # indent=2는 가독성을 위해 들여쓰기를 추가합니다.
            # force_ascii=False는 한글 등이 유니코드 이스케이프 없이 그대로 저장되도록 합니다.
            wbs_json = df.to_json(orient='records', indent=2, force_ascii=False, date_format='iso')
            return wbs_json
        except Exception as e:
            print(f"WBS 파일 읽기 또는 JSON 변환 오류: {e}")
            raise

    def _get_existing_hash(self) -> str | None:
        try:
            results = self.collection.get(
                where={"project_id": self.project_id}, # project_id 필터링
                limit=1, # 가장 최근의 해시 하나만 필요
                include=["metadatas"]
            )
            # 결과가 있고, 메타데이터가 있고, 첫 번째 메타데이터가 존재할 때
            if results and results['metadatas'] and results['metadatas'][0]:
                # project_overview 타입의 문서에서 wbs_hash를 우선적으로 찾음
                for meta in results['metadatas']:
                    if meta.get("output_type") == "project_overview" and 'wbs_hash' in meta:
                        return meta['wbs_hash']
                # project_overview가 없거나 거기에 해시가 없다면, 첫 번째 문서의 해시라도 반환 (Fallback)
                return results['metadatas'][0].get('wbs_hash')
        except Exception as e:
            # 컬렉션이 비어있거나 project_id에 해당하는 데이터가 없을 때 예외 발생 가능
            print(f"기존 해시 조회 중 오류 또는 데이터 없음: {e}")
        return None

    def _delete_old_data(self):
        ids_to_delete = []
        offset = 0
        limit = 100 # 한 번에 가져올 ID 개수
        
        print(f"{self.project_id} 프로젝트의 오래된 데이터 삭제 시도...")
        while True:
            try:
                results = self.collection.get(
                    where={"project_id": self.project_id}, # project_id로 필터링된 항목만 삭제
                    limit=limit,
                    offset=offset,
                    include=[] # ID만 필요하므로 다른 내용은 가져오지 않음
                )
                if not results or not results['ids']: # 결과가 없거나 ID 리스트가 비어있으면 종료
                    break
                
                ids_to_delete.extend(results['ids'])
                
                if len(results['ids']) < limit: # 가져온 ID 수가 limit보다 작으면 마지막 페이지
                    break
                offset += limit
            except Exception as e:
                print(f"오래된 데이터 ID 조회 중 오류: {e}")
                break # 오류 발생 시 중단
            
        if ids_to_delete:
            print(f"{self.project_id} 프로젝트의 오래된 항목 {len(ids_to_delete)}개 삭제 중...")
            # ChromaDB는 한 번에 많은 ID를 삭제할 수 있지만, 너무 많으면 타임아웃 발생 가능
            max_batch_size = 500 
            for i in range(0, len(ids_to_delete), max_batch_size):
                batch_ids = ids_to_delete[i:i + max_batch_size]
                try:
                    self.collection.delete(ids=batch_ids)
                except Exception as e:
                    print(f"ID 배치 삭제 중 오류 (ID: {batch_ids[:3]}...): {e}")
            print("삭제 완료.")
        else:
            print(f"{self.project_id} 프로젝트에 기존 데이터가 없거나 삭제할 데이터가 없습니다.")


    def _process_with_llm(self, wbs_json_text: str) -> Dict[str, Any]:
        print("LLM에 WBS 데이터 전송 및 분석 요청 중...")
        # LangChain 체인 구성: 입력(RunnablePassthrough) -> 프롬프트 -> LLM -> 출력 파서
        chain = (
            {"wbs_data": RunnablePassthrough(), "wbs_agent_output_schema": RunnablePassthrough()} # 프롬프트에 필요한 변수 전달
            | self.prompt_template
            | self.llm
            | StrOutputParser() # LLM 응답을 문자열로 받음
        )
        
        # 프롬프트에서 wbs_agent_output_schema 부분을 제공해야 함.
        # 이 스키마는 LLM이 어떤 JSON 구조로 응답해야 하는지 알려주는 예시임.
        # 실제 프롬프트 파일 내에 이 플레이스홀더가 있고, 그 내용이 채워져야 함.
        # 여기서는 간단히 빈 JSON 객체로 전달하거나, 실제 스키마 문자열을 로드해야 함.
        # 사용자가 제공한 프롬프트에 이미 이 부분이 포함되어 있다고 가정.
        # 만약 schema를 동적으로 생성하거나 파일에서 읽어와야 한다면 해당 로직 추가 필요.
        # 여기서는 프롬프트 파일 내에 하드코딩된 스키마가 있다고 가정하고,
        # invoke 시 wbs_agent_output_schema에 대한 값을 전달할 필요가 없을 수 있음.
        # 프롬프트 템플릿이 {wbs_data}만 받는다면 아래와 같이 수정:
        
        # 프롬프트가 {wbs_data}만 받는 경우
        chain_simple = (
            {"wbs_data": RunnablePassthrough()} 
            | self.prompt_template
            | self.llm
            | StrOutputParser()
        )

        try:
            # response_str = chain.invoke({"wbs_data": wbs_json_text, "wbs_agent_output_schema": "{...}"}) # 스키마를 전달해야 하는 경우
            response_str = chain_simple.invoke(wbs_json_text) # wbs_data만 필요한 경우
            
            print("LLM 분석 완료. 응답 파싱 중...")
            # LLM 응답이 마크다운 코드 블록(```json ... ```)으로 감싸져 오는 경우가 있으므로 처리
            if response_str.strip().startswith("```json"):
                response_str = response_str.strip()[7:]
                if response_str.strip().endswith("```"):
                    response_str = response_str.strip()[:-3]
            
            response_str = response_str.strip()

            # JSON 응답 시작과 끝을 찾아 파싱 (더 견고한 방법 고려 가능)
            json_start = response_str.find('{')
            json_end = response_str.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_response_str = response_str[json_start:json_end]
                parsed_json = json.loads(json_response_str)
                print("LLM 응답 파싱 성공.")
                return parsed_json
            else:
                print(f"LLM 응답에서 유효한 JSON 구조를 찾지 못했습니다. 응답: {response_str}")
                # 새로운 프롬프트 구조에 맞는 기본값 반환
                return {
                    "project_summary": None, 
                    "task_list": [], 
                    "assignee_workload": {}, # 딕셔너리 형태이므로
                    "delayed_tasks": []
                }
        except json.JSONDecodeError as e:
            error_context = response_str if 'response_str' not in locals() else (json_response_str if 'json_response_str' in locals() else response_str)
            print(f"LLM JSON 응답 파싱 오류: {e}")
            print(f"LLM 원본 응답 (파싱 시도 부분):\n{error_context}")
            return { # 오류 시 반환할 기본 구조
                "project_summary": None, 
                "task_list": [], 
                "assignee_workload": {},
                "delayed_tasks": []
            }
        except Exception as e:
            print(f"LLM 처리 중 예상치 못한 오류 발생: {e}")
            raise

    def _add_item_to_vectors(self, item_dict: Dict[str, Any], item_type: str, wbs_hash: str,
                             documents: List[str], metadatas: List[Dict], ids: List[str], 
                             id_counter: int, assignee_name_for_workload: Optional[str] = None) -> int:
        if not isinstance(item_dict, dict):
            print(f"경고: {item_type} 항목이 딕셔너리가 아닙니다. 건너뜁니다: {item_dict}")
            return id_counter

        doc_text_parts = [f"유형: {item_type}"]
        meta = {
            "project_id": self.project_id,
            "wbs_hash": wbs_hash,
            "output_type": item_type,
            "original_data": json.dumps(item_dict, ensure_ascii=False) # 원본 데이터 저장
        }
        
        identifier = None # 각 항목을 고유하게 식별할 수 있는 값 (ID 생성에 사용)

        if item_type == "task_item": # 'task_list' 내부의 각 작업 항목
            task_id = item_dict.get('task_id')
            task_name = item_dict.get('task_name')
            assignee = item_dict.get('assignee')
            start_date = item_dict.get('start_date') 
            end_date = item_dict.get('end_date') or item_dict.get('due_date') # end_date 또는 due_date
            status = item_dict.get('status')
            progress = item_dict.get('progress_percentage')
            deliverables = item_dict.get('deliverables') # 산출물

            identifier = str(task_id) if task_id else str(task_name) # ID 우선, 없으면 이름
            if task_name: doc_text_parts.append(f"작업명: {task_name}")
            if task_id: 
                doc_text_parts.append(f"ID: {task_id}")
                meta["task_id"] = str(task_id)
            if assignee:
                doc_text_parts.append(f"담당자: {assignee}")
                meta["assignee"] = assignee
            if start_date is not None:
                doc_text_parts.append(f"시작일: {start_date}") # 원본 형식 그대로
                meta["start_date"] = start_date 
            if end_date is not None:
                doc_text_parts.append(f"종료일/마감일: {end_date}") # 원본 형식 그대로
                meta["end_date"] = end_date # 또는 "due_date"
            if status:
                doc_text_parts.append(f"상태: {status}")
                meta["status"] = status
            if progress is not None:
                doc_text_parts.append(f"진행도: {progress}%")
                meta["progress_percentage"] = progress
            if deliverables: # 산출물이 있고, 비어있지 않은 리스트일 경우
                if isinstance(deliverables, list) and deliverables:
                    doc_text_parts.append(f"산출물: {', '.join(map(str,deliverables))}")
                    meta["deliverables"] = json.dumps(deliverables, ensure_ascii=False) # 리스트는 JSON 문자열로
                elif isinstance(deliverables, str) and deliverables.strip(): # 문자열이지만 내용이 있는 경우
                    doc_text_parts.append(f"산출물: {deliverables}")
                    meta["deliverables"] = deliverables

            meta["item_identifier"] = identifier

        elif item_type == "assignee_workload_detail": # 'assignee_workload' 내부의 각 담당자별 상세 정보
            # assignee_name_for_workload 인자를 통해 담당자 이름을 받음
            assignee_name = assignee_name_for_workload
            total_tasks = item_dict.get('total_tasks') # 프롬프트 예시의 키 'total_tasks'
            tasks_status_count = item_dict.get('tasks_by_status') # 프롬프트 예시의 키 'tasks_by_status'

            identifier = str(assignee_name)
            if assignee_name:
                doc_text_parts.append(f"담당자: {assignee_name}")
                meta["assignee_name"] = assignee_name # 메타데이터에 담당자 이름 저장
            if total_tasks is not None:
                doc_text_parts.append(f"총 작업 수: {total_tasks}")
                meta["total_tasks"] = total_tasks
            if isinstance(tasks_status_count, dict):
                doc_text_parts.append(f"상태별 작업 수: {json.dumps(tasks_status_count, ensure_ascii=False)}")
                meta["tasks_by_status"] = json.dumps(tasks_status_count, ensure_ascii=False)
            meta["item_identifier"] = identifier

        elif item_type == "delayed_task": # 'delayed_tasks' 리스트 내부의 각 지연 작업 항목
            task_id = item_dict.get('task_id')
            task_name = item_dict.get('task_name')
            assignee = item_dict.get('assignee')
            due_date = item_dict.get('due_date')
            status = item_dict.get('status') # 보통 "Delayed"
            reason = item_dict.get('reason_for_delay')

            identifier = str(task_id) if task_id else str(task_name)
            if task_name: doc_text_parts.append(f"지연 작업명: {task_name}")
            if task_id:
                doc_text_parts.append(f"ID: {task_id}")
                meta["task_id"] = str(task_id)
            if assignee:
                doc_text_parts.append(f"담당자: {assignee}")
                meta["assignee"] = assignee
            if due_date is not None:
                doc_text_parts.append(f"마감일: {due_date}")
                meta["due_date"] = due_date
            if status:
                doc_text_parts.append(f"상태: {status}")
                meta["status"] = status
            if reason:
                doc_text_parts.append(f"지연 사유: {reason}")
                meta["reason_for_delay"] = reason
            meta["item_identifier"] = identifier
        
        else: # 기타 유형 (예: project_summary를 직접 저장하지 않고, 여기서 처리한다면)
            print(f"경고: 알 수 없는 item_type '{item_type}'입니다. 일반적인 처리를 시도합니다.")
            # item_dict의 내용을 기반으로 문서 텍스트와 식별자 생성
            item_name_generic = item_dict.get('name', item_dict.get('id', f"generic_item_{id_counter}"))
            identifier = str(item_name_generic)
            doc_text_parts.append(f"내용: {json.dumps(item_dict, ensure_ascii=False, indent=2)}")
            meta["item_identifier"] = identifier

        if identifier is None: # 만약 위에서 identifier가 설정되지 않았다면 (예: 빈 딕셔너리)
            identifier = f"item_{id_counter}" # 고유 ID 보장
            meta["item_identifier"] = identifier
            
        doc_text = ", ".join(doc_text_parts)
        
        documents.append(doc_text)
        metadatas.append(meta)
        
        # ID 생성: project_id + wbs_hash + item_type + item_identifier + counter
        # identifier에 포함될 수 있는 특수문자 제거 또는 변경
        sanitized_identifier = str(identifier).replace('.', '_').replace(' ', '_').replace('/', '_').replace(':', '_')
        # ID 길이 제한이 있을 수 있으므로, 너무 길어지지 않도록 주의
        unique_id_str = f"{self.project_id}_{wbs_hash[:8]}_{item_type}_{sanitized_identifier}_{id_counter}"
        ids.append(unique_id_str[:255]) # ID 길이 제한 고려 (ChromaDB는 보통 문제 없음)
        
        return id_counter + 1

    def _chunk_and_store(self, llm_output_dict: Dict[str, Any], wbs_hash: str):
        documents: List[str] = []
        metadatas: List[Dict] = []
        ids: List[str] = []
        id_counter = 0 # 각 항목에 대한 고유 ID 생성을 위한 카운터

        print("VectorDB 저장을 위한 데이터 청킹 및 준비 중...")

        # 1. project_summary 저장 (output_type: "project_overview")
        project_summary_dict = llm_output_dict.get("project_summary")
        if isinstance(project_summary_dict, dict):
            summary_doc_text_parts = ["유형: 프로젝트 개요"]
            summary_meta = {
                "project_id": self.project_id,
                "wbs_hash": wbs_hash,
                "output_type": "project_overview",
                "original_data": json.dumps(project_summary_dict, ensure_ascii=False)
            }
            # project_summary_dict 내부의 주요 정보들을 문서 텍스트와 메타데이터에 추가
            if "summary_text" in project_summary_dict:
                 summary_doc_text_parts.append(f"요약: {project_summary_dict['summary_text']}")
                 summary_meta["summary_text"] = project_summary_dict['summary_text'] # 검색 편의를 위해 추가
            if "total_tasks" in project_summary_dict:
                 summary_doc_text_parts.append(f"총 작업 수: {project_summary_dict['total_tasks']}")
                 summary_meta["total_tasks"] = project_summary_dict['total_tasks']
            # 기타 project_summary_dict의 내용을 필요에 따라 추가 가능

            summary_doc_text = ", ".join(summary_doc_text_parts)
            summary_id = f"{self.project_id}_{wbs_hash[:8]}_overview_{id_counter}"
            
            documents.append(summary_doc_text)
            metadatas.append(summary_meta)
            ids.append(summary_id)
            id_counter += 1
        elif project_summary_dict is not None:
            print(f"경고: 'project_summary'가 딕셔너리가 아닙니다: {project_summary_dict}")


        # 2. task_list 처리 (output_type: "task_item")
        task_list = llm_output_dict.get("task_list", [])
        if isinstance(task_list, list):
            for task_item_dict in task_list:
                id_counter = self._add_item_to_vectors(task_item_dict, "task_item", wbs_hash,
                                                       documents, metadatas, ids, id_counter)
        elif task_list is not None:
            print(f"경고: 'task_list'가 리스트가 아닙니다: {task_list}")

        # 3. assignee_workload 처리 (output_type: "assignee_workload_detail")
        assignee_workload_dict = llm_output_dict.get("assignee_workload", {})
        if isinstance(assignee_workload_dict, dict):
            for assignee_name, workload_detail_dict in assignee_workload_dict.items():
                id_counter = self._add_item_to_vectors(workload_detail_dict, "assignee_workload_detail", wbs_hash,
                                                       documents, metadatas, ids, id_counter,
                                                       assignee_name_for_workload=assignee_name)
        elif assignee_workload_dict is not None:
            print(f"경고: 'assignee_workload'가 딕셔너리가 아닙니다: {assignee_workload_dict}")

        # 4. delayed_tasks 처리 (output_type: "delayed_task")
        delayed_tasks_list = llm_output_dict.get("delayed_tasks", [])
        if isinstance(delayed_tasks_list, list):
            for delayed_task_dict in delayed_tasks_list:
                id_counter = self._add_item_to_vectors(delayed_task_dict, "delayed_task", wbs_hash,
                                                       documents, metadatas, ids, id_counter)
        elif delayed_tasks_list is not None:
            print(f"경고: 'delayed_tasks'가 리스트가 아닙니다: {delayed_tasks_list}")


        if documents:
            print(f"VectorDB에 새로운 항목 {len(documents)}개 추가 중 (컬렉션: {self.collection_name})...")
            try:
                # ChromaDB는 add 메서드에서 ID, 문서, 메타데이터 리스트를 받음
                # 배치 처리는 내부적으로 수행될 수 있으나, 너무 큰 배치는 메모리 문제 유발 가능
                # 여기서는 한 번에 모든 문서를 추가 시도
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
                print("데이터 추가 완료.")
            except Exception as e:
                print(f"VectorDB에 데이터 추가 중 오류 발생: {e}")
                print(f"오류 발생 시 ID (일부): {ids[:3]}")
                print(f"오류 발생 시 문서 (일부): {documents[:1]}") # 첫 번째 문서만 출력
                print(f"오류 발생 시 메타데이터 (일부): {metadatas[:1]}") # 첫 번째 메타데이터만 출력
        else:
            print("LLM 분석 결과에서 VectorDB에 저장할 청크된 데이터가 없습니다.")


    def run(self):
        print(f"\n=== {self.project_id} 프로젝트 WBS 분석 시작 ===")
        print(f"WBS 파일: {self.wbs_file_path}")
        print(f"VectorDB 컬렉션: {self.collection_name}")

        current_hash = self._calculate_hash()
        existing_hash = self._get_existing_hash()

        print(f"WBS 해시 (신규: {current_hash[:8]}..., 기존: {existing_hash[:8] if existing_hash else '없음'}).")
        
        if current_hash == existing_hash and existing_hash is not None:
            print(f"{self.project_id} (해시: {current_hash[:8]}...)에 대한 WBS 데이터는 이미 최신입니다. 분석을 건너뜁니다.")
            return

        if existing_hash is None or current_hash != existing_hash:
            print("기존 데이터 삭제 및 WBS 재분석 진행...")
            self._delete_old_data() 
        # else: # 해시가 동일한 경우는 위에서 return 되었으므로 이 부분은 실행되지 않음
        #     pass

        wbs_json_text = self._read_wbs_to_text()
        # print(f"WBS JSON 텍스트 (일부): {wbs_json_text[:500]}...") # 전체 출력은 너무 길 수 있음
        
        llm_output_dict = self._process_with_llm(wbs_json_text)
        
        # LLM 응답 유효성 검사 (주요 키들이 존재하는지 확인)
        if not llm_output_dict or not any(key in llm_output_dict for key in ["project_summary", "task_list", "assignee_workload"]):
            print("LLM으로부터 유효한 분석 결과를 받지 못했습니다. WBS 분석을 중단합니다.")
            if llm_output_dict:
                 print(f"LLM 응답 내용 (일부): {str(llm_output_dict)[:500]}...")
            return
            
        self._chunk_and_store(llm_output_dict, current_hash)

        print(f"=== {self.project_id} 프로젝트 WBS 분석 완료 ===")

if __name__ == '__main__':
    try:
        # --- 기본 경로 설정 ---
        # 이 스크립트 파일의 현재 위치를 기준으로 경로를 설정합니다.
        # __file__은 현재 실행 중인 스크립트의 경로를 나타냅니다.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # 프로젝트 루트 디렉토리를 script_dir의 상위 디렉토리로 가정합니다.
        # (예: script가 project_root/src/analyzer.py 에 있다면 project_root는 script_dir/../..)
        # 여기서는 스크립트가 프로젝트 루트의 하위 폴더(예: 'src')에 있다고 가정
        project_root = os.path.dirname(script_dir) if os.path.basename(script_dir) == 'src' else script_dir
        # 만약 스크립트가 프로젝트 루트에 직접 있다면 project_root = script_dir

        print(f"스크립트 디렉토리: {script_dir}")
        print(f"프로젝트 루트 (추정): {project_root}")

        # .env 파일 경로 설정 (프로젝트 루트에 .env 파일이 있다고 가정)
        dotenv_path = os.path.join(project_root, '.env')
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path)
            print(f".env 파일 로드 완료: {dotenv_path}")
        else:
            # 현재 작업 디렉토리에서도 찾아봄
            dotenv_path_cwd = os.path.join(os.getcwd(), '.env')
            if os.path.exists(dotenv_path_cwd):
                 load_dotenv(dotenv_path_cwd)
                 print(f".env 파일 로드 완료 (현재 작업 디렉토리): {dotenv_path_cwd}")
            else:
                print(f".env 파일을 다음 경로들에서 찾을 수 없습니다: {dotenv_path}, {dotenv_path_cwd}. 환경변수가 직접 설정되었는지 확인하세요.")

        # --- 환경 변수 및 설정값 로드 ---
        api_key_from_env = os.getenv("OPENAI_API_KEY")
        if api_key_from_env:
            print(f"OpenAI API Key 로드됨 (시작 부분): '{api_key_from_env[:5]}...'")
        else:
            print("OpenAI API Key를 찾을 수 없습니다. .env 파일 또는 환경변수를 확인하세요.")
            # 실제 운영 시에는 API 키가 없으면 여기서 중단하는 것이 좋음
            # raise ValueError("OpenAI API Key가 설정되지 않았습니다.")

        # WBS 파일 경로 설정 (프로젝트 루트/data/wbs/파일명.xlsx 형태를 기본으로 가정)
        wbs_file_relative_path = os.path.join('data', 'wbs', 'WBS_스마트팩토리챗봇1.xlsx') # 예시 파일명, 실제 파일명으로 변경 필요
        wbs_file_path_abs = os.path.join(project_root, wbs_file_relative_path)
        
        if not os.path.exists(wbs_file_path_abs):
            wbs_file_path_cwd = os.path.join(os.getcwd(), wbs_file_relative_path)
            if os.path.exists(wbs_file_path_cwd):
                wbs_file_path_abs = wbs_file_path_cwd
                print(f"WBS 파일을 현재 작업 디렉토리에서 찾음: {wbs_file_path_abs}")
            else:
                print(f"WBS 파일을 다음 경로들에서 찾을 수 없습니다: {os.path.join(project_root, wbs_file_relative_path)}, {wbs_file_path_cwd}")
                # 실제 운영 시에는 파일이 없으면 중단
                # raise FileNotFoundError(f"WBS 파일을 찾을 수 없습니다. 경로를 확인하세요: {wbs_file_relative_path}")
        else:
            print(f"WBS 파일 경로: {wbs_file_path_abs}")
            
        # VectorDB 경로 설정 (프로젝트 루트/db/vector_store_revised_prompt 형태를 기본으로 가정)
        vector_db_env_path_setting = os.getenv("VECTOR_DB_PATH")
        if vector_db_env_path_setting:
            # 환경변수에 설정된 경로가 상대경로이면 프로젝트 루트 기준으로 변경
            if not os.path.isabs(vector_db_env_path_setting):
                os.environ["VECTOR_DB_PATH"] = os.path.join(project_root, vector_db_env_path_setting)
        else:
            # 기본 경로 설정
            os.environ["VECTOR_DB_PATH"] = os.path.join(project_root, "db", "vector_store_revised_prompt")
        
        print(f"Vector DB Path 설정됨: {os.getenv('VECTOR_DB_PATH')}")
        os.makedirs(os.getenv('VECTOR_DB_PATH'), exist_ok=True) # DB 디렉토리 생성

        # --- 에이전트 실행 ---
        # 프로젝트 ID는 분석 대상 프로젝트를 식별하는 고유한 값이어야 함
        proj_id = 'smart_factory_chatbot_revised_prompt_v1' 

        if api_key_from_env and os.path.exists(wbs_file_path_abs):
            agent = WBSAnalyzerAgent(project_id=proj_id, wbs_file_path=wbs_file_path_abs)
            # 프롬프트 파일은 _load_prompt_template 내부에서 경로를 탐색하므로,
            # 생성자에서 "prompts/wbs_prompt.md"를 전달하면 됩니다.
            # 만약 다른 프롬프트 파일을 명시적으로 사용하고 싶다면,
            # agent.prompt_template = agent._load_prompt_template("다른_경로/다른_프롬프트.md")
            agent.run()

            # --- VectorDB 조회 테스트 (수정된 구조 기반) ---
            print("\n--- VectorDB 조회 테스트 (수정된 구조 기반) ---")
            vector_db_path_for_test = os.getenv("VECTOR_DB_PATH")
            test_client = chromadb.PersistentClient(path=vector_db_path_for_test)
            test_collection_name = agent.collection_name 
            
            try:
                collection_to_test = test_client.get_collection(
                    name=test_collection_name, 
                    embedding_function=agent.embedding_function # 동일한 임베딩 함수 사용
                )
            except Exception as e:
                print(f"테스트용 컬렉션 '{test_collection_name}' 가져오기 실패: {e}")
                collection_to_test = None

            if collection_to_test:
                print(f"\n'{proj_id}' 프로젝트 개요 조회 (output_type='project_overview'):")
                results_overview = collection_to_test.get(
                    where={"$and": [{"project_id": proj_id}, {"output_type": "project_overview"}]},
                    include=["documents", "metadatas"]
                )
                if results_overview and results_overview['documents']:
                    for doc, meta in zip(results_overview['documents'], results_overview['metadatas']):
                        print(f"  - 문서 (일부): {doc}...")
                        original_data = json.loads(meta.get('original_data', '{}'))
                        print(f"    요약 텍스트 (original_data): {original_data.get('summary_text', 'N/A')}...")
                        print(f"    총 작업 수 (original_data): {original_data.get('total_tasks', 'N/A')}")
                else:
                    print(f"  '{proj_id}' 프로젝트의 개요 정보를 찾을 수 없습니다.")

                # 실제 WBS 데이터에 있는 담당자 이름으로 변경해야 함
                sample_assignee_name_for_test = "김용준" # 예시 담당자, 실제 데이터에 맞게 수정
                print(f"\n'{proj_id}' 프로젝트의 담당자 '{sample_assignee_name_for_test}' 작업 부하 조회 (output_type='assignee_workload_detail'):")
                results_assignee_workload = collection_to_test.get(
                    where={"$and": [
                        {"project_id": proj_id},
                        {"output_type": "assignee_workload_detail"},
                        {"assignee_name": sample_assignee_name_for_test} # 메타데이터 필터링
                    ]},
                    include=["documents", "metadatas"]
                )
                if results_assignee_workload and results_assignee_workload['documents']:
                    for doc, meta in zip(results_assignee_workload['documents'], results_assignee_workload['metadatas']):
                        print(f"  - 문서: {doc}")
                        original_data = json.loads(meta.get('original_data', '{}'))
                        print(f"    담당자: {meta.get('assignee_name')}")
                        print(f"    총 작업 수 (original_data): {original_data.get('total_tasks')}")
                        print(f"    상태별 작업 수 (original_data): {original_data.get('tasks_by_status')}")
                else:
                    print(f"  '{proj_id}' 프로젝트에서 '{sample_assignee_name_for_test}'의 작업 부하 정보를 찾을 수 없습니다.")
                
                # 실제 WBS 데이터에 있는 작업 ID로 변경해야 함
                sample_task_id_for_test = "1.1" # 예시 작업 ID, 실제 데이터에 맞게 수정
                print(f"\n'{proj_id}' 프로젝트의 작업 상세 정보 조회 (output_type='task_item', task_id='{sample_task_id_for_test}'):")
                results_task_detail = collection_to_test.get(
                    where={"$and": [
                        {"project_id": proj_id},
                        {"output_type": "task_item"},
                        {"task_id": sample_task_id_for_test} # 메타데이터 필터링
                    ]},
                    limit=1, # ID는 고유해야 하므로 1개만
                    include=["documents", "metadatas"]
                )
                if results_task_detail and results_task_detail['documents']:
                    for doc, meta in zip(results_task_detail['documents'], results_task_detail['metadatas']):
                        print(f"  - 문서: {doc}")
                        original_data = json.loads(meta.get('original_data', '{}'))
                        print(f"    작업 ID: {meta.get('task_id')}, 작업명: {original_data.get('task_name')}")
                        print(f"    담당자: {meta.get('assignee')}, 상태: {meta.get('status')}")
                        print(f"    시작일: {meta.get('start_date')}, 종료일/마감일: {meta.get('end_date')}")
                        print(f"    진행도: {meta.get('progress_percentage')}%")
                        print(f"    산출물 (original_data): {original_data.get('deliverables')}")
                else:
                    print(f"  '{proj_id}' 프로젝트에서 작업 ID '{sample_task_id_for_test}'의 상세 정보를 찾을 수 없습니다.")

                print(f"\n'{proj_id}' 프로젝트의 지연된 작업 조회 (output_type='delayed_task'):")
                results_delayed_tasks = collection_to_test.get(
                    where={"$and": [{"project_id": proj_id}, {"output_type": "delayed_task"}]},
                    limit=5, # 최대 5개까지
                    include=["documents", "metadatas"]
                )
                if results_delayed_tasks and results_delayed_tasks['documents']:
                    print(f"  지연된 작업 {len(results_delayed_tasks['documents'])}건 발견:")
                    for doc, meta in zip(results_delayed_tasks['documents'], results_delayed_tasks['metadatas']):
                        original_data = json.loads(meta.get('original_data', '{}'))
                        print(f"    - 작업 ID: {meta.get('task_id')}, 작업명: {original_data.get('task_name')}")
                        print(f"      마감일: {meta.get('due_date')}, 지연사유: {meta.get('reason_for_delay', 'N/A')}")
                else:
                    print(f"  '{proj_id}' 프로젝트에서 지연된 작업을 찾을 수 없거나, LLM이 분석하지 않았습니다.")
            else:
                print(f"테스트용 컬렉션 '{test_collection_name}'을 찾을 수 없어 조회 테스트를 건너뜁니다.")
        else:
            print("API 키 또는 WBS 파일 경로 문제로 WBSAnalyzerAgent 실행을 건너뜁니다.")
            print(f"API 키 존재 여부: {'있음' if api_key_from_env else '없음'}")
            print(f"WBS 파일 존재 여부: {'있음' if os.path.exists(wbs_file_path_abs) else '없음'} (경로: {wbs_file_path_abs})")


    except (ValueError, FileNotFoundError) as e:
        print(f"\n스크립트 실행 중 설정 또는 파일 오류 발생: {e}")
    except Exception as e:
        import traceback
        print(f"\n예상치 못한 오류 발생: {e}")
        traceback.print_exc()

