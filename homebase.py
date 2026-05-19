"""
Homebase 360 API Integration
Base URL: https://us-central1-homebase-360.cloudfunctions.net/api/v1
Auth: x-api-key header
"""

import os, requests, pytz
from datetime import datetime, timedelta

MOUNTAIN = pytz.timezone("America/Edmonton")
HB_BASE = "https://us-central1-homebase-360.cloudfunctions.net/api/v1"
MAX_HOURS = 7
AVG_JOB_HOURS = 2.0


def hb_headers():
    return {
        "x-api-key": os.environ.get("HOMEBASE_API_KEY"),
        "Content-Type": "application/json"
    }


def get_jobs_for_date(date):
    """Get all jobs for a specific date."""
    start = date.strftime("%Y-%m-%dT00:00:00Z")
    end = date.strftime("%Y-%m-%dT23:59:59Z")
    try:
        r = requests.get(
            f"{HB_BASE}/jobs",
            headers=hb_headers(),
            params={"startDate": start, "endDate": end, "limit": 100}
        )
        if r.status_code == 200:
            return r.json().get("data", [])
        print(f"Homebase jobs error {r.status_code}: {r.text}")
        return []
    except Exception as e:
        print(f"Homebase request error: {e}")
        return []


def get_todays_jobs():
    """Get today's completed jobs for the leaderboard."""
    today = datetime.now(MOUNTAIN)
    return get_jobs_for_date(today)


def get_schedule_availability():
    """Check availability for next 2 weeks Mon-Fri."""
    today = datetime.now(MOUNTAIN)
    available = []
    full = []

    for i in range(14):
        day = today + timedelta(days=i)
        if day.weekday() >= 5:  # skip weekends
            continue

        jobs = get_jobs_for_date(day)
        day_label = day.strftime("%A, %B %d")

        # Calculate booked hours from start/end times
        booked_hours = 0
        for job in jobs:
            try:
                start_str = job.get("start", "")
                end_str = job.get("end", "")
                if start_str and end_str:
                    start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    hours = (end_dt - start_dt).total_seconds() / 3600
                    booked_hours += hours
                else:
                    booked_hours += AVG_JOB_HOURS
            except:
                booked_hours += AVG_JOB_HOURS

        remaining = MAX_HOURS - booked_hours
        job_count = len(jobs)

        if remaining >= AVG_JOB_HOURS:
            available.append(f"✅ **{day_label}** — {remaining:.0f}h open ({job_count} job{'s' if job_count != 1 else ''} booked)")
        else:
            full.append(f"🔴 **{day_label}** — Fully booked ({job_count} jobs)")

    msg = "📅 **CVC BOOKING AVAILABILITY**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "\n".join(available[:7]) if available else "All days are fully booked right now!"
    if full:
        msg += "\n\n" + "\n".join(full[:3])
    msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n📞 clearestviewcleaners.com | (403) 878-6670"
    return msg


def get_todays_sales():
    """Get today's jobs formatted as sales data for the leaderboard."""
    jobs = get_todays_jobs()
    sales = []
    for job in jobs:
        # Extract rep name from assignedTo or technician field
        rep = "Unknown"
        assigned = job.get("assignedTo", [])
        if assigned and isinstance(assigned, list):
            rep = assigned[0] if isinstance(assigned[0], str) else assigned[0].get("name", "Unknown")
        elif isinstance(assigned, str):
            rep = assigned

        # Extract customer name
        customer = "Customer"
        cust = job.get("customer", {})
        if isinstance(cust, dict):
            fname = cust.get("firstName", "")
            lname = cust.get("lastName", "")
            customer = f"{fname} {lname}".strip() or "Customer"
        elif isinstance(cust, str):
            customer = cust

        # Extract total amount from line items
        amount = 0
        line_items = job.get("lineItems", [])
        for item in line_items:
            try:
                qty = float(item.get("quantity", 1))
                price = float(item.get("unitPrice", 0))
                amount += qty * price
            except:
                pass

        # Extract neighborhood/address
        neighborhood = ""
        addr = job.get("address", "") or job.get("serviceAddress", "")
        if isinstance(addr, dict):
            neighborhood = addr.get("city", "") or addr.get("street", "")
        elif isinstance(addr, str):
            neighborhood = addr

        sales.append({
            "rep": rep,
            "customer": customer,
            "amount": amount,
            "neighborhood": neighborhood,
            "time": job.get("start", "")[:16].replace("T", " ") if job.get("start") else ""
        })

    return sales
