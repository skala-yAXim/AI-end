# tools/wbs_matcher.py

import os
import sys
from typing import Dict, Any, List, Optional
from difflib import SequenceMatcher
from qdrant_client import QdrantClient
import json

# 경로 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core import config
from tools.vector_db_retriever import retrieve_wbs_data, retrieve_documents_for_wbs_matching


class WBSMatcher:
    """
    WBS(Work Breakdown Structure)와 문서를 매칭하는 클래스
    Qdrant 벡터 DB를 사용하여 데이터를 검색하고 매칭합니다.
    """

    def __init__(self, qdrant_client: QdrantClient):
        self.qdrant_client = qdrant_client
        self.similarity_threshold = 0.1

    def match_documents_to_wbs(
        self,
        user_id: str,
        project_id: Optional[str] = None,
        scroll_limit: int = 50
    ) -> Dict[str, Any]:
        # 1. WBS 데이터 검색
        wbs_data_list = retrieve_wbs_data(
            qdrant_client=self.qdrant_client,
            project_id=project_id,
            scroll_limit=scroll_limit
        )
        
        if not wbs_data_list:
            return self._create_error_result("WBS 데이터를 찾을 수 없습니다.")

        # 2. Deliverable 추출
        deliverable_info = self._extract_deliverables_from_original_data(wbs_data_list)
        deliverables = list(deliverable_info.keys())
        
        if not deliverables:
            return self._create_error_result("WBS deliverable을 찾을 수 없습니다.")

        # 3. 사용자 문서 검색
        documents = retrieve_documents_for_wbs_matching(
            qdrant_client=self.qdrant_client,
            user_id=user_id,
            deliverable_keywords=deliverables,
            scroll_limit=scroll_limit
        )

        if not documents:
            return self._create_error_result(f"사용자 '{user_id}'의 문서를 찾을 수 없습니다.")

        # 4. 매칭 수행
        matched_result = self._perform_matching(documents, deliverables)

        return self._create_success_result(matched_result, documents, deliverables, deliverable_info)

    def get_matched_content_for_quality_analysis(
        self, 
        matched_result: Dict[str, Any], 
        deliverable: str,
        similarity_threshold: float = 0.2
    ) -> List[str]:
        matched_deliverables = matched_result.get("matched_deliverables", {})
        matched_docs = matched_deliverables.get(deliverable, [])
        
        high_quality_contents = []
        for doc in matched_docs:
            similarity = doc.get("similarity_score", 0)
            if similarity >= similarity_threshold:
                content = doc.get("page_content", "")
                if content and content.strip():
                    high_quality_contents.append(content.strip())
        
        return high_quality_contents

    def _extract_deliverables_from_original_data(self, wbs_data_list: List[Dict]) -> Dict[str, Dict]:
        """
WBS original_data에서 deliverables와 task 정보를 추출합니다.

Returns:
    Dict[deliverable, {"task_id": str, "task_name": str}]
"""
        deliverable_info = {}
        
        for wbs_data in wbs_data_list:
            metadata = wbs_data.get("metadata", {})
            original_data = metadata.get("original_data")
            
            if not original_data:
                continue
                
            try:
                original_parsed = json.loads(original_data)
                
                # task 정보 추출
                task_id = original_parsed.get("task_id", "")
                task_name = original_parsed.get("task_name", "")
                
                if "deliverables" in original_parsed:
                    deliverables_value = original_parsed["deliverables"]
                    
                    if deliverables_value is None:
                        continue
                    
                    deliverables_list = []
                    if isinstance(deliverables_value, list):
                        deliverables_list = [str(item).strip() for item in deliverables_value if item is not None and str(item).strip()]
                    elif isinstance(deliverables_value, str) and deliverables_value.strip():
                        deliverables_list = [deliverables_value.strip()]
                    
                    # 각 deliverable에 task 정보 매핑
                    for deliverable in deliverables_list:
                        if deliverable not in deliverable_info:
                            deliverable_info[deliverable] = {
                                "task_id": task_id or f"task_{len(deliverable_info) + 1}",
                                "task_name": task_name or deliverable
                            }
                    
            except (json.JSONDecodeError, Exception):
                continue

        return deliverable_info

    def _perform_matching(self, documents: List[Dict], deliverables: List[str]) -> Dict[str, List[Dict]]:
        matched = {deliverable: [] for deliverable in deliverables}

        for doc in documents:
            filename = doc.get("metadata", {}).get("filename", "")
            page_content = doc.get("page_content", "")
            
            best_match = self._find_best_match(filename, page_content, deliverables)

            if best_match:
                doc_with_match = doc.copy()
                doc_with_match.update(best_match)
                matched[best_match["matched_deliverable"]].append(doc_with_match)
        
        return matched

    def _find_best_match(self, filename: str, content: str, deliverables: List[str]) -> Optional[Dict[str, Any]]:
        best_similarity = 0.0
        best_match = None
        best_match_type = ""

        for deliverable in deliverables:
            # 정확한 매칭 우선
            if deliverable.lower() in filename.lower():
                exact_similarity = 0.9
                match_type = "파일명 포함"
                if exact_similarity > best_similarity:
                    best_similarity = exact_similarity
                    best_match = deliverable
                    best_match_type = match_type
                continue
            
            # 파일명 유사도
            filename_without_ext = filename.lower()
            if '.' in filename_without_ext:
                filename_without_ext = filename_without_ext.rsplit('.', 1)[0]
            
            filename_similarity = self._calculate_similarity(filename_without_ext, deliverable.lower())
            
            # 내용 유사도
            content_preview = content[:300] if content else ""
            content_similarity = self._calculate_similarity(content_preview.lower(), deliverable.lower())

            if filename_similarity > content_similarity:
                max_similarity = filename_similarity
                match_type = "파일명"
            else:
                max_similarity = content_similarity
                match_type = "내용"

            if max_similarity > best_similarity and max_similarity >= self.similarity_threshold:
                best_similarity = max_similarity
                best_match = deliverable
                best_match_type = match_type

        if best_match:
            return {
                "matched_deliverable": best_match,
                "similarity_score": round(best_similarity, 3),
                "match_type": best_match_type
            }

        return None

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        return SequenceMatcher(None, text1, text2).ratio()

    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        return {
            "error": error_message,
            "matched_deliverables": {},
            "total_documents": 0,
            "total_matched": 0,
            "total_deliverables": 0,
            "matched_deliverable_count": 0,
            "matching_rate": 0.0,
            "summary": f"매칭 실패: {error_message}"
        }

    def _create_success_result(self, matched: Dict[str, List[Dict]], documents: List[Dict], deliverables: List[str], deliverable_info: Dict[str, Dict]) -> Dict[str, Any]:
        total_matched = sum(len(docs) for docs in matched.values())
        matched_deliverable_count = len([d for d, docs in matched.items() if docs])
        matching_rate = round(total_matched / len(documents) * 100, 1) if documents else 0

        return {
            "matched_deliverables": matched,
            "all_deliverables": deliverables,
            "deliverable_info": deliverable_info,  # task 정보 추가
            "total_documents": len(documents),
            "total_matched": total_matched,
            "total_deliverables": len(deliverables),
            "matched_deliverable_count": matched_deliverable_count,
            "matching_rate": matching_rate,
            "summary": f"{len(documents)}개 문서 중 {total_matched}개 매칭 완료 (매칭률: {matching_rate}%)"
        }
