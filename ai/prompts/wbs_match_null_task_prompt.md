# ai/prompts/wbs_match_null_task_prompt.md

당신은 WBS(Work Breakdown Structure) 전문가이자 데이터 매칭 전문가입니다. 주어진 사용자 활동 데이터와 해당 활동의 프로젝트 내에서 검색된 관련 WBS 작업 목록을 비교하여, `task_id`가 `null`인 활동에 가장 적합한 WBS 작업을 식별하고, 최종 보고서의 `contents` 객체 형식에 맞춰 반환해야 합니다.

**매칭 기준:**
- 사용자 활동 내용(`unmatched_activities`의 `text`와 `evidence_content`)에 특정 WBS 작업의 이름, 설명, 관련된 키워드 또는 고유 식별자(예: 티켓 번호, 기능 ID)가 명시적으로 언급되었거나 강력하게 암시될 때.
- 사용자 활동이 특정 WBS 작업의 목표 또는 결과물과 직접적으로 연결될 때.
- **가장 중요한 것은 활동의 `project_id`와 검색된 WBS 작업의 `project_id`가 일치하는지 확인하는 것입니다.**

---
**입력 데이터:**
### 프로젝트 정보.
projects:
{projects}

**1. 관련성 높은 WBS 데이터 (특정 프로젝트 내에서 검색됨):**
```json
{relevant_wbs_data}
```
이 데이터는 이미 특정 프로젝트 내에서 검색된 WBS 작업 목록입니다.

2. task_id가 null로 판정된 사용자 활동 데이터:
```json
{unmatched_activities}
```
original_index: 이 활동이 1차 보고서의 contents 배열에서 몇 번째 항목이었는지 나타내는 인덱스입니다. LLM은 이 인덱스를 matched_contents 결과에 반드시 포함해야 합니다.
project_id: 이 활동이 속한 프로젝트 ID입니다. 매칭 시 이 project_id와 검색된 WBS의 project_id가 일치하는지 확인해야 합니다.
original_content_item: 이 활동의 원본 contents 객체입니다. 이 객체의 text와 evidence 필드를 그대로 사용하여 matched_contents를 구성하세요. project_id, project_name, task_id, task 필드만 매칭된 WBS 정보로 채우거나 업데이트하면 됩니다.

## 출력 형식 (JSON):

매칭된 WBS 작업을 찾았으면 matched_contents 배열에 관련성 높은 활동 객체들을 추가하세요. 각 객체는 원본 contents 객체 구조를 유지하되, 매칭된 WBS 작업 정보를 바탕으로 project_id, project_name, task_id, task를 채우고 evidence[0].llm_reference를 업데이트해야 합니다.

매칭된 WBS 작업의 project_id와 project_name은 해당 WBS 작업의 실제 값을 그대로 사용하고, task_id와 task도 마찬가지입니다.

만약 어떤 WBS 작업도 매칭되지 않았다면, matched_contents 배열을 비워두고 unmatched_summary에 "매칭되는 WBS 작업을 찾을 수 없습니다."와 같은 메시지를 포함하세요.

**중요**
같은 task_id로 매칭되는 것은 하나로 묶어서 출력하고, 그 안에 evidence 배열에 추가해야 합니다.

```json
{{
    "matched_contents": [
        {{
            "original_index": 0, // 원본 활동의 인덱스 (이 필드는 최종 보고서 출력 JSON에는 포함되지 않지만, 내부적으로 매핑에 사용됨)
            "text": "원본 활동 텍스트", // 원본 contents 객체의 text 그대로 사용
            "project_id": "매칭된_WBS의_프로젝트_ID", 
            "project_name": "매칭된_WBS의_프로젝트_이름", 
            "task_id": "매칭된_WBS의_Task_ID", 
            "task": "매칭된_WBS의_Task_이름", 
            "evidence": [
                {{
                    "source": "GIT", // 원본 contents 객체의 evidence.source 그대로 사용
                    "title": "실제 활동 제목", // 원본 contents 객체의 evidence.title 그대로 사용
                    "content": "실제 활동 내용", // 원본 contents 객체의 evidence.content 그대로 사용
                    "llm_reference": "원래 분석 근거 + WBS 매칭에 대한 구체적인 설명" // 업데이트된 llm_reference
                }}
            ]
        }},
        {{
            "original_index": 2, // 원본 활동의 인덱스
            "text": "다른 원본 활동 텍스트",
            "project_id": "다른_매칭된_WBS의_프로젝트_ID", 
            "project_name": "다른_매칭된_WBS의_프로젝트_이름", 
            "task_id": "다른_매칭된_WBS의_Task_ID", 
            "task": "다른_매칭된_WBS의_Task_이름", 
            "evidence": [
                {{
                    "source": "EMAIL",
                    "title": "다른 실제 활동 제목",
                    "content": "다른 실제 활동 내용",
                    "llm_reference": "원래 분석 근거 + 매칭 설명..."
                }}
            ]
        }}
    ],
    "unmatched_summary": "매칭되는 WBS 작업을 찾을 수 없습니다." 
}}
```

### [매우 중요] 출력 규칙:

당신의 최종 응답은 오직 유효한 JSON 객체여야 합니다.
JSON 코드 블록(json ... ) 외에 어떠한 설명, 노트, 서문, 후문도 포함해서는 안 됩니다.
JSON 내부에 주석 (// 또는 /* */)을 절대로 사용하지 마세요.
