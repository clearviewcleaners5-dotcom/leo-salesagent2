"""
CVC Discord Image Generator
Generates clean graphics and posts them to Discord as image files
"""

from PIL import Image, ImageDraw, ImageFont
import io
import os
import requests

CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "1230709942265188352")

def get_discord_headers_multipart():
    return {"Authorization": f"Bot {os.environ.get('DISCORD_BOT_TOKEN')}"}

def send_discord_image(image_buf, filename="cvc.png", caption=""):
    """Send an image file to Discord channel."""
    image_buf.seek(0)
    files = {"file": (filename, image_buf, "image/png")}
    data = {}
    if caption:
        data["content"] = caption
    response = requests.post(
        f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages",
        headers=get_discord_headers_multipart(),
        files=files,
        data=data
    )
    if response.status_code == 200:
        print(f"✅ Image sent to Discord: {filename}")
        return True
    print(f"❌ Discord image error: {response.status_code} {response.text}")
    return False

def load_fonts():
    try:
        bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        reg = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        return {
            "xl": ImageFont.truetype(bold, 32),
            "lg": ImageFont.truetype(bold, 24),
            "md": ImageFont.truetype(bold, 19),
            "sm": ImageFont.truetype(reg, 16),
            "xs": ImageFont.truetype(reg, 13),
        }
    except:
        f = ImageFont.load_default()
        return {"xl": f, "lg": f, "md": f, "sm": f, "xs": f}

def draw_pill(draw, x, y, w, h, color):
    r = h // 2
    draw.ellipse([x, y, x+r*2, y+h], fill=color)
    draw.ellipse([x+w-r*2, y, x+w, y+h], fill=color)
    draw.rectangle([x+r, y, x+w-r, y+h], fill=color)

def draw_card(draw, x, y, w, h, fill, radius=12):
    draw.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=fill)

def generate_bonus_image(date_str, core_bonuses, creative_bonuses):
    """Generate the morning daily bonuses graphic."""
    W = 900
    ACCENT = "#378ADD"
    BG = "#F8F9FA"
    CARD_BG = "#FFFFFF"
    TEXT_PRIMARY = "#1a1a1a"
    TEXT_SECONDARY = "#666666"
    TEXT_MUTED = "#999999"

    all_bonuses = core_bonuses + creative_bonuses
    rows = (len(all_bonuses) + 1) // 2
    H = 160 + (rows * 130) + 60

    img = Image.new("RGB", (W, H), color=BG)
    draw = ImageDraw.Draw(img)
    fonts = load_fonts()

    # Top accent bar
    draw.rectangle([0, 0, W, 8], fill=ACCENT)

    # Header
    draw.text((W//2, 40), "TODAY'S BONUSES", font=fonts["xl"], fill=TEXT_PRIMARY, anchor="mm")
    draw.text((W//2, 76), date_str, font=fonts["sm"], fill=TEXT_SECONDARY, anchor="mm")
    draw.text((W//2, 100), "Win big. Close more. Medicine Hat's waiting.", font=fonts["xs"], fill=TEXT_MUTED, anchor="mm")

    # Divider
    draw.rectangle([40, 118, W-40, 119], fill="#E0E0E0")

    BADGE_COLORS = {
        "danger":  ("#FFEBEE", "#C62828"),
        "warning": ("#FFF8E1", "#E65100"),
        "success": ("#E8F5E9", "#2E7D32"),
        "info":    ("#E3F2FD", "#1565C0"),
        "purple":  ("#F3E5F5", "#6A1B9A"),
        "teal":    ("#E0F2F1", "#00695C"),
    }

    col_w = (W - 80) // 2
    for i, bonus in enumerate(all_bonuses):
        col = i % 2
        row = i // 2
        cx = 40 + col * (col_w + 20)
        cy = 134 + row * 130

        color_key = bonus.get("color", "info")
        bg_col, text_col = BADGE_COLORS.get(color_key, BADGE_COLORS["info"])

        draw_card(draw, cx, cy, col_w, 110, CARD_BG)

        # Emoji circle
        draw.ellipse([cx+16, cy+16, cx+60, cy+60], fill=bg_col)
        draw.text((cx+38, cy+38), bonus["emoji"], font=fonts["lg"], fill=text_col, anchor="mm")

        # Name
        draw.text((cx+72, cy+22), bonus["name"].title(), font=fonts["md"], fill=TEXT_PRIMARY, anchor="lm")

        # Desc
        draw.text((cx+72, cy+44), bonus["desc"], font=fonts["xs"], fill=TEXT_SECONDARY, anchor="lm")

        # Prize pill
        prize_text = bonus["prize"]
        pill_w = len(prize_text) * 8 + 24
        draw_pill(draw, cx+16, cy+70, pill_w, 26, bg_col)
        draw.text((cx+16+pill_w//2, cy+83), prize_text, font=fonts["xs"], fill=text_col, anchor="mm")

    # Bottom bar
    draw.rectangle([0, H-8, W, H], fill=ACCENT)
    draw.text((W//2, H-26), "Let's get it. Every door is an opportunity.", font=fonts["xs"], fill=TEXT_MUTED, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def generate_eod_image(date_str, leaderboard, rewards, team_total, team_deals):
    """
    Generate end-of-day rewards graphic.
    leaderboard: [{"name": "Jared", "total": 595, "jobs": 3}, ...]
    rewards: [{"emoji": "🩸", "name": "First Blood", "winner": "Jared", "prize": "Tim Hortons on Ryley"}, ...]
    """
    W = 900
    ACCENT = "#378ADD"
    BG = "#F8F9FA"
    CARD_BG = "#FFFFFF"
    TEXT_PRIMARY = "#1a1a1a"
    TEXT_SECONDARY = "#666666"
    TEXT_MUTED = "#999999"
    GREEN = "#2E7D32"
    GREEN_BG = "#E8F5E9"

    H = 200 + (len(leaderboard) * 72) + 80 + (len(rewards) * 80) + 80
    img = Image.new("RGB", (W, H), color=BG)
    draw = ImageDraw.Draw(img)
    fonts = load_fonts()

    # Top bar
    draw.rectangle([0, 0, W, 8], fill=ACCENT)

    # Header
    draw.text((W//2, 44), "CVC END OF DAY REPORT", font=fonts["xl"], fill=TEXT_PRIMARY, anchor="mm")
    draw.text((W//2, 80), date_str, font=fonts["sm"], fill=TEXT_SECONDARY, anchor="mm")
    draw.rectangle([40, 100, W-40, 101], fill="#E0E0E0")

    y = 116

    # Leaderboard section label
    draw.text((56, y+14), "LEADERBOARD", font=fonts["xs"], fill=TEXT_MUTED, anchor="lm")
    y += 36

    MEDAL_COLORS = [("#FFF8E1", "#E65100", "🥇"), ("#F5F5F5", "#616161", "🥈"), ("#FBE9E7", "#BF360C", "🥉")]

    for i, rep in enumerate(leaderboard):
        bg, tc, medal = MEDAL_COLORS[i] if i < 3 else ("#FFFFFF", "#333333", f"#{i+1}")
        draw_card(draw, 40, y, W-80, 60, CARD_BG)
        if i < 3:
            draw.rounded_rectangle([40, y, 52, y+60], radius=6, fill=bg)
        draw.text((72, y+30), medal, font=fonts["lg"], fill=tc, anchor="lm")
        draw.text((120, y+18), rep["name"], font=fonts["md"], fill=TEXT_PRIMARY, anchor="lm")
        draw.text((120, y+42), f"{rep['jobs']} job{'s' if rep['jobs'] != 1 else ''}", font=fonts["xs"], fill=TEXT_SECONDARY, anchor="lm")
        amt_text = f"${rep['total']:,.0f}"
        draw.text((W-60, y+30), amt_text, font=fonts["lg"], fill=GREEN, anchor="rm")
        y += 68

    # Team total bar
    draw_card(draw, 40, y, W-80, 52, GREEN_BG)
    draw.text((68, y+26), "Team total", font=fonts["sm"], fill=GREEN, anchor="lm")
    draw.text((W-60, y+14), f"${team_total:,.0f}", font=fonts["lg"], fill=GREEN, anchor="rm")
    draw.text((W-60, y+38), f"{team_deals} deals", font=fonts["xs"], fill=GREEN, anchor="rm")
    y += 68

    draw.rectangle([40, y, W-40, y+1], fill="#E0E0E0")
    y += 16

    # Rewards section
    draw.text((56, y+14), "REWARD WINNERS", font=fonts["xs"], fill=TEXT_MUTED, anchor="lm")
    y += 36

    REWARD_COLORS = {
        "First Blood":  ("#FFEBEE", "#C62828"),
        "Big Ticket":   ("#FFF8E1", "#E65100"),
        "Most Deals":   ("#FFF3E0", "#E65100"),
        "High Roller":  ("#E8F5E9", "#2E7D32"),
        "Team Goal":    ("#E3F2FD", "#1565C0"),
    }

    for reward in rewards:
        bg, tc = REWARD_COLORS.get(reward["name"], ("#F3E5F5", "#6A1B9A"))
        draw_card(draw, 40, y, W-80, 64, CARD_BG)
        draw.rounded_rectangle([40, y, 52, y+64], radius=6, fill=bg)
        draw.text((72, y+32), reward["emoji"], font=fonts["lg"], fill=tc, anchor="lm")
        draw.text((120, y+16), reward["name"], font=fonts["md"], fill=TEXT_PRIMARY, anchor="lm")
        draw.text((120, y+42), f"→ {reward['winner']}", font=fonts["sm"], fill=TEXT_SECONDARY, anchor="lm")
        draw.text((W-60, y+32), reward["prize"], font=fonts["xs"], fill=TEXT_MUTED, anchor="rm")
        y += 72

    # Footer
    draw.rectangle([40, y+8, W-40, y+9], fill="#E0E0E0")
    draw.text((W//2, y+28), "Good work today. Rest up and let's run it back tomorrow. 🚀", font=fonts["xs"], fill=TEXT_MUTED, anchor="mm")
    draw.rectangle([0, H-8, W, H], fill=ACCENT)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
