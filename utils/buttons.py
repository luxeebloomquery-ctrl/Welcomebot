import re
import json
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Rose syntax: [Button Text](buttonurl:https://example.com)
# Same-line ke multiple buttons ek row mein aate hain agar ':same' lagaya jaye:
# [Btn1](buttonurl:https://a.com:same)
# [Btn2](buttonurl:https://b.com)
BUTTON_PATTERN = re.compile(r"\[([^\[\]]+)\]\(buttonurl:(https?://[^\s)]+?)(:same)?\)")


def extract_buttons(raw_text: str):
    """
    Text ke andar se [Text](buttonurl:URL) patterns nikalta hai.
    Returns: (clean_text, buttons_list)
    buttons_list = [[{"text":..,"url":..}, ...same row], [next row], ...]
    """
    matches = list(BUTTON_PATTERN.finditer(raw_text))
    clean_text = BUTTON_PATTERN.sub("", raw_text).strip()

    rows = []
    for m in matches:
        text, url, same = m.group(1), m.group(2), m.group(3)
        btn = {"text": text, "url": url}
        if same and rows:
            rows[-1].append(btn)
        else:
            rows.append([btn])

    return clean_text, (rows if rows else None)


def buttons_to_json(rows) -> str | None:
    if not rows:
        return None
    return json.dumps(rows)


def buttons_from_json(raw: str | None):
    if not raw:
        return None
    return json.loads(raw)


def build_keyboard(rows) -> InlineKeyboardMarkup | None:
    """DB se aaye button rows ko InlineKeyboardMarkup mein convert karta hai."""
    if not rows:
        return None
    keyboard = []
    for row in rows:
        keyboard.append(
            [InlineKeyboardButton(text=b["text"], url=b["url"]) for b in row]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
