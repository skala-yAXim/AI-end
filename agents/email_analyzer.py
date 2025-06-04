"""
이메일-WBS 업무 분석기
============================
작성자: 김용준
기능: 이메일 데이터 분석 및 WBS 업무 매칭
"""

import openai
import json
import os
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv


class EmailAnalyzer:
    """이메일-WBS 업무 분석기"""
    
    def __init__(self, config_path: str = None):
        # 환경 설정
        load_dotenv()
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
        # 사용자 매핑 테이블 로드
        self.user_mapping = self._load_user_mapping(config_path)
        
        # 프롬프트 로드
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "email_analyze_prompt.md")
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.prompt_template = f.read()
        
        print("✅ EmailAnalyzer 초기화 완료")
    
    def _load_user_mapping(self, config_path: str = None) -> Dict[str, str]:
        """사용자 이메일-이름 매핑 테이블 로드"""
        # 임시 매핑 (추후 DB나 설정파일로 대체)
        return {
            "qkdrkzx@yasim2861.onmicrosoft.com": "김용준",
            "minsuh3203@yasim2861.onmicrosoft.com": "조민서", 
            "dyeo@yasim2861.onmicrosoft.com": "여다건",
            "kosssshhhh@yasim2861.onmicrosoft.com": "고석환",
            "kpro@yasim2861.onmicrosoft.com": "노건표",
            "sermadl1014@yasim2861.onmicrosoft.com": "김세은",
            "472dyd@yasim2861.onmicrosoft.com": "김준용"
        }
    
    def _convert_wbs_status_to_korean(self, status: str) -> str:
        """WBS 상태를 한국어로 변환"""
        status_map = {
            "completed": "완료", "complete": "완료", "done": "완료",
            "in_progress": "진행중", "progress": "진행중", "ongoing": "진행중",
            "planned": "계획", "plan": "계획", "todo": "계획"
        }
        return status_map.get(status.lower(), "진행중")
    
    def load_data(self, email_path: str = None, wbs_path: str = None) -> tuple:
        """이메일과 WBS 데이터 통합 로드"""
        # 기본 경로 설정
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        email_path = email_path or os.path.join(data_dir, "outlook_test_data.json")
        wbs_path = wbs_path or os.path.join(data_dir, "wbs_analysis_result.json")
        
        # 데이터 로드
        with open(email_path, 'r', encoding='utf-8') as f:
            email_data = json.load(f)
        with open(wbs_path, 'r', encoding='utf-8') as f:
            wbs_data = json.load(f)
        
        return self._process_email_data(email_data), wbs_data
    
    def _process_email_data(self, raw_data: List[Dict]) -> List[Dict]:
        """이메일 데이터 전처리"""
        processed = []
        for user_emails in raw_data:
            user_id = user_emails['author']
            for email in user_emails.get('emails', []):
                processed.append({
                    'user_id': user_id,
                    'subject': email.get('subject', ''),
                    'date': email.get('date', ''),
                    'content': email.get('content', ''),
                    'attachments': email.get('attachment_list', [])
                })
        return processed
    
    def analyze_user_tasks(self, user_id: str = None, target_date: str = None) -> Dict:
        """특정 사용자의 업무 분석 (기본값: 김용준)"""
        # 기본값 설정 (임시로 나를 기본 사용자로 설정)
        user_id = user_id or "qkdrkzx@yasim2861.onmicrosoft.com"
        target_date = target_date or datetime.now().strftime("%Y-%m-%d")
        
        # 데이터 로드
        emails, wbs_data = self.load_data()
        
        # 사용자별 데이터 필터링
        user_emails = self._filter_user_emails(emails, user_id, target_date)
        user_wbs = self._filter_user_wbs(wbs_data, user_id)
        
        if not user_emails:
            return self._create_empty_result(user_id, target_date)
        
        # LLM 분석
        return self._analyze_with_llm(user_id, target_date, user_emails, user_wbs)
    
    def _filter_user_emails(self, emails: List[Dict], user_id: str, target_date: str) -> List[Dict]:
        """사용자별 이메일 필터링"""
        return [email for email in emails 
                if email['user_id'] == user_id and target_date in email['date']]
    
    def _filter_user_wbs(self, wbs_data: Dict, user_id: str) -> List[Dict]:
        """사용자별 WBS 업무 필터링"""
        user_name = self.user_mapping.get(user_id, user_id)
        tasks = []
        for task in wbs_data.get('task_list', []):
            if task.get('assignee') == user_name:
                # WBS 상태를 한국어로 변환
                task['status'] = self._convert_wbs_status_to_korean(task.get('status', ''))
                tasks.append(task)
        return tasks
    
    def _analyze_with_llm(self, user_id: str, target_date: str, 
                         emails: List[Dict], wbs_tasks: List[Dict]) -> Dict:
        """LLM을 사용한 업무 분석"""
        # 프롬프트에 맞는 데이터 포맷팅
        prompt = self.prompt_template.format(
            target_user=user_id,
            target_date=target_date,
            email_data=json.dumps(emails, ensure_ascii=False, indent=2),
            wbs_data=json.dumps(wbs_tasks, ensure_ascii=False, indent=2)
        )
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 이메일-WBS 업무 분석 전문가입니다. 주어진 프롬프트를 정확히 따라 JSON 형식으로 응답하세요."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            print(f"✅ LLM 분석 완료: {len(result.get('matched_tasks', []))}개 매칭, {len(result.get('unmatched_tasks', []))}개 미매칭")
            return result
            
        except Exception as e:
            print(f"⚠️ LLM 분석 실패: {e}")
            return self._create_empty_result(user_id, target_date)
    
    def _create_empty_result(self, user_id: str, target_date: str) -> Dict:
        """빈 결과 생성"""
        return {
            "user_id": user_id,
            "date": datetime.now().isoformat(),
            "type": "Email",
            "matched_tasks": [],
            "unmatched_tasks": []
        }


def main():
    """메인 실행 함수"""
    print("🚀 EmailAnalyzer 시작")
    
    # 분석기 초기화
    analyzer = EmailAnalyzer()
    
    # 분석 실행 (기본: 나의 오늘 업무)
    result = analyzer.analyze_user_tasks(
        user_id="qkdrkzx@yasim2861.onmicrosoft.com",  # 임시 기본값
        target_date="2025-05-28"  # 테스트 날짜
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    return result


if __name__ == "__main__":
    result = main()
