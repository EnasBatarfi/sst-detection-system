"""Helper functions to package and (simulated) share user data with partners."""

import json
import hashlib
from datetime import datetime
from pathlib import Path

# All simulated third‑party exports live here for easy review.
SHARED_DIR = Path(__file__).resolve().parent / "shared_with_third_parties"

def _ensure_shared_dir():
    # Keep all simulated third-party exports in a single, easy-to-review folder.
    SHARED_DIR.mkdir(parents=True, exist_ok=True)

def _write_text(filename, content):
    """Append a text payload to the shared folder and return its path."""
    _ensure_shared_dir()
    path = SHARED_DIR / filename
    payload = content.strip() + "\n\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(payload)
    return str(path)


# ----------------- Privacy Summary Builder ----------------
def build_privacy_summary(user, expenses):
    """Summarize the user and recent spending for partner-ready sharing."""
    categories = {}
    total_spend = 0.0

    for e in expenses:
        amount = float(e.amount or 0)
        total_spend += amount
        categories[e.category] = categories.get(e.category, 0.0) + amount

    # Preserve provenance on income: keep the original object so owner tags survive.
    income = user.income if user.income is not None else 0.0

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
    """Simulated marketing vendor payload: segments/goals only."""
    record = {
        "user_email": summary["user_email"],
        "name": summary["name"],
        "segments": list(summary["categories"].keys()),
        "total_spend": summary["total_spend"],
        "budget_style": summary["budget_style"],
        "goals": summary["goals"],
        "vendor": "marketing_platform_v1",
    }

    sample_segments = ', '.join(record['segments']) or 'none'
    txt_lines = [
        "[Marketing Share]",
        f"Timestamp: {datetime.utcnow().isoformat()}Z",
        f"User: {record['name']} <{record['user_email']}>",
        f"Segments: {sample_segments}",
        f"Total spend: {record['total_spend']}",
        f"Budget style: {record['budget_style']}",
        f"Goals: {record['goals'] or '—'}",
        "Payload: text",
        f"Vendor: {record['vendor']}",
    ]
    txt = "\n".join(txt_lines)

    return _write_text("third_party_marketing.txt", txt)


# ----------------- Calculate Risk Score for Third Party ----------------
def third_party_scoring_client(summary):
    """Simulated risk scoring vendor payload: hashed ID plus spend ratios."""
    email = summary["user_email"]
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
        "risk_score": risk_score,
        "segments": list(summary["categories"].keys()),
        "vendor": "risk_scoring_v1",
    }

    txt_lines = [
        "[Risk Scoring Share]",
        f"Timestamp: {datetime.utcnow().isoformat()}Z",
        f"Anon ID: {record['anon_customer_id']}",
        f"Monthly spend: {record['monthly_spend']}",
        f"Risk score: {record['risk_score']}",
        f"Segments: {', '.join(record['segments']) or 'none'}",
        "Payload: text",
        f"Vendor: {record['vendor']}",
        f"Full anon ID: {record['anon_customer_id']}",
    ]
    txt = "\n".join(txt_lines)

    return _write_text("third_party_scoring.txt", txt)

