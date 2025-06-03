from agents.teams_analyzer import analyze_teams_data
import json
import os

from config import DATA_DIR

with open(os.path.join(DATA_DIR, "wbs_analyze_data.json"), "r", encoding="utf-8") as f:
    raw_wbs = f.read()

user_id = "sermadl1014@yasim2861.onmicrosoft.com"
user_name = "김세은"
target_date = "2025-05-29"
wbs_data = json.dumps(raw_wbs, ensure_ascii=False, indent=2)

result = analyze_teams_data(user_id, user_name, target_date, wbs_data)
print(result)