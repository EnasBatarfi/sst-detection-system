# Runtime-Level Server-Side Tracking Detection System

## Overview

This system implements a complete runtime-level instrumentation framework for detecting Server-Side Tracking (SST) in your Flask application. The system automatically tags personal data, tracks its provenance through all operations, and logs all data-sharing events without requiring significant changes to your application code.

## Architecture

The system consists of several key components:

### 1. **Provenance Tracking Module** (`provenance.py`)
- Tags personal data with unique identifiers
- Tracks data lineage and transformations
- Propagates metadata through derived data
- Supports multiple data types (email, name, birthday, income, etc.)

### 2. **Runtime Tracker** (`runtime_tracker.py`)
- Intercepts operations at the Python runtime level
- Patches HTTP libraries (requests, urllib) to detect external API calls
- Intercepts OpenAI/Groq API calls
- Monitors SQLAlchemy database operations
- Automatically detects when tagged data is shared externally

### 3. **Audit Logger** (`audit_logger.py`)
- Logs all data sharing events
- Records destination, data types, and provenance tags
- Captures stack traces for debugging
- Stores events for compliance and transparency

### 4. **Database Models** (`database_provenance.py`)
- `ProvenanceRecord`: Stores provenance metadata
- `AuditLog`: Stores all data sharing events
- Provides queryable history of data flows

### 5. **Data Tagger** (`data_tagger.py`)
- Automatically tags incoming request data
- Tags user model fields
- Infers data types from field names and values

## Features

✅ **Zero/Minimal Code Changes**: Works at runtime with minimal modifications to your Flask app
✅ **Automatic Tagging**: Personal data is automatically tagged when it enters the system
✅ **Provenance Propagation**: Tags propagate through all operations and transformations
✅ **External API Detection**: Automatically detects when data is sent to external APIs (OpenAI, Groq, etc.)
✅ **Database Tracking**: Monitors database operations involving personal data
✅ **Audit Logging**: Complete audit trail of all data sharing events
✅ **Compliance Ready**: GDPR/CCPA compliant logging and tracking

## Installation

The system is already integrated into your Flask application. No additional installation steps are required beyond your existing dependencies.

## How It Works

### 1. Automatic Data Tagging

When data enters your application via Flask requests, the `@app.before_request` hook automatically tags personal data:

```python
@app.before_request
def tag_incoming_data():
    auto_tag_request_data()  # Tags form fields, JSON data, etc.
```

### 2. Runtime Interception

The runtime tracker patches Python libraries to intercept operations:

- **HTTP Requests**: All `requests.post()`, `requests.get()`, etc. are intercepted
- **OpenAI/Groq API**: `client.responses.create()` calls are intercepted
- **Database Operations**: SQLAlchemy flush events are monitored

### 3. Provenance Propagation

When data is transformed or derived, tags are automatically propagated:

```python
# Original data tagged
income = 50000  # Tagged with owner_id and DataType.INCOME

# Derived data automatically inherits tag
summary = aggregate(income)  # Tagged as DERIVED with lineage
```

### 4. Audit Logging

Every time tagged data is shared externally, an audit log entry is created:

```python
{
    "event_type": "external_api",
    "destination": "OpenAI/Groq:responses.create(...)",
    "owner_id": "user_123",
    "data_types": ["income", "derived"],
    "tag_ids": ["tag_abc", "tag_def"],
    "timestamp": 1234567890.0
}
```

## Usage

### Viewing Audit Logs

Access the provenance dashboard:
```
http://localhost:5000/provenance/dashboard
```

View audit logs:
```
http://localhost:5000/provenance/audit-logs
```

### API Endpoints

Get audit logs (JSON):
```
GET /provenance/api/audit-logs
```

Get provenance records (JSON):
```
GET /provenance/api/provenance
```

## Example: Detecting AI API Calls

When your app calls the Groq API with user data:

```python
def generate_ai_insight(expenses, income, ...):
    prompt = f"User income: ${income}..."  # income is tagged
    response = client.responses.create(input=prompt)  # Intercepted!
```

The system automatically:
1. Detects that `income` is tagged personal data
2. Detects that `prompt` contains tagged data
3. Intercepts the API call
4. Logs an audit event with:
   - Destination: "OpenAI/Groq:responses.create(...)"
   - Data types: ["income", "derived"]
   - Owner ID: user identifier
   - Timestamp and stack trace

## Data Types Detected

The system automatically detects and tags:
- **Email addresses**
- **Names** (from field names or heuristics)
- **Birthdays/DOB**
- **Gender**
- **Income**
- **Phone numbers**
- **Derived data** (aggregations, summaries, etc.)

## Database Schema

### ProvenanceRecord
- `tag_id`: Unique identifier for the tag
- `owner_id`: User identifier
- `data_type`: Type of personal data
- `source`: Where data came from
- `lineage`: Chain of parent tags
- `transformations`: Operations applied

### AuditLog
- `event_id`: Unique event identifier
- `event_type`: Type of sharing event
- `owner_id`: User whose data was shared
- `destination`: Where data was sent
- `data_types`: Types of data shared
- `tag_ids`: Provenance tags involved
- `metadata`: Additional event information
- `stack_trace`: Code location where sharing occurred

## Configuration

The system starts automatically when your Flask app initializes:

```python
# In app.py
start_tracking()  # Starts runtime instrumentation
set_storage_callback(store_audit_event)  # Stores events in database
```

## Performance Considerations

- **Minimal Overhead**: Runtime patching adds minimal overhead
- **Selective Tracking**: Only tracks operations involving tagged data
- **Efficient Storage**: Audit logs are stored in database with indexes
- **Non-Blocking**: Tagging failures don't break your application

## Limitations

1. **String Tagging**: Strings are immutable in Python, so tagging strings requires special handling
2. **Third-Party Libraries**: Some libraries may not be intercepted if they use C extensions
3. **Context Inference**: In some cases, owner_id must be inferred from context

## Future Enhancements

- Email notifications to users when their data is shared
- Real-time dashboard for data sharing
- Export audit logs for compliance reports
- Integration with privacy policy enforcement
- Support for more data types and patterns

## Compliance

This system helps with:
- **GDPR**: Right to access, right to be informed about data sharing
- **CCPA**: Transparency about data sharing with third parties
- **Audit Requirements**: Complete audit trail of data flows

## Troubleshooting

### Audit logs not appearing
- Check that `start_tracking()` is called
- Verify database tables are created
- Check console for error messages

### Data not being tagged
- Ensure `@app.before_request` hook is active
- Check that field names match detection patterns
- Verify user is logged in (for owner_id)

### API calls not intercepted
- Verify the library is patched (check `_patched_modules`)
- Some libraries may need manual patching
- Check that data is tagged before API calls

## References

This implementation is based on the research proposal:
"Detecting Server-Side Tracking (SST) via Runtime-Level Instrumentation Approach"
by Enas Batarfi, Boston University

The system incorporates concepts from:
- PASS (Provenance-Aware Storage System)
- CamFlow (Kernel-level information flow tracking)
- W3C PROV (Provenance standard)
- OpenLineage (Data lineage metadata)
