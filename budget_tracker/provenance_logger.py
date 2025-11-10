"""
Provenance Logger - Audit Trail System
Logs all data collection, transformation, and sharing events
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
import sqlite3
import threading

class ProvenanceLogger:
    """
    Logs provenance events to database and/or files
    Maintains audit trail for GDPR/CCPA compliance
    """
    
    def __init__(self, db_path: str = None, log_dir: str = None, console_output: bool = True):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), 'provenance.db')
        self.log_dir = log_dir
        self.console_output = console_output
        self._lock = threading.Lock()
        self._init_database()
        
        if self.log_dir:
            Path(self.log_dir).mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """Initialize provenance database schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Data collection events
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    tag_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    value_preview TEXT,
                    metadata TEXT
                )
            ''')
            
            # Data transformation events
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_transformations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source_tag_id TEXT NOT NULL,
                    derived_tag_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    location TEXT,
                    metadata TEXT
                )
            ''')
            
            # Data sharing events (CRITICAL for SST detection)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_sharing_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    tag_id TEXT,
                    owner_id TEXT,
                    data_type TEXT,
                    destination TEXT NOT NULL,
                    method TEXT NOT NULL,
                    data_preview TEXT,
                    full_payload TEXT,
                    response_preview TEXT,
                    metadata TEXT
                )
            ''')
            
            # Database operations tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS database_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    table_name TEXT,
                    owner_id TEXT,
                    tag_ids TEXT,
                    record_id TEXT,
                    data_preview TEXT,
                    metadata TEXT
                )
            ''')
            
            # Create indexes for efficient querying
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_collections_owner ON data_collections(owner_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_collections_timestamp ON data_collections(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sharing_owner ON data_sharing_events(owner_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sharing_destination ON data_sharing_events(destination)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sharing_timestamp ON data_sharing_events(timestamp)')
            
            conn.commit()
    
    def log_data_collection(self, value: Any, tag):
        """Log when personal data is first collected"""
        with self._lock:
            event = {
                'event_type': 'DATA_COLLECTION',
                'timestamp': datetime.utcnow().isoformat(),
                'tag_id': tag.tag_id,
                'owner_id': tag.owner_id,
                'data_type': tag.data_type,
                'source': tag.source,
                'value_preview': self._preview_value(value)
            }
            
            self._write_to_db('data_collections', event)
            self._write_to_console(event)
            self._write_to_file(event)
    
    def log_transformation(self, source_value: Any, derived_value: Any, operation: str, source_tag, derived_tag):
        """Log when data is transformed/derived"""
        with self._lock:
            event = {
                'event_type': 'DATA_TRANSFORMATION',
                'timestamp': datetime.utcnow().isoformat(),
                'source_tag_id': source_tag.tag_id,
                'derived_tag_id': derived_tag.tag_id,
                'operation': operation,
                'location': derived_tag._get_caller_location(),
                'source_preview': self._preview_value(source_value),
                'derived_preview': self._preview_value(derived_value)
            }
            
            self._write_to_db('data_transformations', event)
            self._write_to_console(event)
            self._write_to_file(event)
    
    def log_sharing_event(self, data: Any, tag, destination: str, method: str, metadata: Dict):
        """
        Log when data is shared with external systems (CRITICAL for SST detection)
        This includes:
        - API calls to third parties (e.g., Groq, analytics)
        - Database writes
        - External service calls
        """
        with self._lock:
            event = {
                'event_type': 'DATA_SHARING',
                'timestamp': datetime.utcnow().isoformat(),
                'tag_id': tag.tag_id if tag else None,
                'owner_id': tag.owner_id if tag else metadata.get('owner_id', 'unknown'),
                'data_type': tag.data_type if tag else metadata.get('data_type', 'unknown'),
                'destination': destination,
                'method': method,
                'data_preview': self._preview_value(data),
                'full_payload': self._safe_json(data) if metadata.get('log_full_payload') else None,
                'response_preview': metadata.get('response_preview'),
                'metadata': json.dumps(metadata)
            }
            
            self._write_to_db('data_sharing_events', event)
            self._write_to_console(event, level='WARNING')  # Highlight sharing events
            self._write_to_file(event)
    
    def log_database_operation(self, operation_type: str, table_name: str, owner_id: str, 
                                tag_ids: list, record_id: str = None, data_preview: str = None, 
                                metadata: Dict = None):
        """Log database operations (INSERT, UPDATE, DELETE)"""
        with self._lock:
            event = {
                'event_type': 'DATABASE_OPERATION',
                'timestamp': datetime.utcnow().isoformat(),
                'operation_type': operation_type,
                'table_name': table_name,
                'owner_id': owner_id,
                'tag_ids': json.dumps(tag_ids),
                'record_id': record_id,
                'data_preview': data_preview,
                'metadata': json.dumps(metadata or {})
            }
            
            self._write_to_db('database_operations', event)
            self._write_to_console(event)
            self._write_to_file(event)
    
    def _write_to_db(self, table: str, event: Dict):
        """Write event to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Remove event_type as it's not in the table
                event_copy = event.copy()
                event_copy.pop('event_type', None)
                
                # Handle nested data
                for key in ['metadata', 'tag_ids']:
                    if key in event_copy and not isinstance(event_copy[key], str):
                        event_copy[key] = json.dumps(event_copy[key])
                
                # Dynamic insert based on table
                columns = ', '.join(event_copy.keys())
                placeholders = ', '.join(['?'] * len(event_copy))
                query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'
                
                cursor.execute(query, list(event_copy.values()))
                conn.commit()
        except Exception as e:
            print(f"[PROVENANCE ERROR] Failed to write to database: {e}")
    
    def _write_to_console(self, event: Dict, level: str = 'INFO'):
        """Write event to console"""
        if not self.console_output:
            return
            
        prefix = f"[PROVENANCE-{level}]"
        event_type = event.get('event_type', 'UNKNOWN')
        
        if event_type == 'DATA_SHARING':
            # Highlight data sharing events
            print(f"\n{'='*80}")
            print(f"{prefix} 🚨 DATA SHARING DETECTED 🚨")
            print(f"  Timestamp: {event['timestamp']}")
            print(f"  Owner: {event.get('owner_id', 'unknown')}")
            print(f"  Data Type: {event.get('data_type', 'unknown')}")
            print(f"  Destination: {event['destination']}")
            print(f"  Method: {event['method']}")
            print(f"  Preview: {event.get('data_preview', 'N/A')}")
            print(f"{'='*80}\n")
        else:
            print(f"{prefix} [{event_type}] {event.get('timestamp', '')} - "
                  f"Owner: {event.get('owner_id', 'N/A')} - "
                  f"{event.get('operation', event.get('data_type', 'N/A'))}")
    
    def _write_to_file(self, event: Dict):
        """Write event to JSON log file"""
        if not self.log_dir:
            return
            
        try:
            today = datetime.utcnow().strftime('%Y-%m-%d')
            log_file = os.path.join(self.log_dir, f'provenance_{today}.jsonl')
            
            with open(log_file, 'a') as f:
                f.write(json.dumps(event) + '\n')
        except Exception as e:
            print(f"[PROVENANCE ERROR] Failed to write to file: {e}")
    
    def _preview_value(self, value: Any, max_length: int = 100) -> str:
        """Create a safe preview of data for logging"""
        try:
            if value is None:
                return "None"
            
            str_val = str(value)
            if len(str_val) > max_length:
                return str_val[:max_length] + "..."
            return str_val
        except:
            return "<unprintable>"
    
    def _safe_json(self, data: Any) -> Optional[str]:
        """Safely convert data to JSON"""
        try:
            return json.dumps(data, default=str)
        except:
            return str(data)
    
    def query_user_data_flow(self, owner_id: str) -> Dict:
        """
        Query all data flows for a specific user
        Useful for GDPR data subject access requests
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get collections
            cursor.execute('''
                SELECT * FROM data_collections 
                WHERE owner_id = ? 
                ORDER BY timestamp DESC
            ''', (owner_id,))
            collections = [dict(row) for row in cursor.fetchall()]
            
            # Get sharing events
            cursor.execute('''
                SELECT * FROM data_sharing_events 
                WHERE owner_id = ? 
                ORDER BY timestamp DESC
            ''', (owner_id,))
            sharing_events = [dict(row) for row in cursor.fetchall()]
            
            # Get database operations
            cursor.execute('''
                SELECT * FROM database_operations 
                WHERE owner_id = ? 
                ORDER BY timestamp DESC
            ''', (owner_id,))
            db_operations = [dict(row) for row in cursor.fetchall()]
            
            return {
                'owner_id': owner_id,
                'collections': collections,
                'sharing_events': sharing_events,
                'database_operations': db_operations,
                'summary': {
                    'total_collections': len(collections),
                    'total_sharing_events': len(sharing_events),
                    'total_db_operations': len(db_operations),
                    'destinations': list(set(e['destination'] for e in sharing_events))
                }
            }
    
    def get_sharing_summary(self, start_date: str = None, end_date: str = None) -> list:
        """Get summary of all data sharing events"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = 'SELECT * FROM data_sharing_events WHERE 1=1'
            params = []
            
            if start_date:
                query += ' AND timestamp >= ?'
                params.append(start_date)
            if end_date:
                query += ' AND timestamp <= ?'
                params.append(end_date)
                
            query += ' ORDER BY timestamp DESC'
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


# Global logger instance
_global_logger = None

def get_logger() -> ProvenanceLogger:
    """Get or create the global provenance logger"""
    global _global_logger
    if _global_logger is None:
        _global_logger = ProvenanceLogger()
    return _global_logger
