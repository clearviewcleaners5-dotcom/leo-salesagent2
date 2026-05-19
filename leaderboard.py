"""
Leo - CVC Sales Manager Agent
------------------------------
Schedule:
  8:00 AM  - Daily leaderboard + AI-generated bonus announcement
  After every sale (via /add-sale) - Real-time sale update  
  9:00 PM  - End of day rewards summary

Environment variables needed in Vercel:
  DISCORD_BOT_TOKEN
  DISCORD_CHANNEL_ID
  HOMEBASE_API_KEY
  ANTHROPIC_API_KEY
"""

import os
import io
import json
import requests
import pytz
import anthropic
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, jsonify, request

app = Flask(__name__)
MOUNTAIN = pytz.timezone("America/Edmonton")

daily_sales_log = []
daily_creative_bonuses = []

CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "1230709942265188352")

CORE_BONUSES = [
    {"emoji": "🩸", "name": "First blood", "desc": "First sale of the day", "prize": "Tim Hortons on Ryley", "color": "danger"},
    {"emoji": "🎯", "name": "Big ticket", "desc": "Highest single job value", "prize": "$20 bonus", "color": "warning"},
    {"emoji": "🔥", "name": "Most deals", "desc": "Most jobs closed today", "prize": "$20 bonus", "color": "warning"},
    {"emoji": "🍽️", "name": "High roller", "desc": "Sell $1,000+ in one day", "prize": "Free dinner on CVC", "color": "success"},
    {"emoji": "🏆", "name": "Team goal", "desc": "Team hits 10 deals today", "prize": "$10 bonus everyone", "color": "info"},
]


def get_discord_headers():
    return {
        "Authorization": f"Bot {os.environ.get('DISCORD_BOT_TOKEN')}",
        "Content-Type": "application/json"
    }


def send_discord_message(content):
    response = requests.post(
        f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages",
        headers=get_discord_headers(),
        json={"content": content}
    )
    if response.status_code == 200:
        print("✅ Discord message sent")
        return True
    print(f"❌ Discord error: {response.status_code} {response.text}")
    return False


def generate_creative_bonuses():
    """Use Claude to generate 2 fresh creative bonus challenges for today."""
    global daily_creative_bonuses
    claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")

    prompt = f"""You are Leo, the AI sales manager for Clearest View Cleaners (CVC), a window cleaning, 
soft washing, pressure washing and gutter cleaning company in Medicine Hat, Alberta, Canada.
Their D2D sales team knocks doors and closes jobs on the spot.

Today is {today}. Generate exactly 2 fresh, creative daily bonus challenges for the sales team.
Keep each bonus budget under $30. Make them fun, competitive, and specific to door-to-door sales.
Ideas to draw from: speed challenges, neighborhood challenges, upsell bonuses, streak bonuses, 
mystery bonuses, time-window bonuses, combo deals, first-to challenges, comeback bonuses.
Vary them daily — never repeat the same bonus two days in a row.

Return ONLY valid JSON, no other text:
[
  {{"emoji": "⚡", "name": "Speed round", "desc": "Close a sale within 10 min of knocking", "prize": "$20 bonus"}},
  {{"emoji": "🗺️", "name": "Neighborhood sweep", "desc": "Close 2 sales on the same street", "prize": "$25 bonus"}}
]"""

    try:
        msg = claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        text = msg.content[0].text.strip()
        daily_creative_bonuses = json.loads(text)
        print(f"✅ Generated {len(daily_creative_bonuses)} creative bonuses")
    except Exception as e:
        print(f"❌ Creative bonus generation failed: {e}")
        daily_creative_bonuses = [
            {"emoji": "⚡", "name": "Speed round", "desc": "Close a sale within 10 min of knocking", "prize": "$20 bonus"},
            {"emoji": "🗺️", "name": "Neighborhood sweep", "desc": "Close 2 sales on the same street", "prize": "$25 bonus"}
        ]
    return daily_creative_bonuses


def get_homebase_sales():
    """Pull today's completed jobs from Homebase 360."""
    api_key = os.environ.get("HOMEBASE_API_KEY")
    if not api_key:
        return daily_sales_log

    try:
        today = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
        response = requests.get(
            "https://app.joinhomebase.com/api/v1/jobs",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"date": today, "status": "completed"}
        )
        if response.status_code == 200:
            data = response.json()
            sales = []
            for job in data.get("jobs", []):
                sales.append({
                    "rep": job.get("assigned_to", "Unknown"),
                    "customer": job.get("customer_name", "Customer"),
                    "amount": float(job.get("total", 0)),
                    "neighborhood": job.get("neighborhood", ""),
                    "time": job.get("time", "")
                })
            return sales if sales else daily_sales_log
        return daily_sales_log
    except Exception as e:
        print(f"Homebase error: {e}")
        return daily_sales_log


def get_rep_totals(sales_data=None):
    if sales_data is None:
        sales_data = daily_sales_log
    totals = {}
    for sale in sales_data:
        rep = sale["rep"]
        if rep not in totals:
            totals[rep] = {"total": 0, "jobs": 0}
        totals[rep]["total"] += sale["amount"]
        totals[rep]["jobs"] += 1
    return totals


def build_leaderboard_message(rep_totals=None):
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")
    if rep_totals is None:
        rep_totals = get_rep_totals()

    if not rep_totals:
        return f"""📊 **CVC LEADERBOARD — {today}**
━━━━━━━━━━━━━━━━━━━━━━
Board is empty. First sale gets 🩸 First Blood!
Let's get moving. 💪
━━━━━━━━━━━━━━━━━━━━━━"""

    sorted_reps = sorted(rep_totals.items(), key=lambda x: x[1]["total"], reverse=True)
    team_total = sum(v["total"] for v in rep_totals.values())
    team_deals = sum(v["jobs"] for v in rep_totals.values())
    medals = ["🥇", "🥈", "🥉"]

    board = f"📊 **CVC LEADERBOARD — {today}**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for i, (rep, data) in enumerate(sorted_reps):
        medal = medals[i] if i < 3 else "▪️"
        board += f"{medal} **{rep}** — ${data['total']:.0f} ({data['jobs']} job{'s' if data['jobs'] != 1 else ''})\n"

    board += f"━━━━━━━━━━━━━━━━━━━━━━\n"
    board += f"💰 **Team Total: ${team_total:.0f}** | 📋 **{team_deals} deals**\n"
    board += "\nKeep closing. Medicine Hat isn't gonna clean itself. 💪"
    return board


def build_bonus_message():
    today = datetime.now(MOUNTAIN).strftime("%A")
    bonuses = CORE_BONUSES + daily_creative_bonuses

    msg = f"🎁 **TODAY'S BONUSES — {today}**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for b in bonuses:
        msg += f"{b['emoji']} **{b['name'].title()}** — {b['desc']} → {b['prize']}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\nLet's get it. 🚀"
    return msg


def post_sale_update(sale):
    rep = sale["rep"]
    customer = sale["customer"]
    amount = sale["amount"]
    neighborhood = sale.get("neighborhood", "")
    time_str = sale.get("time", datetime.now(MOUNTAIN).strftime("%-I:%M %p"))

    rep_totals = get_rep_totals()
    rep_data = rep_totals.get(rep, {"total": 0, "jobs": 0})
    team_total = sum(v["total"] for v in rep_totals.values())
    team_deals = sum(v["jobs"] for v in rep_totals.values())

    msg = f"""💥 **SALE CLOSED — {time_str}**
━━━━━━━━━━━━━━━━━━━━━━
👤 Customer: **{customer}**
📍 Location: **{neighborhood if neighborhood else 'Medicine Hat'}**
💼 Salesman: **{rep}**
💵 Job Total: **${amount:.0f}**
━━━━━━━━━━━━━━━━━━━━━━
📈 {rep}'s day: **${rep_data['total']:.0f}** ({rep_data['jobs']} job{'s' if rep_data['jobs'] != 1 else ''})
💰 Team: **${team_total:.0f}** | **{team_deals} deals today**"""

    if neighborhood:
        msg += f"\n\n🗺️ *{neighborhood} is open — get in there!*"

    send_discord_message(msg)


def build_eod_report():
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")
    sales_data = get_homebase_sales()
    rep_totals = get_rep_totals(sales_data)

    if not rep_totals:
        send_discord_message(f"📊 **EOD SUMMARY — {today}**\nNo sales logged today. Tomorrow we go harder. 💪")
        return

    sorted_reps = sorted(rep_totals.items(), key=lambda x: x[1]["total"], reverse=True)
    team_total = sum(v["total"] for v in rep_totals.values())
    team_deals = sum(v["jobs"] for v in rep_totals.values())

    first_blood = sales_data[0]["rep"] if sales_data else None
    big_ticket_rep = sorted_reps[0][0] if sorted_reps else None
    big_ticket_amt = sorted_reps[0][1]["total"] if sorted_reps else 0
    most_deals_rep = max(rep_totals.items(), key=lambda x: x[1]["jobs"])[0] if rep_totals else None
    most_deals_count = max(rep_totals.items(), key=lambda x: x[1]["jobs"])[1]["jobs"] if rep_totals else 0
    high_rollers = [rep for rep, data in rep_totals.items() if data["total"] >= 1000]
    team_goal_hit = team_deals >= 10

    medals = ["🥇", "🥈", "🥉"]
    msg = f"🏆 **END OF DAY REPORT — {today}**\n━━━━━━━━━━━━━━━━━━━━━━\n📊 **FINAL LEADERBOARD**\n"

    for i, (rep, data) in enumerate(sorted_reps):
        medal = medals[i] if i < 3 else "▪️"
        msg += f"{medal} **{rep}** — ${data['total']:.0f} ({data['jobs']} job{'s' if data['jobs'] != 1 else ''})\n"

    msg += f"\n💰 **Team Total: ${team_total:.0f}** | 📋 **{team_deals} deals**\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n🏅 **REWARD WINNERS**\n"

    if first_blood:
        msg += f"🩸 **First Blood** → {first_blood} — Tim Hortons on Ryley\n"
    if big_ticket_rep:
        msg += f"🎯 **Big Ticket** → {big_ticket_rep} (${big_ticket_amt:.0f}) — $20 bonus\n"
    if most_deals_rep:
        msg += f"🔥 **Most Deals** → {most_deals_rep} ({most_deals_count} jobs) — $20 bonus\n"
    for rep in high_rollers:
        msg += f"🍽️ **High Roller** → {rep} (${rep_totals[rep]['total']:.0f}) — Free dinner on CVC\n"
    if team_goal_hit:
        msg += f"🏆 **TEAM GOAL HIT** → {team_deals} deals! $10 bonus for everyone!\n"

    msg += "━━━━━━━━━━━━━━━━━━━━━━\nGood work today. Rest up and let's run it back tomorrow. 🚀"
    send_discord_message(msg)
    daily_sales_log.clear()


def morning_post():
    generate_creative_bonuses()
    send_discord_message(build_leaderboard_message())
    send_discord_message(build_bonus_message())


scheduler = BackgroundScheduler(timezone=MOUNTAIN)
scheduler.add_job(morning_post, CronTrigger(hour=8, minute=0, timezone=MOUNTAIN), id="morning")
scheduler.add_job(build_eod_report, CronTrigger(hour=21, minute=0, timezone=MOUNTAIN), id="eod")
scheduler.start()


@app.route("/")
def index():
    return jsonify({"status": "Leo - CVC Sales Manager is running ✅"})


@app.route("/add-sale", methods=["POST"])
def add_sale():
    data = request.json
    rep = data.get("rep")
    customer = data.get("customer", "Customer")
    amount = float(data.get("amount", 0))
    neighborhood = data.get("neighborhood", "")

    if not rep or not amount:
        return jsonify({"error": "Missing rep or amount"}), 400

    sale = {
        "rep": rep,
        "customer": customer,
        "amount": amount,
        "neighborhood": neighborhood,
        "time": datetime.now(MOUNTAIN).strftime("%-I:%M %p")
    }
    daily_sales_log.append(sale)
    post_sale_update(sale)
    return jsonify({"status": f"Sale logged — {rep} closed ${amount} with {customer}"})


@app.route("/leaderboard")
def leaderboard():
    send_discord_message(build_leaderboard_message())
    return jsonify({"status": "Leaderboard posted"})


@app.route("/eod")
def eod():
    build_eod_report()
    return jsonify({"status": "EOD report posted"})


@app.route("/test-bonuses")
def test_bonuses():
    generate_creative_bonuses()
    send_discord_message(build_bonus_message())
    return jsonify({"status": "Bonus card posted", "creative_bonuses": daily_creative_bonuses})


@app.route("/test-leaderboard")
def test_leaderboard():
    global daily_sales_log
    daily_sales_log = [
        {"rep": "Jared", "customer": "Mike Johnson", "amount": 280, "neighborhood": "Ross Glen", "time": "10:15 AM"},
        {"rep": "Jared", "customer": "Tom Williams", "amount": 140, "neighborhood": "Ross Glen", "time": "1:45 PM"},
        {"rep": "Jared", "customer": "Dave Martin", "amount": 175, "neighborhood": "Crescent Heights", "time": "3:10 PM"},
    ]
    send_discord_message(build_leaderboard_message())
    return jsonify({"status": "Test leaderboard posted"})


@app.route("/test-sale")
def test_sale():
    sale = {
        "rep": "Jared",
        "customer": "Mike Johnson",
        "amount": 280,
        "neighborhood": "Ross Glen",
        "time": datetime.now(MOUNTAIN).strftime("%-I:%M %p")
    }
    daily_sales_log.append(sale)
    post_sale_update(sale)
    return jsonify({"status": "Test sale posted"})


@app.route("/test-eod")
def test_eod():
    global daily_sales_log
    daily_sales_log = [
        {"rep": "Jared", "customer": "Mike Johnson", "amount": 580, "neighborhood": "Ross Glen", "time": "10:15 AM"},
        {"rep": "Jared", "customer": "Tom Williams", "amount": 240, "neighborhood": "Ross Glen", "time": "1:45 PM"},
        {"rep": "Jared", "customer": "Dave Martin", "amount": 195, "neighborhood": "Crescent Heights", "time": "3:10 PM"},
    ]
    build_eod_report()
    return jsonify({"status": "EOD test posted"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001)
