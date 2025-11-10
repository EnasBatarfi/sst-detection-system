"""
Flask Request/Response Interceptor
Automatically tags incoming personal data from HTTP requests
"""

from flask import request, g
from functools import wraps
from runtime_tracker import get_tracker, tag_data
from typing import Dict, Any
import json

class FlaskInterceptor:
    """
    Intercepts Flask requests to automatically tag personal data
    Integrates with the runtime tracker
    """
    
    def __init__(self, app=None):
        self.app = app
        self.tracker = get_tracker()
        self.personal_data_fields = {
            # Field name -> data type mapping
            'name': 'name',
            'email': 'email',
            'password': 'password',
            'birthday': 'birthday',
            'gender': 'gender',
            'income': 'income',
            'currency': 'currency',
            'budget_style': 'budget_style',
            'goals': 'goals',
            'week_start': 'week_start',
            'amount': 'expense_amount',
            'category': 'expense_category',
            'description': 'expense_description',
            'date': 'expense_date'
        }
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the interceptor with Flask app"""
        self.app = app
        
        # Register before_request hook
        @app.before_request
        def before_request_handler():
            self.process_request()
        
        # Register after_request hook
        @app.after_request
        def after_request_handler(response):
            return self.process_response(response)
    
    def process_request(self):
        """
        Process incoming request and tag personal data
        Called automatically before each request
        """
        if not self.tracker.is_active():
            return
        
        # Get user identifier from session
        from flask import session
        owner_id = self._get_owner_id(session)
        
        if not owner_id:
            return
        
        # Tag form data
        if request.method in ['POST', 'PUT', 'PATCH']:
            source = f"{request.endpoint}_form"
            
            for field_name, field_value in request.form.items():
                if field_name in self.personal_data_fields and field_value:
                    data_type = self.personal_data_fields[field_name]
                    tag_data(field_value, owner_id, data_type, source)
            
            # Tag JSON data if present
            if request.is_json:
                json_data = request.get_json()
                if json_data:
                    for field_name, field_value in json_data.items():
                        if field_name in self.personal_data_fields and field_value:
                            data_type = self.personal_data_fields[field_name]
                            tag_data(field_value, owner_id, data_type, source)
    
    def process_response(self, response):
        """
        Process outgoing response
        Can be used to detect data leaks in responses
        """
        # For now, just return the response unchanged
        # In the future, could check for unintended data exposure
        return response
    
    def _get_owner_id(self, session) -> str:
        """Extract user identifier from session"""
        user_id = session.get('user_id')
        if user_id:
            return f"user_{user_id}"
        return None
    
    def track_route(self, f):
        """
        Decorator to automatically track routes with personal data
        Usage: @interceptor.track_route
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Execute the route handler
            result = f(*args, **kwargs)
            return result
        return decorated_function


def create_interceptor(app) -> FlaskInterceptor:
    """Factory function to create and initialize interceptor"""
    return FlaskInterceptor(app)
