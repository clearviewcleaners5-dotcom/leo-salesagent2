"""
Leo Discord Bot — runs as main process on Railway
"""

import os, json, requests, pytz, anthropic
from datetime import datetime, timedelta
import discord
from discord.ext import commands
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from image_gen import generate_bonus_image, generate_eod_image, send_discord_image

MOUNTAIN = pytz.timezone("America/Edmonton")
daily_sales_log = []
daily_bonuses = []
CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "1230709942265188352")
MAX_HOURS_PER_DAY = 7
AVG_JOB_HOURS = 2.0

CORE_BONUS = {"emoji": "🩸", "name": "First Blood", "desc": "First sale of the day", "prize": "Tim Hortons on Ryley"}

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


def discord_headers():
    return {"Authorization": f"Bot {os.environ.get('DISCORD_BOT_TOKEN')}", "Content-Type": "application/json"}


def send_text(content):
    r = requests.post(f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages",
                      headers=discord_headers(), json={"content": content})
    print("✅ Text sent" if r.status_code == 200 else f"❌ {r.status_code} {r.text}")


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


def build_leaderboard_text():
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")
    rep_totals = get_rep_totals()
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


def get_schedule_availability():
    api_key = os.environ.get("HOMEBASE_API_KEY")
    if not api_key:
        return "📅 **CVC Schedule**\nMonday to Friday. Book at clearestviewcleaners.com or call (403) 878-6670"
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
                booked = sum(float(j.get("duration_hours", AVG_JOB_HOURS)) for j in jobs)
                schedule[date_str] = {"booked": booked, "jobs": len(jobs)}
    except Exception as e:
        print(f"Schedule error: {e}")

    today = datetime.now(MOUNTAIN)
    available, full = [], []
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


@bot.event
async def on_ready():
    print(f"✅ Leo is online as {bot.user}")
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
        await message.channel.send(get_schedule_availability())
        return

    claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    prompt = f"""You are Leo, AI sales manager for Clearest View Cleaners in Medicine Hat, Alberta. D2D sales team.
Someone messaged: "{message.content}"
Reply in 1-3 sentences. Be direct, energetic, helpful."""
    try:
        resp = claude.messages.create(model="claude-sonnet-4-5", max_tokens=150,
                                      messages=[{"role": "user", "content": prompt}])
        await message.channel.send(resp.content[0].text)
    except:
        await message.channel.send("On it. Give me a sec.")

    await bot.process_commands(message)


scheduler = BackgroundScheduler(timezone=MOUNTAIN)
scheduler.add_job(morning_post, CronTrigger(hour=10, minute=0, timezone=MOUNTAIN), id="morning")
scheduler.add_job(eod_report, CronTrigger(hour=21, minute=0, timezone=MOUNTAIN), id="eod")

if __name__ == "__main__":
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ No DISCORD_BOT_TOKEN")
    else:
        print("🚀 Starting Leo...")
        bot.run(token)
