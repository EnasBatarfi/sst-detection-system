"""
Python Runtime-Level Instrumentation for Server-Side Tracking (SST) Detection

This module provides runtime-level instrumentation that works at the Python interpreter
level, requiring NO changes to application code. It can be activated via:
1. Environment variable: PYTHON_TRACKING_ENABLED=1
2. Import hook: import python_runtime_tracking (auto-activates)
3. Site-packages installation (runs on every Python process)

Based on the proposal: "Detecting Server-Side Tracking (SST) via Runtime-Level Instrumentation"
"""

import sys
import os
import uuid
import json
import time
import hashlib
import threading
import functools
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict

# Global state
_tracking_enabled = False
_tracker_instance = None
_tracker_lock = threading.Lock()

# PII field patterns
PII_FIELDS = {
    'email', 'name', 'password', 'birthday', 'birth_date', 'date_of_birth',
    'phone', 'address', 'ssn', 'income', 'gender', 'age', 'user_id', 'id'
}


class DataTag:
    """Represents a tag attached to personal data."""
    
    def __init__(self, identifier: str, data_type: str, source: str, timestamp: float = None):
        self.tag_id = str(uuid.uuid4())
        self.identifier = identifier
        self.data_type = data_type
        self.source = source
        self.timestamp = timestamp or time.time()
        self.operations = []
        self.derived_from = []
        
    def to_dict(self) -> Dict:
        return {
            'tag_id': self.tag_id,
            'identifier': self.identifier,
            'data_type': self.data_type,
            'source': self.source,
            'timestamp': self.timestamp,
            'operations': self.operations,
            'derived_from': [t.tag_id if isinstance(t, DataTag) else t for t in self.derived_from]
        }


class RuntimeProvenanceTracker:
    """Core runtime provenance tracking system."""
    
    def __init__(self):
        self.tags: Dict[str, DataTag] = {}
        self.tag_registry: Dict[str, List[str]] = defaultdict(list)
        self.sharing_events: List[Dict] = []
        self.lock = threading.Lock()
        self.db_session = None
        self._init_database()
        
    def _init_database(self):
        """Initialize database connection if Flask/SQLAlchemy is available."""
        try:
            # Try to get Flask app context
            from flask import has_app_context, current_app
            if has_app_context():
                from models import db, DataTag as DataTagModel, DataSharingEvent, DataLineage
                self.db_session = db.session
                self.DataTagModel = DataTagModel
                self.DataSharingEvent = DataSharingEvent
                self.DataLineage = DataLineage
        except ImportError:
            pass  # Flask not available, use in-memory only
    
    def tag_data(self, value: Any, data_type: str, identifier: str, source: str) -> Optional[DataTag]:
        """Tag personal data with provenance metadata."""
        if value is None:
            return None
            
        value_str = str(value)
        with self.lock:
            if value_str not in self.tags:
                tag = DataTag(identifier, data_type, source)
                self.tags[value_str] = tag
                self.tag_registry[identifier].append(value_str)
                self._persist_tag(tag, value_str)
            else:
                tag = self.tags[value_str]
                if source not in tag.operations:
                    tag.operations.append(source)
            return tag
    
    def _persist_tag(self, tag: DataTag, value_str: str):
        """Persist tag to database if available."""
        if self.db_session:
            try:
                value_hash = hashlib.sha256(value_str.encode()).hexdigest()
                db_tag = self.DataTagModel(
                    tag_id=tag.tag_id,
                    identifier=tag.identifier,
                    data_type=tag.data_type,
                    data_value_hash=value_hash,
                    source=tag.source,
                    timestamp=datetime.fromtimestamp(tag.timestamp),
                    operations_json=json.dumps(tag.operations),
                    derived_from_json=json.dumps([t.tag_id for t in tag.derived_from])
                )
                self.db_session.add(db_tag)
                self.db_session.commit()
            except Exception:
                pass  # Fallback to in-memory
    
    def get_tags_for_value(self, value: Any) -> Optional[DataTag]:
        """Retrieve tags for a data value."""
        if value is None:
            return None
        return self.tags.get(str(value))
    
    def log_sharing_event(self, event_type: str, destination: str, data: Dict, 
                         tags: List[DataTag], metadata: Dict = None):
        """Log a data sharing event."""
        event_record = {
            'event_id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'destination': destination,
            'data': data,
            'tags': [tag.to_dict() if isinstance(tag, DataTag) else tag for tag in tags],
            'identifiers': list(set([tag.identifier for tag in tags if tag])),
            'metadata': metadata or {}
        }
        
        with self.lock:
            self.sharing_events.append(event_record)
        
        self._persist_sharing_event(event_record)
    
    def _persist_sharing_event(self, event_record: Dict):
        """Persist sharing event to database if available."""
        if self.db_session:
            try:
                event_obj = self.DataSharingEvent(
                    event_id=event_record['event_id'],
                    timestamp=datetime.fromisoformat(event_record['timestamp']),
                    event_type=event_record['event_type'],
                    destination=event_record['destination'],
                    data_json=json.dumps(event_record['data']),
                    tags_json=json.dumps(event_record['tags']),
                    identifiers_json=json.dumps(event_record['identifiers']),
                    metadata_json=json.dumps(event_record['metadata'])
                )
                self.db_session.add(event_obj)
                self.db_session.commit()
            except Exception:
                pass  # Fallback to in-memory


def get_tracker() -> RuntimeProvenanceTracker:
    """Get the global tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        with _tracker_lock:
            if _tracker_instance is None:
                _tracker_instance = RuntimeProvenanceTracker()
    return _tracker_instance


def is_pii_field(field_name: str) -> bool:
    """Check if a field name indicates PII."""
    field_lower = field_name.lower()
    return any(pii in field_lower for pii in PII_FIELDS)


# Runtime instrumentation functions
_original_import = __builtins__.__import__


def _tracking_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Wrapped import that instruments modules as they're imported."""
    module = _original_import(name, globals, locals, fromlist, level)
    
    # Instrument specific modules
    if name == 'requests':
        _instrument_requests_module(module)
    elif name == 'openai':
        _instrument_openai_module(module)
    elif name == 'flask' or name.startswith('flask.'):
        _instrument_flask_sqlalchemy(module)
    elif 'sqlalchemy' in name:
        _setup_sqlalchemy_tracking()
    
    return module


def _instrument_requests_module(requests_module):
    """Instrument the requests module at import time."""
    if hasattr(requests_module, '_tracking_instrumented'):
        return
    
    original_post = requests_module.post
    original_get = requests_module.get
    original_request = requests_module.request
    
    def tracked_post(url, *args, **kwargs):
        tracker = get_tracker()
        data = kwargs.get('data') or kwargs.get('json') or {}
        tags = _extract_tags_from_dict(data, tracker)
        
        if tags:
            tracker.log_sharing_event(
                event_type='api_call',
                destination=str(url),
                data=_sanitize_data(data),
                tags=tags,
                metadata={'method': 'POST'}
            )
        
        return original_post(url, *args, **kwargs)
    
    def tracked_get(url, *args, **kwargs):
        tracker = get_tracker()
        params = kwargs.get('params', {})
        tags = _extract_tags_from_dict(params, tracker)
        
        if tags:
            tracker.log_sharing_event(
                event_type='api_call',
                destination=str(url),
                data=_sanitize_data(params),
                tags=tags,
                metadata={'method': 'GET'}
            )
        
        return original_get(url, *args, **kwargs)
    
    def tracked_request(method, url, *args, **kwargs):
        tracker = get_tracker()
        data = kwargs.get('data') or kwargs.get('json') or kwargs.get('params') or {}
        tags = _extract_tags_from_dict(data, tracker)
        
        if tags:
            tracker.log_sharing_event(
                event_type='api_call',
                destination=str(url),
                data=_sanitize_data(data),
                tags=tags,
                metadata={'method': method}
            )
        
        return original_request(method, url, *args, **kwargs)
    
    requests_module.post = tracked_post
    requests_module.get = tracked_get
    requests_module.request = tracked_request
    requests_module._tracking_instrumented = True


def _instrument_openai_module(openai_module):
    """Instrument OpenAI module at import time."""
    if hasattr(openai_module, '_tracking_instrumented'):
        return
    
    if hasattr(openai_module, 'OpenAI'):
        original_init = openai_module.OpenAI.__init__
        
        def tracked_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            
            # Instrument responses.create for Groq API
            if hasattr(self, 'responses') and hasattr(self.responses, 'create'):
                if not hasattr(self.responses, '_tracking_instrumented'):
                    original_create = self.responses.create
                    base_url = getattr(self, 'base_url', 'groq_api') or 'groq_api'
                    
                    def tracked_create(*args, **kwargs):
                        tracker = get_tracker()
                        input_val = kwargs.get('input', '')
                        tags = []
                        data_dict = {}
                        
                        if isinstance(input_val, str):
                            tags = _extract_tags_from_string(input_val, tracker)
                            data_dict['input'] = input_val[:500]
                        
                        if tags:
                            tracker.log_sharing_event(
                                event_type='api_call',
                                destination=base_url,
                                data=data_dict,
                                tags=tags,
                                metadata={'model': kwargs.get('model'), 'api_type': 'groq'}
                            )
                        
                        return original_create(*args, **kwargs)
                    
                    self.responses.create = tracked_create
                    self.responses._tracking_instrumented = True
        
        openai_module.OpenAI.__init__ = tracked_init
        openai_module._tracking_instrumented = True


def _add_flask_hooks(app_instance):
    """Add Flask hooks to an app instance."""
    tracker = get_tracker()
    
    @app_instance.before_request
    def _tag_flask_request_data():
        """Automatically tag PII data from Flask requests."""
        try:
            from flask import request, session
            
            identifier = None
            if hasattr(session, 'get') and session.get('user_id'):
                identifier = f"user_{session.get('user_id')}"
            elif hasattr(request, 'form') and request.form.get('email'):
                identifier = f"email_{request.form.get('email')}"
            
            if identifier:
                # Tag form data
                if hasattr(request, 'form'):
                    for key, value in request.form.items():
                        if is_pii_field(key) and value:
                            tracker.tag_data(value, key, identifier, f"flask.request.form.{key}")
                
                # Tag JSON data
                if hasattr(request, 'json') and request.json:
                    for key, value in request.json.items():
                        if is_pii_field(key) and value:
                            tracker.tag_data(value, key, identifier, f"flask.request.json.{key}")
                
                # Tag URL parameters
                if hasattr(request, 'args'):
                    for key, value in request.args.items():
                        if is_pii_field(key) and value:
                            tracker.tag_data(value, key, identifier, f"flask.request.args.{key}")
        except Exception:
            pass  # Silently fail


def _instrument_flask_sqlalchemy(module):
    """Instrument Flask/SQLAlchemy at import time."""
    if hasattr(module, '_tracking_instrumented'):
        return
    
    # Instrument Flask request handling
    if hasattr(module, 'Flask'):
        Flask = module.Flask
        
        # Patch Flask.__init__ to add hooks to new app instances
        if not hasattr(Flask, '_tracking_patched'):
            original_flask_init = Flask.__init__
            
            def tracked_flask_init(self, *args, **kwargs):
                original_flask_init(self, *args, **kwargs)
                _add_flask_hooks(self)
            
            Flask.__init__ = tracked_flask_init
            Flask._tracking_patched = True
        
        # Also instrument any existing Flask app instances
        # (in case Flask was imported before tracking was enabled)
        try:
            import flask
            if hasattr(flask, '_app_ctx_stack'):
                # Try to get current app from context
                try:
                    from flask import has_app_context, current_app
                    if has_app_context():
                        _add_flask_hooks(current_app)
                except:
                    pass
        except:
            pass
        
        module._tracking_instrumented = True


def _extract_tags_from_dict(data: Dict, tracker: RuntimeProvenanceTracker) -> List[DataTag]:
    """Extract tags from a dictionary."""
    tags = []
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (str, int, float)):
                tag = tracker.get_tags_for_value(value)
                if tag:
                    tags.append(tag)
    return tags


def _extract_tags_from_string(text: str, tracker: RuntimeProvenanceTracker) -> List[DataTag]:
    """Extract tags from a string by checking for tagged values."""
    import re
    tags = []
    
    # Extract numbers that might be tagged
    numbers = re.findall(r'\b\d+\.?\d*\b', text)
    for num in numbers:
        tag = tracker.get_tags_for_value(num)
        if tag:
            tags.append(tag)
    
    # Check full string
    tag = tracker.get_tags_for_value(text)
    if tag:
        tags.append(tag)
    
    # Deduplicate
    seen = set()
    unique_tags = []
    for tag in tags:
        if tag and tag.tag_id not in seen:
            unique_tags.append(tag)
            seen.add(tag.tag_id)
    
    return unique_tags


def _sanitize_data(data: Dict) -> Dict:
    """Sanitize data for logging (truncate long values)."""
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, str):
            sanitized[key] = value[:100]
        elif isinstance(value, (int, float)):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)[:100]
    return sanitized


# Python trace function for function call tracking
def _trace_function(frame, event, arg):
    """Python trace function to track function calls and data flow."""
    if not _tracking_enabled:
        return
    
    if event == 'call':
        # Tag function arguments if they contain PII
        tracker = get_tracker()
        code = frame.f_code
        func_name = code.co_name
        
        # Check local variables for PII
        for var_name, value in frame.f_locals.items():
            if is_pii_field(var_name) and isinstance(value, (str, int, float)) and value:
                # Try to get identifier from context
                identifier = _extract_identifier_from_frame(frame)
                if identifier:
                    tracker.tag_data(value, var_name, identifier, f"function.{func_name}.{var_name}")
    
    return _trace_function


def _extract_identifier_from_frame(frame) -> Optional[str]:
    """Extract user identifier from frame context."""
    # Check for Flask session
    try:
        from flask import has_request_context, session
        if has_request_context():
            user_id = session.get('user_id')
            if user_id:
                return f"user_{user_id}"
    except:
        pass
    
    # Check frame locals for user_id or email
    for key in ['user_id', 'id', 'email']:
        if key in frame.f_locals:
            value = frame.f_locals[key]
            if value:
                if key == 'email':
                    return f"email_{value}"
                else:
                    return f"user_{value}"
    
    return None


# SQLAlchemy instrumentation
def _setup_sqlalchemy_tracking():
    """Setup SQLAlchemy event listeners."""
    try:
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        
        @event.listens_for(Engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            tracker = get_tracker()
            
            if parameters and ('INSERT' in statement.upper() or 'UPDATE' in statement.upper()):
                tags = []
                data_dict = {}
                
                if isinstance(parameters, dict):
                    for key, value in parameters.items():
                        if isinstance(value, (str, int, float)):
                            tag = tracker.get_tags_for_value(value)
                            if tag:
                                tags.append(tag)
                            elif is_pii_field(key) and value:
                                identifier = _extract_identifier_from_sql_params(parameters)
                                if identifier:
                                    tracker.tag_data(value, key, identifier, f"database.write.{key}")
                                    tag = tracker.get_tags_for_value(value)
                                    if tag:
                                        tags.append(tag)
                                
                                if is_pii_field(key):
                                    data_dict[key] = str(value)[:100]
                
                if tags:
                    table_name = _extract_table_name(statement)
                    tracker.log_sharing_event(
                        event_type='database_write',
                        destination=f"database:{table_name}",
                        data=data_dict,
                        tags=tags,
                        metadata={'statement': statement[:200]}
                    )
        
        print("[Runtime Tracking] SQLAlchemy instrumentation active")
    except ImportError:
        pass


def _extract_identifier_from_sql_params(params: Dict) -> Optional[str]:
    """Extract identifier from SQL parameters."""
    if 'user_id' in params:
        return f"user_{params['user_id']}"
    if 'id' in params:
        return f"user_{params['id']}"
    if 'email' in params:
        return f"email_{params['email']}"
    return None


def _extract_table_name(statement: str) -> str:
    """Extract table name from SQL statement."""
    statement_upper = statement.upper()
    if 'INSERT' in statement_upper:
        parts = statement_upper.split('INSERT')
        if len(parts) > 1:
            return parts[1].split()[0].replace('INTO', '').strip()
    elif 'UPDATE' in statement_upper:
        parts = statement_upper.split('UPDATE')
        if len(parts) > 1:
            return parts[1].split()[0].strip()
    return 'unknown'


def enable_runtime_tracking():
    """Enable Python runtime-level tracking."""
    global _tracking_enabled
    
    if _tracking_enabled:
        return
    
    _tracking_enabled = True
    
    # Replace builtin import to instrument modules as they load
    __builtins__.__import__ = _tracking_import
    
    # Instrument already-loaded modules
    if 'requests' in sys.modules:
        _instrument_requests_module(sys.modules['requests'])
    if 'openai' in sys.modules:
        _instrument_openai_module(sys.modules['openai'])
    if 'flask' in sys.modules:
        _instrument_flask_sqlalchemy(sys.modules['flask'])
    
    # Also try to instrument any existing Flask app instances
    try:
        import flask
        if hasattr(flask, 'current_app'):
            try:
                from flask import has_app_context, current_app
                if has_app_context():
                    _add_flask_hooks(current_app)
            except:
                pass
    except:
        pass
    
    # Setup SQLAlchemy tracking
    _setup_sqlalchemy_tracking()
    
    # Enable function tracing (optional, can be performance-intensive)
    # sys.settrace(_trace_function)
    
    print("[Runtime Tracking] Python runtime instrumentation ENABLED")
    print("[Runtime Tracking] Tracking: HTTP requests, API calls, database operations, Flask requests")


def instrument_flask_app(app_instance):
    """Manually instrument a Flask app instance (useful if app was created before tracking enabled)."""
    _add_flask_hooks(app_instance)
    print(f"[Runtime Tracking] Instrumented Flask app: {app_instance.name}")


def disable_runtime_tracking():
    """Disable Python runtime-level tracking."""
    global _tracking_enabled
    _tracking_enabled = False
    __builtins__.__import__ = _original_import
    sys.settrace(None)
    print("[Runtime Tracking] Python runtime instrumentation DISABLED")


# Auto-enable if environment variable is set
if os.getenv('PYTHON_TRACKING_ENABLED', '').lower() in ('1', 'true', 'yes'):
    enable_runtime_tracking()

# Auto-enable on import (can be disabled by setting env var PYTHON_TRACKING_ENABLED=0)
elif os.getenv('PYTHON_TRACKING_ENABLED', '').lower() not in ('0', 'false', 'no'):
    enable_runtime_tracking()
