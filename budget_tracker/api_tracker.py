"""
External API Call Tracker
Intercepts and logs all external API calls (e.g., to Groq, analytics services)
Critical for detecting server-side tracking (SST)
"""

import functools
import requests
import json
from typing import Any, Dict, Callable
from runtime_tracker import get_tracker
from provenance_logger import get_logger

class APITracker:
    """
    Tracks external API calls to detect server-side tracking
    Wraps HTTP libraries and API clients
    """
    
    def __init__(self):
        self.tracker = get_tracker()
        self.logger = get_logger()
        self._original_request = None
        self._original_post = None
        self._original_get = None
    
    def patch_requests_library(self):
        """
        Patch the requests library to track all HTTP calls
        This is the runtime-level instrumentation
        """
        if self._original_request is not None:
            return  # Already patched
        
        # Store original functions
        self._original_request = requests.request
        self._original_post = requests.post
        self._original_get = requests.get
        
        # Create tracked versions
        def tracked_request(method, url, **kwargs):
            return self._track_http_call(self._original_request, method, url, **kwargs)
        
        def tracked_post(url, **kwargs):
            return self._track_http_call(self._original_post, url, **kwargs)
        
        def tracked_get(url, **kwargs):
            return self._track_http_call(self._original_get, url, **kwargs)
        
        # Monkey-patch requests module
        requests.request = tracked_request
        requests.post = tracked_post
        requests.get = tracked_get
    
    def unpatch_requests_library(self):
        """Restore original requests library"""
        if self._original_request is None:
            return
        
        requests.request = self._original_request
        requests.post = self._original_post
        requests.get = self._original_get
        
        self._original_request = None
        self._original_post = None
        self._original_get = None
    
    def _track_http_call(self, original_func, *args, **kwargs):
        """Track an HTTP call and log it"""
        if not self.tracker.is_active():
            return original_func(*args, **kwargs)
        
        # Extract request details
        if len(args) >= 2:
            method = args[0]
            url = args[1]
        elif len(args) == 1:
            url = args[0]
            method = original_func.__name__.upper()
        else:
            url = kwargs.get('url', 'unknown')
            method = kwargs.get('method', 'GET')
        
        # Extract data being sent
        data = kwargs.get('data')
        json_data = kwargs.get('json')
        payload = json_data if json_data is not None else data
        
        # Identify if this is a third-party service
        destination = self._classify_destination(url)
        
        # Check if payload contains tagged data
        tags = self.tracker.get_current_tags()
        
        # Log BEFORE making the call
        self.tracker.log_data_sharing(
            data=payload,
            destination=destination,
            method=f"HTTP_{method}",
            metadata={
                'url': url,
                'log_full_payload': True,
                'payload': self._safe_serialize(payload),
                'headers': self._safe_headers(kwargs.get('headers', {})),
                'tags_in_context': [tag.tag_id for tag in tags]
            }
        )
        
        # Make the actual call
        try:
            response = original_func(*args, **kwargs)
            
            # Log response metadata
            response_preview = f"Status: {response.status_code}"
            try:
                if response.headers.get('content-type', '').startswith('application/json'):
                    response_preview += f", Body: {response.text[:200]}"
            except:
                pass
            
            # Update sharing event with response
            self.tracker.log_data_sharing(
                data=payload,
                destination=destination,
                method=f"HTTP_{method}_RESPONSE",
                metadata={
                    'url': url,
                    'response_status': response.status_code,
                    'response_preview': response_preview
                }
            )
            
            return response
            
        except Exception as e:
            # Log failed call
            self.tracker.log_data_sharing(
                data=payload,
                destination=destination,
                method=f"HTTP_{method}_ERROR",
                metadata={
                    'url': url,
                    'error': str(e)
                }
            )
            raise
    
    def track_api_function(self, destination: str):
        """
        Decorator to track specific API functions
        Usage: @api_tracker.track_api_function("Groq AI")
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if not self.tracker.is_active():
                    return func(*args, **kwargs)
                
                # Extract arguments that might contain personal data
                func_args = self._extract_function_args(func, args, kwargs)
                
                # Check for tagged data in arguments
                tags = []
                for arg in args:
                    tag = self.tracker.get_tag(arg)
                    if tag:
                        tags.append(tag)
                
                # Log the API call
                self.tracker.log_data_sharing(
                    data=func_args,
                    destination=destination,
                    method=f"API_CALL_{func.__name__}",
                    metadata={
                        'function': func.__name__,
                        'module': func.__module__,
                        'tags': [tag.tag_id for tag in tags],
                        'arguments': self._safe_serialize(func_args)
                    }
                )
                
                # Execute the function
                result = func(*args, **kwargs)
                
                # Log the result
                self.tracker.log_data_sharing(
                    data=result,
                    destination=destination,
                    method=f"API_RESPONSE_{func.__name__}",
                    metadata={
                        'function': func.__name__,
                        'result_preview': self._safe_serialize(result)[:200]
                    }
                )
                
                return result
            
            return wrapper
        return decorator
    
    def _classify_destination(self, url: str) -> str:
        """Classify the destination of an API call"""
        url_lower = url.lower()
        
        # Identify known third-party services
        if 'groq.com' in url_lower:
            return 'Groq AI (Third-Party LLM)'
        elif 'openai.com' in url_lower:
            return 'OpenAI (Third-Party LLM)'
        elif 'google-analytics' in url_lower or 'analytics.google' in url_lower:
            return 'Google Analytics (Third-Party Tracking)'
        elif 'facebook.com' in url_lower or 'meta.com' in url_lower:
            return 'Meta/Facebook (Third-Party Tracking)'
        elif 'doubleclick' in url_lower or 'googleadservices' in url_lower:
            return 'Google Ads (Third-Party Advertising)'
        elif any(ad_network in url_lower for ad_network in ['ads', 'analytics', 'tracking', 'pixel']):
            return f'Potential Ad Network ({url})'
        else:
            return f'External API ({url})'
    
    def _safe_serialize(self, data: Any) -> str:
        """Safely serialize data to string"""
        try:
            if isinstance(data, (str, int, float, bool)):
                return str(data)
            return json.dumps(data, default=str)
        except:
            return str(data)
    
    def _safe_headers(self, headers: Dict) -> Dict:
        """Sanitize headers for logging (remove auth tokens)"""
        safe_headers = {}
        sensitive_headers = ['authorization', 'api-key', 'api_key', 'token', 'cookie', 'session']
        
        for key, value in headers.items():
            if any(sensitive in key.lower() for sensitive in sensitive_headers):
                safe_headers[key] = '***REDACTED***'
            else:
                safe_headers[key] = value
        
        return safe_headers
    
    def _extract_function_args(self, func: Callable, args: tuple, kwargs: dict) -> Dict:
        """Extract function arguments with names"""
        import inspect
        sig = inspect.signature(func)
        bound_args = sig.bind_partial(*args, **kwargs)
        bound_args.apply_defaults()
        return dict(bound_args.arguments)


# Global API tracker instance
_global_api_tracker = None

def get_api_tracker() -> APITracker:
    """Get or create the global API tracker"""
    global _global_api_tracker
    if _global_api_tracker is None:
        _global_api_tracker = APITracker()
    return _global_api_tracker
