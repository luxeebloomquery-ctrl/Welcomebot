import io

from PIL import Image, ImageDraw, ImageFont

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

THEMES = {
    "blue": {"bg": (30, 60, 114), "bg2": (42, 82, 152), "text": (255, 255, 255), "accent": (100, 181, 246)},
    "dark": {"bg": (24, 24, 27), "bg2": (49, 46, 62), "text": (255, 255, 255), "accent": (167, 139, 250)},
    "sunset": {"bg": (255, 94, 98), "bg2": (255, 195, 113), "text": (255, 255, 255), "accent": (255, 235, 205)},
    "forest": {"bg": (17, 74, 44), "bg2": (56, 142, 60), "text": (255, 255, 255), "accent": (200, 230, 201)},
    "purple": {"bg": (74, 20, 140), "bg2": (156, 39, 176), "text": (255, 255, 255), "accent": (225, 190, 231)},
}

CARD_SIZE = (800, 400)


def _vertical_gradient(size, color1, color2):
    w, h = size
    img = Image.new("RGB", size, color1)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        ratio = y / h
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def _circle_avatar(avatar_bytes: bytes | None, size: int, border_color):
    """Avatar ko circle mein crop karta hai. Agar avatar na ho to solid color placeholder circle banata hai."""
    circle = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)

    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGB")
            avatar = avatar.resize((size, size))
            circle.paste(avatar, (0, 0), mask)
        except Exception:
            avatar_bytes = None

    if not avatar_bytes:
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, size, size), fill=border_color + (255,))

    border = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(border).ellipse((0, 0, size - 1, size - 1), outline=(255, 255, 255, 255), width=6)
    circle = Image.alpha_composite(circle, border)
    return circle


def generate_welcome_card(
    user_name: str,
    chat_name: str,
    member_count: int,
    theme: str = "blue",
    avatar_bytes: bytes | None = None,
) -> bytes:
    """Welcome card PNG bytes generate karta hai. Avatar na mile to initial-letter placeholder use hota hai."""
    colors = THEMES.get(theme, THEMES["blue"])
    img = _vertical_gradient(CARD_SIZE, colors["bg"], colors["bg2"]).convert("RGBA")
    draw = ImageDraw.Draw(img)

    avatar_size = 160
    avatar = _circle_avatar(avatar_bytes, avatar_size, colors["accent"])
    avatar_pos = (CARD_SIZE[0] // 2 - avatar_size // 2, 40)
    img.paste(avatar, avatar_pos, avatar)

    if not avatar_bytes:
        initial = (user_name.strip()[:1] or "?").upper()
        try:
            initial_font = ImageFont.truetype(FONT_BOLD, 70)
        except Exception:
            initial_font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), initial, font=initial_font)
        iw, ih = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            (avatar_pos[0] + avatar_size / 2 - iw / 2, avatar_pos[1] + avatar_size / 2 - ih / 2 - bbox[1]),
            initial, font=initial_font, fill=colors["text"],
        )

    try:
        name_font = ImageFont.truetype(FONT_BOLD, 42)
        sub_font = ImageFont.truetype(FONT_REGULAR, 24)
    except Exception:
        name_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    welcome_line = f"Welcome, {user_name}!"
    bbox = draw.textbbox((0, 0), welcome_line, font=name_font)
    tw = bbox[2] - bbox[0]
    draw.text(((CARD_SIZE[0] - tw) / 2, 220), welcome_line, font=name_font, fill=colors["text"])

    sub_line = f"{chat_name} • Member #{member_count}"
    bbox2 = draw.textbbox((0, 0), sub_line, font=sub_font)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((CARD_SIZE[0] - tw2) / 2, 280), sub_line, font=sub_font, fill=colors["accent"])

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
