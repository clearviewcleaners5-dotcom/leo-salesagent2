"""
Leo - CVC Sales Manager Agent
------------------------------
Schedule:
  8:00 AM  - Daily leaderboard + bonus announcement
  After every sale (via /add-sale) - Real-time sale update
  9:00 PM  - End of day rewards summary graphic (HTML image via Discord embed)

Environment variables needed in Vercel:
  DISCORD_BOT_TOKEN
  DISCORD_CHANNEL_ID
  HOMEBASE_API_KEY
  ANTHROPIC_API_KEY
"""

import os
import io
import base64
import requests
import pytz
import anthropic
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, jsonify, request

app = Flask(__name__)
MOUNTAIN = pytz.timezone("America/Edmonton")

# In-memory sales log for the day
# Each entry: { "rep": "Jared", "customer": "John Smith", "amount": 250, "neighborhood": "Ross Glen", "time": "2:34 PM" }
daily_sales_log = []

REWARDS = {
    "first_blood": {"name": "🩸 First Blood", "desc": "First sale of the day", "prize": "Tim Hortons on Ryley"},
    "big_ticket": {"name": "🎯 Big Ticket", "desc": "Highest single job", "prize": "$30 dinner on CVC"},
    "hot_streak": {"name": "🔥 Hot Streak", "desc": "3+ sales in one day", "prize": "$30 dinner on CVC"},
    "team_goal": {"name": "🏆 Team Goal", "desc": "Team hits $2,000", "prize": "Team dinner on Ryley"},
}

CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "1230709942265188352")


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


def get_rep_totals():
    """Aggregate daily_sales_log by rep."""
    totals = {}
    for sale in daily_sales_log:
        rep = sale["rep"]
        if rep not in totals:
            totals[rep] = {"total": 0, "jobs": 0}
        totals[rep]["total"] += sale["amount"]
        totals[rep]["jobs"] += 1
    return totals


def build_leaderboard_message():
    """Morning leaderboard — shows current standings."""
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")
    rep_totals = get_rep_totals()

    if not rep_totals:
        return f"""📊 **CVC LEADERBOARD — {today}**
━━━━━━━━━━━━━━━━━━━━━━
Board is empty. First sale gets 🩸 First Blood!
Let's get moving. 💪
━━━━━━━━━━━━━━━━━━━━━━"""

    sorted_reps = sorted(rep_totals.items(), key=lambda x: x[1]["total"], reverse=True)
    team_total = sum(v["total"] for v in rep_totals.values())
    medals = ["🥇", "🥈", "🥉"]

    board = f"📊 **CVC LEADERBOARD — {today}**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for i, (rep, data) in enumerate(sorted_reps):
        medal = medals[i] if i < 3 else "▪️"
        board += f"{medal} **{rep}** — ${data['total']:.0f} ({data['jobs']} job{'s' if data['jobs'] != 1 else ''})\n"

    board += f"━━━━━━━━━━━━━━━━━━━━━━\n💰 **Team Total: ${team_total:.0f}**\n"
    board += "\nKeep closing. Medicine Hat isn't gonna clean itself. 💪"
    return board


def build_bonus_message():
    today = datetime.now(MOUNTAIN).strftime("%A")
    return f"""🎁 **TODAY'S BONUSES — {today}**
━━━━━━━━━━━━━━━━━━━━━━
🩸 **First Blood** — First sale of the day → Tim Hortons on Ryley
🎯 **Big Ticket** — Highest single job → $30 dinner on CVC
🔥 **Hot Streak** — 3+ sales today → $30 dinner on CVC
🏆 **Team Goal** — Team hits $2,000 → Team dinner on Ryley
━━━━━━━━━━━━━━━━━━━━━━
Let's get it. 🚀"""


def post_sale_update(sale):
    """Real-time sale notification after every close."""
    rep = sale["rep"]
    customer = sale["customer"]
    amount = sale["amount"]
    neighborhood = sale.get("neighborhood", "")
    time_str = sale["time"]

    rep_totals = get_rep_totals()
    rep_today = rep_totals.get(rep, {})
    rep_total = rep_today.get("total", 0)
    rep_jobs = rep_today.get("jobs", 0)

    team_total = sum(v["total"] for v in rep_totals.values())

    location_line = f" in **{neighborhood}**" if neighborhood else ""
    msg = f"""💥 **SALE CLOSED — {time_str}**
━━━━━━━━━━━━━━━━━━━━━━
👤 Customer: **{customer}**
📍 Location:{location_line if neighborhood else " Medicine Hat"}
💼 Salesman: **{rep}**
💵 Job Total: **${amount:.0f}**
━━━━━━━━━━━━━━━━━━━━━━
📈 {rep}'s day: **${rep_total:.0f}** ({rep_jobs} job{'s' if rep_jobs != 1 else ''})
💰 Team total: **${team_total:.0f}**"""

    if neighborhood:
        msg += f"\n\n🗺️ *{neighborhood} is open — get in there!*"

    send_discord_message(msg)


def build_eod_rewards_graphic():
    """Generate end-of-day rewards summary as a clean Discord message."""
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")
    rep_totals = get_rep_totals()

    if not rep_totals:
        send_discord_message(f"📊 **EOD SUMMARY — {today}**\nNo sales logged today. Tomorrow we go harder. 💪")
        return

    sorted_reps = sorted(rep_totals.items(), key=lambda x: x[1]["total"], reverse=True)
    team_total = sum(v["total"] for v in rep_totals.values())

    # Determine winners
    first_blood_winner = daily_sales_log[0]["rep"] if daily_sales_log else None
    big_ticket_winner = sorted_reps[0][0] if sorted_reps else None
    big_ticket_amount = sorted_reps[0][1]["total"] if sorted_reps else 0
    hot_streak_winners = [rep for rep, data in rep_totals.items() if data["jobs"] >= 3]
    team_goal_hit = team_total >= 2000

    # Build the summary
    msg = f"""🏆 **END OF DAY REPORT — {today}**
━━━━━━━━━━━━━━━━━━━━━━
📊 **FINAL LEADERBOARD**\n"""

    medals = ["🥇", "🥈", "🥉"]
    for i, (rep, data) in enumerate(sorted_reps):
        medal = medals[i] if i < 3 else "▪️"
        msg += f"{medal} **{rep}** — ${data['total']:.0f} ({data['jobs']} job{'s' if data['jobs'] != 1 else ''})\n"

    msg += f"\n💰 **Team Total: ${team_total:.0f}**\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "🏅 **TODAY'S REWARD WINNERS**\n"

    if first_blood_winner:
        msg += f"🩸 **First Blood** → {first_blood_winner} — Tim Hortons on Ryley\n"
    if big_ticket_winner:
        msg += f"🎯 **Big Ticket** → {big_ticket_winner} (${big_ticket_amount:.0f}) — $30 dinner on CVC\n"
    if hot_streak_winners:
        for winner in hot_streak_winners:
            msg += f"🔥 **Hot Streak** → {winner} — $30 dinner on CVC\n"
    if team_goal_hit:
        msg += f"🏆 **TEAM GOAL HIT** → Everyone eats — Team dinner on Ryley!\n"

    if not any([first_blood_winner, big_ticket_winner, hot_streak_winners, team_goal_hit]):
        msg += "No rewards earned today. Tomorrow we come back stronger.\n"

    msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "Good work today. Rest up and let's run it back tomorrow. 🚀"

    send_discord_message(msg)

    # Reset daily log after EOD report
    daily_sales_log.clear()


def morning_post():
    send_discord_message(build_leaderboard_message())
    send_discord_message(build_bonus_message())


# ── SCHEDULER ────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone=MOUNTAIN)
scheduler.add_job(morning_post, CronTrigger(hour=8, minute=0, timezone=MOUNTAIN), id="morning")
scheduler.add_job(build_eod_rewards_graphic, CronTrigger(hour=21, minute=0, timezone=MOUNTAIN), id="eod")
scheduler.start()


# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return jsonify({"status": "Leo - CVC Sales Manager is running ✅"})


@app.route("/add-sale", methods=["POST"])
def add_sale():
    """
    Log a sale and post real-time update.
    POST: { "rep": "Jared", "customer": "Mike Johnson", "amount": 250, "neighborhood": "Ross Glen" }
    """
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
    build_eod_rewards_graphic()
    return jsonify({"status": "EOD report posted"})


@app.route("/test-leaderboard")
def test_leaderboard():
    """Test with dummy sales data."""
    global daily_sales_log
    daily_sales_log = [
        {"rep": "Jared", "customer": "Mike Johnson", "amount": 280, "neighborhood": "Ross Glen", "time": "10:15 AM"},
        {"rep": "Kael", "customer": "Sarah Patel", "amount": 195, "neighborhood": "Southridge", "time": "11:30 AM"},
        {"rep": "Jared", "customer": "Tom Williams", "amount": 140, "neighborhood": "Ross Glen", "time": "1:45 PM"},
        {"rep": "Braxton", "customer": "Linda Chen", "amount": 320, "neighborhood": "Redcliff", "time": "2:20 PM"},
        {"rep": "Jared", "customer": "Dave Martin", "amount": 175, "neighborhood": "Crescent Heights", "time": "3:10 PM"},
    ]
    send_discord_message(build_leaderboard_message())
    return jsonify({"status": "Test leaderboard posted"})


@app.route("/test-eod")
def test_eod():
    """Test EOD rewards summary."""
    global daily_sales_log
    daily_sales_log = [
        {"rep": "Jared", "customer": "Mike Johnson", "amount": 280, "neighborhood": "Ross Glen", "time": "10:15 AM"},
        {"rep": "Kael", "customer": "Sarah Patel", "amount": 195, "neighborhood": "Southridge", "time": "11:30 AM"},
        {"rep": "Jared", "customer": "Tom Williams", "amount": 140, "neighborhood": "Ross Glen", "time": "1:45 PM"},
        {"rep": "Braxton", "customer": "Linda Chen", "amount": 320, "neighborhood": "Redcliff", "time": "2:20 PM"},
        {"rep": "Jared", "customer": "Dave Martin", "amount": 175, "neighborhood": "Crescent Heights", "time": "3:10 PM"},
    ]
    build_eod_rewards_graphic()
    return jsonify({"status": "EOD test posted"})


@app.route("/test-sale")
def test_sale():
    """Test a single real-time sale notification."""
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001)
