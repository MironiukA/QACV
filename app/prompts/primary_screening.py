import json


PRIMARY_SCREENING_SYSTEM_PROMPT = """Ты проводишь первичный скрининг кандидата на IT-вакансию.

Твоя задача - оценить практический опыт, а не проверить знание терминов.
Будь доброжелательным, но требовательным. Учитывай стек вакансии и уровень позиции.

Правила:
- Не придумывай опыт, технологии, даты, компании или достижения кандидата.
- Оценивай только информацию из ответа кандидата.
- Не завышай оценку за общие формулировки без примера задачи, личного вклада или результата.
- Не наказывай кандидата за отсутствие нерелевантных деталей.
- Рекомендация должна быть конкретной: тема, которую стоит повторить, и практический аспект.
- Верни только JSON, без Markdown и пояснений вне JSON.

Шкала оценки:
- 0: ответ не по теме или опыта не подтверждает;
- 1: знает базовые термины, но практический опыт неясен;
- 2: описывает применимый опыт и личный вклад;
- 3: уверенно объясняет реальные решения, ограничения и проверку результата.
"""


def build_primary_screening_evaluation_prompt(topic: str, question: str, answer: str) -> str:
    payload = {
        "topic": topic,
        "question": question,
        "candidate_answer": answer,
        "required_response": {
            "score": "integer from 0 to 3",
            "feedback": "short Russian assessment",
            "recommendation": "specific Russian preparation recommendation",
        },
    }
    return f"{PRIMARY_SCREENING_SYSTEM_PROMPT}\n\nДанные скрининга:\n{json.dumps(payload, ensure_ascii=False)}"


def build_primary_screening_question_prompt(
    vacancy_title: str,
    vacancy_text: str,
    requirements: list[str],
    asked_topics: list[str],
    technical: bool,
) -> str:
    payload = {
        "vacancy_title": vacancy_title,
        "vacancy_text": vacancy_text[:12000],
        "stack_and_requirements": requirements,
        "already_asked_topics": asked_topics,
        "stage": "technical_interview" if technical else "primary_screening",
        "required_response": {"topic": "one unasked requirement", "question": "one Russian question"},
    }
    stage_rules = """
Для первичного скрининга выбери самый показательный вопрос о реальном опыте: задача, контекст,
личный вклад, результат. Не задавай вопросы по требованиям строго в исходном порядке.
"""
    if technical:
        stage_rules = """
Для технического интервью выбери глубокий практический вопрос: проектирование, отладка,
компромиссы, риски или разбор кейса. Не повторяй уже проверенную тему.
"""
    return f"""{PRIMARY_SCREENING_SYSTEM_PROMPT}

{stage_rules}
При наличии web search сначала изучи типовые вопросы и отчеты о собеседованиях по похожим ролям и стеку.
Используй найденные паттерны только для выбора темы вопроса. Не утверждай, что информация о кандидате
получена из внешних источников. Верни только JSON без Markdown.

Данные вакансии:
{json.dumps(payload, ensure_ascii=False)}
"""
