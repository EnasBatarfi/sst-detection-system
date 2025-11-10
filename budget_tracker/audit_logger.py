"""
Audit Logger Module
Logs all data sharing events for compliance and transparency.
"""
import time
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
from urllib.parse import urlparse
import traceback


class SharingEventType(Enum):
    """Types of data sharing events"""
    HTTP_REQUEST = "http_request"
    DATABASE_READ = "database_read"
    DATABASE_WRITE = "database_write"
    FILE_WRITE = "file_write"
    EXTERNAL_API = "external_api"
    EMAIL_SEND = "email_send"
    UNKNOWN = "unknown"


@dataclass
class SharingEvent:
    """Represents a data sharing event"""
    event_id: str
    event_type: SharingEventType
    timestamp: float
    owner_id: str  # User whose data is being shared
    destination: str  # Where data is being sent
    data_types: List[str]  # Types of personal data shared
    tag_ids: List[str]  # Provenance tag IDs involved
    metadata: Dict[str, Any]  # Additional event metadata
    stack_trace: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp,
            'owner_id': self.owner_id,
            'destination': self.destination,
            'data_types': self.data_types,
            'tag_ids': self.tag_ids,
            'metadata': self.metadata,
            'stack_trace': self.stack_trace
        }


class AuditLogger:
    """Logs data sharing events for audit purposes"""
    
    def __init__(self, storage_callback=None):
        """
        Initialize audit logger
        
        Args:
            storage_callback: Function to call with SharingEvent for storage
        """
        self.storage_callback = storage_callback
        self.events: List[SharingEvent] = []
        self.enabled = True
    
    def log_sharing_event(self, event_type: SharingEventType, owner_id: str,
                         destination: str, data_types: List[str],
                         tag_ids: List[str], metadata: Dict[str, Any] = None,
                         capture_stack: bool = True):
        """Log a data sharing event"""
        if not self.enabled:
            return
        
        import uuid
        event = SharingEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=time.time(),
            owner_id=owner_id,
            destination=destination,
            data_types=data_types,
            tag_ids=tag_ids,
            metadata=metadata or {},
            stack_trace=traceback.format_stack()[:-1] if capture_stack else None
        )
        
        self.events.append(event)
        
        # Call storage callback if provided
        if self.storage_callback:
            try:
                self.storage_callback(event)
            except Exception as e:
                print(f"Error in storage callback: {e}")
    
    def log_http_request(self, url: str, method: str, data: Any,
                        owner_id: str, tag_ids: List[str], data_types: List[str]):
        """Log an HTTP request that shares data"""
        parsed = urlparse(url)
        destination = f"{parsed.scheme}://{parsed.netloc}"
        
        metadata = {
            'url': url,
            'method': method,
            'path': parsed.path,
            'has_data': data is not None
        }
        
        self.log_sharing_event(
            event_type=SharingEventType.HTTP_REQUEST,
            owner_id=owner_id,
            destination=destination,
            data_types=data_types,
            tag_ids=tag_ids,
            metadata=metadata
        )
    
    def log_external_api(self, api_name: str, endpoint: str, data: Any,
                        owner_id: str, tag_ids: List[str], data_types: List[str]):
        """Log an external API call"""
        metadata = {
            'api_name': api_name,
            'endpoint': endpoint,
            'has_data': data is not None
        }
        
        self.log_sharing_event(
            event_type=SharingEventType.EXTERNAL_API,
            owner_id=owner_id,
            destination=f"{api_name}:{endpoint}",
            data_types=data_types,
            tag_ids=tag_ids,
            metadata=metadata
        )
    
    def log_database_operation(self, operation: str, table: str, owner_id: str,
                              tag_ids: List[str], data_types: List[str],
                              record_id: Any = None):
        """Log a database operation"""
        event_type = SharingEventType.DATABASE_WRITE if operation == 'write' else SharingEventType.DATABASE_READ
        
        metadata = {
            'operation': operation,
            'table': table,
            'record_id': str(record_id) if record_id else None
        }
        
        self.log_sharing_event(
            event_type=event_type,
            owner_id=owner_id,
            destination=f"database:{table}",
            data_types=data_types,
            tag_ids=tag_ids,
            metadata=metadata
        )
    
    def get_events_by_owner(self, owner_id: str) -> List[SharingEvent]:
        """Get all events for a specific owner"""
        return [e for e in self.events if e.owner_id == owner_id]
    
    def get_events_by_destination(self, destination: str) -> List[SharingEvent]:
        """Get all events to a specific destination"""
        return [e for e in self.events if e.destination == destination]
    
    def get_all_events(self) -> List[SharingEvent]:
        """Get all logged events"""
        return self.events.copy()
    
    def clear(self):
        """Clear all events"""
        self.events.clear()


# Global instance
_logger = AuditLogger()


def get_logger() -> AuditLogger:
    """Get the global audit logger instance"""
    return _logger


def set_storage_callback(callback):
    """Set the storage callback for audit events"""
    _logger.storage_callback = callback
