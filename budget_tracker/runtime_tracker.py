"""
Runtime-Level Data Tracking System
Implements automatic tagging and provenance tracking for personal data
Based on SST Detection via Runtime-Level Instrumentation
"""

import sys
import functools
import threading
import uuid
from typing import Any, Dict, Set, Optional, Callable
from datetime import datetime
import inspect
import weakref

# Thread-local storage for tracking context
_tracking_context = threading.local()


class DataTag:
    """Represents a provenance tag attached to data"""
    
    def __init__(self, owner_id: str, data_type: str, source: str, timestamp: Optional[datetime] = None):
        self.tag_id = str(uuid.uuid4())
        self.owner_id = owner_id  # User identifier (e.g., email, user_id)
        self.data_type = data_type  # e.g., "name", "email", "expense", "income"
        self.source = source  # Where the data came from (e.g., "signup_form", "expense_form")
        self.timestamp = timestamp or datetime.utcnow()
        self.derived_from = []  # List of parent tag_ids if this is derived data
        self.transformations = []  # Operations applied to this data
        
    def add_transformation(self, operation: str, location: str):
        """Record a transformation applied to this data"""
        self.transformations.append({
            'operation': operation,
            'location': location,
            'timestamp': datetime.utcnow()
        })
        
    def derive(self, operation: str) -> 'DataTag':
        """Create a derived tag when data is transformed"""
        new_tag = DataTag(
            owner_id=self.owner_id,
            data_type=f"derived_{self.data_type}",
            source=f"derived_from_{self.source}"
        )
        new_tag.derived_from.append(self.tag_id)
        new_tag.add_transformation(operation, self._get_caller_location())
        return new_tag
    
    @staticmethod
    def _get_caller_location() -> str:
        """Get the location of the code that called this function"""
        frame = inspect.currentframe()
        try:
            # Go up the stack to find the actual caller
            caller_frame = frame.f_back.f_back.f_back
            if caller_frame:
                return f"{caller_frame.f_code.co_filename}:{caller_frame.f_lineno}:{caller_frame.f_code.co_name}"
        finally:
            del frame
        return "unknown"
    
    def to_dict(self) -> Dict:
        """Convert tag to dictionary for logging"""
        return {
            'tag_id': self.tag_id,
            'owner_id': self.owner_id,
            'data_type': self.data_type,
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'derived_from': self.derived_from,
            'transformations': self.transformations
        }


class TaggedData:
    """Wrapper for data with provenance tags"""
    
    def __init__(self, value: Any, tag: DataTag):
        self._value = value
        self._tag = tag
        
    @property
    def value(self):
        return self._value
        
    @property
    def tag(self):
        return self._tag
    
    def __repr__(self):
        return f"TaggedData(value={self._value}, tag_id={self._tag.tag_id})"


class RuntimeTracker:
    """Core runtime tracking system"""
    
    def __init__(self):
        self._tracked_objects = weakref.WeakValueDictionary()  # Maps object ids to tags
        self._active = False
        self._logger = None
        self._tracked_functions: Set[str] = set()
        
    def set_logger(self, logger):
        """Set the provenance logger"""
        self._logger = logger
        
    def activate(self):
        """Activate runtime tracking"""
        self._active = True
        
    def deactivate(self):
        """Deactivate runtime tracking"""
        self._active = False
        
    def is_active(self) -> bool:
        return self._active
    
    def tag_data(self, value: Any, owner_id: str, data_type: str, source: str) -> Any:
        """
        Tag a piece of data with provenance information
        This is the core tagging function - data entering the system gets tagged here
        """
        if not self._active:
            return value
            
        tag = DataTag(owner_id=owner_id, data_type=data_type, source=source)
        
        # Store tag metadata
        self._tracked_objects[id(value)] = tag
        
        # Log the tagging event
        if self._logger:
            self._logger.log_data_collection(value, tag)
            
        # Store in thread-local context
        self._set_current_tag(tag)
        
        return value
    
    def get_tag(self, value: Any) -> Optional[DataTag]:
        """Get the tag associated with a value"""
        return self._tracked_objects.get(id(value))
    
    def propagate_tag(self, source_value: Any, derived_value: Any, operation: str) -> Any:
        """
        Propagate a tag from source data to derived data
        This tracks data transformations
        """
        if not self._active:
            return derived_value
            
        source_tag = self.get_tag(source_value)
        if source_tag:
            # Create derived tag
            new_tag = source_tag.derive(operation)
            self._tracked_objects[id(derived_value)] = new_tag
            
            if self._logger:
                self._logger.log_transformation(source_value, derived_value, operation, source_tag, new_tag)
                
            self._set_current_tag(new_tag)
            
        return derived_value
    
    def log_data_sharing(self, data: Any, destination: str, method: str, metadata: Dict = None):
        """
        Log when data is shared with third parties or external systems
        This is critical for SST detection
        """
        if not self._active or not self._logger:
            return
            
        tag = self.get_tag(data)
        if tag or metadata:  # Log even without tag if we have metadata
            self._logger.log_sharing_event(
                data=data,
                tag=tag,
                destination=destination,
                method=method,
                metadata=metadata or {}
            )
    
    def track_function(self, func: Callable) -> Callable:
        """
        Decorator to automatically track function calls and propagate tags
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not self._active:
                return func(*args, **kwargs)
            
            # Track function entry
            func_name = f"{func.__module__}.{func.__name__}"
            self._tracked_functions.add(func_name)
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Check if any arguments had tags
            for arg in args:
                if self.get_tag(arg):
                    # Propagate tag to result
                    self.propagate_tag(arg, result, f"function_{func_name}")
                    break
            
            return result
        
        return wrapper
    
    def _set_current_tag(self, tag: DataTag):
        """Store current tag in thread-local storage"""
        if not hasattr(_tracking_context, 'tags'):
            _tracking_context.tags = []
        _tracking_context.tags.append(tag)
    
    def get_current_tags(self) -> list:
        """Get all tags in current tracking context"""
        if not hasattr(_tracking_context, 'tags'):
            return []
        return _tracking_context.tags
    
    def clear_context(self):
        """Clear the current tracking context"""
        if hasattr(_tracking_context, 'tags'):
            _tracking_context.tags = []


# Global tracker instance
_global_tracker = RuntimeTracker()


def get_tracker() -> RuntimeTracker:
    """Get the global runtime tracker instance"""
    return _global_tracker


def tag_data(value: Any, owner_id: str, data_type: str, source: str) -> Any:
    """Convenience function to tag data"""
    return _global_tracker.tag_data(value, owner_id, data_type, source)


def propagate_tag(source_value: Any, derived_value: Any, operation: str) -> Any:
    """Convenience function to propagate tags"""
    return _global_tracker.propagate_tag(source_value, derived_value, operation)


def log_sharing(data: Any, destination: str, method: str, metadata: Dict = None):
    """Convenience function to log data sharing"""
    _global_tracker.log_data_sharing(data, destination, method, metadata)


def tracked(func: Callable) -> Callable:
    """Decorator for automatic function tracking"""
    return _global_tracker.track_function(func)
