"""
Database Operation Tracker
Intercepts SQLAlchemy operations to log data storage and retrieval
"""

from sqlalchemy import event
from sqlalchemy.orm import Session
from runtime_tracker import get_tracker
from provenance_logger import get_logger
from typing import Any
import json

class DatabaseTracker:
    """
    Tracks database operations for provenance logging
    Hooks into SQLAlchemy events
    """
    
    def __init__(self, db=None):
        self.db = db
        self.tracker = get_tracker()
        self.logger = get_logger()
        self.tracked_tables = {'user', 'expense'}  # Tables containing personal data
        
        if db:
            self.init_db(db)
    
    def init_db(self, db):
        """Initialize database tracking hooks"""
        self.db = db
        
        # Hook into insert events
        event.listen(Session, 'before_flush', self.before_flush)
        event.listen(Session, 'after_flush', self.after_flush)
    
    def before_flush(self, session, flush_context, instances):
        """Called before database flush - track what's being written"""
        if not self.tracker.is_active():
            return
        
        # Store pending operations for after_flush
        if not hasattr(session, '_provenance_pending'):
            session._provenance_pending = []
        
        # Track new objects
        for obj in session.new:
            table_name = obj.__tablename__
            if table_name in self.tracked_tables:
                session._provenance_pending.append({
                    'type': 'INSERT',
                    'table': table_name,
                    'obj': obj,
                    'state': self._get_object_state(obj)
                })
        
        # Track modified objects
        for obj in session.dirty:
            table_name = obj.__tablename__
            if table_name in self.tracked_tables:
                session._provenance_pending.append({
                    'type': 'UPDATE',
                    'table': table_name,
                    'obj': obj,
                    'state': self._get_object_state(obj)
                })
        
        # Track deleted objects
        for obj in session.deleted:
            table_name = obj.__tablename__
            if table_name in self.tracked_tables:
                session._provenance_pending.append({
                    'type': 'DELETE',
                    'table': table_name,
                    'obj': obj,
                    'state': self._get_object_state(obj)
                })
    
    def after_flush(self, session, flush_context):
        """Called after database flush - log the operations"""
        if not self.tracker.is_active():
            return
        
        if not hasattr(session, '_provenance_pending'):
            return
        
        # Log all pending operations
        for op in session._provenance_pending:
            self._log_database_operation(op)
        
        # Clear pending operations
        session._provenance_pending = []
    
    def _log_database_operation(self, operation: dict):
        """Log a database operation"""
        op_type = operation['type']
        table_name = operation['table']
        obj = operation['obj']
        state = operation['state']
        
        # Extract owner_id
        owner_id = self._extract_owner_id(obj, table_name)
        
        # Get tag IDs for tracked data
        tag_ids = []
        for key, value in state.items():
            tag = self.tracker.get_tag(value)
            if tag:
                tag_ids.append(tag.tag_id)
        
        # Get record ID
        record_id = str(getattr(obj, 'id', None))
        
        # Create data preview
        data_preview = self._create_preview(state)
        
        # Log to provenance logger
        self.logger.log_database_operation(
            operation_type=op_type,
            table_name=table_name,
            owner_id=owner_id,
            tag_ids=tag_ids,
            record_id=record_id,
            data_preview=data_preview,
            metadata={'operation': op_type}
        )
        
        # Also log as sharing event since database is a "destination"
        self.tracker.log_data_sharing(
            data=state,
            destination=f"database_{table_name}",
            method="SQL_WRITE",
            metadata={
                'operation': op_type,
                'table': table_name,
                'owner_id': owner_id,
                'record_id': record_id
            }
        )
    
    def _get_object_state(self, obj) -> dict:
        """Get the current state of a database object"""
        state = {}
        for column in obj.__table__.columns:
            key = column.name
            if hasattr(obj, key):
                state[key] = getattr(obj, key)
        return state
    
    def _extract_owner_id(self, obj, table_name: str) -> str:
        """Extract owner identifier from object"""
        if table_name == 'user':
            return f"user_{obj.id}" if hasattr(obj, 'id') else "unknown"
        elif table_name == 'expense':
            return f"user_{obj.user_id}" if hasattr(obj, 'user_id') else "unknown"
        return "unknown"
    
    def _create_preview(self, state: dict, max_length: int = 200) -> str:
        """Create a preview of the data being stored"""
        try:
            # Filter out sensitive fields for preview
            filtered_state = {k: v for k, v in state.items() if k not in ['password_hash', 'password']}
            preview = json.dumps(filtered_state, default=str)
            if len(preview) > max_length:
                return preview[:max_length] + "..."
            return preview
        except:
            return str(state)[:max_length]


def create_database_tracker(db) -> DatabaseTracker:
    """Factory function to create database tracker"""
    return DatabaseTracker(db)
