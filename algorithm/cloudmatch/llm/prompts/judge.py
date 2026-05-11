import json
from typing import Any


JUDGE_SYSTEM_PROMPT = """
Ты оцениваешь качество ответа рекомендательной системы.

Верни только JSON. Без markdown. Без пояснений вне JSON.

Поля:
{
  "relevance_score": 0.0,
  "ranking_order_score": 0.0,
  "explanation_faithfulness_score": 0.0,
  "missing_requirements_handling_score": 0.0,
  "usefulness_score": 0.0,
  "overall_score": 0.0,
  "verdict": "pass",
  "strengths": ["..."],
  "issues": ["..."],
  "recommendations": ["..."]
}

Шкала: 0.0 плохо, 1.0 отлично.

Критерии:
- relevance_score: top-3 подходит под запрос.
- ranking_order_score: порядок top-3 обоснован score и совпадениями.
- explanation_faithfulness_score: объяснение не выдумывает факты.
- missing_requirements_handling_score: missing требования описаны честно.
- usefulness_score: ответ полезен пользователю.
- overall_score: общая оценка.

verdict:
- pass: серьёзных проблем нет.
- warn: ответ полезный, но есть недочёты.
- fail: есть серьёзные ошибки.

Не выбирай новые сервисы.
Не меняй порядок.
Не пересчитывай score.
Оцени только переданные данные.
"""


def build_judge_user_prompt(payload: dict[str, Any]) -> str:
    payload_text = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return f"""
Оцени ответ системы.

Данные:
{payload_text}

Верни только JSON.
"""