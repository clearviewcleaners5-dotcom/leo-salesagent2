"""
CVC Discord Image Generator — Gold & Black Brand
"""

from PIL import Image, ImageDraw, ImageFont
import io
import os
import requests

CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "1230709942265188352")
GOLD = "#C9A84C"
GOLD_LIGHT = "#F0D080"
GOLD_BG = "#1F1A0E"
BLACK = "#111111"
CARD = "#1A1A1A"
BORDER = "#2A2A2A"
GOLD_BORDER = "#3A3010"
WHITE = "#FFFFFF"
GRAY = "#666666"
MUTED = "#444444"


def send_discord_image(image_buf, filename="cvc.png", caption=""):
    image_buf.seek(0)
    files = {"file": (filename, image_buf, "image/png")}
    data = {}
    if caption:
        data["content"] = caption
    response = requests.post(
        f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages",
        headers={"Authorization": f"Bot {os.environ.get('DISCORD_BOT_TOKEN')}"},
        files=files,
        data=data
    )
    if response.status_code == 200:
        print(f"✅ Image sent: {filename}")
        return True
    print(f"❌ Discord image error: {response.status_code} {response.text}")
    return False


def load_fonts():
    try:
        bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        reg = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        return {
            "xxl": ImageFont.truetype(bold, 38),
            "xl":  ImageFont.truetype(bold, 28),
            "lg":  ImageFont.truetype(bold, 22),
            "md":  ImageFont.truetype(bold, 17),
            "sm":  ImageFont.truetype(reg,  15),
            "xs":  ImageFont.truetype(reg,  12),
            "tag": ImageFont.truetype(bold, 11),
        }
    except:
        f = ImageFont.load_default()
        return {k: f for k in ["xxl","xl","lg","md","sm","xs","tag"]}


def draw_rounded_rect(draw, x, y, w, h, r, fill, outline=None, outline_width=1):
    draw.rounded_rectangle([x, y, x+w, y+h], radius=r, fill=fill, outline=outline, width=outline_width)


def draw_gold_bar(draw, x, y, w, h=4):
    """Draw a gold gradient-style bar using dithered stripes."""
    draw.rectangle([x, y, x+w, y+h], fill=GOLD)


def generate_bonus_image(date_str, bonuses):
    """
    Generate morning daily bonuses graphic.
    bonuses: list of {"emoji", "name", "desc", "prize"} — 3 or 4 items
    """
    W = 900
    cols = 2
    rows = (len(bonuses) + 1) // 2
    card_h = 130
    card_w = (W - 80 - 20) // 2
    H = 180 + (rows * (card_h + 12)) + 60

    img = Image.new("RGB", (W, H), color=BLACK)
    draw = ImageDraw.Draw(img)
    fonts = load_fonts()

    # Gold top bar
    draw_gold_bar(draw, 0, 0, W, 6)

    # Tag line
    draw.text((50, 26), "CLEAREST VIEW CLEANERS", font=fonts["tag"], fill=GOLD)

    # Title
    draw.text((50, 50), "Today's Bonuses", font=fonts["xxl"], fill=WHITE)

    # Subtitle
    draw.text((50, 98), "Win big. Close more. Let's go.", font=fonts["sm"], fill=GRAY)

    # Date badge
    badge_text = date_str
    bw = len(badge_text) * 9 + 28
    bx = W - 50 - bw
    draw_rounded_rect(draw, bx, 26, bw, 28, 14, GOLD_BG, GOLD_BORDER, 1)
    draw.text((bx + bw//2, 40), badge_text, font=fonts["xs"], fill=GOLD, anchor="mm")

    # Divider
    draw.rectangle([50, 120, W-50, 121], fill=BORDER)

    # Bonus cards
    for i, bonus in enumerate(bonuses):
        col = i % 2
        row = i // 2
        cx = 40 + col * (card_w + 20)
        cy = 136 + row * (card_h + 12)

        # Card background
        draw_rounded_rect(draw, cx, cy, card_w, card_h, 12, CARD, BORDER, 1)

        # Gold top accent on card
        draw_gold_bar(draw, cx, cy, card_w, 3)
        draw.rounded_rectangle([cx, cy, cx+card_w, cy+6], radius=3, fill=GOLD)

        # Emoji
        draw.text((cx+20, cy+28), bonus["emoji"], font=fonts["xl"], fill=WHITE, anchor="lm")

        # Name
        draw.text((cx+72, cy+22), bonus["name"], font=fonts["md"], fill=WHITE, anchor="lm")

        # Desc
        desc = bonus["desc"]
        if len(desc) > 38:
            desc = desc[:36] + "…"
        draw.text((cx+72, cy+44), desc, font=fonts["xs"], fill=GRAY, anchor="lm")

        # Prize pill
        prize = bonus["prize"]
        pw = len(prize) * 8 + 24
        draw_rounded_rect(draw, cx+16, cy+card_h-36, pw, 22, 11, GOLD_BG, GOLD_BORDER, 1)
        draw.text((cx+16+pw//2, cy+card_h-25), prize, font=fonts["xs"], fill=GOLD, anchor="mm")

    # Footer
    footer_y = H - 48
    draw.rectangle([50, footer_y, W-50, footer_y+1], fill=BORDER)
    draw.text((W//2, H-22), "Every door is an opportunity — Medicine Hat's waiting.", font=fonts["xs"], fill=MUTED, anchor="mm")

    # Gold bottom bar
    draw_gold_bar(draw, 0, H-5, W, 5)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def generate_eod_image(date_str, leaderboard, rewards, team_total, team_deals):
    """
    Generate end-of-day report graphic.
    leaderboard: [{"name", "total", "jobs"}, ...]
    rewards: [{"emoji", "name", "winner", "prize"}, ...]
    """
    W = 900
    rep_h = 68
    reward_h = 68
    H = 200 + (len(leaderboard) * rep_h) + 80 + 40 + (len(rewards) * reward_h) + 70

    img = Image.new("RGB", (W, H), color=BLACK)
    draw = ImageDraw.Draw(img)
    fonts = load_fonts()

    # Gold top bar
    draw_gold_bar(draw, 0, 0, W, 6)

    # Tag
    draw.text((50, 26), "CLEAREST VIEW CLEANERS", font=fonts["tag"], fill=GOLD)

    # Title
    draw.text((50, 50), "End of Day Report", font=fonts["xxl"], fill=WHITE)
    draw.text((50, 98), "Final standings + reward winners", font=fonts["sm"], fill=GRAY)

    # Date badge
    bw = len(date_str) * 9 + 28
    bx = W - 50 - bw
    draw_rounded_rect(draw, bx, 26, bw, 28, 14, GOLD_BG, GOLD_BORDER, 1)
    draw.text((bx + bw//2, 40), date_str, font=fonts["xs"], fill=GOLD, anchor="mm")

    draw.rectangle([50, 120, W-50, 121], fill=BORDER)

    y = 136

    # Section label
    draw.text((50, y+10), "LEADERBOARD", font=fonts["tag"], fill=MUTED)
    y += 32

    medals = ["🥇", "🥈", "🥉"]
    for i, rep in enumerate(leaderboard):
        is_top = i == 0
        card_fill = "#1C1800" if is_top else CARD
        card_border = "#3A3010" if is_top else BORDER
        draw_rounded_rect(draw, 40, y, W-80, 58, 10, card_fill, card_border, 1)
        if is_top:
            draw_gold_bar(draw, 40, y, W-80, 3)
            draw.rounded_rectangle([40, y, W-40, y+6], radius=3, fill=GOLD)

        medal = medals[i] if i < 3 else f"#{i+1}"
        draw.text((68, y+29), medal, font=fonts["lg"], fill=GOLD if is_top else WHITE, anchor="lm")
        draw.text((120, y+18), rep["name"], font=fonts["md"], fill=WHITE, anchor="lm")
        draw.text((120, y+40), f"{rep['jobs']} job{'s' if rep['jobs']!=1 else ''} closed", font=fonts["xs"], fill=GRAY, anchor="lm")
        draw.text((W-60, y+29), f"${rep['total']:,.0f}", font=fonts["lg"], fill=GOLD, anchor="rm")
        y += rep_h

    # Team total bar
    draw_rounded_rect(draw, 40, y, W-80, 56, 10, GOLD_BG, GOLD_BORDER, 1)
    draw.text((68, y+28), "Team Total", font=fonts["md"], fill=GOLD, anchor="lm")
    draw.text((W-60, y+18), f"${team_total:,.0f}", font=fonts["lg"], fill=GOLD, anchor="rm")
    draw.text((W-60, y+40), f"{team_deals} deals today", font=fonts["xs"], fill=GRAY, anchor="rm")
    y += 68

    draw.rectangle([50, y+8, W-50, y+9], fill=BORDER)
    y += 26

    # Rewards section
    draw.text((50, y+10), "REWARD WINNERS", font=fonts["tag"], fill=MUTED)
    y += 32

    for reward in rewards:
        draw_rounded_rect(draw, 40, y, W-80, 58, 10, CARD, BORDER, 1)
        draw_gold_bar(draw, 40, y, 4, 58)
        draw.rounded_rectangle([40, y, 44, y+58], radius=2, fill=GOLD)

        draw.text((68, y+29), reward["emoji"], font=fonts["lg"], fill=WHITE, anchor="lm")
        draw.text((118, y+18), reward["name"], font=fonts["md"], fill=WHITE, anchor="lm")
        draw.text((118, y+40), f"→ {reward['winner']}", font=fonts["sm"], fill=GRAY, anchor="lm")

        pw = len(reward["prize"]) * 8 + 24
        draw_rounded_rect(draw, W-60-pw, y+18, pw, 22, 11, GOLD_BG, GOLD_BORDER, 1)
        draw.text((W-60-pw//2, y+29), reward["prize"], font=fonts["xs"], fill=GOLD, anchor="mm")
        y += reward_h

    # Footer
    draw.rectangle([50, y+8, W-50, y+9], fill=BORDER)
    draw.text((W//2, y+26), "Good work today. Let's run it back tomorrow.", font=fonts["xs"], fill=MUTED, anchor="mm")

    draw_gold_bar(draw, 0, H-5, W, 5)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
