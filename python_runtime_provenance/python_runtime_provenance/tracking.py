"""
Python Runtime-Level Instrumentation for Server-Side Tracking (SST) Detection

This module provides runtime-level instrumentation that works at the Python interpreter
level, requiring NO changes to application code. It can be activated via:
1. Environment variable: PYTHON_TRACKING_ENABLED=1
2. Import hook: import python_runtime_provenance (auto-activates)
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
        self.DataTagModel = None
        self.DataSharingEvent = None
        self.DataLineage = None
        
    def connect_database(self, db_session, DataTagModel=None, DataSharingEvent=None, DataLineage=None):
        """Connect tracker to an external database (e.g., Flask-SQLAlchemy)."""
        self.db_session = db_session
        self.DataTagModel = DataTagModel
        self.DataSharingEvent = DataSharingEvent
        self.DataLineage = DataLineage
    
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
        if self.db_session and self.DataTagModel:
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
        if self.db_session and self.DataSharingEvent:
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


def is_tracking_enabled() -> bool:
    """Check if runtime tracking is enabled."""
    return _tracking_enabled


def is_pii_field(field_name: str) -> bool:
    """Check if a field name indicates PII."""
    field_lower = field_name.lower()
    return any(pii in field_lower for pii in PII_FIELDS)


# Deep runtime instrumentation (no monkey patching)
from .runtime_instrumentation import (
    enable_deep_instrumentation,
    disable_deep_instrumentation,
    is_deep_instrumentation_enabled
)

# Import hooks for module-level instrumentation
_original_import = __builtins__.__import__


def _tracking_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Wrapped import that instruments modules using deep runtime hooks."""
    module = _original_import(name, globals, locals, fromlist, level)
    
    # Use deep instrumentation instead of monkey patching
    # The runtime instrumentation will catch function calls automatically
    if name == 'requests' or name == 'openai' or name == 'flask' or 'sqlalchemy' in name:
        # Deep instrumentation will handle these via sys.settrace
        pass
    
    return module


# Removed monkey patching - using deep runtime instrumentation instead
# The runtime_instrumentation module handles this via sys.settrace


# Removed monkey patching - using deep runtime instrumentation instead
# The runtime_instrumentation module handles this via sys.settrace


def _add_flask_hooks(app_instance):
    """Add Flask hooks to an app instance (minimal - deep instrumentation handles the rest)."""
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
                # Tag form data (deep instrumentation will catch function calls)
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
    """Instrument Flask at import time (minimal - deep instrumentation handles the rest)."""
    if hasattr(module, '_tracking_instrumented'):
        return
    
    # Only add Flask hooks - deep instrumentation handles function calls
    if hasattr(module, 'Flask'):
        Flask = module.Flask
        
        if not hasattr(Flask, '_tracking_patched'):
            original_flask_init = Flask.__init__
            
            def tracked_flask_init(self, *args, **kwargs):
                original_flask_init(self, *args, **kwargs)
                _add_flask_hooks(self)
            
            Flask.__init__ = tracked_flask_init
            Flask._tracking_patched = True
        
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
    """Enable Python runtime-level tracking using deep instrumentation."""
    global _tracking_enabled
    
    if _tracking_enabled:
        return
    
    _tracking_enabled = True
    
    # Enable deep runtime instrumentation (sys.settrace, sys.setprofile)
    enable_deep_instrumentation()
    
    # Replace builtin import for module-level hooks
    __builtins__.__import__ = _tracking_import
    
    # Instrument Flask if already loaded
    if 'flask' in sys.modules:
        _instrument_flask_sqlalchemy(sys.modules['flask'])
    
    # Setup SQLAlchemy tracking (uses events, not monkey patching)
    _setup_sqlalchemy_tracking()
    
    print("[Runtime Tracking] Deep Python runtime instrumentation ENABLED")
    print("[Runtime Tracking] Using: sys.settrace, sys.setprofile, import hooks")
    print("[Runtime Tracking] Tracking: Function calls, data flow, HTTP requests, API calls, database operations")


def instrument_flask_app(app_instance):
    """Manually instrument a Flask app instance (useful if app was created before tracking enabled)."""
    _add_flask_hooks(app_instance)
    print(f"[Runtime Tracking] Instrumented Flask app: {app_instance.name}")


def disable_runtime_tracking():
    """Disable Python runtime-level tracking."""
    global _tracking_enabled
    _tracking_enabled = False
    
    # Disable deep instrumentation
    disable_deep_instrumentation()
    
    # Restore original import
    __builtins__.__import__ = _original_import
    
    print("[Runtime Tracking] Deep Python runtime instrumentation DISABLED")
