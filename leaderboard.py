"""
Leo - CVC Sales Manager Agent
Full Discord bot with message listening, scheduling, image graphics.
Schedule: 10AM bonuses, real-time sale alerts, 9PM EOD report.
Leo responds to scheduling questions in Discord automatically.
"""

import os, io, json, requests, pytz, anthropic, threading
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, jsonify, request
from image_gen import generate_bonus_image, generate_eod_image, send_discord_image
import discord
from discord.ext import commands

app = Flask(__name__)
MOUNTAIN = pytz.timezone("America/Edmonton")
daily_sales_log = []
daily_bonuses = []
CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "1230709942265188352")
MAX_HOURS_PER_DAY = 7
AVG_JOB_HOURS = 2.0  # average job length in hours

CORE_BONUS = {"emoji": "🩸", "name": "First Blood", "desc": "First sale of the day", "prize": "Tim Hortons on Ryley"}

# ── DISCORD BOT ───────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.polls = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Leo is online as {bot.user}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content.lower()
    is_addressed = "leo" in content or "hey leo" in content

    if not is_addressed:
        await bot.process_commands(message)
        return

    # Scheduling questions
    schedule_keywords = ["schedule", "book", "available", "opening", "when", "slot", "appointment"]
    if any(word in content for word in schedule_keywords):
        await message.channel.send("📅 Checking the schedule, one sec...")
        schedule_info = get_schedule_availability()
        await message.channel.send(schedule_info, tts=False)
        return

    # General questions — ask Claude
    claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    prompt = f"""You are Leo, the AI sales manager for Clearest View Cleaners (CVC), a window cleaning, soft washing, pressure washing and gutter cleaning company in Medicine Hat, Alberta.
A team member just messaged you in Discord: "{message.content}"
Reply in 1-3 sentences max. Be direct, energetic, helpful. You're a hype sales manager."""
    try:
        msg = claude.messages.create(model="claude-sonnet-4-5", max_tokens=150,
                                     messages=[{"role": "user", "content": prompt}])
        await message.channel.send(msg.content[0].text)
    except Exception as e:
        await message.channel.send("I'm on it. Give me a sec.")

    await bot.process_commands(message)


def get_homebase_schedule():
    """Get booked jobs from Homebase 360 for the next 2 weeks."""
    api_key = os.environ.get("HOMEBASE_API_KEY")
    if not api_key:
        return {}

    schedule = {}
    try:
        today = datetime.now(MOUNTAIN)
        for i in range(14):
            day = today + timedelta(days=i)
            if day.weekday() >= 5:  # skip weekends
                continue
            date_str = day.strftime("%Y-%m-%d")
            r = requests.get(
                "https://app.joinhomebase.com/api/v1/jobs",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"date": date_str}
            )
            if r.status_code == 200:
                jobs = r.json().get("jobs", [])
                booked_hours = sum(float(j.get("duration_hours", AVG_JOB_HOURS)) for j in jobs)
                schedule[date_str] = {"booked": booked_hours, "jobs": len(jobs)}
    except Exception as e:
        print(f"Homebase schedule error: {e}")
    return schedule


def get_schedule_availability():
    """Return a Discord-friendly message about available booking slots."""
    schedule = get_homebase_schedule()

    if not schedule:
        return "📅 **Schedule**\nMonday to Friday, 7 hours max per day. DM or call to book: (403) 878-6670 or visit clearestviewcleaners.com"

    today = datetime.now(MOUNTAIN)
    available_days = []
    full_days = []

    for i in range(14):
        day = today + timedelta(days=i)
        if day.weekday() >= 5:
            continue
        date_str = day.strftime("%Y-%m-%d")
        day_label = day.strftime("%A, %B %d")
        data = schedule.get(date_str, {"booked": 0, "jobs": 0})
        booked = data["booked"]
        remaining = MAX_HOURS_PER_DAY - booked

        if remaining >= AVG_JOB_HOURS:
            available_days.append(f"✅ **{day_label}** — {remaining:.0f}h available ({data['jobs']} job{'s' if data['jobs']!=1 else ''} booked)")
        else:
            full_days.append(f"🔴 **{day_label}** — Fully booked")

    msg = "📅 **CVC BOOKING AVAILABILITY**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    if available_days:
        msg += "\n".join(available_days[:7])
    else:
        msg += "All days are fully booked right now!"

    if full_days:
        msg += "\n\n" + "\n".join(full_days[:3])

    msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n📞 Book at clearestviewcleaners.com or call (403) 878-6670"
    return msg


# ── HELPERS ───────────────────────────────────────────────────────────────────
def discord_headers():
    return {"Authorization": f"Bot {os.environ.get('DISCORD_BOT_TOKEN')}", "Content-Type": "application/json"}


def send_text(content, tts=False):
    r = requests.post(f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages",
                      headers=discord_headers(), json={"content": content, "tts": tts})
    print("✅ Text sent" if r.status_code == 200 else f"❌ Text error: {r.status_code} {r.text}")
    return r.status_code == 200


def get_bonus_count():
    day = datetime.now(MOUNTAIN).weekday()
    return 4 if day in [4, 5, 6] else 3


def generate_daily_bonuses():
    global daily_bonuses
    claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    count = get_bonus_count()
    creative_count = count - 1
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")

    prompt = f"""You are Leo, AI sales manager for Clearest View Cleaners in Medicine Hat, Alberta. D2D sales team.
Today is {today}. Generate exactly {creative_count} creative bonus challenges. Budget $20-30 each.
Mix from: speed challenges, neighborhood sweeps, upsell bonuses, streak bonuses, mystery bonuses, time-window challenges, combo deals, comeback bonuses.
Return ONLY valid JSON array:
[{{"emoji": "⚡", "name": "Speed Round", "desc": "Close a sale within 10 min of knocking", "prize": "$20 cash bonus"}}]"""

    try:
        msg = claude.messages.create(model="claude-sonnet-4-5", max_tokens=400,
                                     messages=[{"role": "user", "content": prompt}])
        creative = json.loads(msg.content[0].text.strip())[:creative_count]
    except Exception as e:
        print(f"Bonus gen error: {e}")
        creative = [
            {"emoji": "⚡", "name": "Speed Round", "desc": "Close within 10 min of knocking", "prize": "$20 cash bonus"},
            {"emoji": "🗺️", "name": "Neighborhood Sweep", "desc": "2 sales on the same street", "prize": "$25 cash bonus"},
            {"emoji": "🎲", "name": "Mystery Bonus", "desc": "Ask Ryley — decided at EOD", "prize": "$20 cash bonus"},
        ][:creative_count]

    daily_bonuses = [CORE_BONUS] + creative
    return daily_bonuses


def get_homebase_sales():
    api_key = os.environ.get("HOMEBASE_API_KEY")
    if not api_key:
        return daily_sales_log
    try:
        today = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
        r = requests.get("https://app.joinhomebase.com/api/v1/jobs",
                         headers={"Authorization": f"Bearer {api_key}"},
                         params={"date": today, "status": "completed"})
        if r.status_code == 200:
            jobs = r.json().get("jobs", [])
            sales = [{"rep": j.get("assigned_to","Unknown"), "customer": j.get("customer_name","Customer"),
                      "amount": float(j.get("total",0)), "neighborhood": j.get("neighborhood",""),
                      "time": j.get("time","")} for j in jobs]
            return sales or daily_sales_log
    except Exception as e:
        print(f"Homebase error: {e}")
    return daily_sales_log


def get_rep_totals(sales=None):
    totals = {}
    for s in (sales or daily_sales_log):
        r = s["rep"]
        if r not in totals:
            totals[r] = {"total": 0, "jobs": 0}
        totals[r]["total"] += s["amount"]
        totals[r]["jobs"] += 1
    return totals


def build_leaderboard_text(rep_totals=None):
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")
    rep_totals = rep_totals or get_rep_totals()
    if not rep_totals:
        return f"📊 **CVC LEADERBOARD — {today}**\n━━━━━━━━━━━━━━━━━━━━━━\nBoard is empty. First sale gets 🩸 First Blood! Let's move. 💪\n━━━━━━━━━━━━━━━━━━━━━━"
    sorted_reps = sorted(rep_totals.items(), key=lambda x: x[1]["total"], reverse=True)
    team_total = sum(v["total"] for v in rep_totals.values())
    team_deals = sum(v["jobs"] for v in rep_totals.values())
    medals = ["🥇","🥈","🥉"]
    board = f"📊 **CVC LEADERBOARD — {today}**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for i, (rep, data) in enumerate(sorted_reps):
        board += f"{medals[i] if i<3 else '▪️'} **{rep}** — ${data['total']:.0f} ({data['jobs']} job{'s' if data['jobs']!=1 else ''})\n"
    board += f"━━━━━━━━━━━━━━━━━━━━━━\n💰 **${team_total:.0f}** | 📋 **{team_deals} deals**\nKeep closing. 💪"
    return board


def post_sale_update(sale):
    rep, customer, amount = sale["rep"], sale["customer"], sale["amount"]
    neighborhood = sale.get("neighborhood","")
    time_str = sale.get("time", datetime.now(MOUNTAIN).strftime("%-I:%M %p"))
    rep_totals = get_rep_totals()
    rd = rep_totals.get(rep, {"total":0,"jobs":0})
    team_total = sum(v["total"] for v in rep_totals.values())
    team_deals = sum(v["jobs"] for v in rep_totals.values())
    msg = f"💥 **SALE CLOSED — {time_str}**\n━━━━━━━━━━━━━━━━━━━━━━\n👤 **{customer}**\n📍 **{neighborhood or 'Medicine Hat'}**\n💼 **{rep}**\n💵 **${amount:.0f}**\n━━━━━━━━━━━━━━━━━━━━━━\n📈 {rep}: **${rd['total']:.0f}** ({rd['jobs']} job{'s' if rd['jobs']!=1 else ''})\n💰 Team: **${team_total:.0f}** | **{team_deals} deals**"
    if neighborhood:
        msg += f"\n\n🗺️ *{neighborhood} is open — get in there!*"
    send_text(msg)


def morning_post():
    generate_daily_bonuses()
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")
    send_text(build_leaderboard_text())
    buf = generate_bonus_image(today, daily_bonuses)
    send_discord_image(buf, filename="cvc_bonuses.png")


def eod_report():
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")
    sales_data = get_homebase_sales()
    rep_totals = get_rep_totals(sales_data)
    if not rep_totals:
        send_text("No sales logged today. Tomorrow we go harder. 💪")
        return
    sorted_reps = sorted(rep_totals.items(), key=lambda x: x[1]["total"], reverse=True)
    team_total = sum(v["total"] for v in rep_totals.values())
    team_deals = sum(v["jobs"] for v in rep_totals.values())
    leaderboard = [{"name": r, "total": d["total"], "jobs": d["jobs"]} for r,d in sorted_reps]
    rewards = []
    if sales_data:
        rewards.append({"emoji":"🩸","name":"First Blood","winner":sales_data[0]["rep"],"prize":"Tim Hortons on Ryley"})
    if sorted_reps:
        rewards.append({"emoji":"🎯","name":"Big Ticket","winner":sorted_reps[0][0],"prize":"$20 cash bonus"})
    most_deals = max(rep_totals.items(), key=lambda x: x[1]["jobs"])
    rewards.append({"emoji":"🔥","name":"Most Deals","winner":most_deals[0],"prize":"$20 cash bonus"})
    for rep, data in rep_totals.items():
        if data["total"] >= 1000:
            rewards.append({"emoji":"🍽️","name":"High Roller","winner":rep,"prize":"Free dinner on CVC"})
    if team_deals >= 10:
        rewards.append({"emoji":"🏆","name":"Team Goal","winner":"Everyone","prize":"$10 bonus each"})
    buf = generate_eod_image(today, leaderboard, rewards, team_total, team_deals)
    send_discord_image(buf, filename="cvc_eod_report.png")
    daily_sales_log.clear()


# ── SCHEDULER ─────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone=MOUNTAIN)
scheduler.add_job(morning_post, CronTrigger(hour=10, minute=0, timezone=MOUNTAIN), id="morning")
scheduler.add_job(eod_report, CronTrigger(hour=21, minute=0, timezone=MOUNTAIN), id="eod")
scheduler.start()

# Run Discord bot in background thread
def run_bot():
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if token:
        bot.run(token)
    else:
        print("No Discord bot token found")

bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()


# ── FLASK ROUTES ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return jsonify({"status": "Leo - CVC Sales Manager is running ✅"})

@app.route("/add-sale", methods=["POST"])
def add_sale():
    data = request.json
    rep, customer = data.get("rep"), data.get("customer","Customer")
    amount = float(data.get("amount",0))
    neighborhood = data.get("neighborhood","")
    if not rep or not amount:
        return jsonify({"error": "Missing rep or amount"}), 400
    sale = {"rep":rep,"customer":customer,"amount":amount,"neighborhood":neighborhood,
            "time":datetime.now(MOUNTAIN).strftime("%-I:%M %p")}
    daily_sales_log.append(sale)
    post_sale_update(sale)
    return jsonify({"status": f"Sale logged — {rep} closed ${amount} with {customer}"})

@app.route("/schedule")
def schedule():
    msg = get_schedule_availability()
    send_text(msg)
    return jsonify({"status": "Schedule posted", "message": msg})

@app.route("/test-bonuses")
def test_bonuses():
    generate_daily_bonuses()
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")
    buf = generate_bonus_image(today, daily_bonuses)
    send_discord_image(buf, filename="cvc_bonuses.png")
    return jsonify({"status": "Bonus image posted", "count": len(daily_bonuses), "bonuses": daily_bonuses})

@app.route("/test-leaderboard")
def test_leaderboard():
    global daily_sales_log
    daily_sales_log = [
        {"rep":"Jared","customer":"Mike Johnson","amount":580,"neighborhood":"Ross Glen","time":"10:15 AM"},
        {"rep":"Jared","customer":"Tom Williams","amount":240,"neighborhood":"Ross Glen","time":"1:45 PM"},
        {"rep":"Jared","customer":"Dave Martin","amount":195,"neighborhood":"Crescent Heights","time":"3:10 PM"},
    ]
    send_text(build_leaderboard_text())
    return jsonify({"status": "Test leaderboard posted"})

@app.route("/test-sale")
def test_sale():
    sale = {"rep":"Jared","customer":"Mike Johnson","amount":280,"neighborhood":"Ross Glen",
            "time":datetime.now(MOUNTAIN).strftime("%-I:%M %p")}
    daily_sales_log.append(sale)
    post_sale_update(sale)
    return jsonify({"status": "Test sale posted"})

@app.route("/test-eod")
def test_eod():
    global daily_sales_log
    daily_sales_log = [
        {"rep":"Jared","customer":"Mike Johnson","amount":580,"neighborhood":"Ross Glen","time":"10:15 AM"},
        {"rep":"Jared","customer":"Tom Williams","amount":240,"neighborhood":"Ross Glen","time":"1:45 PM"},
        {"rep":"Jared","customer":"Dave Martin","amount":195,"neighborhood":"Crescent Heights","time":"3:10 PM"},
    ]
    eod_report()
    return jsonify({"status": "EOD image posted"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001)
