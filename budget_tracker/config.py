"""Base configuration for the budget tracker."""

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Use an environment-provided secret; fall back to a dev-only value.
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-change-me")
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "database.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
