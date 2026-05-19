"""
Leo - CVC Sales Manager Agent
------------------------------
Runs scheduled jobs:
  1. Posts daily leaderboard to Discord #salesmen-cvc at 8 AM Mountain Time
  2. Posts daily bonus graphic description at 8 AM Mountain Time
  3. Allows manual sale entry via /add-sale endpoint

Required environment variables (add to Vercel):
  DISCORD_BOT_TOKEN      - Your Discord bot token
  DISCORD_CHANNEL_ID     - The #salesmen-cvc channel ID
  HOMEBASE_API_KEY       - Your Homebase 360 API key
  ANTHROPIC_API_KEY      - Your Claude API key
"""

import os
import requests
import pytz
import anthropic
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, jsonify, request

app = Flask(__name__)
MOUNTAIN = pytz.timezone("America/Edmonton")

# Sales data stored in memory (resets daily)
daily_sales = {}

REWARDS = {
    "first_blood": {"name": "🩸 First Blood", "desc": "First sale of the day", "prize": "Tim Hortons on Ryley"},
    "big_ticket": {"name": "🎯 Big Ticket", "desc": "Highest single job value today", "prize": "$30 dinner on CVC"},
    "hot_streak": {"name": "🔥 Hot Streak", "desc": "3+ sales in one day", "prize": "$30 dinner on CVC"},
    "team_goal": {"name": "🏆 Team Goal", "desc": "Team hits $2000 in a day", "prize": "Team dinner on Ryley"},
}


def get_discord_headers():
    return {
        "Authorization": f"Bot {os.environ.get('DISCORD_BOT_TOKEN')}",
        "Content-Type": "application/json"
    }


def send_discord_message(content):
    channel_id = os.environ.get("DISCORD_CHANNEL_ID")
    response = requests.post(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        headers=get_discord_headers(),
        json={"content": content}
    )
    if response.status_code == 200:
        print("✅ Discord message sent")
        return True
    print(f"❌ Discord error: {response.status_code} {response.text}")
    return False


def get_homebase_sales():
    """Pull today's completed jobs from Homebase 360."""
    api_key = os.environ.get("HOMEBASE_API_KEY")
    if not api_key:
        print("No Homebase API key — using manual sales data")
        return daily_sales

    try:
        today = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
        response = requests.get(
            "https://app.joinhomebase.com/api/v1/jobs",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"date": today, "status": "completed"}
        )
        if response.status_code == 200:
            data = response.json()
            sales = {}
            for job in data.get("jobs", []):
                rep = job.get("assigned_to", "Unknown")
                amount = float(job.get("total", 0))
                if rep not in sales:
                    sales[rep] = {"total": 0, "jobs": 0}
                sales[rep]["total"] += amount
                sales[rep]["jobs"] += 1
            return sales
        else:
            print(f"Homebase error: {response.status_code}")
            return daily_sales
    except Exception as e:
        print(f"Homebase connection error: {e}")
        return daily_sales


def build_leaderboard_message(sales_data):
    """Build the leaderboard text message."""
    today = datetime.now(MOUNTAIN).strftime("%A, %B %d")

    if not sales_data:
        return f"""📊 **CVC LEADERBOARD — {today}**
━━━━━━━━━━━━━━━━━━━━━━
No sales logged yet today.
First one on the board gets 🩸 **First Blood**!
Get out there and make it happen. 💪
━━━━━━━━━━━━━━━━━━━━━━"""

    sorted_reps = sorted(sales_data.items(), key=lambda x: x[1]["total"], reverse=True)
    total_revenue = sum(v["total"] for v in sales_data.values())

    medals = ["🥇", "🥈", "🥉"]
    board = f"📊 **CVC LEADERBOARD — {today}**\n━━━━━━━━━━━━━━━━━━━━━━\n"

    for i, (rep, data) in enumerate(sorted_reps):
        medal = medals[i] if i < 3 else "▪️"
        board += f"{medal} **{rep}** — ${data['total']:.0f} ({data['jobs']} job{'s' if data['jobs'] != 1 else ''})\n"

    board += f"━━━━━━━━━━━━━━━━━━━━━━\n💰 **Team Total: ${total_revenue:.0f}**\n"

    rewards_earned = []
    if sorted_reps:
        top_rep = sorted_reps[0][0]
        top_amount = sorted_reps[0][1]["total"]
        rewards_earned.append(f"🎯 **Big Ticket** → {top_rep} (${top_amount:.0f})")

    for rep, data in sales_data.items():
        if data["jobs"] >= 3:
            rewards_earned.append(f"🔥 **Hot Streak** → {rep} ({data['jobs']} sales!)")

    if total_revenue >= 2000:
        rewards_earned.append("🏆 **TEAM GOAL HIT** → Dinner on Ryley tonight!")

    if rewards_earned:
        board += "\n🏅 **REWARDS EARNED TODAY:**\n" + "\n".join(rewards_earned)

    board += "\n\nKeep closing. Medicine Hat isn't gonna clean itself. 💪"
    return board


def post_daily_update():
    """Pull sales data and post leaderboard + bonus info to Discord."""
    sales_data = get_homebase_sales()
    leaderboard = build_leaderboard_message(sales_data)
    send_discord_message(leaderboard)

    today = datetime.now(MOUNTAIN).strftime("%A")
    bonus_msg = f"""🎁 **TODAY'S BONUSES — {today}**
━━━━━━━━━━━━━━━━━━━━━━
🩸 **First Blood** — First sale of the day → Tim Hortons on Ryley
🎯 **Big Ticket** — Highest single job → $30 dinner on CVC
🔥 **Hot Streak** — 3+ sales today → $30 dinner on CVC
🏆 **Team Goal** — Team hits $2,000 → Team dinner on Ryley
━━━━━━━━━━━━━━━━━━━━━━
Let's get it. 🚀"""

    send_discord_message(bonus_msg)


def post_sale_notification(rep_name, amount, neighborhood=""):
    """Send a real-time sale notification to Discord."""
    claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    prompt = f"""Write a short hype message (2-3 sentences max) for a sales team Discord announcing that {rep_name} just closed a ${amount} job{f' in {neighborhood}' if neighborhood else ''} for Clearest View Cleaners window cleaning company in Medicine Hat Alberta. Make it energetic, use their name, mention the neighborhood if provided so teammates can name-drop it for nearby sales. Keep it punchy."""
    msg = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    hype = msg.content[0].text
    send_discord_message(f"💥 **SALE CLOSED!**\n{hype}")


scheduler = BackgroundScheduler(timezone=MOUNTAIN)
scheduler.add_job(post_daily_update, CronTrigger(hour=8, minute=0, timezone=MOUNTAIN), id="daily_leaderboard")
scheduler.start()


@app.route("/")
def index():
    return jsonify({"status": "Leo - CVC Sales Manager is running ✅"})


@app.route("/leaderboard")
def leaderboard():
    post_daily_update()
    return jsonify({"status": "Leaderboard posted to Discord"})


@app.route("/add-sale", methods=["POST"])
def add_sale():
    """
    Log a sale manually.
    POST: { "rep": "Jared", "amount": 250, "neighborhood": "Ross Glen" }
    """
    data = request.json
    rep = data.get("rep")
    amount = float(data.get("amount", 0))
    neighborhood = data.get("neighborhood", "")

    if not rep or not amount:
        return jsonify({"error": "Missing rep or amount"}), 400

    if rep not in daily_sales:
        daily_sales[rep] = {"total": 0, "jobs": 0}
    daily_sales[rep]["total"] += amount
    daily_sales[rep]["jobs"] += 1

    post_sale_notification(rep, amount, neighborhood)
    return jsonify({"status": f"Sale logged for {rep}: ${amount}"})


@app.route("/test-leaderboard")
def test_leaderboard():
    """Test with dummy data."""
    test_data = {
        "Jared": {"total": 480, "jobs": 3},
        "Kael": {"total": 320, "jobs": 2},
        "Braxton": {"total": 150, "jobs": 1},
    }
    msg = build_leaderboard_message(test_data)
    send_discord_message(msg)
    return jsonify({"status": "Test leaderboard posted"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001)
