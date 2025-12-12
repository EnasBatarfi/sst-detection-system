"""
Comprehensive provenance regression covering propagation + sink coverage.

Sinks exercised:
  - stdout / stderr / logging
  - file writes (text, JSON, Path.write_text, json.dumps + write)
  - sockets (raw TCP), HTTP, HTTPS
  - simulated partner shares (marketing + risk scoring)

Provenance is expected to tag owners on PII (emails) and propagate through
simple string/arith operations. Outputs are written under ./output_files.
"""

import io
import json
import logging
import os
import socket
import sys
from pathlib import Path
import http.client
import requests

from dotenv import load_dotenv

# --- Paths and env setup ---
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output_files"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


load_dotenv(BASE_DIR.parent /"test_cases" / ".env")  



# Make budget_tracker importable for privacy_share
ROOT = BASE_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    from budget_tracker.privacy_share import (
        build_privacy_summary,
        third_party_marketing_client,
        third_party_scoring_client,
    )
except Exception as e:
    print("Failed to import budget_tracker modules. Ensure you run from repo root.", e)
    sys.exit(1)


# --- Data classes ---
class User:
    def __init__(self, email, age, nationality, income, name="User", budget_style="Balanced", goals=""):
        self.email = email
        self.age = age
        self.nationality = nationality
        self.income = income
        self.name = name
        self.budget_style = budget_style
        self.goals = goals


class ExpenseStub:
    def __init__(self, category, amount):
        self.category = category
        self.amount = amount
        self.description = category
        self.date = None


# --- Test helpers ---
def write_file_sinks(user, friend):
    paths = {
        "text": OUTPUT_DIR / "test_text.txt",
        "json": OUTPUT_DIR / "test_json.json",
        "json2": OUTPUT_DIR / "test_json2.json",
        "json3": OUTPUT_DIR / "test_json3.json",
        "path": OUTPUT_DIR / "test_path.txt",
        "append": OUTPUT_DIR / "test_append.log",
    }

    with paths["text"].open("w") as f:
        f.write(str(user.age))
        f.write("\nclean line")

    with paths["json"].open("w") as f:
        json.dump(user.age, f)
        json.dump("\n cleanline", f)

    with paths["json3"].open("w") as f:
        json.dump(str(user.age), f)
        json.dump("\n cleanline", f)

    with paths["json2"].open("w") as f:
        f.write(str(user.age))
        f.write("user age")

    (paths["path"]).write_text("from_path: " + str(friend.age))

    with paths["append"].open("a") as f:
        f.write(f"append age {user.age}\n")

    return paths


def failing_file_sinks(user):
    """Intentionally attempt an unsupported write to ensure failures are visible."""
    bad_path = OUTPUT_DIR / "no_such_dir" / "fail.txt"
    try:
        bad_path.write_text("should_fail " + user.email)
    except Exception:
        pass


def network_sinks(user):
    buf = io.StringIO()
    buf.write("stringio: " + str(user.age))

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.send(b"email: " + str(user.age).encode())
    except Exception:
        pass
    s.close()

    try:
        conn = http.client.HTTPConnection("example.com", 80, timeout=1)
        conn.request("GET", "/?q=" + str(user.age))
    except Exception:
        pass

    try:
        https_conn = http.client.HTTPSConnection("example.com", 443, timeout=2)
        https_conn.request("POST", "/insights", body=json.dumps({"user": user.email, "goal": user.goals}))
    except Exception:
        pass

    # Requests client (expected to be logged as http_request)
    try:
        requests.post("http://example.com/collect", data={"email": user.email}, timeout=1)
    except Exception:
        pass
    try:
        requests.post("https://example.com/metrics", json={"user": user.email, "goal": user.goals}, timeout=2)
    except Exception:
        pass
    try:
        requests.get("https://example.com/profile", params={"q": user.email}, timeout=2)
    except Exception:
        pass



def share_sinks(user, expenses):
    summary = build_privacy_summary(user, expenses)
    marketing_path = third_party_marketing_client(summary)
    scoring_path = third_party_scoring_client(summary)
    return marketing_path, scoring_path


def run():
    print("=== Provenance test: propagation and sink coverage ===")
    print(f"Using log: {os.getenv('PY_PROVENANCE_LOG_JSON')}")
    print(f"Output dir: {OUTPUT_DIR}")

    # --- Setup two users ---
    u1 = User("alice@example.com", 30, "USA", 600.5, name="Alice", budget_style="Balanced", goals="Save for trip")
    u2 = User("bob@example.com", 25, "Canada", 600.0, name="Bob", budget_style="Aggressive", goals="Pay debt")

    def helper(email):
        email = email + "  --- "
        print("Helper email:", email)

    # --- Direct attribute reads & derived ---
    print("Alice email:", u1.email)
    print("Alice age:", u1.age)
    print("Alice nationality:", u1.nationality)
    helper(u1.email)
    derived = u1.email + " -- verified"
    print("Alice email modified:", derived)
    num = 70
    print("Clean number (should stay clean):", num)
    u1.age = 999
    print("Alice age modified:", u1.age)

    # --- Multiple owner propagation ---
    combined = u1.age + u2.age
    print("Alice and Bob ages combined:", combined)
    print("Bob age:", u2.age)
    u2.nationality = "Canada" + " - North America"
    print("Bob nationality:", u2.nationality)
    income_diff = u2.income - u1.income
    print("Income difference:", income_diff)
    bob_income_sum = u2.income + 1000
    print("Bob income plus 1000:", bob_income_sum)
    bob_income_like_alice = u2.income + 0.5
    print("Bob income plus 0.5:", bob_income_like_alice)
    x = u2.age + 5
    print("Bob age modified:", x)
    combined2 = combined + 5
    print("Combined modified ages:", combined2)

    # --- File sinks ---
    write_file_sinks(u1, u2)
    failing_file_sinks(u1)

    # --- stdout/stderr/logging ---
    sys.stdout.write("stdout test: " + str(u1.age) + "\n")
    sys.stderr.write("stderr test: " + str(u1.age) + "\n")
    logging.basicConfig(level=logging.WARNING)
    logging.warning("log test: " + str(u1.age))

    # --- Network sinks ---
    network_sinks(u1)

    # --- Share flows ---
    sample_expenses = [ExpenseStub("Food", 120.0), ExpenseStub("Transport", 80.0), ExpenseStub("Entertainment", 45.5)]
    share_sinks(u1, sample_expenses)

    print("=== Done ===")


if __name__ == "__main__":
    run()
