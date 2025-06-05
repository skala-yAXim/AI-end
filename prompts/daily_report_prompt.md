## 보고서 템플릿
DAILY_REPORT_PROMPT = """
다음 정보를 바탕으로 {user_name}님의 {target_date} 업무 진행 현황에 대한 종합 보고서를 JSON 형식으로 작성해주세요.

### 사용자 정보
- **사용자 ID**: {user_id}
- **사용자 이름**: {user_name}
- **대상 날짜**: {target_date}

## 입력 데이터
### WBS 데이터
```json
{wbs_data}
```

### 문서 분석 결과
```json
{docs_analysis}
```

### Teams 분석 결과
```json
{teams_analysis}
```

### Git 분석 결과
```json
{git_analysis}
```

### 이메일 분석 결과
```json
{email_analysis}
```

## 보고서 생성 지침
### 1. 보고서 기본 구조

- "report_title" 필드에는 작성자 이름과 날짜가 들어갑니다. 예: "홍길동님의 2025-06-05 일일 업무 보고서"
- "info" 필드는 업무 개요와 핵심 지표를 포함합니다.
  - "date": 보고서 작성 날짜 (예: 2025-06-05)
  - "total_tasks": 오늘 처리한 업무 총 개수
  - "completed_tasks": 완료한 업무 수
  - "in_progress_tasks": 진행 중인 업무 수
  - "daily_achievement": 오늘의 주요 성과를 한 문장으로 요약
  - "key_metrics": 코딩 시간, 참석한 회의 수, 작성한 문서 수 등 업무 관련 핵심 수치 포함

---

### 2. daily_report (일일 업무 진행 내용)

- "title"은 "📌 일일 업무 진행 내용"으로 고정합니다.
- "content"는 업무 진행 상황을 설명하는 여러 문단으로 구성됩니다.
- 각 문단은 다음을 포함해야 합니다:
  - "text": 자연스럽고 간결한 문장으로 업무 내용을 설명
  - 업무명과 task_id는 "**"로 강조하며 괄호 안에 task_id를 포함합니다. 예: **이상 탐지 알고리즘 성능 개선(WBS-231)**
  - "evidence":  **기존 분석 결과(docs_analysis, teams_analysis, git_analysis, email_analysis)의 evidence 내용을 그대로 인용**
    - "title": 문서명 또는 회의명
    - "content": 문서나 회의의 핵심 내용 요약 
    - "llm_reference":
        - 예시: docs_analysis의 matched_tasks[0].evidence[0].content 내용을 그대로 가져오기
        - 예시: teams_analysis의 unmatched_tasks[1].evidence[0].content 내용을 그대로 가져오기
        - 예시: git_analysis의 matched_tasks[0].evidence[0].content 내용을 그대로 가져오기

- 업무 완료, 진행 중 상황, 회의 내용, 특이 사항 등을 포함해 전체 업무 흐름을 알기 쉽게 작성하세요.

---

### 3. daily_reflection (오늘의 회고 및 개선점)

- "title"은 "🔍 오늘의 회고 및 개선점"으로 고정합니다.
- "content"는 리스트 형식으로, 업무 중 느낀 점과 개선할 점, 향후 계획을 적습니다.
- 긍정적인 점과 아쉬운 점, 구체적인 개선 방안까지 균형 있게 서술하세요.

### 응답 요구사항

- 보고서는 객관적이고 데이터에 기반해야 합니다.
- 모든 수치는 정확해야 합니다.
- 중요한 정보와 이슈를 강조하세요.
- 보고서는 간결하면서도 필요한 정보를 모두 포함해야 합니다.
- 마크다운 형식을 사용하여 가독성을 높이세요.
- 데이터가 부족한 경우, 해당 섹션에 "데이터 없음" 또는 "해당 없음"으로 표시하세요.

## 보고서 템플릿
DAILY_REPORT_PROMPT = """
다음 정보를 바탕으로 {user_name}님의 {target_date} 업무 진행 현황에 대한 종합 보고서를 JSON 형식으로 작성해주세요.

다음 JSON 구조로 **Daily 보고서 형식의 완전한 보고서 데이터**를 작성해주세요:

```json
{{
  "report_title": "홍길동님의 2025-06-05 일일 업무 보고서",
  "info": {{
    "date": "{target_date}",
    "total_tasks": 5,
    "completed_tasks": 2,
    "in_progress_tasks": 2,
    "daily_achievement": "AI 기반 이상 탐지 알고리즘 개선 완료 및 문서화",
    "key_metrics": {{
      "coding_time": "6시간",
      "meetings_attended": 2,
      "documents_created": 1
    }}
  }},
  "daily_report": {{
    "title": "📌 일일 업무 진행 내용",
    "summray": "오늘은 총 5개의 업무 항목 중 2건을 완료하고 2건을 진행 중입니다.",
    "contents": [
      {
        "text": "**이상 탐지 알고리즘 성능 개선(WBS-231)** 작업을 완료하였습니다. 기존 F1-score 0.82에서 0.94로 향상되었으며, 개선 과정 및 실험 결과는 문서로 정리되어 공유되었습니다.",
        "evidence": [
           {
              "title": "2025-06-05_AnomalyDetection_ModelRefactor.docx",
              "content": "성능 개선 결과 및 테스트 비교표 포함",
              "LLM_reference": "docs_analysis.section[3]"
           },
           {
              "title": "2025-06-05_AnomalyDetection_ModelRefactor.docx",
              "content": "성능 개선 결과 및 테스트 비교표 포함",
              "LLM_reference": "docs_analysis.section[3]"
           }
        ]
      },
      {
        "text": "**데이터 파이프라인 안정성 점검(WBS-234)** 작업에서는 로그 누락 현상을 중심으로 데이터 흐름을 추적했습니다. 로그 누락이 발생한 시점을 중심으로 전처리 모듈을 재실행하여 오류 발생 조건을 파악하고 있습니다.",
        "evidence": [
           {
              "title": "2025-06-05_AnomalyDetection_ModelRefactor.docx",
              "content": "성능 개선 결과 및 테스트 비교표 포함",
              "LLM_reference": "docs_analysis.section[3]"
           },
           {
              "title": "2025-06-05_AnomalyDetection_ModelRefactor.docx",
              "content": "성능 개선 결과 및 테스트 비교표 포함",
              "LLM_reference": "docs_analysis.section[3]"
           }
        ]
      },
      {
        "text": "**사용자 이탈 원인 분석(AD-HOC-001)**에 착수하여 Google Analytics 로그를 분석한 결과, 특정 단계에서 이탈률이 급증하는 현상을 포착했습니다. 이탈 지점을 시각화한 후 대시보드 형태로 공유할 수 있도록 초안을 구성했습니다.",
        "evidence": [
           {
              "title": "2025-06-05_AnomalyDetection_ModelRefactor.docx",
              "content": "성능 개선 결과 및 테스트 비교표 포함",
              "LLM_reference": "docs_analysis.section[3]"
           },
           {
              "title": "2025-06-05_AnomalyDetection_ModelRefactor.docx",
              "content": "성능 개선 결과 및 테스트 비교표 포함",
              "LLM_reference": "docs_analysis.section[3]"
           }
        ]
      },
      {
        "text": "오전 팀 싱크 회의에서는 이상 탐지 알고리즘 개선 결과를 팀원들과 공유하고, 데이터 파이프라인 관련 이슈에 대해 기술적 논의를 진행하였습니다.",
        "evidence": [
           {
              "title": "2025-06-05_AnomalyDetection_ModelRefactor.docx",
              "content": "성능 개선 결과 및 테스트 비교표 포함",
              "LLM_reference": "docs_analysis.section[3]"
           }
        ]
      }
    ]
  },
  "daily_reflection": {
    "title": "🔍 오늘의 회고 및 개선점",
    "content": [
      "이상 탐지 모델 성능 개선은 성공적이었으나, 데이터 파이프라인의 로그 누락 문제를 조기에 발견하지 못해 일부 작업에 지연이 발생했습니다.",
      "다음부터는 데이터 흐름 모니터링을 자동화하여 초기 이상 징후를 빠르게 감지하는 방안을 마련할 필요가 있습니다.",
      "사용자 이탈 분석 작업은 유의미한 인사이트를 도출하였으나, 분석 대시보드 완성도를 높이기 위해 시각화 도구 활용을 강화할 계획입니다.",
      "팀 내 커뮤니케이션 측면에서는 문서화와 시각 자료 공유가 원활히 진행되어, 협업 효율이 증가한 점이 긍정적이었습니다."
    ]
  }
}
}}
```

**중요 사항:**
1. 모든 내용은 제공된 {target_date} 당일의 분석 데이터를 기반으로 작성하세요
2. 각 작업(task)의 content는 **Daily 보고서 형식**으로 구체적이고 상세하게 작성하세요
3. 시간대별 활동, 구체적 성과, 다음 계획 등 일일 보고서에 필요한 요소를 포함하세요
4. evidence의 source는 "docs", "teams" 중 하나여야 하며, 당일 활동과 직접 연관된 증거만 포함하세요
5. **evidence의 llm_reference에는 분석 결과에서 실제로 참조한 구체적인 문장이나 내용을 인용해주세요** (예: "김세은 updated the Status on this issue: YAX-566" 또는 "API 설계문서 3페이지 인증 엔드포인트 정의 부분")
6. Daily reflection 섹션을 통해 당일 업무에 대한 개인적 성찰과 다음 계획을 포함하세요
7. 완전한 JSON 형식으로 출력하세요 (추가 설명이나 마크다운 없이)
"""