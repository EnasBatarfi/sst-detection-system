"""
Runtime-Level Instrumentation for Server-Side Tracking (SST) Detection
Implements automatic data tagging, provenance tracking, and audit logging
with minimal changes to application code.
"""

import uuid
import json
import time
import functools
import inspect
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import threading
from flask import request, session, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sys

# Thread-local storage for provenance context
_provenance_context = threading.local()


class DataTag:
    """Represents a tag attached to personal data with provenance metadata."""
    
    def __init__(self, identifier: str, data_type: str, source: str, timestamp: float = None):
        self.identifier = identifier  # Unique ID (e.g., user email, user_id)
        self.data_type = data_type  # Type of data (email, name, income, etc.)
        self.source = source  # Where data came from (form, database, etc.)
        self.timestamp = timestamp or time.time()
        self.operations = []  # List of operations this data went through
        self.derived_from = []  # Parent tags if this is derived data
        
    def to_dict(self) -> Dict:
        return {
            'identifier': self.identifier,
            'data_type': self.data_type,
            'source': self.source,
            'timestamp': self.timestamp,
            'operations': self.operations,
            'derived_from': [t.to_dict() if isinstance(t, DataTag) else t for t in self.derived_from]
        }
    
    def __repr__(self):
        return f"DataTag(id={self.identifier}, type={self.data_type}, source={self.source})"


class ProvenanceTracker:
    """Core provenance tracking system."""
    
    def __init__(self, db: SQLAlchemy):
        self.db = db
        self.tags: Dict[str, DataTag] = {}  # Map of data values to tags
        self.tag_registry: Dict[str, List[str]] = defaultdict(list)  # identifier -> list of tagged values
        self.sharing_events: List[Dict] = []
        self.lock = threading.Lock()
        
    def tag_data(self, value: Any, data_type: str, identifier: str, source: str) -> DataTag:
        """Tag personal data with provenance metadata."""
        if value is None:
            return None
            
        value_str = str(value)
        with self.lock:
            if value_str not in self.tags:
                tag = DataTag(identifier, data_type, source)
                self.tags[value_str] = tag
                self.tag_registry[identifier].append(value_str)
                # Persist to database
                self._persist_tag(tag, value_str)
            else:
                tag = self.tags[value_str]
                # Update operations if needed
                if source not in tag.operations:
                    tag.operations.append(source)
                    self._update_tag_operations(tag, value_str)
            return tag
    
    def _persist_tag(self, tag: DataTag, value_str: str):
        """Persist tag to database."""
        try:
            from models import DataTag as DataTagModel
            import hashlib
            
            tag_id = str(uuid.uuid4())
            value_hash = hashlib.sha256(value_str.encode()).hexdigest()
            
            db_tag = DataTagModel(
                tag_id=tag_id,
                identifier=tag.identifier,
                data_type=tag.data_type,
                data_value_hash=value_hash,
                source=tag.source,
                timestamp=datetime.fromtimestamp(tag.timestamp),
                operations_json=json.dumps(tag.operations),
                derived_from_json=json.dumps([t.tag_id if hasattr(t, 'tag_id') else str(t) for t in tag.derived_from])
            )
            self.db.session.add(db_tag)
            self.db.session.commit()
            tag.tag_id = tag_id  # Store DB ID for reference
        except Exception as e:
            # Silently fail if DB not ready - in-memory tracking still works
            pass
    
    def _update_tag_operations(self, tag: DataTag, value_str: str):
        """Update tag operations in database."""
        try:
            from models import DataTag as DataTagModel
            import hashlib
            
            value_hash = hashlib.sha256(value_str.encode()).hexdigest()
            db_tag = DataTagModel.query.filter_by(data_value_hash=value_hash).first()
            if db_tag:
                db_tag.operations_json = json.dumps(tag.operations)
                self.db.session.commit()
        except Exception:
            pass
    
    def tag_derived_data(self, derived_value: Any, data_type: str, parent_tags: List[DataTag], operation: str) -> Optional[DataTag]:
        """Tag data derived from other tagged data."""
        if derived_value is None or not parent_tags:
            return None
            
        identifier = parent_tags[0].identifier  # Inherit identifier from parent
        tag = DataTag(identifier, data_type, f"derived:{operation}")
        tag.derived_from = parent_tags
        tag.operations = [op for t in parent_tags for op in t.operations] + [operation]
        
        value_str = str(derived_value)
        with self.lock:
            self.tags[value_str] = tag
            self.tag_registry[identifier].append(value_str)
            # Persist derived tag and lineage
            self._persist_tag(tag, value_str)
            self._persist_lineage(tag, parent_tags, operation)
        return tag
    
    def _persist_lineage(self, child_tag: DataTag, parent_tags: List[DataTag], operation: str):
        """Persist data lineage relationships."""
        try:
            from models import DataLineage
            
            if not hasattr(child_tag, 'tag_id'):
                return  # Tag not persisted yet
            
            for parent_tag in parent_tags:
                parent_tag_id = getattr(parent_tag, 'tag_id', None)
                if parent_tag_id:
                    lineage = DataLineage(
                        parent_tag_id=parent_tag_id,
                        child_tag_id=child_tag.tag_id,
                        operation=operation,
                        timestamp=datetime.fromtimestamp(child_tag.timestamp)
                    )
                    self.db.session.add(lineage)
            self.db.session.commit()
        except Exception:
            pass
    
    def get_tags_for_value(self, value: Any) -> Optional[DataTag]:
        """Retrieve tags for a data value."""
        if value is None:
            return None
        return self.tags.get(str(value))
    
    def get_tags_for_identifier(self, identifier: str) -> List[DataTag]:
        """Get all tags associated with an identifier."""
        with self.lock:
            return [self.tags.get(v) for v in self.tag_registry.get(identifier, []) if v in self.tags]
    
    def log_sharing_event(self, event_type: str, destination: str, data: Dict, tags: List[DataTag], 
                         metadata: Dict = None):
        """Log a data sharing event (external API call, database write, etc.)."""
        event_record = {
            'event_id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,  # 'api_call', 'database_write', 'email', etc.
            'destination': destination,  # URL, database table, email address, etc.
            'data': data,
            'tags': [tag.to_dict() if isinstance(tag, DataTag) else tag for tag in tags],
            'identifiers': list(set([tag.identifier for tag in tags if tag])),
            'metadata': metadata or {},
            'request_id': getattr(g, 'request_id', None) if hasattr(g, 'request_id') else None,
            'user_id': session.get('user_id') if hasattr(session, 'get') else None
        }
        
        with self.lock:
            self.sharing_events.append(event_record)
        
        # Also write to database if available
        self._persist_sharing_event(event_record)
    
    def _persist_sharing_event(self, event_record: Dict):
        """Persist sharing event to database."""
        try:
            from models import DataSharingEvent
            event_obj = DataSharingEvent(
                event_id=event_record['event_id'],
                timestamp=datetime.fromisoformat(event_record['timestamp']),
                event_type=event_record['event_type'],
                destination=event_record['destination'],
                data_json=json.dumps(event_record['data']),
                tags_json=json.dumps(event_record['tags']),
                identifiers_json=json.dumps(event_record['identifiers']),
                metadata_json=json.dumps(event_record['metadata']),
                user_id=event_record.get('user_id')
            )
            self.db.session.add(event_obj)
            self.db.session.commit()
        except Exception as e:
            # Fallback to in-memory storage if DB not ready
            print(f"Warning: Could not persist sharing event: {e}")


# Global tracker instance (will be initialized by app)
_tracker: Optional[ProvenanceTracker] = None


def init_tracker(db: SQLAlchemy):
    """Initialize the global provenance tracker."""
    global _tracker
    _tracker = ProvenanceTracker(db)
    return _tracker


def get_tracker() -> ProvenanceTracker:
    """Get the global tracker instance."""
    global _tracker
    if _tracker is None:
        raise RuntimeError("Provenance tracker not initialized. Call init_tracker() first.")
    return _tracker


# PII field patterns for automatic detection
PII_FIELDS = {
    'email', 'name', 'password', 'birthday', 'birth_date', 'date_of_birth',
    'phone', 'address', 'ssn', 'income', 'gender', 'age', 'user_id', 'id'
}


def is_pii_field(field_name: str) -> bool:
    """Check if a field name indicates PII."""
    field_lower = field_name.lower()
    return any(pii in field_lower for pii in PII_FIELDS)


def extract_identifier_from_request() -> Optional[str]:
    """Extract user identifier from Flask request context."""
    try:
        # Try to get user_id from session
        if hasattr(session, 'get') and session.get('user_id'):
            return f"user_{session.get('user_id')}"
        
        # Try to get email from form data
        if hasattr(request, 'form'):
            email = request.form.get('email')
            if email:
                return f"email_{email}"
        
        # Try to get from JSON body
        if hasattr(request, 'json') and request.json:
            email = request.json.get('email')
            if email:
                return f"email_{email}"
                
    except Exception:
        pass
    return None


def auto_tag_request_data():
    """Automatically tag PII data from Flask request."""
    tracker = get_tracker()
    identifier = extract_identifier_from_request()
    
    if not identifier:
        return
    
    # Tag form data
    if hasattr(request, 'form'):
        for key, value in request.form.items():
            if is_pii_field(key) and value:
                tracker.tag_data(value, key, identifier, f"request.form.{key}")
    
    # Tag JSON data
    if hasattr(request, 'json') and request.json:
        for key, value in request.json.items():
            if is_pii_field(key) and value:
                tracker.tag_data(value, key, identifier, f"request.json.{key}")
    
    # Tag URL parameters
    if hasattr(request, 'args'):
        for key, value in request.args.items():
            if is_pii_field(key) and value:
                tracker.tag_data(value, key, identifier, f"request.args.{key}")


def track_function_call(func):
    """Decorator to track function calls and tag return values if inputs are tagged."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tracker = get_tracker()
        
        # Check if any arguments are tagged
        input_tags = []
        for arg in args:
            if isinstance(arg, (str, int, float)):
                tag = tracker.get_tags_for_value(arg)
                if tag:
                    input_tags.append(tag)
        
        for key, value in kwargs.items():
            if isinstance(value, (str, int, float)):
                tag = tracker.get_tags_for_value(value)
                if tag:
                    input_tags.append(tag)
        
        # Execute function
        result = func(*args, **kwargs)
        
        # Tag result if inputs were tagged
        if input_tags and result:
            if isinstance(result, (str, int, float)):
                tracker.tag_derived_data(result, f"return:{func.__name__}", input_tags, func.__name__)
            elif isinstance(result, (list, tuple)):
                for item in result:
                    if isinstance(item, (str, int, float)):
                        tracker.tag_derived_data(item, f"return:{func.__name__}", input_tags, func.__name__)
            elif isinstance(result, dict):
                for key, value in result.items():
                    if isinstance(value, (str, int, float)):
                        tracker.tag_derived_data(value, f"return:{func.__name__}.{key}", input_tags, func.__name__)
        
        return result
    return wrapper


# HTTP request interception for external API calls
_original_requests_post = None
_original_requests_get = None
_original_requests_request = None


def _instrument_requests():
    """Instrument the requests library to track external API calls."""
    global _original_requests_post, _original_requests_get, _original_requests_request
    
    try:
        import requests
        
        if _original_requests_post is None:
            _original_requests_post = requests.post
            _original_requests_get = requests.get
            _original_requests_request = requests.request
            
            def tracked_post(url, *args, **kwargs):
                tracker = get_tracker()
                
                # Extract data being sent
                data = kwargs.get('data') or kwargs.get('json') or {}
                if isinstance(data, dict):
                    # Find tagged data in the payload
                    tags = []
                    for key, value in data.items():
                        if isinstance(value, (str, int, float)):
                            tag = tracker.get_tags_for_value(value)
                            if tag:
                                tags.append(tag)
                    
                    # Log sharing event
                    if tags:
                        tracker.log_sharing_event(
                            event_type='api_call',
                            destination=url,
                            data=data,
                            tags=tags,
                            metadata={
                                'method': 'POST',
                                'headers': dict(kwargs.get('headers', {}))
                            }
                        )
                
                return _original_requests_post(url, *args, **kwargs)
            
            def tracked_get(url, *args, **kwargs):
                tracker = get_tracker()
                
                # Extract params
                params = kwargs.get('params', {})
                if isinstance(params, dict):
                    tags = []
                    for key, value in params.items():
                        if isinstance(value, (str, int, float)):
                            tag = tracker.get_tags_for_value(value)
                            if tag:
                                tags.append(tag)
                    
                    if tags:
                        tracker.log_sharing_event(
                            event_type='api_call',
                            destination=url,
                            data=params,
                            tags=tags,
                            metadata={
                                'method': 'GET',
                                'headers': dict(kwargs.get('headers', {}))
                            }
                        )
                
                return _original_requests_get(url, *args, **kwargs)
            
            def tracked_request(method, url, *args, **kwargs):
                tracker = get_tracker()
                
                data = kwargs.get('data') or kwargs.get('json') or kwargs.get('params') or {}
                if isinstance(data, dict):
                    tags = []
                    for key, value in data.items():
                        if isinstance(value, (str, int, float)):
                            tag = tracker.get_tags_for_value(value)
                            if tag:
                                tags.append(tag)
                    
                    if tags:
                        tracker.log_sharing_event(
                            event_type='api_call',
                            destination=url,
                            data=data,
                            tags=tags,
                            metadata={
                                'method': method,
                                'headers': dict(kwargs.get('headers', {}))
                            }
                        )
                
                return _original_requests_request(method, url, *args, **kwargs)
            
            requests.post = tracked_post
            requests.get = tracked_get
            requests.request = tracked_request
            
    except ImportError:
        pass  # requests not installed


def _instrument_openai_client():
    """Instrument OpenAI client for API calls."""
    try:
        import openai
        
        # Store original methods
        if not hasattr(openai.OpenAI, '_original_chat_completions_create'):
            original_create = openai.OpenAI.chat.completions.create
            
            def tracked_create(self, *args, **kwargs):
                tracker = get_tracker()
                
                # Extract messages/data from kwargs
                messages = kwargs.get('messages', [])
                data_dict = {}
                tags = []
                
                for msg in messages:
                    if isinstance(msg, dict):
                        content = msg.get('content', '')
                        if isinstance(content, str):
                            # Check if content contains tagged data
                            tag = tracker.get_tags_for_value(content)
                            if tag:
                                tags.append(tag)
                            data_dict[f"message_{len(data_dict)}"] = content[:100]  # Truncate for logging
                
                # Also check input parameter (for Groq API)
                if 'input' in kwargs:
                    input_val = kwargs.get('input', '')
                    if isinstance(input_val, str):
                        tag = tracker.get_tags_for_value(input_val)
                        if tag:
                            tags.append(tag)
                        data_dict['input'] = input_val[:500]  # Truncate
                
                if tags:
                    tracker.log_sharing_event(
                        event_type='api_call',
                        destination=kwargs.get('base_url', 'openai_api') or 'openai_api',
                        data=data_dict,
                        tags=tags,
                        metadata={
                            'model': kwargs.get('model'),
                            'api_type': 'openai'
                        }
                    )
                
                return original_create(self, *args, **kwargs)
            
            # Monkey patch
            openai.OpenAI.chat.completions.create = tracked_create
            openai.OpenAI._original_chat_completions_create = original_create
            
            # Patch OpenAI.__init__ to instrument instances
            original_init = openai.OpenAI.__init__
            
            def tracked_init(client_instance, *args, **kwargs):
                original_init(client_instance, *args, **kwargs)
                
                # Instrument responses attribute if it exists (Groq API)
                if hasattr(client_instance, 'responses') and hasattr(client_instance.responses, 'create'):
                    if not hasattr(client_instance.responses, '_original_create'):
                        original_responses_create = client_instance.responses.create
                        client_base_url = getattr(client_instance, 'base_url', 'groq_api') or 'groq_api'
                        
                        def tracked_responses_create(*args, **kwargs):
                            tracker = get_tracker()
                            
                            input_val = kwargs.get('input', '')
                            tags = []
                            data_dict = {}
                            
                            if isinstance(input_val, str):
                                # Check if prompt contains tagged data by checking substrings
                                import re
                                
                                # Extract potential PII values from prompt
                                # Look for patterns like "Income: $1234.56"
                                income_match = re.search(r'Income:\s*\$?([\d,]+\.?\d*)', input_val)
                                if income_match:
                                    income_val = income_match.group(1).replace(',', '')
                                    tag = tracker.get_tags_for_value(income_val)
                                    if tag:
                                        tags.append(tag)
                                
                                # Check for other numeric values that might be tagged
                                numbers = re.findall(r'\b\d+\.?\d*\b', input_val)
                                for num in numbers:
                                    tag = tracker.get_tags_for_value(num)
                                    if tag:
                                        tags.append(tag)
                                
                                # Also check the full prompt string
                                tag = tracker.get_tags_for_value(input_val)
                                if tag:
                                    tags.append(tag)
                                
                                data_dict['input'] = input_val[:500]
                            
                            if tags:
                                # Deduplicate tags
                                unique_tags = []
                                seen_ids = set()
                                for tag in tags:
                                    if tag:
                                        tag_id = (getattr(tag, 'identifier', '') + 
                                                 getattr(tag, 'data_type', ''))
                                        if tag_id not in seen_ids:
                                            unique_tags.append(tag)
                                            seen_ids.add(tag_id)
                                
                                tracker.log_sharing_event(
                                    event_type='api_call',
                                    destination=client_base_url,
                                    data=data_dict,
                                    tags=unique_tags,
                                    metadata={
                                        'model': kwargs.get('model'),
                                        'api_type': 'groq'
                                    }
                                )
                            
                            return original_responses_create(*args, **kwargs)
                        
                        client_instance.responses.create = tracked_responses_create
                        client_instance.responses._original_create = original_responses_create
            
            openai.OpenAI.__init__ = tracked_init
                    
    except ImportError:
        pass  # openai not installed


def _instrument_sqlalchemy(db: SQLAlchemy):
    """Instrument SQLAlchemy to track database operations."""
    
    @event.listens_for(Engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Track database writes that contain tagged data."""
        tracker = get_tracker()
        
        if parameters:
            tags = []
            data_dict = {}
            identifier = None
            
            if isinstance(parameters, dict):
                for key, value in parameters.items():
                    if isinstance(value, (str, int, float)):
                        tag = tracker.get_tags_for_value(value)
                        if tag:
                            tags.append(tag)
                            if not identifier:
                                identifier = tag.identifier
                        # Also tag PII fields automatically if not already tagged
                        if is_pii_field(key) and value and not tag:
                            if key == 'user_id' or key == 'id':
                                identifier = f"user_{value}"
                            elif key == 'email':
                                identifier = f"email_{value}"
                            else:
                                identifier = extract_identifier_from_request() or f"user_{session.get('user_id')}" if hasattr(session, 'get') else None
                            
                            if identifier:
                                tracker.tag_data(value, key, identifier, f"database.write.{key}")
                                tag = tracker.get_tags_for_value(value)
                                if tag:
                                    tags.append(tag)
                        
                        if is_pii_field(key):
                            data_dict[key] = str(value)[:100]  # Truncate for logging
            elif isinstance(parameters, (list, tuple)):
                for i, value in enumerate(parameters):
                    if isinstance(value, (str, int, float)):
                        tag = tracker.get_tags_for_value(value)
                        if tag:
                            tags.append(tag)
            
            if tags and ('INSERT' in statement.upper() or 'UPDATE' in statement.upper()):
                # Extract table name from statement
                table_name = 'unknown'
                if 'INSERT' in statement.upper():
                    parts = statement.upper().split('INSERT')
                    if len(parts) > 1:
                        table_part = parts[1].split()[0] if parts[1].split() else 'unknown'
                        table_name = table_part.replace('INTO', '').strip()
                elif 'UPDATE' in statement.upper():
                    parts = statement.upper().split('UPDATE')
                    if len(parts) > 1:
                        table_name = parts[1].split()[0] if parts[1].split() else 'unknown'
                
                tracker.log_sharing_event(
                    event_type='database_write',
                    destination=f"database:{table_name}",
                    data=data_dict,
                    tags=tags,
                    metadata={
                        'statement': statement[:200],  # Truncate SQL
                        'operation': 'INSERT' if 'INSERT' in statement.upper() else 'UPDATE'
                    }
                )
    
    # Tag data when User or Expense models are loaded
    try:
        from models import User, Expense
        
        @event.listens_for(User, "load")
        def receive_user_load(target, context):
            """Tag user data loaded from database."""
            tracker = get_tracker()
            identifier = f"user_{target.id}"
            
            # Tag all PII fields
            for field_name in ['name', 'email', 'birthday', 'income', 'gender', 'goals']:
                value = getattr(target, field_name, None)
                if value and isinstance(value, (str, int, float)):
                    tracker.tag_data(value, field_name, identifier, f"database.read.User.{field_name}")
        
        @event.listens_for(Expense, "load")
        def receive_expense_load(target, context):
            """Tag expense data loaded from database."""
            tracker = get_tracker()
            identifier = f"user_{target.user_id}"
            
            # Tag amount and description
            if target.amount:
                tracker.tag_data(target.amount, 'amount', identifier, f"database.read.Expense.amount")
            if target.description:
                tracker.tag_data(target.description, 'description', identifier, f"database.read.Expense.description")
    except ImportError:
        pass  # Models not available yet


def _instrument_existing_openai_clients():
    """Instrument any existing OpenAI client instances (e.g., from ai_insights module)."""
    try:
        import openai
        import sys
        
        # Find all OpenAI client instances in loaded modules
        for module_name, module in sys.modules.items():
            if hasattr(module, 'client') and isinstance(getattr(module, 'client', None), openai.OpenAI):
                client = getattr(module, 'client')
                if hasattr(client, 'responses') and hasattr(client.responses, 'create'):
                    if not hasattr(client.responses, '_original_create'):
                        original_responses_create = client.responses.create
                        client_base_url = getattr(client, 'base_url', 'groq_api') or 'groq_api'
                        
                        def tracked_responses_create(*args, **kwargs):
                            tracker = get_tracker()
                            
                            input_val = kwargs.get('input', '')
                            tags = []
                            data_dict = {}
                            
                            if isinstance(input_val, str):
                                import re
                                
                                income_match = re.search(r'Income:\s*\$?([\d,]+\.?\d*)', input_val)
                                if income_match:
                                    income_val = income_match.group(1).replace(',', '')
                                    tag = tracker.get_tags_for_value(income_val)
                                    if tag:
                                        tags.append(tag)
                                
                                numbers = re.findall(r'\b\d+\.?\d*\b', input_val)
                                for num in numbers:
                                    tag = tracker.get_tags_for_value(num)
                                    if tag:
                                        tags.append(tag)
                                
                                tag = tracker.get_tags_for_value(input_val)
                                if tag:
                                    tags.append(tag)
                                
                                data_dict['input'] = input_val[:500]
                            
                            if tags:
                                unique_tags = []
                                seen_ids = set()
                                for tag in tags:
                                    if tag:
                                        tag_id = (getattr(tag, 'identifier', '') + 
                                                 getattr(tag, 'data_type', ''))
                                        if tag_id not in seen_ids:
                                            unique_tags.append(tag)
                                            seen_ids.add(tag_id)
                                
                                tracker.log_sharing_event(
                                    event_type='api_call',
                                    destination=client_base_url,
                                    data=data_dict,
                                    tags=unique_tags,
                                    metadata={
                                        'model': kwargs.get('model'),
                                        'api_type': 'groq'
                                    }
                                )
                            
                            return original_responses_create(*args, **kwargs)
                        
                        client.responses.create = tracked_responses_create
                        client.responses._original_create = original_responses_create
    except Exception:
        pass


def setup_runtime_instrumentation(app, db: SQLAlchemy):
    """
    Setup complete runtime instrumentation for the Flask app.
    This is the main entry point - call this once at app startup.
    """
    # Initialize tracker
    init_tracker(db)
    
    # Instrument HTTP requests
    _instrument_requests()
    
    # Instrument OpenAI/Groq client (patches __init__ for future instances)
    _instrument_openai_client()
    
    # Instrument any existing OpenAI client instances
    _instrument_existing_openai_clients()
    
    # Instrument SQLAlchemy
    _instrument_sqlalchemy(db)
    
    # Add before_request hook to auto-tag request data
    @app.before_request
    def tag_request_data():
        auto_tag_request_data()
    
    # Add after_request hook to tag response data if needed
    @app.after_request
    def track_response(response):
        # Could add response tracking here if needed
        return response
    
    print("Runtime instrumentation initialized for SST detection")
