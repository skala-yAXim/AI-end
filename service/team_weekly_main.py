import os
import json
import argparse
from typing import List

from ai.graphs.state_definition import TeamWeeklyLangGraphState
from ai.graphs.team_weekly_graph import create_team_weekly_graph

# weekly_report_generator 모듈에서 WeeklyReportGenerator 클래스를 임포트합니다.
# 이 스크립트는 프로젝트의 루트 디렉토리에서 실행되는 것을 가정합니다.


def run_team_weekly_workflow():
    """
    주간 업무 보고서 생성 프로세스를 실행하는 메인 함수입니다.
    """
    # 명령줄 인자를 파싱하여 사용자 정보를 받을 수 있도록 설정합니다.
    parser = argparse.ArgumentParser(description="사용자의 주간 업무 보고서를 생성합니다.")
    parser.add_argument("--team-name", type=str, default="yAXim", help="보고서를 생성할 사용자 이름")
    parser.add_argument("--team-id", type=str, default="G-12345", help="사용자의 고유 ID")
    parser.add_argument("--team_description", type=str, default="업무 관리 Agent 개발팀", help="팀 설명")
    parser.add_argument("--team_members", type=List[str], default=["고석환", "김세은", "김용준", "노건표", "여다건", "조민서"], help="소속 팀원")
    parser.add_argument("--start-date", type=str, default="2025-06-02", help="보고서 시작일 (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default="2025-06-06", help="보고서 종료일 (YYYY-MM-DD)")
    parser.add_argument("--last-week-progress", type=str, default="진행도 : 50", help="지난 주 진행 상황")
    parser.add_argument("--project-name", type=str, default="yAXim", help="프로젝트 이름")
    parser.add_argument("--project-start-date", type=str, default="2025-06-02", help="프로젝트 시작일")
    parser.add_argument("--project-end-date", type=str, default="2025-06-14", help="프로젝트 종료일")
    # 프로젝트 인풋 템플릿 삽입.
    parser.add_argument("--weekly-input-template", type=str, default="# [Pre-sales] 지누스, 생성형AI 기반 고객 리뷰 분류 PoC (w/ CV혁신산업개발팀, Data Science1팀)\n개요: 아마존의 상품 리뷰 데이터 중, 불만 데이터의 카테고리를 Hybrid(생성형+AI) 모델로 분류\n규모: 미정\n기간: 2개월\n경쟁: EY, 메가존\n진행사항: 고객 초도미팅 (7/25): ChatGPT 기반으로 고객 내부 진행 시 40% 정확도 수준 / Feasibility (7/25 ~ 7/28): 약 70% 정확도 달성 (GPT-4 활용) → 고객 미팅 (7/31): 현업 통한 사업화 타진 후 미팅 진행 / PoC 제안 고객 미팅 (8/30): 제안 방향 및 요건 확인 → 자주 제출", help="팀위클리 인풋 템플릿")
    # parser.add_argument("--weekly-input-template", type=str, default="[Pre-sales] 지누스, 생성형AI 기반 고객 리뷰 분류 PoC (w/ CV혁신산업개발팀, Data Science1팀) 개요: 아마존의 상품 리뷰 데이터 중, 불만 데이터의 카테고리를 Hybrid(생성형+AI) 모델로 분류 규모: 미정 기간: 2개월 경쟁: EY, 메가존 진행사항: 고객 초도미팅 (7/25): ChatGPT 기반으로 고객 내부 진행 시 40% 정확도 수준 / Feasibility (7/25 ~ 7/28): 약 70% 정확도 달성 (GPT-4 활용) → 고객 미팅 (7/31): 현업 통한 사업화 타진 후 미팅 진행 / PoC 제안 고객 미팅 (8/30): 제안 방향 및 요건 확인 → 자주 제출", help="팀위클리 인풋 템플릿")
    args = parser.parse_args()

    # --- 설정값 ---
    TEAM_NAME = args.team_name
    TEAM_ID = args.team_id
    TEAM_DESCRIPTION = args.team_description
    TEAM_MEMBERS = args.team_members
    START_DATE = args.start_date
    END_DATE = args.end_date
    LAST_WEEK_PROGRESS = args.last_week_progress
    PROJECT_NAME = args.project_name
    PROJECT_START_DATE = args.project_start_date
    PROJECT_END_DATE = args.project_end_date
    WEEKLY_INPUT_TEMPLATE = args.weekly_input_template
    
    # 프로젝트 루트 디렉토리 설정
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    
    # 보고서 파일들이 저장된 디렉토리 경로
    REPORTS_INPUT_DIR = os.path.join(project_root, 'outputs', 'weekly_reports')
    # 출력 디렉토리
    REPORTS_OUTPUT_DIR = os.path.join(project_root, 'outputs', 'team_weekly_reports')
    
    # 출력 디렉토리가 없으면 생성
    os.makedirs(REPORTS_OUTPUT_DIR, exist_ok=True)
    
    print("--- 주간 보고서 생성 시작 ---")
    print(f"대상 기간: {START_DATE} ~ {END_DATE}")
    print(f"일일 보고서 입력 디렉토리: {os.path.abspath(REPORTS_INPUT_DIR)}")
    print(f"주간 보고서 출력 디렉토리: {os.path.abspath(REPORTS_OUTPUT_DIR)}")
    print("-" * 30)
    
    initial_state = TeamWeeklyLangGraphState(
        team_name=TEAM_NAME,
        team_id=TEAM_ID,
        team_description=TEAM_DESCRIPTION,
        team_members=TEAM_MEMBERS,
        start_date=START_DATE,
        end_date=END_DATE,
        project_id="project_sample_001",
        wbs_data=None,
        weekly_reports_data=None,
        team_weekly_report_result=None,
        error_message="",
        last_week_progress=LAST_WEEK_PROGRESS,
        project_name=PROJECT_NAME,
        project_start_date=PROJECT_START_DATE,
        project_end_date=PROJECT_END_DATE,
        weekly_input_template=WEEKLY_INPUT_TEMPLATE,
    )
    
    # --- 실행 ---
    try:
        app = create_team_weekly_graph()
        
        print(f"DEBUG: initial_state: {initial_state}")

        print("\n--- LangGraph 워크플로우 실행 시작 ---")
        final_state = app.invoke(initial_state)
        print("--- LangGraph 워크플로우 실행 완료 ---\n")

        print("최종 분석 결과 (State 내용):")
        
        team_weekly_report_result = final_state.get("team_weekly_report_result")
        if team_weekly_report_result:
            if team_weekly_report_result and not team_weekly_report_result.get("error"):
                print("주간 보고서 생성 성공!")
                
                output_filename = f"weekly_report_{TEAM_NAME}_{START_DATE}_to_{END_DATE}.json"
                output_filepath = os.path.join(REPORTS_OUTPUT_DIR, output_filename)
                
                with open(output_filepath, "w", encoding="utf-8") as f:
                    json.dump(team_weekly_report_result, f, ensure_ascii=False, indent=4)
                    
                print(f"\n[성공] 주간 보고서가 다음 경로에 저장되었습니다:\n{os.path.abspath(output_filepath)}")
                
                # 생성된 보고서 내용 미리보기 출력
                print("\n--- 생성된 주간 보고서 내용 미리보기 ---")
                print(json.dumps(team_weekly_report_result, ensure_ascii=False, indent=2))
                print("---------------------------------------\n")
            else:
                print(f"\n[실패] 주간 보고서 생성에 실패했습니다: {team_weekly_report_result['message']}")
        else:
            print("\n[알림] 주간 보고서를 생성할 데이터가 없어 작업을 종료합니다.")
    except Exception as e:
        print(f"\n[오류] 예기치 않은 오류가 발생했습니다: {e}")

if __name__ == '__main__':
    # 이 스크립트가 직접 실행될 때 main 함수를 호출합니다.
    run_team_weekly_workflow()