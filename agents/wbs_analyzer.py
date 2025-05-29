import pandas as pd
import chromadb
import hashlib
import json
import os
from typing import Dict, List, Any

# LangChain 및 OpenAI 관련 임포트
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

# .env 파일 로드 (실제 실행은 main.py에서 하는 것이 좋음)
load_dotenv()

class WBSAnalyzerAgent:
    """
    WBS 파일을 분석하여 LLM으로 처리하고, 그 결과를 VectorDB(ChromaDB)에
    업무 단위로 청킹하여 저장(캐싱)하는 에이전트.
    WBS 업데이트를 감지하여 기존 데이터를 처리합니다.
    """

    def __init__(self, project_id: str, wbs_file_path: str):
        """
        에이전트를 초기화합니다.

        Args:
            project_id (str): WBS가 속한 프로젝트의 고유 ID.
            wbs_file_path (str): 분석할 WBS 파일 경로 (Excel).
        """
        self.project_id = project_id
        self.wbs_file_path = wbs_file_path
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.vector_db_path = os.getenv("VECTOR_DB_PATH", "db/vector_store")
        self.collection_name = "wbs_analysis" # WBS 데이터를 저장할 컬렉션 이름

        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        if not os.path.exists(self.wbs_file_path):
            raise FileNotFoundError(f"WBS 파일을 찾을 수 없습니다: {self.wbs_file_path}")

        # ChromaDB 클라이언트 및 컬렉션 설정
        self.client = chromadb.PersistentClient(path=self.vector_db_path)
        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=self.openai_api_key,
            model_name="text-embedding-ada-002" # 혹은 최신 임베딩 모델
        )
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function
        )

        # LangChain LLM 및 프롬프트 설정
        self.llm = ChatOpenAI(model_name="gpt-4-1106-preview", openai_api_key=self.openai_api_key, temperature=0) # 혹은 gpt-4
        self.prompt = self._load_prompt("prompts/wbs_prompt.md")

    def _load_prompt(self, prompt_path: str) -> PromptTemplate:
        """프롬프트 파일을 로드합니다."""
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                template = f.read()
            return PromptTemplate.from_template(template)
        except FileNotFoundError:
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {prompt_path}")

    def _calculate_hash(self) -> str:
        """WBS 파일 내용의 SHA256 해시를 계산합니다."""
        hasher = hashlib.sha256()
        try:
            with open(self.wbs_file_path, 'rb') as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            print(f"Error calculating hash: {e}")
            raise

    def _read_wbs_to_text(self) -> str:
        """Excel WBS 파일을 읽어 LLM에 전달할 텍스트 형식으로 변환합니다."""
        try:
            df = pd.read_excel(self.wbs_file_path)
            # 데이터프레임을 JSON 문자열로 변환 (LLM이 이해하기 용이)
            return df.to_json(orient='records', indent=2, force_ascii=False)
        except Exception as e:
            print(f"Error reading WBS file: {e}")
            raise

    def _get_existing_hash(self) -> str | None:
        """현재 project_id로 저장된 데이터의 해시를 가져옵니다."""
        results = self.collection.get(
            where={"project_id": self.project_id},
            limit=1,
            include=["metadatas"]
        )
        if results and results['metadatas']:
            return results['metadatas'][0].get('wbs_hash')
        return None

    def _delete_old_data(self):
        """현재 project_id와 관련된 모든 데이터를 삭제합니다."""
        # ChromaDB는 ID 목록으로 삭제하므로, 먼저 ID를 조회해야 합니다.
        ids_to_delete = []
        offset = 0
        limit = 100 # 한 번에 가져올 ID 개수
        while True:
            results = self.collection.get(
                where={"project_id": self.project_id},
                limit=limit,
                offset=offset,
                include=[] # ID만 필요
            )
            if not results or not results['ids']:
                break
            ids_to_delete.extend(results['ids'])
            offset += limit

        if ids_to_delete:
            print(f"Deleting {len(ids_to_delete)} old entries for project {self.project_id}...")
            self.collection.delete(ids=ids_to_delete)
            print("Deletion complete.")
        else:
            print(f"No existing data found for project {self.project_id}.")


    def _process_with_llm(self, wbs_text: str) -> Dict[str, Any]:
        """LLM을 사용하여 WBS 텍스트를 분석하고 JSON 결과를 반환합니다."""
        print("Sending WBS data to LLM for analysis...")
        chain = (
            {"wbs_data": RunnablePassthrough()}
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        try:
            response = chain.invoke(wbs_text)
            print("LLM analysis complete.")
            # LLM 응답에서 JSON만 추출 (가끔 불필요한 텍스트가 붙는 경우 대비)
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end != -1:
                json_response = response[json_start:json_end]
                return json.loads(json_response)
            else:
                raise ValueError("LLM did not return a valid JSON response.")
        except json.JSONDecodeError as e:
            print(f"Error decoding LLM JSON response: {e}")
            print(f"LLM Response:\n{response}")
            raise
        except Exception as e:
            print(f"Error during LLM processing: {e}")
            raise

    def _chunk_and_store(self, llm_output: Dict[str, Any], wbs_hash: str):
        """LLM 결과를 업무 단위로 청킹하여 VectorDB에 저장합니다."""
        documents: List[str] = []
        metadatas: List[Dict] = []
        ids: List[str] = []
        id_counter = 0

        print("Chunking and preparing data for VectorDB...")

        def add_item(item: Dict, output_type: str):
            nonlocal id_counter
            # 담당자와 기간 추출 (없으면 None)
            assignee = item.get('assignee')
            start_date = item.get('start_date')
            end_date = item.get('end_date')
            task_id = item.get('task_id') or item.get('goal_id') or item.get('sub_task_id') or f"dep_{id_counter}"

            # 문서 텍스트 생성 (LLM이 검색하기 좋도록)
            doc_text = f"Type: {output_type}, Task: {item.get('description', json.dumps(item, ensure_ascii=False))}"
            if assignee: doc_text += f", Assignee: {assignee}"
            if start_date: doc_text += f", Start: {start_date}"
            if end_date: doc_text += f", End: {end_date}"

            # 메타데이터 생성 (필터링용)
            meta = {
                "project_id": self.project_id,
                "wbs_hash": wbs_hash,
                "output_type": output_type,
                "task_id": str(task_id), # ID는 문자열로
                # 담당자와 기간이 있는 경우에만 메타데이터에 추가
                **({"assignee": assignee} if assignee else {}),
                **({"start_date": start_date} if start_date else {}),
                **({"end_date": end_date} if end_date else {}),
                "original_data": json.dumps(item, ensure_ascii=False) # 원본 데이터 저장
            }

            documents.append(doc_text)
            metadatas.append(meta)
            ids.append(f"{self.project_id}_{wbs_hash}_{output_type}_{id_counter}")
            id_counter += 1

        # 각 항목별로 처리
        for task in llm_output.get("personal_tasks", []):
            add_item(task, "personal_task")
        for goal in llm_output.get("personal_goals", []):
            add_item(goal, "personal_goal")
        for dep in llm_output.get("dependencies", []):
            add_item(dep, "dependency")
        for sub_task in llm_output.get("sub_tasks", []):
            add_item(sub_task, "sub_task")

        # VectorDB에 저장
        if documents:
            print(f"Adding {len(documents)} new entries to VectorDB...")
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print("Data added successfully.")
        else:
            print("No data generated by LLM to store.")

    def run(self):
        """WBS 분석 및 캐싱 프로세스를 실행합니다."""
        print(f"Starting WBS analysis for project: {self.project_id}")
        print(f"WBS file: {self.wbs_file_path}")

        current_hash = self._calculate_hash()
        existing_hash = self._get_existing_hash()

        if current_hash == existing_hash:
            print(f"WBS data for {self.project_id} (hash: {current_hash}) is already up-to-date. Skipping.")
            return

        print(f"New WBS version detected (New: {current_hash}, Old: {existing_hash}). Processing...")

        # 기존 데이터 삭제 (새 버전이므로 무조건 삭제 후 추가)
        self._delete_old_data()

        # WBS 읽기 및 LLM 처리
        wbs_text = self._read_wbs_to_text()
        llm_output = self._process_with_llm(wbs_text)

        # VectorDB에 저장
        self._chunk_and_store(llm_output, current_hash)

        print(f"WBS analysis for project {self.project_id} completed.")


if __name__ == '__main__':

    try:
        # data 폴더에 샘플 WBS 파일이 있다고 가정
        wbs_file = 'data/wbs/project_wbs.xlsx'
        # project_id는 파일명이나 경로에서 추출하거나, 직접 지정
        proj_id = 'my_awesome_project'

        # WBS 파일이 없으면 샘플 생성 (테스트용)
        if not os.path.exists(wbs_file):
            os.makedirs(os.path.dirname(wbs_file), exist_ok=True)
            sample_data = {
                'ID': ['1', '1.1', '1.2', '2'],
                'Task Name': ['기획', '요구사항 정의', '화면 설계', '개발'],
                'Assignee': ['Alice', 'Alice', 'Bob', 'Charlie'],
                'Start Date': ['2025-06-01', '2025-06-01', '2025-06-03', '2025-06-10'],
                'End Date': ['2025-06-09', '2025-06-05', '2025-06-09', '2025-07-10'],
                'Status': ['In Progress', 'Done', 'In Progress', 'To Do']
            }
            pd.DataFrame(sample_data).to_excel(wbs_file, index=False)
            print(f"Created sample WBS file: {wbs_file}")


        agent = WBSAnalyzerAgent(project_id=proj_id, wbs_file_path=wbs_file)
        agent.run()

        # --- VectorDB 조회 예시 (테스트용) ---
        print("\n--- Testing VectorDB Query ---")
        client = chromadb.PersistentClient(path=os.getenv("VECTOR_DB_PATH", "db/vector_store"))
        collection = client.get_collection(name="wbs_analysis")

        # Alice의 2025-06-01 ~ 2025-06-05 사이 작업 조회 (메타데이터 필터링)
        # 참고: ChromaDB의 메타데이터 필터링은 현재 '$and', '$or' 등 복잡한 쿼리는 지원하지만,
        # 날짜 범위 같은 '대소 비교'는 직접 지원하지 않을 수 있습니다.
        # 이 경우, 가져온 후 Python에서 필터링하거나, 날짜를 숫자로 변환하여 저장하는 전략이 필요할 수 있습니다.
        # 여기서는 담당자로만 필터링합니다.
        results = collection.get(
            where={
                "$and": [
                    {"project_id": proj_id},
                    {"assignee": "Alice"},
                    {"output_type": "personal_task"}
                ]
            },
            include=["documents", "metadatas"]
        )
        print("\nAlice's Tasks:")
        for doc, meta in zip(results['documents'], results['metadatas']):
            print(f"  - {doc} (Meta: {meta})")

    except (ValueError, FileNotFoundError, Exception) as e:
        print(f"\nAn error occurred: {e}")