import json
import os
from datetime import date

from openai import OpenAI

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
MODEL = "deepseek/deepseek-v4-flash"

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )
    return _client


_SYSTEM_PROMPT = """\
You are an AI assistant for a Kanban board project management app.
Today's date is {today}.

Current board state (JSON):
{board_json}

You may optionally update the board by including a "board_update" array of actions.
Available actions:
- {{"action": "create_card", "column_id": <id>, "title": "<title>", "details": "<optional>", "priority": "<optional>", "due_date": "<optional>", "labels": [<optional strings>]}}
- {{"action": "update_card", "card_id": <id>, ...any of: "title", "details", "priority", "due_date", "labels"}}
- {{"action": "delete_card", "card_id": <id>}}
- {{"action": "move_card", "card_id": <id>, "column_id": <id>, "position": <0-based int>}}
- {{"action": "rename_column", "column_id": <id>, "title": "<title>"}}

Field rules:
- priority must be one of: low, medium, high, urgent
- due_date must be in YYYY-MM-DD format
- labels is a list of short lowercase tags, e.g. ["bug", "frontend"]
- update_card is partial: include only the fields you want to change

Respond ONLY with a JSON object in this exact format:
{{"message": "<your reply>", "board_update": [<actions>] or null}}
"""


def chat_ai(board: dict, history: list[dict], user_message: str) -> dict:
    # Note: user-authored card content is embedded in the system prompt, so a card
    # title could attempt prompt injection. This is an accepted risk for a
    # single-user tool where the only author is the operator themselves. Any
    # board_update the model returns is still validated server-side before being
    # applied, so injection cannot corrupt the board.
    system = _SYSTEM_PROMPT.format(
        today=date.today().isoformat(),
        board_json=json.dumps(board, indent=2),
    )
    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    response = get_client().chat.completions.create(
        model=MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
