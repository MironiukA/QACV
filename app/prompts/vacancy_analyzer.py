import json


def build_vacancy_profile_prompt(title: str, description: str) -> str:
    return f"""Analyze this QA vacancy and return JSON only in this exact shape:
{{"role":"QA Lead","level":"lead","profile":["backend","manual","automation"],"must_have":["..."],"nice_to_have":["..."],"leadership":["..."],"high_risk_gaps":["..."],"domain":"fintech"}}

Use only explicit or strongly implied requirements from the vacancy. Do not invent the candidate's experience.

{json.dumps({"title": title, "description": description[:30000]}, ensure_ascii=False)}
"""
