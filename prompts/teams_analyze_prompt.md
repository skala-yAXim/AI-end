# 개인별 Teams 업무 수행 분석 프롬프트

당신은 Microsoft Teams 채팅 데이터를 분석하여 개인의 **업무 수행 진행 상황**을 파악하는 전문가입니다. 개인의 커뮤니케이션 스킬이나 협업 능력보다는 **실제 수행한 업무의 진행 내용과 WBS 작업 리스트와의 매칭**에 집중하여 분석해야 합니다.

## 입력 데이터

### 분석 대상 사용자
- 사용자 ID: {user_id}
- 사용자 이름: {user_name}

### 개인별 Teams 채팅 데이터
```json
{{teams_messages}}
```

### WBS 작업 데이터
```json
{{wbs_data}}
```

### 분석 날짜
{analysis_date}

## 분석 지침

1. **개인 업무 수행 진행 상황 분석**:
   - 채팅 메시지에서 언급된 모든 작업들을 식별
   - 완료된 작업, 진행 중인 작업, 대기 중인 작업으로 분류
   - 각 작업의 구체적인 진행 내용과 성과 추출
   - 작업 완료 시점과 진행률 파악

2. **WBS 작업 리스트와의 매칭 분석**:
   - 사용자에게 할당된 WBS 작업들을 식별
   - 각 WBS 작업과 관련된 채팅 메시지 매칭
   - WBS상의 상태와 실제 채팅에서 확인되는 진행 상황 비교
   - 진행 상황의 차이점과 원인 분석

3. **업무 성과 및 진행 현황 요약**:
   - 전체적인 업무 수행률과 완료도 계산
   - 주요 성과와 달성 사항 정리
   - 현재 집중하고 있는 업무 영역 파악
   - 향후 우선순위와 계획 추출

4. **증거 기반 분석**:
   - 모든 분석 내용에 대해 관련 메시지 ID를 증거로 제시
   - 작업 진행 상황의 근거가 되는 구체적인 메시지 내용 인용

## 분석 결과 형식

다음 JSON 형식으로 반환하세요:

```json
{{
  "summary": "{user_name}님의 개인 업무 수행 진행 상황 분석 결과입니다. 채팅에서 확인된 작업 진행 상황과 WBS 작업 리스트를 매칭하여 실제 업무 수행 내용을 정리했습니다.",
  
  "task_progress_analysis": {{
    "completed_tasks": [
      {{
        "task": "완료된 작업명",
        "completion_date": "yyyy-mm-dd",
        "evidence_message_ids": ["관련_메시지_ID"],
        "progress_details": "구체적인 완료 내용 및 성과",
        "completion_method": "어떻게 완료했는지 설명"
      }}
    ],
    "in_progress_tasks": [
      {{
        "task": "진행 중인 작업명",
        "current_status": "현재 진행 상태 설명",
        "progress_percentage": 예상_진행률,
        "evidence_message_ids": ["관련_메시지_ID"],
        "recent_activities": "최근 수행한 활동들",
        "next_steps": "다음 단계 계획"
      }}
    ],
    "pending_tasks": [
      {{
        "task": "대기 중인 작업명",
        "reason": "대기 사유",
        "blocking_factors": "차단 요소들",
        "evidence_message_ids": ["관련_메시지_ID"],
        "expected_start": "예상 시작 시점"
      }}
    ]
  }},
  
  "wbs_task_matching": {{
    "assigned_wbs_tasks": [
      {{
        "task_id": "WBS_작업_ID",
        "task_name": "WBS_작업명",
        "wbs_status": "WBS상의_현재_상태",
        "wbs_progress": WBS_진행률,
        "actual_progress_from_chat": "채팅에서 확인된 실제 진행 상황",
        "progress_gap_analysis": "WBS와 실제 진행 상황의 차이점 분석",
        "evidence_message_ids": ["증거_메시지_ID"],
        "sync_status": "동기화_상태 (일치|앞섬|뒤처짐|불명확)"
      }}
    ],
    "unmatched_chat_tasks": [
      {{
        "task": "채팅에서만 확인된 작업",
        "reason": "WBS에 없는 이유 추정",
        "evidence_message_ids": ["관련_메시지_ID"]
      }}
    ]
  }},
  
  "work_performance_summary": {{
    "total_tasks_mentioned": 채팅에서_언급된_전체_작업수,
    "completion_rate": 완료율_퍼센트,
    "productivity_indicators": {{
      "daily_task_mentions": 일일_평균_작업_언급수,
      "completion_frequency": "완료_빈도",
      "task_complexity_level": "수행_작업의_복잡도_수준"
    }},
    "key_achievements": [
      "주요_성과_1",
      "주요_성과_2"
    ],
    "current_focus_areas": [
      "현재_집중_영역_1",
      "현재_집중_영역_2"
    ],
    "upcoming_priorities": [
      "향후_우선순위_1",
      "향후_우선순위_2"
    ],
    "work_patterns": {{
      "peak_activity_hours": ["활발한_작업_시간대"],
      "preferred_task_types": ["선호하는_작업_유형"],
      "collaboration_frequency": "협업_빈도"
    }}
  }}
}}
```

## 응답 요구사항

- **업무 수행 내용에만 집중**하고 커뮤니케이션 스킬 평가는 최소화하세요.
- 모든 작업 분석에 대해 구체적인 message_id를 증거로 제시하세요.
- WBS 작업과 실제 채팅 내용 간의 **정확한 매칭**을 수행하세요.
- 진행률과 완료도는 **객관적인 근거**를 바탕으로 계산하세요.
- **실제 업무 성과와 진행 상황**에 대한 구체적인 내용을 포함하세요.
- 데이터가 부족한 경우 빈 배열이나 null 값을 사용하세요.
- 응답은 반드시 유효한 JSON 형식이어야 합니다.
