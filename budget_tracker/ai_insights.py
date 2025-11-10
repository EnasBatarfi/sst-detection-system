import os
from dotenv import load_dotenv
from openai import OpenAI
import json

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY is not set in your environment!")

client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

def generate_ai_insight(expenses, income, budget_style="Balanced", goals=""):
    """
    Generate structured AI insights in JSON format:
    [
        {
            "title": "...",
            "problem": "...",
            "action_steps": ["...", "..."]
        },
        ...
    ]
    """
    if not expenses:
        return []

    # Summarize spending
    summary = {}
    total_spent = 0
    for e in expenses:
        summary[e.category] = summary.get(e.category, 0) + e.amount
        total_spent += e.amount

    spent_pct = (total_spent / income * 100) if income > 0 else 0

    # Prompt Groq LLM
    prompt = f"""
You are a helpful financial assistant.

User data:
- Income: ${income:.2f}
- Total Spent: ${total_spent:.2f} ({spent_pct:.1f}% of income)
- Spending Breakdown: {summary}
- Budget Style: {budget_style}
- Goal: {goals}

Return 3–5 actionable insights in **JSON array** format. Each insight must contain:
- title
- problem
- action_steps (list of 2–4 steps)
Do not include any extra text outside the JSON array.
"""

    try:
        response = client.responses.create(
            model="openai/gpt-oss-20b",
            input=prompt
        )

        output_text = response.output_text.strip()
        try:
            insights = json.loads(output_text)
        except json.JSONDecodeError:
            # fallback if AI outputs raw text
            insights = [{"title": "Insight", "problem": output_text, "action_steps": []}]
        return insights

    except Exception as e:
        print("AI Insight Error:", e)
        return [{"title": "Insight Error", "problem": "Couldn't generate insights.", "action_steps": []}]

def generate_rule_based_insight(expenses, income, budget_style="Balanced", goals=""):
    """
    Generate concise, realistic, rule-based financial insights:
    - Focus on top spending categories
    - Compare spending vs income
    - Give actionable advice based on essential vs discretionary spending
    """
    if not expenses:
        return "No spending data yet. Add some expenses to get insights!"

    # Summarize spending by category
    summary = {}
    for e in expenses:
        summary[e.category] = summary.get(e.category, 0) + e.amount

    total_spent = sum(summary.values())
    spent_pct = (total_spent / income * 100) if income > 0 else 0

    # Determine if budget exceeded
    if budget_style.lower() == "conservative":
        budget_msg = "Budget exceeded!" if spent_pct > 90 else "Budget on track."
    elif budget_style.lower() == "aggressive":
        budget_msg = "Budget exceeded!" if spent_pct > 120 else "Budget on track."
    else:
        budget_msg = "Budget exceeded!" if spent_pct > 100 else "Budget on track."

    # Identify top 2 categories
    essential_cats = ["Food", "Transport", "Bills"]
    top_cats_sorted = sorted(summary.items(), key=lambda x: x[1], reverse=True)[:2]

    # Build insight string
    insight_lines = [
        f"Total spent: ${total_spent:.0f} ({spent_pct:.0f}% of income) — {budget_msg}"
    ]

    for cat, amt in top_cats_sorted:
        cat_type = "Essential" if cat in essential_cats else "Discretionary"
        if cat_type == "Essential":
            advice = f"Review {cat} expenses to save while maintaining essentials."
        else:
            advice = f"Cut or limit {cat} spending to free up money for your goal ({goals})."
        insight_lines.append(f"{cat} ({cat_type}): ${amt:.0f}. {advice}")

    # Optional: Suggest goal focus
    if total_spent > income:
        insight_lines.append(f"Your spending exceeds your income. Consider adjusting top categories to reach your goal ({goals}).")
    else:
        insight_lines.append(f"You're within your income. Redirect some savings to your goal ({goals}).")

    return "\n".join(insight_lines)
