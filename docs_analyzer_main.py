from agents.docs_analyzer import analyze_docs_data
import json
import os

from config import DATA_DIR

with open(os.path.join(DATA_DIR, "wbs_analyze_data.json"), "r", encoding="utf-8") as f:
    raw_wbs = f.read()

user_id = "minsuh3203@yasim2861.onmicrosoft.com"
user_name = "조민서"
target_date = "2025-05-29"
wbs_data = json.dumps(raw_wbs, ensure_ascii=False, indent=2)

result = analyze_docs_data(user_id, user_name, target_date, wbs_data)
print(result)