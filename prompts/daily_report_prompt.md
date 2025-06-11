# 🎯 Daily Report Generator v2.0 - Expert Level

## 📋 CO-STAR Framework

**Context**: Multi-agent system (Git, Teams, Email, Docs) analysis integration  
**Objective**: Complete daily report with ALL activities as individual objects  
**Style**: Structured JSON with evidence-based content  
**Tone**: Professional, data-driven accuracy  
**Audience**: Team leads, project managers, individual contributors  
**Response**: Validated JSON structure with personalized reflection

---

## ⚠️ CRITICAL RULES

### 🚨 **NEVER DO (즉시 재생성)**

❌ **그룹화 금지**: 여러 활동을 하나의 객체로 요약  
❌ **생략 금지**: 비슷한 작업도 각각 별도 객체 필수  
❌ **개수 조작 금지**: Teams 6건 = 6개 객체, Git 2건 = 2개 객체

### ✅ **MUST DO (필수 준수)**

✅ **완전한 1:1 매핑**: analysis task → contents object (정확히 1:1)  
✅ **전수 포함**: matched_tasks + unmatched_tasks 모든 항목 개별 처리  
✅ **수치 일치**: TOTAL_ACTIVITIES = 전체 evidence 개수 (1개 차이도 실패)
  - contents 배열 내 모든 evidence를 펼쳤을 때 그 총합이 정확히 TOTAL_ACTIVITIES와 같아야 함
  - 동일한 작업 내용이라도 서로 다른 evidence(source)가 있으면 각각 별도 evidence로 기록
  - 하나의 contents에 여러 evidence가 있다면, 그 개수만큼 TOTAL_ACTIVITIES에 포함됨
✅ **reflection 전수 포함**: 각 Agent가 전달한 reflections 리스트의 모든 항목을 각각 별도의 객체로 daily_reflection.contents 배열에 포함해야 합니다.

---

## 🔢 COUNTING FORMULA

```python
# Phase 1: Agent별 개별 카운팅
Git_total = len(activity_analysis.matched_activities) + len(activity_analysis.unmatched_activities)
Teams_total = len(teams_analysis.matched_tasks) + len(teams_analysis.unmatched_tasks)
Email_total = len(email_analysis.matched_emails) + len(email_analysis.unmatched_emails)
Docs_total = len(docs_analysis.matched_docs) + len(docs_analysis.unmatched_docs)

# Phase 2: 전체 합계 (이것이 contents 배열 길이와 정확히 일치해야 함)
TOTAL_ACTIVITIES = Git_total + Teams_total + Email_total + Docs_total

# Phase 3: 필수 검증
✅ TOTAL_ACTIVITIES = contents 내 모든 evidence 항목의 총합
✅ 매칭수 + 미매칭수 = TOTAL_ACTIVITIES
✅ summary 총활동수 = TOTAL_ACTIVITIES
```

---

## 🧠 EXECUTION PROCESS

### **STEP 1: COUNT EVERYTHING**

각 Agent의 matched_tasks와 unmatched_tasks를 **개별적으로** 카운팅하여 예상 총 객체 수 계산

### **STEP 2: CREATE INDIVIDUAL OBJECTS**

각 task마다 별도 contents 객체 생성 (절대 그룹화 금지)

### **STEP 3: VALIDATE NUMBERS**

생성된 contents의 모든 evidence의 개수 = STEP 1에서 계산한 TOTAL_ACTIVITIES 인지 검증

---

## 📋 JSON STRUCTURE

### **올바른 객체 구조**

```json
{{
  "text": "**[WBS 매칭/미매칭] 구체적 작업명** 작업을 진행하였습니다.",
  "task": "실제작업명" | null,
  "evidence": [
	  {{
	    "source": "git" | "teams" | "email" | "docs",
	    "title": "실제 활동 제목",
	    "content": "실제 활동 내용",
	    "llm_reference": "구체적 분석 근거"
	  }}
	 ]
}}
```

### **Source 매핑 규칙**
"type" -> "source"로 매핑
- Git 분석 결과 → `"source": "git"`
- Teams 분석 결과 → `"source": "teams"`
- Email 분석 결과 → `"source": "email"`
- Docs 분석 결과 → `"source": "docs"`

---

## ❌ 금지 패턴 vs ✅ 올바른 패턴

### **❌ 틀린 예시 (그룹화)**

```json
{{
  "text": "Teams 관련 업무들을 종합적으로 완료했습니다.",
  "task": "Teams 관련 업무",
  "evidence": {{
    "source": "teams",
    "title": "여러 이슈 처리",
    "content": "YAX-1, YAX-36 등 여러 이슈들",
    "llm_reference": "여러 Teams 활동을 묶어서 처리"
  }}
}}
```

**문제**: Teams 6건이 1개 객체로 그룹화 → 5건 누락

### **✅ 올바른 예시 (개별 처리)**

```json
{{
  "text": "**[WBS 매칭] VectorDB 구축(20)** 작업을 진행하였습니다.",
  "task": "VectorDB 구축",
  "evidence": [
    {{
      "source": "teams",
      "title": "노건표 changed the Assignee on this issue",
      "content": "YAX-1 Weekly 보고서 초안을 위한 AI 베이스코드",
      "llm_reference": "노건표가 YAX-1 작업의 Assignee로 변경함"
    }},
    {{
      "source": "email",
      "title": "Re: VectorDB 기능 문의",
      "content": "VectorDB 리팩토링 관련 논의 이메일",
      "llm_reference": "20번 작업 진행 맥락에서 주고받은 이메일"
    }}
  ]
}}
```

```json
{{
  "text": "**[WBS 미매칭] graph 및 state 구현** 작업을 수행하였습니다.",
  "task": null,
  "evidence": [
    {{
      "source": "teams",
      "title": "노건표 created this issue",
      "content": "YAX-36: graph 및 state 구현",
      "llm_reference": "노건표가 YAX-36 이슈를 새로 생성함"
    }}
  ]
}}
```

**핵심**: Teams 6건이면 위와 같은 개별 객체 6개 생성

---

## 🎯 DAILY REFLECTION 규칙

```
❌ 금지: "긍정적인 성과와 잘 진행된 부분" (템플릿 표현)
✅ 필수: "Git analyzer 구현(38번) 완료, Teams 6건 중 1건만 매칭" (구체적 데이터)
✅ 필수: 실제 매칭/미매칭 비율과 작업명 포함
✅ 필수: 개인 업무 맥락에 맞는 고유한 관찰과 계획
```

### ✅ Summary 작성 방식:
- **입력 데이터**만 사용하여 구성 (Git, Teams, Email, Docs 분석 결과만 활용)
- **총 미매칭 항목의 수와 개선 방향**을 구체적으로 언급
- 템플릿 표현 절대 금지. 내용은 모두 실제 분석 데이터를 기반으로 구성
- 템플릿 표현, 일반론, 추상적인 말 금지
- 객관적 활동 데이터 기반으로 작성

---

## 🔍 FINAL VALIDATION

### **생성 후 필수 검증 (하나라도 NO면 재생성)**

- [ ] contents 내 모든 evidence 개수의 총합 = TOTAL_ACTIVITIES? (YES/NO)
- [ ] 모든 matched_tasks가 개별 객체로 포함? (YES/NO)
- [ ] 모든 unmatched_tasks가 개별 객체로 포함? (YES/NO)
- [ ] 그룹화된 객체 없음? (YES/NO)
- [ ] 모든 evidence에 source 필드 포함? (YES/NO)
- [ ] WBS 매칭 시 task=작업명, 미매칭 시 task=null? (YES/NO)

---

## 🎨 OUTPUT TEMPLATE

```json
{{
  "report_title": "{user_name}님의 {target_date} 일일 업무 보고서",
  "daily_report": {{
    "title": "📌 일일 업무 진행 내용",
    "summary": "총 [WBS 매칭 content 객체 수]개의 WBS에 기여. 총 [계산된총활동수]개 업무 활동 중 WBS 매칭 [매칭수]건, 미매칭 [미매칭수]건 수행 (Git [Git개수]건, Teams [Teams개수]건, Email [Email개수]건, Docs [Docs개수]건)",
    "contents": [
      "각 analysis task마다 개별 객체 생성",
      "evidence에 source 필드 필수 포함",
      "절대 그룹화 금지"
    ]
  }},
    "daily_reflection": {{
    "title": "🔍 오늘의 회고 및 개선점",
    "summary": "오늘의 업무는 주로 문서 작성과 관련된 작업이었습니다. Git을 통한 커밋은 프로젝트의 중요 기능 개발에 직접적으로 연관되어 있으며, 문서 작업은 WBS 작업 목록과 잘 일치하고 있습니다. 하지만, 보고서 설계서 작성과 같은 미매칭 작업이 발생하였습니다. 이는 프로젝트 관리의 효율성을 높이기 위해 작업별로 문서의 필요성과 목적을 명확히 할 필요가 있음을 보여줍니다. 또한, Git 활동을 좀 더 자주 기록하여 변경 사항을 세분화하고 기록하는 습관을 개선할 필요가 있습니다."
    "contents": [
      {{
        "source": "git",
        "reflection": "Git Agent가 전달한 회고 내용입니다."
      }},
      {{
        "source": "teams",
        "reflection": "Teams Agent가 전달한 회고 내용입니다."
      }},
      {{
        "source": "email",
        "reflection": "email Agent가 전달한 회고 내용입니다."
      }},
      {{
        "source": "docs",
        "reflection": "docs Agent가 전달한 회고 내용입니다."
      }}
    ]
}}
```

---

## 🎯 MISSION EXECUTION

**{user_name}님의 {target_date} 완전 업무 보고서를 생성하세요.**

**입력 데이터**: `{wbs_data}`, `{git_analysis}`, `{teams_analysis}`, `{email_analysis}`, `{docs_analysis}`

**실행 순서**:

1. 각 Agent별 task 개수 계산 (TOTAL_ACTIVITIES 도출)
2. 모든 task를 개별 객체로 변환 (source 필드 포함)
3. 검증 통과 확인 후 JSON 출력

**⚠️ 핵심**: 이 프롬프트의 모든 규칙을 준수하여 완전성과 정확성을 보장하는 JSON만 출력하세요. **(추가 설명이나 마크다운 없이)** daily_reflection은 입력 데이터에 기반한 균형 있고 구체적인 회고로 생성되어야 하며, 그 외 템플릿적 표현은 금지합니다.
