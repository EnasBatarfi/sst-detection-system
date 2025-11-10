from config import Config
from models import db, User
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
from models import Expense
import pycountry
from flask import Flask, render_template, request, redirect, url_for, session, flash
import re
from werkzeug.security import generate_password_hash
from datetime import datetime
from models import db, User
import pycountry
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash
from datetime import datetime, date
import re
import pycountry
from models import db, User

from dotenv import load_dotenv
load_dotenv()

from ai_insights import generate_ai_insight, generate_rule_based_insight

# Python runtime-level tracking (auto-enabled via sitecustomize.py or PYTHON_TRACKING_ENABLED)
# Just connect it to our database when app starts
try:
    import python_runtime_tracking
    python_runtime_tracking.enable_runtime_tracking()
except ImportError:
    pass  # Runtime tracking not available




app = Flask(__name__)
CATEGORIES = ["Food", "Transport", "Entertainment", "Bills", "Shopping", "Other"]

app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()
    # Connect runtime tracking to Flask database (if runtime tracking is enabled)
    try:
        import python_runtime_tracking
        # Ensure Flask app is instrumented (in case it was created before tracking enabled)
        python_runtime_tracking.instrument_flask_app(app)
        # Connect tracker to Flask database session
        tracker = python_runtime_tracking.get_tracker()
        from models import db as flask_db, DataTag, DataSharingEvent, DataLineage
        tracker.db_session = flask_db.session
        tracker.DataTagModel = DataTag
        tracker.DataSharingEvent = DataSharingEvent
        tracker.DataLineage = DataLineage
        print("[Runtime Tracking] Connected to Flask database")
    except Exception as e:
        pass  # Runtime tracking will work in-memory only

# ---------------- Home ----------------
@app.route('/')
def index():
    return render_template('index.html', datetime=datetime)

# ---------------- Signup ----------------

@app.route('/signup', methods=['GET', 'POST'])
def signup():
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

        # ===== VALIDATION =====
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
        hashed_pw = generate_password_hash(password)
        new_user = User(
            name=form_data['name'],
            email=form_data['email'].lower(),
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
    errors = {}
    email_value = ""

    if request.method == 'POST':
        email_value = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email_value).first()

        # Generic validation
        if not email_value or not password or not user or not check_password_hash(user.password_hash, password):
            errors['credentials'] = "Email or password is incorrect."

        # If no errors → login success
        if not errors:
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))

    return render_template('login.html', errors=errors, email=email_value)



# ---------------- Dashboard ----------------
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        amount = float(request.form['amount'])
        category = request.form['category']
        description = request.form['description']
        date_str = request.form.get('date')
        date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.utcnow()
        expense = Expense(user_id=user.id, amount=amount, category=category, description=description, date=date)
        db.session.add(expense)
        db.session.commit()
        return redirect(url_for('dashboard'))

    expenses = Expense.query.filter_by(user_id=user.id).order_by(Expense.date.desc()).all()

    # Totals
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    def total(query_filter):
        return db.session.query(func.sum(Expense.amount)).filter(query_filter).scalar() or 0

    daily_total = total((Expense.user_id == user.id) & (func.date(Expense.date) == today))
    weekly_total = total((Expense.user_id == user.id) & (func.date(Expense.date) >= week_start))
    monthly_total = total((Expense.user_id == user.id) & (func.date(Expense.date) >= month_start))

    def category_data(start_date=None):
        q = db.session.query(Expense.category, func.sum(Expense.amount)).filter(Expense.user_id==user.id)
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
 


    return render_template(
        'dashboard.html', user=user, expenses=expenses, categories=CATEGORIES,
        daily_total=daily_total, weekly_total=weekly_total, monthly_total=monthly_total,
        daily_labels=daily_labels, daily_values=daily_values,
        weekly_labels=weekly_labels, weekly_values=weekly_values,
        monthly_labels=monthly_labels, monthly_values=monthly_values,
        insight=insight  
    )

# ---------------- All Transactions ----------------
@app.route('/transactions')
def all_transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    start = request.args.get('start')
    end = request.args.get('end')
    category = request.args.get('category')

    query = Expense.query.filter_by(user_id=user.id)
    if start:
        query = query.filter(func.date(Expense.date) >= start)
    if end:
        query = query.filter(func.date(Expense.date) <= end)
    if category:
        query = query.filter_by(category=category)

    expenses = query.order_by(Expense.date.desc()).all()
    return render_template('all_transactions.html', expenses=expenses, categories=CATEGORIES, user=user)





# ---------------- Profile ----------------
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
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
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    expenses = Expense.query.filter_by(user_id=user.id).order_by(Expense.date.desc()).all()

    # Generate AI insights
    ai_insight = generate_ai_insight(
        expenses=expenses,
        income=user.income,
        budget_style=user.budget_style,
        goals=user.goals
    )

    return render_template('ai_insights.html', user=user, ai_insight=ai_insight)

# ---------------- Logout ----------------
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

# ---------------- Provenance & SST Detection View ----------------
@app.route('/provenance')
def provenance():
    """View data provenance and server-side tracking logs."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    from provenance_utils import get_sharing_events_for_user, get_sst_summary
    
    user_id = session['user_id']
    events = get_sharing_events_for_user(user_id, limit=100)
    summary = get_sst_summary(user_id=user_id)
    
    return render_template('provenance.html', events=events, summary=summary)


if __name__ == '__main__':
    app.secret_key = Config.SECRET_KEY
    app.run(debug=True)
