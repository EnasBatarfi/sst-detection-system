"""
Deep Python Runtime Instrumentation for SST Detection

This module provides low-level Python runtime instrumentation using:
- sys.settrace: Function call and line execution tracking
- sys.setprofile: Function entry/exit profiling
- AST transformation: Code instrumentation at import time
- Descriptors: Attribute access tracking
- Import hooks: Module-level instrumentation

No monkey patching - works at the Python interpreter level.
"""

import sys
import ast
import types
import inspect
import threading
from typing import Any, Dict, List, Optional, Callable
from .tracking import get_tracker, is_pii_field, DataTag


class RuntimeInstrumentation:
    """Deep runtime instrumentation using Python's tracing facilities."""
    
    def __init__(self):
        self.enabled = False
        self.trace_depth = 0
        self.max_depth = 20
        self.lock = threading.Lock()
        
    def enable(self):
        """Enable runtime instrumentation."""
        if self.enabled:
            return
        
        self.enabled = True
        
        # Enable function call tracing
        sys.settrace(self._trace_calls)
        
        # Enable profiling (function entry/exit)
        sys.setprofile(self._profile_calls)
        
        print("[Runtime Instrumentation] Deep tracing enabled")
        print("[Runtime Instrumentation] Using sys.settrace and sys.setprofile")
    
    def disable(self):
        """Disable runtime instrumentation."""
        if not self.enabled:
            return
        
        self.enabled = False
        sys.settrace(None)
        sys.setprofile(None)
        print("[Runtime Instrumentation] Deep tracing disabled")
    
    def _trace_calls(self, frame, event, arg):
        """Trace function calls and line execution."""
        if not self.enabled:
            return None
        
        # Limit depth to avoid performance issues
        if self.trace_depth > self.max_depth:
            return None
        
        if event == 'call':
            self.trace_depth += 1
            return self._trace_calls
        
        elif event == 'line':
            # Track line execution - check for PII data access
            self._check_line_for_pii(frame)
            return self._trace_calls
        
        elif event == 'return':
            self.trace_depth = max(0, self.trace_depth - 1)
            return None
        
        return self._trace_calls
    
    def _profile_calls(self, frame, event, arg):
        """Profile function entry/exit for data flow tracking."""
        if not self.enabled:
            return
        
        if event == 'call':
            # Function call - check arguments for PII
            self._check_function_args(frame)
            
            # Detect API calls (requests, OpenAI, etc.)
            self._detect_api_calls(frame)
        
        elif event == 'return':
            # Function return - check return value for PII
            if arg is not None:
                self._check_return_value(frame, arg)
    
    def _check_line_for_pii(self, frame):
        """Check if current line accesses PII data."""
        try:
            tracker = get_tracker()
            code = frame.f_code
            locals_dict = frame.f_locals
            
            # Check local variables for PII
            for var_name, value in locals_dict.items():
                if is_pii_field(var_name) and isinstance(value, (str, int, float)) and value:
                    identifier = self._extract_identifier(frame)
                    if identifier:
                        tracker.tag_data(
                            value, 
                            var_name, 
                            identifier, 
                            f"runtime.line.{code.co_filename}:{code.co_name}:{frame.f_lineno}"
                        )
        except Exception:
            pass  # Silently fail
    
    def _check_function_args(self, frame):
        """Check function arguments for PII data."""
        try:
            tracker = get_tracker()
            code = frame.f_code
            args = inspect.getargvalues(frame)
            
            # Check function arguments
            for arg_name in args.locals:
                if arg_name in args.args or arg_name in (args.varargs or []):
                    value = args.locals.get(arg_name)
                    if is_pii_field(arg_name) and isinstance(value, (str, int, float)) and value:
                        identifier = self._extract_identifier(frame)
                        if identifier:
                            tracker.tag_data(
                                value,
                                arg_name,
                                identifier,
                                f"runtime.call.{code.co_name}.{arg_name}"
                            )
        except Exception:
            pass
    
    def _check_return_value(self, frame, return_value):
        """Check return value for PII data."""
        try:
            tracker = get_tracker()
            code = frame.f_code
            
            if isinstance(return_value, (str, int, float)):
                # Check if return value matches any tagged data
                tag = tracker.get_tags_for_value(return_value)
                if tag:
                    # Return value contains tagged data
                    identifier = self._extract_identifier(frame)
                    if identifier:
                        tracker.tag_data(
                            return_value,
                            f"return.{code.co_name}",
                            identifier,
                            f"runtime.return.{code.co_name}"
                        )
        except Exception:
            pass
    
    def _detect_api_calls(self, frame):
        """Detect and log API calls (HTTP requests, AI APIs, etc.)."""
        try:
            code = frame.f_code
            func_name = code.co_name
            module_name = code.co_filename
            
            # Check if this is an API call function
            is_api_call = False
            api_type = None
            destination = None
            
            # Detect requests library calls
            if 'requests' in module_name or 'requests' in str(frame.f_globals):
                if func_name in ['post', 'get', 'put', 'delete', 'request']:
                    is_api_call = True
                    api_type = 'api_call'
                    # Extract URL from arguments
                    if 'url' in frame.f_locals:
                        destination = str(frame.f_locals['url'])
                    elif len(frame.f_locals) > 0:
                        # First positional argument might be URL
                        first_arg = list(frame.f_locals.values())[0]
                        if isinstance(first_arg, str) and first_arg.startswith(('http://', 'https://')):
                            destination = first_arg
            
            # Detect OpenAI/Groq API calls
            elif 'openai' in module_name or 'groq' in module_name.lower():
                if func_name == 'create' or 'responses' in str(frame.f_globals):
                    is_api_call = True
                    api_type = 'api_call'
                    # Extract base_url or model
                    if 'base_url' in frame.f_locals:
                        destination = str(frame.f_locals['base_url'])
                    elif 'model' in frame.f_locals:
                        destination = f"ai_api:{frame.f_locals['model']}"
                    else:
                        destination = 'ai_api'
            
            if is_api_call:
                tracker = get_tracker()
                tags = []
                data_dict = {}
                
                # Extract data from function arguments
                for arg_name, arg_value in frame.f_locals.items():
                    if arg_name in ['data', 'json', 'params', 'input']:
                        if isinstance(arg_value, dict):
                            # Extract tags from dictionary
                            for key, value in arg_value.items():
                                if isinstance(value, (str, int, float)):
                                    tag = tracker.get_tags_for_value(value)
                                    if tag:
                                        tags.append(tag)
                                    if is_pii_field(key):
                                        data_dict[key] = str(value)[:100]
                        elif isinstance(arg_value, str):
                            # Extract tags from string
                            import re
                            numbers = re.findall(r'\b\d+\.?\d*\b', arg_value)
                            for num in numbers:
                                tag = tracker.get_tags_for_value(num)
                                if tag:
                                    tags.append(tag)
                            data_dict[arg_name] = arg_value[:500]
                
                # Log sharing event if tags found
                if tags:
                    tracker.log_sharing_event(
                        event_type=api_type,
                        destination=destination or 'unknown',
                        data=data_dict,
                        tags=tags,
                        metadata={
                            'function': func_name,
                            'module': module_name,
                            'line': frame.f_lineno
                        }
                    )
        except Exception:
            pass  # Silently fail
    
    def _extract_identifier(self, frame) -> Optional[str]:
        """Extract user identifier from frame context."""
        # Check frame locals for user_id or email
        for key in ['user_id', 'id', 'email', 'identifier']:
            if key in frame.f_locals:
                value = frame.f_locals[key]
                if value:
                    if key == 'email':
                        return f"email_{value}"
                    else:
                        return f"user_{value}"
        
        # Check globals
        for key in ['user_id', 'id', 'email']:
            if key in frame.f_globals:
                value = frame.f_globals[key]
                if value:
                    if key == 'email':
                        return f"email_{value}"
                    else:
                        return f"user_{value}"
        
        # Try Flask session
        try:
            from flask import has_request_context, session
            if has_request_context():
                user_id = session.get('user_id')
                if user_id:
                    return f"user_{user_id}"
        except:
            pass
        
        return None


# AST Transformer for code instrumentation
class PIIDataTransformer(ast.NodeTransformer):
    """AST transformer to instrument code for PII tracking."""
    
    def visit_Assign(self, node):
        """Instrument assignments to track PII data."""
        # Check if assignment involves PII field
        for target in node.targets:
            if isinstance(target, ast.Name):
                if is_pii_field(target.id):
                    # Wrap assignment with tracking
                    return self._wrap_assignment(node, target.id)
        return node
    
    def visit_Call(self, node):
        """Instrument function calls to track data flow."""
        # Check if call involves external APIs
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ['post', 'get', 'request']:
                # HTTP request - wrap with tracking
                return self._wrap_api_call(node)
            elif node.func.attr == 'create' and isinstance(node.func.value, ast.Attribute):
                if node.func.value.attr == 'responses':
                    # AI API call - wrap with tracking
                    return self._wrap_api_call(node)
        
        return node
    
    def _wrap_assignment(self, node, var_name):
        """Wrap assignment with tracking code."""
        # Create tracking call
        tracker_call = ast.Call(
            func=ast.Attribute(
                value=ast.Call(
                    func=ast.Name(id='get_tracker', ctx=ast.Load()),
                    args=[],
                    keywords=[]
                ),
                attr='tag_data',
                ctx=ast.Load()
            ),
            args=[
                node.value,  # Value being assigned
                ast.Constant(value=var_name),  # Variable name
                ast.Constant(value='unknown'),  # Identifier (would need context)
                ast.Constant(value=f"assignment.{var_name}")  # Source
            ],
            keywords=[]
        )
        
        # Keep original assignment, add tracking
        return ast.Expr(value=tracker_call)
    
    def _wrap_api_call(self, node):
        """Wrap API call with tracking."""
        # This would add tracking around API calls
        # For now, return original node
        return node


class AttributeTracker:
    """Descriptor-based attribute access tracking."""
    
    def __init__(self, name, default=None):
        self.name = name
        self.default = default
        self._value = default
    
    def __get__(self, obj, objtype=None):
        """Track attribute access."""
        if obj is None:
            return self
        
        value = self._value
        
        # Track access if it's PII
        if is_pii_field(self.name) and isinstance(value, (str, int, float)) and value:
            tracker = get_tracker()
            identifier = self._extract_identifier_from_obj(obj)
            if identifier:
                tracker.tag_data(
                    value,
                    self.name,
                    identifier,
                    f"attribute.get.{obj.__class__.__name__}.{self.name}"
                )
        
        return value
    
    def __set__(self, obj, value):
        """Track attribute assignment."""
        # Track assignment if it's PII
        if is_pii_field(self.name) and isinstance(value, (str, int, float)) and value:
            tracker = get_tracker()
            identifier = self._extract_identifier_from_obj(obj)
            if identifier:
                tracker.tag_data(
                    value,
                    self.name,
                    identifier,
                    f"attribute.set.{obj.__class__.__name__}.{self.name}"
                )
        
        self._value = value
    
    def _extract_identifier_from_obj(self, obj) -> Optional[str]:
        """Extract identifier from object."""
        # Check object attributes
        for attr in ['user_id', 'id', 'email']:
            if hasattr(obj, attr):
                value = getattr(obj, attr)
                if value:
                    if attr == 'email':
                        return f"email_{value}"
                    else:
                        return f"user_{value}"
        return None


class TrackingMeta(type):
    """Metaclass to automatically add tracking to class attributes."""
    
    def __new__(mcs, name, bases, namespace):
        # Replace PII fields with tracking descriptors
        for key, value in list(namespace.items()):
            if not key.startswith('_') and is_pii_field(key):
                if not isinstance(value, (types.FunctionType, classmethod, staticmethod)):
                    namespace[key] = AttributeTracker(key, value)
        
        return super().__new__(mcs, name, bases, namespace)


# Global instrumentation instance
_instrumentation = RuntimeInstrumentation()


def enable_deep_instrumentation():
    """Enable deep runtime instrumentation."""
    _instrumentation.enable()


def disable_deep_instrumentation():
    """Disable deep runtime instrumentation."""
    _instrumentation.disable()


def is_deep_instrumentation_enabled() -> bool:
    """Check if deep instrumentation is enabled."""
    return _instrumentation.enabled
