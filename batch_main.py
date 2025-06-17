# main.py (간략화된 버전)
import os
import sys
from dotenv import load_dotenv
import json 
from datetime import datetime
import time
import schedule

# 현재 디렉토리를 sys.path에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from ai.graphs.daily_graph import create_analysis_graph 
from ai.graphs.state_definition import LangGraphState

from langchain.globals import set_llm_cache
set_llm_cache(None)

# 하드코딩된 사용자 데이터
HARDCODED_USERS = [
    {
        'user_id': 4,
        'user_name': '조민서',
        'project_id': 'project_sample_001',
        'github_email': 'minsuh3203@gmail.com',
        'project_name': '개인 업무 관리 AI 프로젝트',
        'project_description': 'AI 기술로 자동 수집·분석하여 객관적이고 정확한 개인 업무 성과 보고서를 자동 생성하는 시스템'
    },
    {
        'user_id': 7,
        'user_name': "노건표",
        'project_id': 'project_sample_001',
        'github_email': 'kproh99@naver.com',
        'project_name': '개인 업무 관리 AI 프로젝트',
        'project_description': 'AI 기술로 자동 수집·분석하여 객관적이고 정확한 개인 업무 성과 보고서를 자동 생성하는 시스템'
    },
]

def run_analysis_workflow(user_config):
    """단일 사용자 분석 워크플로우 실행 (간략화된 버전)"""
    load_dotenv()
    
    # 사용자 정보 설정
    input_user_id = user_config['user_id']
    input_user_name = user_config['user_name']
    input_github_email = user_config.get('github_email', user_config['user_id'])
    input_target_date = datetime.now().strftime('%Y-%m-%d')
    input_project_id = user_config['project_id']
    input_project_name = user_config['project_name']
    input_project_description = user_config.get('project_description', '')

    print(f"{input_user_name} 분석 중... (날짜: {input_target_date})")
    
    # LangGraph State 생성
    initial_state = LangGraphState(
        user_id=input_user_id,
        user_name=input_user_name,
        github_email=input_user_id,
        target_date=input_target_date,
        project_id=input_project_id,
        docs_quality_analysis_result=None,
        documents_analysis_result=None,
        email_analysis_result=None,
        git_analysis_result=None,
        teams_analysis_result=None,
        wbs_data=None,
        comprehensive_report=None,
        project_name=input_project_name,
        project_description=input_project_description,
        error_message="" 
    )

    try:
        # LangGraph 워크플로우 실행
        app = create_analysis_graph()
        final_state = app.invoke(initial_state)

        # 보고서 저장
        comprehensive_report = final_state.get("comprehensive_report")
        if comprehensive_report and not comprehensive_report.get("error"):
            # 파일 저장
            json_string = json.dumps(comprehensive_report, ensure_ascii=False, indent=2)
            output_filename = f"daily_report_{input_user_name}_{input_target_date}.json"
            output_path = os.path.join("outputs", output_filename)
            os.makedirs("outputs", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_string)
            
            print(f"✅ {input_user_name} 완료: {output_path}")
            return {"status": "success", "output_file": output_path}
        else:
            print(f"❌ {input_user_name} 보고서 생성 실패")
            return {"status": "failed", "error": "Report generation failed"}

    except Exception as e:
        print(f"❌ {input_user_name} 오류: {e}")
        return {"status": "error", "error": str(e)}


def run_batch():
    """배치 실행 (간략화된 버전)"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{timestamp}] 배치 시작 - {len(HARDCODED_USERS)}명")
    
    success_count = 0
    for i, user in enumerate(HARDCODED_USERS, 1):
        print(f"[{i}/{len(HARDCODED_USERS)}] ", end="")
        try:
            result = run_analysis_workflow(user)
            if result['status'] == 'success':
                success_count += 1
        except Exception as e:
            print(f"❌ {user['user_name']} 예외 오류: {e}")
    
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] 배치 완료 - 성공: {success_count}/{len(HARDCODED_USERS)}명\n")


def run_scheduler_auto():
    """정해진 시간(09:00, 18:00)에 배치 실행하는 스케줄러"""
    print("="*50)
    print("Daily Report 자동 스케줄러")
    print("실행 시간: 매일 09:00, 18:00")
    print(f"대상 사용자: {len(HARDCODED_USERS)}명")
    print(f"현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    print("Ctrl+C로 중지할 수 있습니다.\n")
    
    # 스케줄 등록 (고정 시간)
    schedule.every().day.at("11:46").do(run_batch)
    
    # 다음 실행 시간 표시
    next_run = schedule.next_run()
    if next_run:
        print(f"⏰ 다음 실행: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n스케줄러 실행 중...")
    try:
        loop_count = 0
        while True:
            loop_count += 1
            schedule.run_pending()
            
            # 상태 정보 출력 (1시간마다)
            if loop_count % 60 == 1:  # 60분마다
                next_run = schedule.next_run()
                if next_run:
                    print(f"⏳ [{datetime.now().strftime('%H:%M')}] 다음 실행: {next_run.strftime('%m/%d %H:%M')}")
            
            time.sleep(60)  # 1분마다 체크
            
    except KeyboardInterrupt:
        print(f"\n🛑 스케줄러 중지됨: {datetime.now().strftime('%H:%M:%S')}")


def run_scheduler_test():
    """테스트용 1분마다 실행"""
    print("="*50)
    print("테스트 스케줄러 (1분마다 실행)")
    print(f"대상 사용자: {len(HARDCODED_USERS)}명")
    print("="*50)
    
    schedule.every(1).minutes.do(run_batch)
    
    print("첫 번째 실행...")
    run_batch()
    
    print("1분마다 자동 실행 중... (Ctrl+C로 중지)")
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n🛑 테스트 스케줄러 중지됨")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "batch":
            # 배치 한 번만 실행
            run_batch()
        elif sys.argv[1] == "auto":
            # 정해진 시간(09:00, 18:00) 자동 스케줄러
            run_scheduler_auto()
        elif sys.argv[1] == "test":
            # 테스트용 1분마다 실행
            run_scheduler_test()
        else:
            print("사용법:")
            print("  python main.py batch     # 배치 한 번만 실행")
            print("  python main.py auto      # 자동 스케줄러 (매일 09:00, 18:00)")
            print("  python main.py test      # 테스트용 (1분마다)")
    else:
        # 기본: 첫 번째 사용자 단일 실행
        if HARDCODED_USERS:
            result = run_analysis_workflow(HARDCODED_USERS[0])
            print(f"단일 실행 완료: {result['status']}")
        else:
            print("설정된 사용자가 없습니다.")