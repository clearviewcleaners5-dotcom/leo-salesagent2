"""
Leo - CVC Sales Manager Agent
Discord bot is the main process. Flask runs in background thread.
"""

import os, io, json, requests, pytz, anthropic, threading
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, jsonify, request
from image_gen import generate_bonus_image, generate_eod_image, send_discord_image
import discord
from discord.ext import commands

MOUNTAIN = pytz.timezone("America/Edmonton")
daily_sales_log = []
daily_bonuses = []
CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "1230709942265188352")
MAX_HOURS_PER_DAY = 7
AVG_JOB_HOURS = 2.0

CORE_BONUS = {"emoji": "🩸", "name": "First Blood", "desc": "First sale of the day", "prize": "Tim Hortons on Ryley"}

# ── DISCORD BOT ───────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Leo is online as {bot.user}")
    # Start scheduler once bot is ready
    if not scheduler.running:
        scheduler.start()
        print("✅ Scheduler started")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content.lower()
    if "leo" not in content:
        await bot.process_commands(message)
        return

    schedule_keywords = ["schedule", "book", "available", "opening", "when", "slot", "appointment"]
    if any(word in content for word in schedule_keywords):
        await message.channel.send("📅 Checking the schedule, one sec...")
        msg = get_schedule_availability()
        await message.channel.send(msg)
        return

    # General Leo question
    claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    prompt = f"""You are Leo, AI sales manager for Clearest View Cleaners in Medicine Hat, Alberta. D2D sales team.
Someone messaged: "{message.content}"
Reply in 1-3 sentences. Be direct, energetic, helpful."""
    try:
        resp = claude.messages.create(model="claude-sonnet-4-5", max_tokens=150,
                                      messages=[{"role": "user", "content": prompt}])
        await message.channel.send(resp.content[0].text)
    except Exception as e:
        await message.channel.send("On it. Give me a sec.")

    await bot.process_commands(message)


# ── SCHEDULE CHECK ────────────────────────────────────────────────────────────
def get_homebase_schedule():
    api_key = os.environ.get("HOMEBASE_API_KEY")
    if not api_key:
        return {}
    schedule = {}
    try:
        today = datetime.now(MOUNTAIN)
        for i in range(14):
            day = today + timedelta(days=i)
            if day.weekday() >= 5:
                continue
            date_str = day.strftime("%Y-%m-%d")
            r = requests.get("https://app.joinhomebase.com/api/v1/jobs",
                             headers={"Authorization": f"Bearer {api_key}"},
                             params={"date": date_str})
            if r.status_code == 200:
                jobs = r.json().get("jobs", [])
                booked_hours = sum(float(j.get("duration_hours", AVG_JOB_HOURS)) for j in jobs)
                schedule[date_str] = {"booked": booked_hours, "jobs": len(jobs)}
    except Exception as e:
        print(f"Homebase schedule error: {e}")
    return schedule


def get_schedule_availability():
    schedule = get_homebase_schedule()
    if not schedule:
        return "📅 **CVC Schedule**\nMonday to Friday. Call (403) 878-6670 or visit clearestviewcleaners.com to book."

    today = datetime.now(MOUNTAIN)
    available = []
    full = []

    for i in range(14):
        day = today + timedelta(days=i)
        if day.weekday() >= 5:
            continue
        date_str = day.strftime("%Y-%m-%d")
        day_label = day.strftime("%A, %B %d")
        data = schedule.get(date_str, {"booked": 0, "jobs": 0})
        remaining = MAX_HOURS_PER_DAY - data["booked"]
        if remaining >= AVG_JOB_HOURS:
            available.append(f"✅ **{day_label}** — {remaining:.0f}h open ({data['jobs']} job{'s' if data['jobs']!=1 else ''} booked)")
        else:
            full.append(f"🔴 **{day_label}** — Fully booked")

    msg = "📅 **CVC BOOKING AVAILABILITY**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "\n".join(available[:7]) if available else "All days fully booked!"
    if full:
        msg += "\n\n" + "\n".join(full[:3])
    msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n📞 clearestviewcleaners.com | (403) 878-6670"
    return msg


# ── HELPERS ───────────────────────────────────────────────────────────────────
def discord_headers():
    return {"Authorization": f"Bot {os.environ.get('DISCORD_BOT_TOKEN')}", "Content-Type": "application/json"}


def send_text(content):
    r = requests.post(f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages",
                      headers=discord_headers(), json={"content": content})
    print("✅ Text sent" if r.status_code == 200 else f"❌ {r.status_code} {r.text}")
    return r.status_code == 200


def get_bonus_count():
    return 4 if datetime.now(MOUNTAIN).weekday() in [4, 5, 6] else 3


def generate_daily_bonuses():
    global daily_bonuses
    claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    count = get_bonus_count()
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")
    prompt = f"""You are Leo, AI sales manager for Clearest View Cleaners in Medicine Hat, Alberta.
Today is {today}. Generate exactly {count-1} creative bonus challenges for a D2D sales team. Budget $20-30 each.
Ideas: speed challenges, neighborhood sweeps, upsell bonuses, streak bonuses, mystery bonuses, time-window challenges.
Return ONLY valid JSON array:
[{{"emoji": "⚡", "name": "Speed Round", "desc": "Close within 10 min of knocking", "prize": "$20 cash bonus"}}]"""
    try:
        msg = claude.messages.create(model="claude-sonnet-4-5", max_tokens=400,
                                     messages=[{"role": "user", "content": prompt}])
        creative = json.loads(msg.content[0].text.strip())[:(count-1)]
    except:
        creative = [
            {"emoji": "⚡", "name": "Speed Round", "desc": "Close within 10 min of knocking", "prize": "$20 cash bonus"},
            {"emoji": "🗺️", "name": "Neighborhood Sweep", "desc": "2 sales on the same street", "prize": "$25 cash bonus"},
            {"emoji": "🎲", "name": "Mystery Bonus", "desc": "Ask Ryley — decided at EOD", "prize": "$20 cash bonus"},
        ][:(count-1)]
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
            return [{"rep": j.get("assigned_to","Unknown"), "customer": j.get("customer_name","Customer"),
                     "amount": float(j.get("total",0)), "neighborhood": j.get("neighborhood",""),
                     "time": j.get("time","")} for j in jobs] or daily_sales_log
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
        return f"📊 **CVC LEADERBOARD — {today}**\n━━━━━━━━━━━━━━━━━━━━━━\nBoard is empty. First sale gets 🩸 First Blood!\n━━━━━━━━━━━━━━━━━━━━━━"
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


# ── FLASK (runs in background thread) ─────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return jsonify({"status": "Leo - CVC Sales Manager is running ✅"})

@flask_app.route("/add-sale", methods=["POST"])
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

@flask_app.route("/test-bonuses")
def test_bonuses():
    generate_daily_bonuses()
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")
    buf = generate_bonus_image(today, daily_bonuses)
    send_discord_image(buf, filename="cvc_bonuses.png")
    return jsonify({"status": "Bonus image posted", "count": len(daily_bonuses)})

@flask_app.route("/test-leaderboard")
def test_leaderboard():
    global daily_sales_log
    daily_sales_log = [
        {"rep":"Jared","customer":"Mike Johnson","amount":580,"neighborhood":"Ross Glen","time":"10:15 AM"},
        {"rep":"Jared","customer":"Tom Williams","amount":240,"neighborhood":"Ross Glen","time":"1:45 PM"},
        {"rep":"Jared","customer":"Dave Martin","amount":195,"neighborhood":"Crescent Heights","time":"3:10 PM"},
    ]
    send_text(build_leaderboard_text())
    return jsonify({"status": "Test leaderboard posted"})

@flask_app.route("/test-sale")
def test_sale():
    sale = {"rep":"Jared","customer":"Mike Johnson","amount":280,"neighborhood":"Ross Glen",
            "time":datetime.now(MOUNTAIN).strftime("%-I:%M %p")}
    daily_sales_log.append(sale)
    post_sale_update(sale)
    return jsonify({"status": "Test sale posted"})

@flask_app.route("/test-eod")
def test_eod():
    global daily_sales_log
    daily_sales_log = [
        {"rep":"Jared","customer":"Mike Johnson","amount":580,"neighborhood":"Ross Glen","time":"10:15 AM"},
        {"rep":"Jared","customer":"Tom Williams","amount":240,"neighborhood":"Ross Glen","time":"1:45 PM"},
        {"rep":"Jared","customer":"Dave Martin","amount":195,"neighborhood":"Crescent Heights","time":"3:10 PM"},
    ]
    eod_report()
    return jsonify({"status": "EOD image posted"})

@flask_app.route("/schedule")
def schedule():
    msg = get_schedule_availability()
    send_text(msg)
    return jsonify({"status": "Schedule posted"})


def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3001)))


# ── MAIN — Discord bot is primary process ─────────────────────────────────────
if __name__ == "__main__":
    # Flask runs in background
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ Flask started in background")

    # Discord bot runs as main process (keeps app alive)
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if token:
        bot.run(token)
    else:
        print("❌ No DISCORD_BOT_TOKEN found")
        import time
        while True:
            time.sleep(60)
