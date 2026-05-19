"""
CVC Discord Image Generator — Gold & Black Brand
Uses bundled fonts so it works on any server including Vercel
"""

from PIL import Image, ImageDraw, ImageFont
import io, os, requests

CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "1230709942265188352")
GOLD = "#C9A84C"
BLACK = "#111111"
CARD = "#1A1A1A"
BORDER = "#2A2A2A"
GOLD_BG = "#1C1800"
GOLD_BORDER = "#3A3010"
WHITE = "#FFFFFF"
GRAY = "#666666"
MUTED = "#444444"

# Font paths — bundled with the project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_BOLD = os.path.join(BASE_DIR, "fonts", "Bold.ttf")
FONT_REG  = os.path.join(BASE_DIR, "fonts", "Regular.ttf")


def send_discord_image(image_buf, filename="cvc.png", caption=""):
    image_buf.seek(0)
    files = {"file": (filename, image_buf, "image/png")}
    data = {"content": caption} if caption else {}
    response = requests.post(
        f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages",
        headers={"Authorization": f"Bot {os.environ.get('DISCORD_BOT_TOKEN')}"},
        files=files, data=data
    )
    if response.status_code == 200:
        print(f"✅ Image sent: {filename}")
        return True
    print(f"❌ Discord image error: {response.status_code} {response.text}")
    return False


def load_fonts():
    try:
        return {
            "xxl": ImageFont.truetype(FONT_BOLD, 36),
            "xl":  ImageFont.truetype(FONT_BOLD, 26),
            "lg":  ImageFont.truetype(FONT_BOLD, 20),
            "md":  ImageFont.truetype(FONT_BOLD, 16),
            "sm":  ImageFont.truetype(FONT_REG,  14),
            "xs":  ImageFont.truetype(FONT_REG,  12),
            "tag": ImageFont.truetype(FONT_BOLD, 10),
        }
    except Exception as e:
        print(f"Font load error: {e} — using default")
        f = ImageFont.load_default()
        return {k: f for k in ["xxl","xl","lg","md","sm","xs","tag"]}


def rr(draw, x, y, w, h, r, fill, outline=None, ow=1):
    draw.rounded_rectangle([x, y, x+w, y+h], radius=r, fill=fill,
                            outline=outline, width=ow)


def gold_bar(draw, x, y, w, h=5):
    draw.rectangle([x, y, x+w, y+h], fill=GOLD)


def generate_bonus_image(date_str, bonuses):
    W = 900
    cols = 2
    rows = (len(bonuses) + 1) // 2
    card_h = 128
    card_w = (W - 80 - 16) // 2
    H = 172 + (rows * (card_h + 12)) + 52

    img = Image.new("RGB", (W, H), color=BLACK)
    draw = ImageDraw.Draw(img)
    fonts = load_fonts()

    gold_bar(draw, 0, 0, W, 6)
    draw.text((50, 24), "CLEAREST VIEW CLEANERS", font=fonts["tag"], fill=GOLD)
    draw.text((50, 44), "Today's Bonuses", font=fonts["xxl"], fill=WHITE)
    draw.text((50, 92), "Win big. Close more. Let's go.", font=fonts["sm"], fill=GRAY)

    bw = len(date_str) * 8 + 28
    bx = W - 50 - bw
    rr(draw, bx, 24, bw, 26, 13, GOLD_BG, GOLD_BORDER, 1)
    draw.text((bx + bw//2, 37), date_str, font=fonts["xs"], fill=GOLD, anchor="mm")

    draw.rectangle([50, 114, W-50, 115], fill=BORDER)

    for i, bonus in enumerate(bonuses):
        col = i % 2
        row = i // 2
        cx = 40 + col * (card_w + 16)
        cy = 128 + row * (card_h + 12)

        rr(draw, cx, cy, card_w, card_h, 12, CARD, BORDER, 1)
        draw.rectangle([cx, cy, cx+card_w, cy+4], fill=GOLD)
        draw.rounded_rectangle([cx, cy, cx+card_w, cy+8], radius=4, fill=GOLD)

        draw.text((cx+18, cy+32), bonus["emoji"], font=fonts["xl"], fill=WHITE, anchor="lm")
        draw.text((cx+70, cy+20), bonus["name"], font=fonts["md"], fill=WHITE, anchor="lm")

        desc = bonus["desc"][:42] + "…" if len(bonus["desc"]) > 42 else bonus["desc"]
        draw.text((cx+70, cy+40), desc, font=fonts["xs"], fill=GRAY, anchor="lm")

        prize = bonus["prize"]
        pw = len(prize) * 8 + 22
        rr(draw, cx+16, cy+card_h-34, pw, 22, 11, GOLD_BG, GOLD_BORDER, 1)
        draw.text((cx+16+pw//2, cy+card_h-23), prize, font=fonts["xs"], fill=GOLD, anchor="mm")

    draw.rectangle([50, H-44, W-50, H-43], fill=BORDER)
    draw.text((W//2, H-24), "Every door is an opportunity. Medicine Hat's waiting.", font=fonts["xs"], fill=MUTED, anchor="mm")
    gold_bar(draw, 0, H-5, W, 5)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def generate_eod_image(date_str, leaderboard, rewards, team_total, team_deals):
    W = 900
    rep_h = 66
    reward_h = 66
    H = 190 + (len(leaderboard) * rep_h) + 76 + 40 + (len(rewards) * reward_h) + 66

    img = Image.new("RGB", (W, H), color=BLACK)
    draw = ImageDraw.Draw(img)
    fonts = load_fonts()

    gold_bar(draw, 0, 0, W, 6)
    draw.text((50, 24), "CLEAREST VIEW CLEANERS", font=fonts["tag"], fill=GOLD)
    draw.text((50, 44), "End of Day Report", font=fonts["xxl"], fill=WHITE)
    draw.text((50, 92), "Final standings + reward winners", font=fonts["sm"], fill=GRAY)

    bw = len(date_str) * 8 + 28
    bx = W - 50 - bw
    rr(draw, bx, 24, bw, 26, 13, GOLD_BG, GOLD_BORDER, 1)
    draw.text((bx + bw//2, 37), date_str, font=fonts["xs"], fill=GOLD, anchor="mm")

    draw.rectangle([50, 114, W-50, 115], fill=BORDER)

    y = 128
    draw.text((50, y+8), "LEADERBOARD", font=fonts["tag"], fill=MUTED)
    y += 28

    medals = ["🥇", "🥈", "🥉"]
    for i, rep in enumerate(leaderboard):
        is_top = i == 0
        fill = GOLD_BG if is_top else CARD
        border = GOLD_BORDER if is_top else BORDER
        rr(draw, 40, y, W-80, 56, 10, fill, border, 1)
        if is_top:
            draw.rectangle([40, y, W-40, y+4], fill=GOLD)
            draw.rounded_rectangle([40, y, W-40, y+8], radius=4, fill=GOLD)

        medal = medals[i] if i < 3 else f"#{i+1}"
        draw.text((66, y+28), medal, font=fonts["lg"], fill=GOLD if is_top else WHITE, anchor="lm")
        draw.text((116, y+16), rep["name"], font=fonts["md"], fill=WHITE, anchor="lm")
        draw.text((116, y+38), f"{rep['jobs']} job{'s' if rep['jobs']!=1 else ''} closed", font=fonts["xs"], fill=GRAY, anchor="lm")
        draw.text((W-56, y+28), f"${rep['total']:,.0f}", font=fonts["lg"], fill=GOLD, anchor="rm")
        y += rep_h

    rr(draw, 40, y, W-80, 54, 10, GOLD_BG, GOLD_BORDER, 1)
    draw.text((66, y+27), "Team Total", font=fonts["md"], fill=GOLD, anchor="lm")
    draw.text((W-56, y+16), f"${team_total:,.0f}", font=fonts["lg"], fill=GOLD, anchor="rm")
    draw.text((W-56, y+40), f"{team_deals} deals today", font=fonts["xs"], fill=GRAY, anchor="rm")
    y += 70

    draw.rectangle([50, y+6, W-50, y+7], fill=BORDER)
    y += 22

    draw.text((50, y+8), "REWARD WINNERS", font=fonts["tag"], fill=MUTED)
    y += 28

    for reward in rewards:
        rr(draw, 40, y, W-80, 56, 10, CARD, BORDER, 1)
        draw.rectangle([40, y, 44, y+56], fill=GOLD)
        draw.rounded_rectangle([40, y, 46, y+56], radius=2, fill=GOLD)

        draw.text((66, y+28), reward["emoji"], font=fonts["lg"], fill=WHITE, anchor="lm")
        draw.text((114, y+16), reward["name"], font=fonts["md"], fill=WHITE, anchor="lm")
        draw.text((114, y+38), f"→ {reward['winner']}", font=fonts["sm"], fill=GRAY, anchor="lm")

        pw = len(reward["prize"]) * 8 + 22
        rr(draw, W-56-pw, y+17, pw, 22, 11, GOLD_BG, GOLD_BORDER, 1)
        draw.text((W-56-pw//2, y+28), reward["prize"], font=fonts["xs"], fill=GOLD, anchor="mm")
        y += reward_h

    draw.rectangle([50, y+6, W-50, y+7], fill=BORDER)
    draw.text((W//2, y+24), "Good work today. Let's run it back tomorrow.", font=fonts["xs"], fill=MUTED, anchor="mm")
    gold_bar(draw, 0, H-5, W, 5)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
