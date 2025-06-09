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
{{{{
  "report_title": "{user_name}님의 {target_date} 일일 업무 보고서",
  "daily_report": {{{{
    "title": "📌 일일 업무 진행 내용",
    "summary": "(예시: 오늘은 총 N개의 업무 항목 중 X건을 완료하고 Y건을 진행 중입니다.)",
    "contents": [
      {{{{
        "text": "(예시: **주요 업무명(WBS-ID)** 작업을 완료/진행하였습니다. 구체적인 성과와 결과를 포함하여 설명합니다.)",
        "evidence": [
           {{{{
              "title": "(예시: 관련 문서, Teams 게시물, Git 커밋 내용 또는 이메일)",
              "content": "(예시: 핵심 내용 요약)",
              "LLM_reference": "(예시: 분석 결과에서 참조한 구체적인 내용)"
           }}}}
        ]
      }}}},
      {{{{
        "text": "(예시: **업무 진행 상황(WBS-ID)** 에서는 특정 이슈나 진행 내용을 설명합니다.)",
        "evidence": [
           {{{{
              "title": "(예시: 관련 문서, Teams 게시물, Git 커밋 내용 또는 이메일)",
              "content": "(예시: 핵심 내용 요약)",
              "LLM_reference": "(예시: 분석 결과에서 참조한 구체적인 내용)"
           }}}}
        ]
      }}}},
      {{{{
        "text": "(예시: 회의 참석 또는 커뮤니케이션 활동 내용을 기술합니다.)",
        "evidence": [
           {{{{
              "title": "(예시: 관련 문서, Teams 게시물, Git 커밋 내용 또는 이메일)",
              "content": "(예시: 핵심 내용 요약)",
              "LLM_reference": "(예시: 분석 결과에서 참조한 구체적인 내용)"
           }}}}
        ]
      }}}}
    ]
  }}}},
  "daily_reflection": {{{{
    "title": "🔍 오늘의 회고 및 개선점",
    "content": [
      "(예시: 긍정적인 성과와 잘 진행된 부분에 대한 평가)",
      "(예시: 아쉬웠던 점이나 개선이 필요한 부분)",
      "(예시: 향후 계획이나 개선 방안)",
      "(예시: 팀워크나 협업 관련 소감)"
    ]
  }}}}
}}}}
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