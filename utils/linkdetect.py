import re

URL_PATTERN = re.compile(
    r"(https?://[^\s]+)|(www\.[^\s]+)|(t\.me/[^\s]+)|(@[a-zA-Z0-9_]{5,})"
)


def contains_link(text: str | None) -> bool:
    """Text ke andar URL, t.me link, ya @username mention hai ya nahi check karta hai."""
    if not text:
        return False
    return bool(URL_PATTERN.search(text))


def extract_links(text: str | None) -> list[str]:
    if not text:
        return []
    matches = URL_PATTERN.findall(text)
    links = []
    for group in matches:
        for item in group:
            if item:
                links.append(item)
    return links
