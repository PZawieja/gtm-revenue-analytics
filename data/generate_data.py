"""
Synthetic SaaS revenue data generator.

Produces three CSV files in dbt/seeds/:
  accounts.csv          — 100 B2B accounts (Salesforce-style)
  subscriptions.csv     — current subscription state per account
  subscription_events.csv — the event log that drives MRR calculations

The event log is the canonical source of truth. Every revenue motion
(new business, expansion, contraction, churn, reactivation) is an event.
This mirrors how Chargebee and Stripe emit webhook events in production.

Usage:
    python data/generate_data.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
random.seed(SEED)

START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 12, 31)
NUM_ACCOUNTS = 100

PLANS = [
    {"plan_id": "starter",    "plan_name": "Starter",    "mrr": 199},
    {"plan_id": "growth",     "plan_name": "Growth",     "mrr": 499},
    {"plan_id": "pro",        "plan_name": "Pro",        "mrr": 999},
    {"plan_id": "enterprise", "plan_name": "Enterprise", "mrr": 2499},
]

INDUSTRIES = ["SaaS", "FinTech", "eCommerce", "HealthTech", "EdTech", "Logistics", "HR Tech"]
COUNTRIES = ["PL", "PL", "PL", "DE", "NL", "UK", "CZ", "SE"]  # weighted toward Poland
SIZE_BANDS = ["1-10", "11-50", "51-200", "201-500", "501+"]
OWNERS = ["owner_01", "owner_02", "owner_03", "owner_04"]

SEEDS_DIR = Path(__file__).parent.parent / "dbt" / "seeds"


def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def first_of_month(d: date) -> date:
    return d.replace(day=1)


def add_months(d: date, n: int) -> date:
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1
    return d.replace(year=year, month=month, day=1)


def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def generate_accounts() -> list[dict]:
    accounts = []
    for i in range(1, NUM_ACCOUNTS + 1):
        accounts.append({
            "account_id": f"acc_{i:03d}",
            "account_name": f"Company {i:03d}",
            "industry": random.choice(INDUSTRIES),
            "country": random.choice(COUNTRIES),
            "company_size_band": random.choice(SIZE_BANDS),
            "owner_id": random.choice(OWNERS),
            "created_at": random_date(date(2023, 1, 1), date(2024, 6, 30)).isoformat(),
        })
    return accounts


def generate_events(accounts: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Simulate subscription lifecycle for each account over 24 months.
    Returns (subscriptions, subscription_events).
    """
    events = []
    subscriptions = []
    event_seq = 1

    for acc in accounts:
        account_id = acc["account_id"]
        sub_id = f"sub_{account_id}"

        # Each account starts on a random date in the first 12 months
        start_date = random_date(START_DATE, add_months(START_DATE, 12))
        start_month = first_of_month(start_date)
        plan = random.choice(PLANS)
        current_mrr = plan["mrr"]
        current_plan = plan["plan_id"]
        current_status = "active"
        last_cancelled_month = None

        # Emit subscription_created event
        events.append({
            "event_id": f"evt_{event_seq:05d}",
            "subscription_id": sub_id,
            "account_id": account_id,
            "event_type": "subscription_created",
            "old_mrr": 0,
            "new_mrr": current_mrr,
            "plan_id": current_plan,
            "effective_date": start_month.isoformat(),
        })
        event_seq += 1

        # Walk through each subsequent month until END_DATE
        cursor = add_months(start_month, 1)
        while cursor <= first_of_month(END_DATE):
            if current_status == "active":
                roll = random.random()

                if roll < 0.03:
                    # Churn
                    events.append({
                        "event_id": f"evt_{event_seq:05d}",
                        "subscription_id": sub_id,
                        "account_id": account_id,
                        "event_type": "subscription_cancelled",
                        "old_mrr": current_mrr,
                        "new_mrr": 0,
                        "plan_id": current_plan,
                        "effective_date": cursor.isoformat(),
                    })
                    event_seq += 1
                    current_mrr = 0
                    current_status = "cancelled"
                    last_cancelled_month = cursor

                elif roll < 0.08:
                    # Expansion: upgrade to a higher plan
                    higher_plans = [p for p in PLANS if p["mrr"] > current_mrr]
                    if higher_plans:
                        new_plan = random.choice(higher_plans)
                        events.append({
                            "event_id": f"evt_{event_seq:05d}",
                            "subscription_id": sub_id,
                            "account_id": account_id,
                            "event_type": "subscription_changed",
                            "old_mrr": current_mrr,
                            "new_mrr": new_plan["mrr"],
                            "plan_id": new_plan["plan_id"],
                            "effective_date": cursor.isoformat(),
                        })
                        event_seq += 1
                        current_mrr = new_plan["mrr"]
                        current_plan = new_plan["plan_id"]

                elif roll < 0.11:
                    # Contraction: downgrade to a lower plan
                    lower_plans = [p for p in PLANS if p["mrr"] < current_mrr]
                    if lower_plans:
                        new_plan = random.choice(lower_plans)
                        events.append({
                            "event_id": f"evt_{event_seq:05d}",
                            "subscription_id": sub_id,
                            "account_id": account_id,
                            "event_type": "subscription_changed",
                            "old_mrr": current_mrr,
                            "new_mrr": new_plan["mrr"],
                            "plan_id": new_plan["plan_id"],
                            "effective_date": cursor.isoformat(),
                        })
                        event_seq += 1
                        current_mrr = new_plan["mrr"]
                        current_plan = new_plan["plan_id"]

                # else: no change this month

            elif current_status == "cancelled":
                # Reactivation: 8% chance per month, but only after ≥1 month cooling-off period.
                # The 1-month minimum prevents same-month churn+reactivation in the generator
                # (which is a valid real-world scenario, but keeping it clean for demo purposes).
                months_since_churn = months_between(last_cancelled_month, cursor)
                if months_since_churn >= 1 and random.random() < 0.08:
                    plan = random.choice(PLANS)
                    events.append({
                        "event_id": f"evt_{event_seq:05d}",
                        "subscription_id": sub_id,
                        "account_id": account_id,
                        "event_type": "subscription_reactivated",
                        "old_mrr": 0,
                        "new_mrr": plan["mrr"],
                        "plan_id": plan["plan_id"],
                        "effective_date": cursor.isoformat(),
                    })
                    event_seq += 1
                    current_mrr = plan["mrr"]
                    current_plan = plan["plan_id"]
                    current_status = "active"

            cursor = add_months(cursor, 1)

        # Final subscription state
        subscriptions.append({
            "subscription_id": sub_id,
            "account_id": account_id,
            "plan_id": current_plan,
            "status": current_status,
            "mrr": current_mrr,
            "started_at": start_month.isoformat(),
            "updated_at": first_of_month(END_DATE).isoformat(),
        })

    return subscriptions, events


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {len(rows):,} rows → {path}")


def main() -> None:
    print("Generating synthetic SaaS revenue data...")

    accounts = generate_accounts()
    subscriptions, events = generate_events(accounts)

    write_csv(SEEDS_DIR / "accounts.csv", accounts)
    write_csv(SEEDS_DIR / "subscriptions.csv", subscriptions)
    write_csv(SEEDS_DIR / "subscription_events.csv", events)

    print(f"\nSummary:")
    print(f"  {len(accounts)} accounts")
    print(f"  {len(subscriptions)} subscriptions")
    print(f"  {len(events)} events")

    active = sum(1 for s in subscriptions if s["status"] == "active")
    ending_mrr = sum(s["mrr"] for s in subscriptions)
    print(f"  {active} active at end of period")
    print(f"  ending MRR: ${ending_mrr:,}")


if __name__ == "__main__":
    main()
