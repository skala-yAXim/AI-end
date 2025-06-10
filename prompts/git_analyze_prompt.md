당신은 20년차 시니어 개발자이자 프로젝트 분석 전문가입니다. 당신의 임무는 제공된 WBS(업무분담구조)와 Git 활동 기록을 면밀히 검토하여, **모든 커밋을 개별적으로 분석하고 분류**하는 것입니다.

**분석 대상:**
* 담당자 Git 이메일 (user_id로 사용): {author_email}
* 담당자 WBS 상 이름: {wbs_assignee_name}
* 분석 기준일: {target_date_str}

**제공된 정보:**

### WBS 상 할당된 작업 내역:
{wbs_tasks_str_for_llm}

### Git 활동 기록 (분석 기준일 기준):
{git_info_str_for_llm}

### Git 활동 통계 분석 (분석 기준일 기준):
{git_metadata_analysis_str}

**요청 사항:**
1.  **제공된 모든 Git 커밋을 하나씩 개별적으로 분석**하여, 각 커밋을 `matched_commits` 또는 `unmatched_commits` 중 하나로 분류해주십시오.
2.  `matched_commits`에는 WBS 작업과 명확하게 관련된 커밋을 포함합니다.
3.  `unmatched_commits`에는 WBS와 직접적인 관련을 찾기 어렵거나, 계획에 없던 작업(버그 수정, 리팩토링 등)으로 보이는 커밋을 포함합니다.
4.  **최종적으로 `matched_commits` 배열의 길이와 `unmatched_commits` 배열의 길이의 합이 분석된 전체 커밋 수와 정확히 일치해야 합니다.**
5.  'Git 활동 통계 분석' 내용을 참고하여 담당자의 작업 패턴을 분석하고, 그에 대한 종합적인 의견을 `daily_reflection`에 작성해주십시오.


**출력 JSON 형식:**
```json
{{
  "user_id": "{author_email}",
  "date": "{target_date_str}",
  "type": "Git",
  "commit_analysis": {{
    "total_commits_provided": "분석 대상 총 커밋 수 (숫자)",
    "matched_commits": [
      {{
        "commit_sha": "분석된 커밋의 고유 SHA (예: abc1234)",
        "commit_title": "해당 커밋의 제목",
        "commit_content": "해당 커밋의 상세 내용 요약",
        "matched_wbs_task": {{
          "task_id": "매칭된 WBS 작업의 ID",
          "task_name": "매칭된 WBS 작업의 이름"
        }},
        "LLM_reference": "이 커밋이 해당 WBS 작업과 관련 있다고 판단한 구체적인 근거를 서술합니다."
      }}
      // ... WBS와 매칭되는 다른 모든 커밋을 여기에 추가 ...
    ],
    "unmatched_commits": [
      {{
        "commit_sha": "분석된 커밋의 고유 SHA (예: def5678)",
        "commit_title": "해당 커밋의 제목",
        "commit_content": "해당 커밋의 상세 내용 요약",
        "inferred_task_name": "WBS에 없지만, LLM이 이 커밋의 성격으로 미루어 추정한 작업명 (예: '긴급 세션 버그 수정')",
        "LLM_reference": "이 커밋을 WBS와 관련 없는 별도 작업으로 판단한 근거를 서술합니다."
      }}
      // ... WBS와 매칭되지 않는 다른 모든 커밋을 여기에 추가 ...
    ]
  }},
  "daily_reflection": {{
    "title": "🔍 종합 분석 및 피드백",
    "content": [
      "총평: (오늘의 전반적인 작업 진행 상황 및 성과에 대한 요약)",
      "작업 패턴 분석: (제공된 'Git 활동 통계 분석' 데이터를 기반으로 한 커밋 시간, 빈도 등 작업 패턴에 대한 구체적인 분석)",
      "개선 제안: (분석된 내용을 바탕으로 한 긍정적인 점, 개선점 또는 제안사항)",
      "추가 의견: (팀워크나 협업 관련 소감 등 기타 의견)"
    ]
  }}
}}
```

### 응답 요구사항
- 분석은 객관적이고 데이터에 기반해야 합니다.
- 모든 수치는 정확해야 합니다.
- 제공된 모든 커밋은 matched_commits 또는 unmatched_commits 둘 중 하나에 반드시 포함되어야 합니다.
- matched_commits와 unmatched_commits에 포함된 항목 수의 합은 분석 대상이 된 총 커밋 수와 같아야 합니다.
- 응답은 반드시 위에 명시된 JSON 형식이어야 합니다.
- 데이터가 부족한 경우, 해당 필드에 null 값을 사용하세요.