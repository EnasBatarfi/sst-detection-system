"""
Runtime-Level Instrumentation Module
Intercepts operations at the Python runtime level to track data flow.
"""
import sys
import inspect
import functools
from typing import Any, Callable, Dict, List, Optional
import importlib.util

from provenance import get_tracker, ProvenanceTag, DataType, detect_personal_data
from audit_logger import get_logger, SharingEventType


class RuntimeTracker:
    """Runtime-level instrumentation for tracking data flow"""
    
    def __init__(self):
        self.tracker = get_tracker()
        self.logger = get_logger()
        self.enabled = True
        self._patched_modules = {}
        self._wrapped_functions = {}
    
    def start(self):
        """Start runtime tracking"""
        if not self.enabled:
            return
        
        # Patch requests library
        self._patch_requests()
        
        # Patch urllib
        self._patch_urllib()
        
        # Patch OpenAI client
        self._patch_openai()
        
        # Patch SQLAlchemy operations
        self._patch_sqlalchemy()
        
        print("[RuntimeTracker] Started runtime instrumentation")
    
    def stop(self):
        """Stop runtime tracking"""
        self.enabled = False
        # Restore original functions if needed
        print("[RuntimeTracker] Stopped runtime instrumentation")
    
    def _patch_requests(self):
        """Patch requests library to intercept HTTP calls"""
        try:
            import requests
            
            original_request = requests.request
            original_post = requests.post
            original_get = requests.get
            original_put = requests.put
            original_delete = requests.delete
            
            def wrapped_request(method, url, **kwargs):
                return self._intercept_http_call(original_request, method, url, **kwargs)
            
            def wrapped_post(url, **kwargs):
                return self._intercept_http_call(original_post, 'POST', url, **kwargs)
            
            def wrapped_get(url, **kwargs):
                return self._intercept_http_call(original_get, 'GET', url, **kwargs)
            
            def wrapped_put(url, **kwargs):
                return self._intercept_http_call(original_put, 'PUT', url, **kwargs)
            
            def wrapped_delete(url, **kwargs):
                return self._intercept_http_call(original_delete, 'DELETE', url, **kwargs)
            
            requests.request = wrapped_request
            requests.post = wrapped_post
            requests.get = wrapped_get
            requests.put = wrapped_put
            requests.delete = wrapped_delete
            
            self._patched_modules['requests'] = True
        except ImportError:
            pass
    
    def _patch_urllib(self):
        """Patch urllib to intercept HTTP calls"""
        try:
            import urllib.request
            
            original_urlopen = urllib.request.urlopen
            
            def wrapped_urlopen(url, data=None, **kwargs):
                url_str = url if isinstance(url, str) else url.get_full_url()
                return self._intercept_http_call(original_urlopen, 'GET', url_str, data=data, **kwargs)
            
            urllib.request.urlopen = wrapped_urlopen
            self._patched_modules['urllib'] = True
        except ImportError:
            pass
    
    def _patch_openai(self):
        """Patch OpenAI client to intercept API calls"""
        try:
            import openai
            
            # Patch OpenAI client initialization
            if hasattr(openai, 'OpenAI'):
                original_init = openai.OpenAI.__init__
                
                def wrapped_init(self, *args, **kwargs):
                    result = original_init(self, *args, **kwargs)
                    # Store original methods after initialization
                    try:
                        if hasattr(self, 'chat') and hasattr(self.chat, 'completions'):
                            original_create = self.chat.completions.create
                            def wrapped_chat_create(*args, **kwargs):
                                return self._intercept_openai_chat_create(original_create, *args, **kwargs)
                            self.chat.completions.create = wrapped_chat_create
                    except:
                        pass
                    
                    # Patch responses if it exists (for Groq API)
                    try:
                        if hasattr(self, 'responses'):
                            original_responses_create = self.responses.create
                            def wrapped_responses_create(*args, **kwargs):
                                return self._intercept_openai_responses_create(original_responses_create, *args, **kwargs)
                            self.responses.create = wrapped_responses_create
                    except:
                        pass
                    
                    return result
                
                openai.OpenAI.__init__ = wrapped_init
            
            self._patched_modules['openai'] = True
        except (ImportError, AttributeError) as e:
            pass
    
    def _patch_sqlalchemy(self):
        """Patch SQLAlchemy to intercept database operations"""
        try:
            from sqlalchemy.orm import Session
            from sqlalchemy import event
            
            # Track session operations
            @event.listens_for(Session, 'before_flush')
            def receive_before_flush(session, flush_context, instances):
                self._intercept_db_write(session, instances)
            
            @event.listens_for(Session, 'after_flush')
            def receive_after_flush(session, flush_context):
                pass
            
            self._patched_modules['sqlalchemy'] = True
        except ImportError:
            pass
    
    def _intercept_http_call(self, original_func, method, url, **kwargs):
        """Intercept and log HTTP calls"""
        # Extract data from kwargs
        data = kwargs.get('data') or kwargs.get('json')
        
        # Check if data contains tagged personal information
        owner_ids = set()
        tag_ids = []
        data_types = []
        
        if data:
            self._extract_tags_from_data(data, owner_ids, tag_ids, data_types)
        
        # Log the event
        if owner_ids or tag_ids:
            for owner_id in owner_ids:
                self.logger.log_http_request(
                    url=url,
                    method=method,
                    data=data,
                    owner_id=owner_id,
                    tag_ids=tag_ids,
                    data_types=data_types
                )
        
        # Execute original function
        return original_func(method, url, **kwargs)
    
    def _intercept_openai_call(self, original_func, method, url, **kwargs):
        """Intercept OpenAI API calls"""
        data = kwargs.get('data') or kwargs.get('json') or kwargs.get('body')
        
        owner_ids = set()
        tag_ids = []
        data_types = []
        
        if data:
            self._extract_tags_from_data(data, owner_ids, tag_ids, data_types)
        
        if owner_ids or tag_ids:
            for owner_id in owner_ids:
                self.logger.log_external_api(
                    api_name="OpenAI/Groq",
                    endpoint=url,
                    data=data,
                    owner_id=owner_id,
                    tag_ids=tag_ids,
                    data_types=data_types
                )
        
        return original_func(method, url, **kwargs)
    
    def _intercept_openai_chat_create(self, original_func, *args, **kwargs):
        """Intercept OpenAI chat.completions.create calls"""
        messages = kwargs.get('messages', [])
        model = kwargs.get('model', 'unknown')
        
        owner_ids = set()
        tag_ids = []
        data_types = []
        
        # Extract tags from messages
        for msg in messages:
            content = msg.get('content', '') if isinstance(msg, dict) else str(msg)
            self._extract_tags_from_data(content, owner_ids, tag_ids, data_types)
        
        if owner_ids or tag_ids:
            for owner_id in owner_ids:
                self.logger.log_external_api(
                    api_name="OpenAI",
                    endpoint=f"chat.completions.create({model})",
                    data=messages,
                    owner_id=owner_id,
                    tag_ids=tag_ids,
                    data_types=data_types
                )
        elif not owner_ids:
            # If no tags found but we have messages, try to infer owner from context
            # This is a fallback for cases where data wasn't tagged before string conversion
            pass
        
        return original_func(*args, **kwargs)
    
    def _intercept_openai_responses_create(self, original_func, *args, **kwargs):
        """Intercept OpenAI responses.create calls (Groq API)"""
        # Extract input/prompt from kwargs
        prompt = kwargs.get('input') or kwargs.get('prompt') or ''
        model = kwargs.get('model', 'unknown')
        
        owner_ids = set()
        tag_ids = []
        data_types = []
        
        # Check prompt for personal data
        if isinstance(prompt, str):
            self._extract_tags_from_data(prompt, owner_ids, tag_ids, data_types)
        elif isinstance(prompt, (dict, list)):
            self._extract_tags_from_data(prompt, owner_ids, tag_ids, data_types)
        
        if owner_ids or tag_ids:
            for owner_id in owner_ids:
                self.logger.log_external_api(
                    api_name="OpenAI/Groq",
                    endpoint=f"responses.create({model})",
                    data=prompt,
                    owner_id=owner_id,
                    tag_ids=tag_ids,
                    data_types=data_types
                )
        
        return original_func(*args, **kwargs)
    
    def _intercept_db_write(self, session, instances):
        """Intercept database write operations"""
        for instance in session.new:
            owner_id = None
            tag_ids = []
            data_types = []
            
            # Check if instance has tagged attributes
            if hasattr(instance, '__dict__'):
                for key, value in instance.__dict__.items():
                    if value is not None:
                        tag = self.tracker.get_tag(value)
                        if tag:
                            tag_ids.append(tag.tag_id)
                            owner_id = tag.owner_id
                            data_types.append(tag.data_type.value)
            
            # Also check for user_id or email fields
            if hasattr(instance, 'user_id'):
                user_id = instance.user_id
                if not owner_id:
                    owner_id = str(user_id)
            
            if hasattr(instance, 'email'):
                email = instance.email
                if not owner_id:
                    owner_id = email
                # Tag the email if not already tagged
                if not self.tracker.has_tag(email):
                    self.tracker.tag_data(email, owner_id, DataType.EMAIL, "database")
            
            if owner_id and tag_ids:
                table_name = instance.__class__.__tablename__ if hasattr(instance.__class__, '__tablename__') else instance.__class__.__name__
                self.logger.log_database_operation(
                    operation='write',
                    table=table_name,
                    owner_id=owner_id,
                    tag_ids=tag_ids,
                    data_types=data_types,
                    record_id=getattr(instance, 'id', None)
                )
    
    def _extract_tags_from_data(self, data: Any, owner_ids: set, tag_ids: list, data_types: list):
        """Recursively extract provenance tags from data structure"""
        if data is None:
            return
        
        # Check if data itself is tagged
        if hasattr(data, 'tag'):
            tag = data.tag
            owner_ids.add(tag.owner_id)
            tag_ids.append(tag.tag_id)
            data_types.append(tag.data_type.value)
        
        # Check if data has a tag in tracker
        tag = self.tracker.get_tag(data)
        if tag:
            owner_ids.add(tag.owner_id)
            tag_ids.append(tag.tag_id)
            data_types.append(tag.data_type.value)
        
        # Recursively check containers
        if isinstance(data, dict):
            for value in data.values():
                self._extract_tags_from_data(value, owner_ids, tag_ids, data_types)
        elif isinstance(data, (list, tuple)):
            for item in data:
                self._extract_tags_from_data(item, owner_ids, tag_ids, data_types)
        elif isinstance(data, str):
            # Check if string itself is tagged
            tag = self.tracker.get_tag(data)
            if tag:
                owner_ids.add(tag.owner_id)
                tag_ids.append(tag.tag_id)
                data_types.append(tag.data_type.value)
            
            # Check if string contains personal data patterns
            detected_type = detect_personal_data(data)
            if detected_type and not tag:
                # String contains personal data but isn't tagged
                # Try to find owner from context
                # This is a fallback - ideally data should be tagged before being in strings
                pass


# Global instance
_runtime_tracker = RuntimeTracker()


def get_runtime_tracker() -> RuntimeTracker:
    """Get the global runtime tracker instance"""
    return _runtime_tracker


def start_tracking():
    """Start runtime tracking"""
    _runtime_tracker.start()


def stop_tracking():
    """Stop runtime tracking"""
    _runtime_tracker.stop()
