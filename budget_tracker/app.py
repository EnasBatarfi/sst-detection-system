import os
import re
import secrets
import sys
from datetime import date, datetime, timedelta
from sqlalchemy import func

import pycountry
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.serving import WSGIRequestHandler

from ai_insights import generate_ai_insight, generate_rule_based_insight
from config import Config
from models import Expense, Income, User, db
from privacy_share import (
    build_privacy_summary,
    third_party_marketing_client,
    third_party_scoring_client,
)

load_dotenv()
# This is to ensure we are using the correct Python interpreter 
print(f">> Python Interprete Used: {sys.executable}")


app = Flask(__name__)
CATEGORIES = ["Food", "Transport", "Entertainment", "Bills", "Shopping", "Other"]

app.config.from_object(Config)
db.init_app(app)

def ensure_schema():
    """Create tables from the declared models (fresh DB expected)."""
    with app.app_context():
        db.create_all()


def get_current_user():
    """Return the logged-in user instance or None if no session user exists."""
    user_id = session.get('user_id')
    if not user_id:
        return None

    user = User.query.get(user_id)
    if user is None:
        return None

    # Central taint trigger: every time we load the user from session,
    # we force an attribute read so provenance tags this instance.
    _ = user.email

    return user

# --- CSRF protection ---
# This is basically a simplified version of Flask-WTF's CSRF protection.
# It will help prevent cross-site request forgery attacks on state-changing requests.
def _generate_csrf_token():
    token = session.get('csrf_token')
    if not token:
        token = secrets.token_hex(16)
        session['csrf_token'] = token
    return token

@app.before_request
def _csrf_protect():
    if request.method in ('POST', 'PUT', 'DELETE'):
        sent = request.form.get('_csrf')
        session_token = session.get('csrf_token')
        if not sent or not session_token or sent != session_token:
            abort(400)

app.jinja_env.globals['csrf_token'] = _generate_csrf_token

@app.route('/')
def index():
    """Landing page with links to auth."""
    return render_template('index.html', datetime=datetime)

# ---------------- Signup ----------------

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handle new user registration with basic validation."""
    currencies = [(c.alpha_3, c.name) for c in pycountry.currencies]

    form_data = {
        "name": "",
        "email": "",
        "password": "",
        "birthday": "",
        "gender": "",
        "income": "",
        "currency": "SAR",
        "budget_style": "Balanced",
        "goals": "",
        "week_start": "Monday"
    }

    errors = {}

    if request.method == 'POST':
        # Fill form data
        for key in form_data.keys():
            form_data[key] = request.form.get(key, '').strip()

        # Name
        if not form_data['name']:
            errors['name'] = "Please enter your full name."

        # Email
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', form_data['email']):
            errors['email'] = "Please enter a valid email address."
        elif User.query.filter_by(email=form_data['email'].lower()).first():
            errors['email'] = "This email is already registered."

        # Password
        password = form_data['password']
        if len(password) < 8:
            errors['password'] = "Password must be at least 8 characters long."

        # Birthday (valid and age ≥ 18)
        try:
            birthday = datetime.strptime(form_data['birthday'], '%Y-%m-%d').date()
            today = date.today()
            age = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
            if age < 18:
                errors['birthday'] = "You must be at least 18 years old to sign up."
        except ValueError:
            errors['birthday'] = "Please enter a valid date."

        # Gender
        if not form_data['gender']:
            errors['gender'] = "Please select your gender."

        # Income
        try:
            income = float(form_data['income'])
            if income <= 0:
                errors['income'] = "Income must be greater than zero."
        except ValueError:
            errors['income'] = "Please enter a valid number for income."


        # ===== IF ERRORS, SHOW FORM AGAIN =====
        if errors:
            return render_template(
                'signup.html',
                currencies=currencies,
                form_data=form_data,
                errors=errors
            )

        # ===== CREATE USER =====
        hashed_pw = generate_password_hash(password, method="pbkdf2:sha256")
        new_user = User(
            email=form_data['email'].lower(),
            name=form_data['name'],
            password_hash=hashed_pw,
            birthday=birthday,
            gender=form_data['gender'],
            income=income,
            currency=form_data['currency'],
            budget_style=form_data['budget_style'],
            goals=form_data['goals'],
            week_start=form_data['week_start']
        )

        db.session.add(new_user)
        db.session.commit()

        session['user_id'] = new_user.id
        return redirect(url_for('dashboard'))

    return render_template('signup.html', currencies=currencies, form_data=form_data, errors=errors)



# ---------------- Login ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    """Authenticate an existing user and start a session."""
    errors = {}
    email_value = ""
    

    if request.method == 'POST':
        email_value = request.form.get('email', '').strip()
        normalized_email = email_value.lower()  # keep lookups case-insensitive
        password = request.form.get('password', '')

        user = User.query.filter_by(email=normalized_email).first()

        # Generic validation
        if not email_value or not password or not user or not check_password_hash(user.password_hash, password):
            errors['credentials'] = "Email or password is incorrect."

        # If no errors → login success
        if not errors:
            # Get user and set session
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        
    return render_template('login.html', errors=errors, email=email_value)
    



# ---------------- Dashboard ----------------
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Show recent activity and allow adding a quick expense."""
    user = get_current_user()
    if user is None:
        return redirect(url_for('login'))

    if request.method == 'POST':
        amount = float(request.form['amount'])
        flow = request.form.get('flow', 'expense')
        category = request.form.get('category', 'Other')
        description = request.form['description']
        date_str = request.form.get('date')
        date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.utcnow()

        if flow == 'income':
            income = Income(
                user_id=user.id,
                amount=amount,
                category=category,
                description=description,
                date=date,
            )
            db.session.add(income)
        else:
            expense = Expense(
                user_id=user.id,
                amount=amount,
                category=category,
                description=description,
                date=date,
            )
            db.session.add(expense)
        db.session.commit()
        return redirect(url_for('dashboard'))

    expenses = Expense.query.filter_by(user_id=user.id).order_by(Expense.date.desc()).all()
    incomes = Income.query.filter_by(user_id=user.id).order_by(Income.date.desc()).all()

    # Totals
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    def expense_sum(filters):
        return db.session.query(func.sum(Expense.amount)).filter(filters).scalar() or 0

    def income_sum(filters):
        return db.session.query(func.sum(Income.amount)).filter(filters).scalar() or 0

    daily_total = expense_sum((Expense.user_id == user.id) & (func.date(Expense.date) == today))
    weekly_total = expense_sum((Expense.user_id == user.id) & (func.date(Expense.date) >= week_start))
    monthly_total = expense_sum((Expense.user_id == user.id) & (func.date(Expense.date) >= month_start))

    income_added = income_sum(Income.user_id == user.id)
    expense_added = expense_sum(Expense.user_id == user.id)
    wallet_balance = income_added - expense_added

    def category_data(start_date=None):
        q = db.session.query(Expense.category, func.sum(Expense.amount)).filter(
            Expense.user_id == user.id
        )
        if start_date:
            q = q.filter(func.date(Expense.date) >= start_date)

        results = q.group_by(Expense.category).all()
        if not results:
            return [], []  # safe fallback
        labels, values = zip(*results)
        return list(labels), list(values)
    

    daily_labels, daily_values = category_data(today)
    weekly_labels, weekly_values = category_data(week_start)
    monthly_labels, monthly_values = category_data(month_start)

    # Generate rule based insights
    insight = generate_rule_based_insight(
        expenses=expenses,
        income=user.income,
        budget_style=user.budget_style,
        goals=user.goals,
    )
 


    transactions = []
    for e in expenses:
        transactions.append({
            "date": e.date,
            "flow": "expense",
            "category": e.category,
            "description": e.description,
            "amount": e.amount,
        })
    for inc in incomes:
        transactions.append({
            "date": inc.date,
            "flow": "income",
            "category": inc.category,
            "description": inc.description,
            "amount": inc.amount,
        })
    transactions.sort(key=lambda x: x["date"], reverse=True)

    return render_template(
        'dashboard.html', user=user, transactions=transactions, categories=CATEGORIES,
        daily_total=daily_total, weekly_total=weekly_total, monthly_total=monthly_total,
        daily_labels=daily_labels, daily_values=daily_values,
        weekly_labels=weekly_labels, weekly_values=weekly_values,
        monthly_labels=monthly_labels, monthly_values=monthly_values,
        insight=insight,
        wallet_balance=wallet_balance,
        income_added=income_added,
        expense_added=expense_added
    )

# ---------------- All Transactions ----------------
@app.route('/transactions')
def all_transactions():
    """Filterable list of all transactions for the current user."""
    user = get_current_user()
    if user is None:
        return redirect(url_for('login'))
    start = request.args.get('start')
    end = request.args.get('end')
    category = request.args.get('category')
    flow = request.args.get('flow')

    expenses_query = Expense.query.filter_by(user_id=user.id)
    incomes_query = Income.query.filter_by(user_id=user.id)

    if start:
        expenses_query = expenses_query.filter(func.date(Expense.date) >= start)
        incomes_query = incomes_query.filter(func.date(Income.date) >= start)
    if end:
        expenses_query = expenses_query.filter(func.date(Expense.date) <= end)
        incomes_query = incomes_query.filter(func.date(Income.date) <= end)
    if category:
        expenses_query = expenses_query.filter_by(category=category)
        incomes_query = incomes_query.filter_by(category=category)

    expenses = expenses_query.all()
    incomes = incomes_query.all()

    combined = []
    for e in expenses:
        combined.append({
            "date": e.date,
            "flow": "expense",
            "category": e.category,
            "description": e.description,
            "amount": e.amount,
        })
    for inc in incomes:
        combined.append({
            "date": inc.date,
            "flow": "income",
            "category": inc.category,
            "description": inc.description,
            "amount": inc.amount,
        })

    if flow == "income":
        combined = [c for c in combined if c["flow"] == "income"]
    elif flow == "expense":
        combined = [c for c in combined if c["flow"] == "expense"]

    combined.sort(key=lambda x: x["date"], reverse=True)

    filter_categories = ['Salary'] + CATEGORIES
    return render_template('all_transactions.html', expenses=combined, categories=filter_categories, user=user)





# ---------------- Profile ----------------
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    """View and edit profile details (except email)."""
    user = get_current_user()
    if user is None:
        return redirect(url_for('login'))
    
    # Get currencies for select field
    currencies = [(c.alpha_3, c.name) for c in pycountry.currencies]

    if request.method == 'POST':
        # update only editable fields
        user.name = request.form['name']
        user.gender = request.form['gender']
        user.birthday = datetime.strptime(request.form['birthday'], '%Y-%m-%d').date()
        user.income = float(request.form['income'])
        user.currency = request.form['currency']
        user.budget_style = request.form['budget_style']
        user.goals = request.form['goals']
        user.week_start = request.form['week_start']
        db.session.commit()
        return redirect(url_for('profile'))
    
    return render_template('profile.html', user=user, currencies=currencies)

# ---------------- AI Insights Page ----------------
@app.route('/ai-insights')
def ai_insights_page():
    """Display AI-generated insights for the user's spending."""
    user = get_current_user()
    if user is None:
        return redirect(url_for('login'))

    expenses = Expense.query.filter_by(user_id=user.id).order_by(Expense.date.desc()).all()

    # Generate AI insights
    ai_insight = generate_ai_insight(
        expenses=expenses,
        income=user.income,
        budget_style=user.budget_style,
        goals=user.goals
    )


    return render_template('ai_insights.html', user=user, ai_insight=ai_insight)

# ---------------- Test Third Party Share ----------------
@app.route('/share', methods=['GET', 'POST'])
def share():
    """Build and (simulated) send a minimal partner snapshot."""
    user = get_current_user()
    if user is None:
        return redirect(url_for('login'))

    # Prepare a lightweight, partner-safe snapshot (no full history).
    expenses = Expense.query.filter_by(user_id=user.id) \
                            .order_by(Expense.date.desc()) \
                            .limit(50).all()

    summary = build_privacy_summary(user, expenses)
    shared_paths = []

    if request.method == 'POST':
        shared_paths.append(third_party_marketing_client(summary))
        shared_paths.append(third_party_scoring_client(summary))
        flash("Data package shared with trusted third parties.", "success")

    return render_template(
        'share.html',
        user=user,
        summary=summary,
        expenses=expenses,
        shared_paths=shared_paths,
        shared=bool(shared_paths)
    )

# ---------------- Logout ----------------
@app.route('/logout')
def logout():
    """Clear session and return to landing page."""
    session.pop('user_id', None)
    return redirect(url_for('index'))

class _QuietRequestHandler(WSGIRequestHandler):
    """Suppress per-request logs to keep provenance logs clean."""
    def log(self, type, message, *args):
        pass


if __name__ == '__main__':
    import argparse

    ensure_schema()
    app.secret_key = Config.SECRET_KEY

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    app.run(
        host="127.0.0.1",
        port=args.port,
        debug=False,
        use_reloader=False,
        use_debugger=False,
        request_handler=_QuietRequestHandler,
    )
