"""
Automatic Data Tagging Module
Automatically tags personal data when it enters the system via Flask requests.
"""
from flask import request, session
from provenance import get_tracker, DataType, tag_personal_data
from runtime_tracker import get_runtime_tracker


def auto_tag_request_data():
    """Automatically tag personal data from Flask request"""
    tracker = get_tracker()
    runtime_tracker = get_runtime_tracker()
    
    # Get user context if available
    user_id = session.get('user_id')
    owner_id = str(user_id) if user_id else "anonymous"
    
    # Tag form data
    if request.method == 'POST' and request.form:
        for key, value in request.form.items():
            if value:
                data_type = _infer_data_type(key, value)
                if data_type:
                    tagged = tag_personal_data(value, owner_id, data_type, f"form_field:{key}")
                    # Store reference for propagation
                    runtime_tracker.tracker.tag_object(value, owner_id, data_type, f"form_field:{key}")
    
    # Tag JSON data
    if request.is_json and request.json:
        for key, value in request.json.items():
            if value and isinstance(value, (str, int, float)):
                data_type = _infer_data_type(key, value)
                if data_type:
                    tag_personal_data(str(value), owner_id, data_type, f"json_field:{key}")
                    runtime_tracker.tracker.tag_object(value, owner_id, data_type, f"json_field:{key}")


def _infer_data_type(key: str, value) -> DataType:
    """Infer data type from field name and value"""
    key_lower = key.lower()
    
    # Email
    if 'email' in key_lower:
        return DataType.EMAIL
    
    # Name
    if 'name' in key_lower:
        return DataType.NAME
    
    # Birthday/Date of birth
    if 'birthday' in key_lower or 'dob' in key_lower or 'date_of_birth' in key_lower:
        return DataType.BIRTHDAY
    
    # Gender
    if 'gender' in key_lower:
        return DataType.GENDER
    
    # Income
    if 'income' in key_lower:
        return DataType.INCOME
    
    # Phone
    if 'phone' in key_lower or 'mobile' in key_lower:
        return DataType.PHONE
    
    # Try to detect from value
    if isinstance(value, str):
        from provenance import detect_personal_data
        detected = detect_personal_data(value)
        if detected:
            return detected
    
    return None


def tag_user_model(user):
    """Tag all personal data fields in a User model"""
    tracker = get_tracker()
    owner_id = str(user.id) if hasattr(user, 'id') else user.email
    
    # Tag email
    if hasattr(user, 'email') and user.email:
        tracker.tag_object(user.email, owner_id, DataType.EMAIL, "user_model")
    
    # Tag name
    if hasattr(user, 'name') and user.name:
        tracker.tag_object(user.name, owner_id, DataType.NAME, "user_model")
    
    # Tag birthday
    if hasattr(user, 'birthday') and user.birthday:
        tracker.tag_object(user.birthday, owner_id, DataType.BIRTHDAY, "user_model")
    
    # Tag gender
    if hasattr(user, 'gender') and user.gender:
        tracker.tag_object(user.gender, owner_id, DataType.GENDER, "user_model")
    
    # Tag income
    if hasattr(user, 'income') and user.income:
        tracker.tag_object(user.income, owner_id, DataType.INCOME, "user_model")
    
    return owner_id
