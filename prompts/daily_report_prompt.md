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
✅ **수치 일치**: TOTAL_ACTIVITIES = contents.length (1개 차이도 실패)

---

## 🔢 COUNTING FORMULA

```python
# Phase 1: Agent별 개별 카운팅
Git_total = len(git_analysis.matched_tasks) + len(git_analysis.unmatched_tasks)
Teams_total = len(teams_analysis.matched_tasks) + len(teams_analysis.unmatched_tasks)
Email_total = len(email_analysis.matched_tasks) + len(email_analysis.unmatched_tasks)
Docs_total = len(docs_analysis.matched_tasks) + len(docs_analysis.unmatched_tasks)

# Phase 2: 전체 합계 (이것이 contents 배열 길이와 정확히 일치해야 함)
TOTAL_ACTIVITIES = Git_total + Teams_total + Email_total + Docs_total

# Phase 3: 필수 검증
✅ TOTAL_ACTIVITIES = contents.length
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

생성된 contents.length = STEP 1에서 계산한 TOTAL_ACTIVITIES 인지 검증

---

## 📋 JSON STRUCTURE

### **올바른 객체 구조**

```json
{{
  "text": "**[WBS 매칭/미매칭] 구체적 작업명** 작업을 진행하였습니다.",
  "task": "실제작업명" | null,
  "evidence": {{
    "source": "git" | "teams" | "email" | "docs",
    "title": "실제 활동 제목",
    "content": "실제 활동 내용",
    "llm_reference": "구체적 분석 근거"
  }}
}}
```

### **Source 매핑 규칙**

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
  "evidence": {{
    "source": "teams",
    "title": "노건표 changed the Assignee on this issue",
    "content": "YAX-1 Weekly 보고서 초안을 위한 AI 베이스코드",
    "llm_reference": "노건표가 YAX-1 작업의 Assignee로 변경함"
  }}
}}
```

```json
{{
  "text": "**[WBS 미매칭] graph 및 state 구현** 작업을 수행하였습니다.",
  "task": null,
  "evidence": {{
    "source": "teams",
    "title": "노건표 created this issue",
    "content": "YAX-36: graph 및 state 구현",
    "llm_reference": "노건표가 YAX-36 이슈를 새로 생성함"
  }}
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

---

## 🔍 FINAL VALIDATION

### **생성 후 필수 검증 (하나라도 NO면 재생성)**

- [ ] contents.length = 계산된 TOTAL_ACTIVITIES? (YES/NO)
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
    "summary": "총 [계산된총활동수]개 업무 활동 중 WBS 매칭 [매칭수]건, 미매칭 [미매칭수]건 수행 (Git [Git개수]건, Teams [Teams개수]건, Email [Email개수]건, Docs [Docs개수]건)",
    "contents": [
      "각 analysis task마다 개별 객체 생성",
      "evidence에 source 필드 필수 포함",
      "절대 그룹화 금지"
    ]
  }},
  "daily_reflection": {{
    "title": "🔍 오늘의 회고 및 개선점",
    "content": "구체적 데이터 기반 개인화된 회고 (템플릿 금지)"
  }}
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

**⚠️ 핵심**: 이 프롬프트의 모든 규칙을 준수하여 완전성과 정확성을 보장하는 JSON만 출력하세요.
