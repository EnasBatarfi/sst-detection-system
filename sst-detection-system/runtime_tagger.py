"""
Runtime Tagger - Functions injected into code for runtime tagging
These functions are called from instrumented code.
"""
import sys
import os
# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from budget_tracker.provenance import get_tracker, DataType, detect_personal_data
    from budget_tracker.audit_logger import get_logger, SharingEventType
except ImportError:
    try:
        from provenance import get_tracker, DataType, detect_personal_data
        from audit_logger import get_logger, SharingEventType
    except ImportError:
        # Create minimal stubs if modules not available
        class DataType:
            EMAIL = "email"
            INCOME = "income"
            DERIVED = "derived"
        
        def detect_personal_data(value):
            return None
        
        def get_tracker():
            return None
        
        def get_logger():
            return None


def tag_value(value, var_name=None, owner_id=None, data_type=None):
    """
    Tag a value with provenance metadata
    Called from instrumented code
    """
    if value is None:
        return value
    
    tracker = get_tracker()
    
    # Skip if already tagged
    if tracker.has_tag(value):
        return value
    
    # Auto-detect data type if not provided
    if data_type is None:
        data_type = detect_personal_data(value) if isinstance(value, str) else None
    
    if data_type is None:
        return value  # Not personal data
    
    # Get owner_id from context if not provided
    if owner_id is None:
        owner_id = _get_owner_from_context()
    
    if owner_id:
        tracker.tag_object(value, owner_id, data_type, f"runtime_tagged:{var_name or 'unknown'}")
    
    return value


def check_and_tag(value):
    """
    Check if value contains personal data and tag it
    Called from instrumented code
    """
    if value is None:
        return value
    
    tracker = get_tracker()
    
    # Skip if already tagged
    if tracker.has_tag(value):
        return value
    
    # Detect personal data
    if isinstance(value, str):
        data_type = detect_personal_data(value)
        if data_type:
            owner_id = _get_owner_from_context()
            if owner_id:
                tracker.tag_object(value, owner_id, data_type, "auto_detected")
    
    return value


def _track_external_call(original_call_result):
    """
    Track an external API call
    Wraps the original call and logs it
    """
    import inspect
    frame = inspect.currentframe().f_back
    
    tracker = get_tracker()
    logger = get_logger()
    
    # Extract tagged data from call arguments
    # This is a simplified version - in practice, you'd need to extract from the call
    owner_ids = set()
    tag_ids = []
    data_types = []
    
    # Check local variables in the calling frame
    if frame:
        for var_name, var_value in frame.f_locals.items():
            if var_value is not None:
                tag = tracker.get_tag(var_value)
                if tag:
                    owner_ids.add(tag.owner_id)
                    tag_ids.append(tag.tag_id)
                    data_types.append(tag.data_type.value)
    
    # Log the external call
    if owner_ids or tag_ids:
        func_name = frame.f_code.co_name if frame else "unknown"
        filename = frame.f_code.co_filename if frame else "unknown"
        
        for owner_id in owner_ids:
            logger.log_external_api(
                api_name=_get_api_name(filename),
                endpoint=func_name,
                data=None,  # Would need to extract from call
                owner_id=owner_id,
                tag_ids=tag_ids,
                data_types=data_types
            )
    
    return original_call_result


def _track_data_operation(original_call_result):
    """
    Track a data operation (database, file, etc.)
    """
    import inspect
    frame = inspect.currentframe().f_back
    
    tracker = get_tracker()
    logger = get_logger()
    
    # Similar to _track_external_call but for data operations
    owner_ids = set()
    tag_ids = []
    data_types = []
    
    if frame:
        for var_name, var_value in frame.f_locals.items():
            if var_value is not None:
                tag = tracker.get_tag(var_value)
                if tag:
                    owner_ids.add(tag.owner_id)
                    tag_ids.append(tag.tag_id)
                    data_types.append(tag.data_type.value)
    
    if owner_ids or tag_ids:
        func_name = frame.f_code.co_name if frame else "unknown"
        
        for owner_id in owner_ids:
            logger.log_database_operation(
                operation='write',  # Would need to determine from context
                table='unknown',
                owner_id=owner_id,
                tag_ids=tag_ids,
                data_types=data_types
            )
    
    return original_call_result


def _get_owner_from_context():
    """Extract owner_id from execution context"""
    import inspect
    
    frame = inspect.currentframe()
    depth = 0
    
    while frame and depth < 10:
        # Check for user_id
        if 'user_id' in frame.f_locals:
            return str(frame.f_locals['user_id'])
        
        # Check for user object
        if 'user' in frame.f_locals:
            user = frame.f_locals['user']
            if hasattr(user, 'id'):
                return str(user.id)
            if hasattr(user, 'email'):
                return user.email
        
        # Check globals
        if 'user_id' in frame.f_globals:
            return str(frame.f_globals['user_id'])
        
        frame = frame.f_back
        depth += 1
    
    return None


def _get_api_name(filename: str) -> str:
    """Extract API name from filename"""
    if 'openai' in filename.lower() or 'groq' in filename.lower():
        return "OpenAI/Groq"
    elif 'requests' in filename:
        return "HTTP/Requests"
    elif 'urllib' in filename:
        return "HTTP/urllib"
    else:
        return "External API"
