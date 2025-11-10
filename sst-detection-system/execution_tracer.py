"""
Execution Tracer - Uses sys.settrace to track Python execution at runtime
"""
import sys
import types
import inspect
from typing import Any, Dict, Optional, Set
from collections import defaultdict

import sys
import os
# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from budget_tracker.provenance import get_tracker, DataType
    from budget_tracker.audit_logger import get_logger, SharingEventType
except ImportError:
    # Fallback if running standalone
    try:
        from provenance import get_tracker, DataType
        from audit_logger import get_logger, SharingEventType
    except ImportError:
        # Create minimal stubs if modules not available
        class DataType:
            EMAIL = "email"
            INCOME = "income"
            DERIVED = "derived"
        
        def get_tracker():
            return None
        
        def get_logger():
            return None


class ExecutionTracer:
    """
    Traces Python execution using sys.settrace to detect data flow
    without monkey patching.
    """
    
    def __init__(self):
        self.tracker = get_tracker()
        self.logger = get_logger()
        self.enabled = False
        self._original_trace = None
        self._call_stack = []
        self._variable_tags = {}  # Track which variables are tagged
        self._function_calls = defaultdict(list)
        self._external_calls = []  # Track calls to external APIs
        
    def start(self):
        """Start execution tracing"""
        if self.enabled:
            return
        
        self._original_trace = sys.gettrace()
        sys.settrace(self._trace_function)
        self.enabled = True
        print("[ExecutionTracer] Started execution tracing")
    
    def stop(self):
        """Stop execution tracing"""
        if not self.enabled:
            return
        
        sys.settrace(self._original_trace)
        self.enabled = False
        print("[ExecutionTracer] Stopped execution tracing")
    
    def _trace_function(self, frame, event, arg):
        """
        Trace function called by Python interpreter for every event
        """
        if not self.enabled:
            return None
        
        try:
            # Get frame information
            code = frame.f_code
            filename = code.co_filename
            func_name = code.co_name
            line_no = frame.f_lineno
            
            # Skip internal Python files
            if filename.startswith('<') or 'site-packages' in filename:
                return self._trace_function
            
            # Handle different event types
            if event == 'call':
                return self._handle_call(frame, event, arg)
            elif event == 'return':
                return self._handle_return(frame, event, arg)
            elif event == 'line':
                return self._handle_line(frame, event, arg)
            elif event == 'exception':
                return self._handle_exception(frame, event, arg)
            
            return self._trace_function
        except Exception as e:
            # Don't break execution if tracing fails
            return self._trace_function
    
    def _handle_call(self, frame, event, arg):
        """Handle function call events"""
        code = frame.f_code
        func_name = code.co_name
        filename = code.co_filename
        
        # Track call stack
        self._call_stack.append({
            'function': func_name,
            'file': filename,
            'line': frame.f_lineno
        })
        
        # Check if this is an external API call
        if self._is_external_api_call(frame):
            self._track_external_call(frame)
        
        # Check if this is a data operation
        if self._is_data_operation(func_name, frame):
            self._track_data_operation(frame)
        
        return self._trace_function
    
    def _handle_return(self, frame, event, arg):
        """Handle function return events"""
        if self._call_stack:
            self._call_stack.pop()
        
        # Check if return value contains tagged data
        if arg is not None:
            self._check_return_value(arg, frame)
        
        return self._trace_function
    
    def _handle_line(self, frame, event, arg):
        """Handle line execution events"""
        # Check for assignments that might involve tagged data
        code = frame.f_code
        line_no = frame.f_lineno
        
        # Get local variables
        locals_dict = frame.f_locals
        
        # Check if any local variables are tagged
        for var_name, var_value in locals_dict.items():
            if var_value is not None:
                # Check if value is tagged
                if self.tracker.has_tag(var_value):
                    self._variable_tags[f"{code.co_filename}:{line_no}:{var_name}"] = var_value
                
                # Check if value contains personal data patterns
                if isinstance(var_value, str):
                    detected_type = self.tracker.detect_personal_data(var_value)
                    if detected_type:
                        # Auto-tag if not already tagged
                        if not self.tracker.has_tag(var_value):
                            owner_id = self._get_owner_from_context(frame)
                            if owner_id:
                                self.tracker.tag_object(var_value, owner_id, detected_type, f"auto_detected:{code.co_filename}:{line_no}")
        
        return self._trace_function
    
    def _handle_exception(self, frame, event, arg):
        """Handle exception events"""
        return self._trace_function
    
    def _is_external_api_call(self, frame) -> bool:
        """Check if this is a call to an external API"""
        code = frame.f_code
        filename = code.co_filename
        
        # Check for HTTP libraries
        if 'requests' in filename or 'urllib' in filename:
            return True
        
        # Check for OpenAI/Groq
        if 'openai' in filename.lower():
            return True
        
        # Check function name patterns
        func_name = code.co_name
        external_patterns = ['post', 'get', 'put', 'delete', 'request', 'urlopen', 'create', 'send']
        if any(pattern in func_name.lower() for pattern in external_patterns):
            # Check if it's in an external library context
            if 'site-packages' in filename:
                return True
        
        return False
    
    def _track_external_call(self, frame):
        """Track an external API call"""
        code = frame.f_code
        func_name = code.co_name
        filename = code.co_filename
        
        # Get function arguments
        args = inspect.getargvalues(frame)
        locals_dict = frame.f_locals
        
        # Extract tagged data from arguments
        owner_ids = set()
        tag_ids = []
        data_types = []
        
        # Check all local variables for tagged data
        for var_name, var_value in locals_dict.items():
            if var_value is not None:
                tag = self.tracker.get_tag(var_value)
                if tag:
                    owner_ids.add(tag.owner_id)
                    tag_ids.append(tag.tag_id)
                    data_types.append(tag.data_type.value)
                
                # Recursively check containers
                self._extract_tags_from_value(var_value, owner_ids, tag_ids, data_types)
        
        # Log the external call
        if owner_ids or tag_ids:
            destination = f"{filename}:{func_name}"
            for owner_id in owner_ids:
                self.logger.log_external_api(
                    api_name=self._get_api_name(filename),
                    endpoint=func_name,
                    data=locals_dict,
                    owner_id=owner_id,
                    tag_ids=tag_ids,
                    data_types=data_types
                )
    
    def _is_data_operation(self, func_name: str, frame) -> bool:
        """Check if this is a data operation (database, file, etc.)"""
        filename = frame.f_code.co_filename
        
        # Database operations
        if 'sqlalchemy' in filename or 'db' in func_name.lower():
            return True
        
        # File operations
        if 'open' in func_name.lower() and 'write' in str(frame.f_locals.get('mode', '')):
            return True
        
        return False
    
    def _track_data_operation(self, frame):
        """Track a data operation"""
        # Similar to _track_external_call but for data operations
        pass
    
    def _check_return_value(self, return_value: Any, frame):
        """Check if return value contains tagged data and propagate tags"""
        if return_value is None:
            return
        
        # Check if return value itself is tagged
        if self.tracker.has_tag(return_value):
            return
        
        # Check if return value is derived from tagged data
        # This would require tracking the call stack and operations
        # For now, we'll check if it's a container with tagged items
        if isinstance(return_value, (dict, list, tuple)):
            for item in (return_value.values() if isinstance(return_value, dict) else return_value):
                if item is not None:
                    tag = self.tracker.get_tag(item)
                    if tag:
                        # Propagate tag to container
                        self.tracker.propagate_tag(item, return_value, "return_value")
                        break
    
    def _extract_tags_from_value(self, value: Any, owner_ids: set, tag_ids: list, data_types: list):
        """Recursively extract tags from a value"""
        if value is None:
            return
        
        # Check if value itself is tagged
        tag = self.tracker.get_tag(value)
        if tag:
            owner_ids.add(tag.owner_id)
            tag_ids.append(tag.tag_id)
            data_types.append(tag.data_type.value)
        
        # Check containers
        if isinstance(value, dict):
            for v in value.values():
                self._extract_tags_from_value(v, owner_ids, tag_ids, data_types)
        elif isinstance(value, (list, tuple)):
            for v in value:
                self._extract_tags_from_value(v, owner_ids, tag_ids, data_types)
    
    def _get_owner_from_context(self, frame) -> Optional[str]:
        """Try to extract owner_id from execution context"""
        # Look for user_id in local/global variables
        for f in [frame] + list(self._get_frame_chain(frame)):
            # Check locals
            if 'user_id' in f.f_locals:
                return str(f.f_locals['user_id'])
            if 'user' in f.f_locals:
                user = f.f_locals['user']
                if hasattr(user, 'id'):
                    return str(user.id)
                if hasattr(user, 'email'):
                    return user.email
            
            # Check globals
            if 'user_id' in f.f_globals:
                return str(f.f_globals['user_id'])
        
        return None
    
    def _get_frame_chain(self, frame):
        """Get chain of parent frames"""
        frames = []
        current = frame.f_back
        while current and len(frames) < 10:  # Limit depth
            frames.append(current)
            current = current.f_back
        return frames
    
    def _get_api_name(self, filename: str) -> str:
        """Extract API name from filename"""
        if 'openai' in filename.lower() or 'groq' in filename.lower():
            return "OpenAI/Groq"
        elif 'requests' in filename:
            return "HTTP/Requests"
        elif 'urllib' in filename:
            return "HTTP/urllib"
        else:
            return "External API"
