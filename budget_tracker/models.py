from flask_sqlalchemy import SQLAlchemy
from datetime import datetime



db = SQLAlchemy()


class User(db.Model):
    """Registered budget-tracking user."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    birthday = db.Column(db.Date, nullable=False)
    income = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), nullable=False, default='SAR')
    budget_style = db.Column(db.String(50), default='Balanced')
    goals = db.Column(db.String(500))
    week_start = db.Column(db.String(20), default='Monday')
    gender = db.Column(db.String(20), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Expense(db.Model):
    """Single outgoing transaction belonging to a user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('expenses', lazy=True))


class Income(db.Model):
    """Single incoming transaction belonging to a user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False, default='Salary')
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('incomes', lazy=True))
