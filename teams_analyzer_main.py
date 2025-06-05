from agents.teams_analyzer import TeamsAnalyzer
import json
import os

from config import DATA_DIR

with open(os.path.join(DATA_DIR, "wbs_analyze_data.json"), "r", encoding="utf-8") as f:
    raw_wbs = f.read()

user_id = "sermadl1014@yasim2861.onmicrosoft.com"
user_name = "김세은"
target_date = "2025-05-29"
wbs_data = json.dumps(raw_wbs, ensure_ascii=False, indent=2)

# TeamsAnalyzer 인스턴스 생성
analyzer = TeamsAnalyzer()

# State 객체 생성
state = {
    "user_id": user_id,
    "user_name": user_name,
    "target_date": target_date,
    "wbs_data": wbs_data
}

# __call__ 메서드를 사용하여 호출
result = analyzer(state)
print(result)