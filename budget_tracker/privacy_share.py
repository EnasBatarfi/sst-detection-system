import json
import hashlib


# ----------------- Privacy Summary Builder ----------------
def build_privacy_summary(user, expenses):
    """Summarize user and spending for third parties."""
    categories = {}
    total_spend = 0.0

    for e in expenses:
        amount = float(e.amount or 0)
        total_spend += amount
        categories[e.category] = categories.get(e.category, 0.0) + amount

    income = float(user.income or 0.0)

    return {
        "user_email": user.email,
        "name": user.name,
        "income": income,
        "total_spend": total_spend,
        "categories": categories,
        "budget_style": user.budget_style,
        "goals": user.goals,
    }


# ----------------- Send to Third Party Marketing ----------------
def third_party_marketing_client(summary):
    """
    Simulated marketing vendor.
    Writes one JSON object per line into third_party_marketing.jsonl
    """
    record = {
        "user_email": summary["user_email"],
        "name": summary["name"],
        "segments": list(summary["categories"].keys()),
        "total_spend": summary["total_spend"],
        "budget_style": summary["budget_style"],
        "goals": summary["goals"],
        "vendor": "marketing_platform_v1",
    }

    # Convert to JSON string *explicitly* so provenance logs work
    json_str = json.dumps(record)


    # This not working 
    # with open("third_party_marketing.jsonl", "a", encoding="utf-8") as f:
    #     f.write(json_str)
    #     f.write("\n")
    # Doesn't work 
    # with open("third_party_marketing.jsonl", "a", encoding="utf-8") as f:
    #     json.dump(record, f)
    #     f.write("\n")
    # Work perfectly
    # print("Sending to third party marketing vendor:", record)


# ----------------- Calculate Risk Score for Third Party ----------------
def third_party_scoring_client(summary):
    """
    Simulated risk scoring vendor.
    Uses a hashed ID but still derived from the email.
    """
    email = summary["user_email"]
    print("Third party scoring client received email:", summary["goals"])
    anon_id = hashlib.sha256(email.encode("utf-8")).hexdigest()

    income = summary["income"]
    total = summary["total_spend"]
    if income > 0:
        ratio = total / income
        if ratio > 1.0:
            risk_score = 0.9
        elif ratio > 0.5:
            risk_score = 0.6
        else:
            risk_score = 0.2
    else:
        risk_score = 0.0

    record = {
        "anon_customer_id": anon_id,
        "monthly_spend": total,
        "income": income,
        "risk_score": risk_score,
        "segments": list(summary["categories"].keys()),
        "vendor": "risk_scoring_v1",
    }

    # json_str = json.dumps(record)

    # with open("third_party_scoring.jsonl", "a", encoding="utf-8") as f:
    #     f.write(json_str)
    #     f.write("\n")

    # with open("third_party_scoring.jsonl", "a", encoding="utf-8") as f:
    #     json.dump(record, f)
    #     f.write("\n")
    # print("Sending to third party scoring vendor:", record)
