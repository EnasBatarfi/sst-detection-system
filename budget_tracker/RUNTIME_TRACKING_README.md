# Runtime-Level Server-Side Tracking (SST) Detection System

This implementation provides complete runtime tagging and logging for detecting Server-Side Tracking (SST) in the Flask budget tracker application, with **minimal changes** to the existing codebase.

## Overview

The system automatically:
1. **Tags personal data** (PII) with unique identifiers when collected
2. **Tracks data propagation** through all operations and transformations
3. **Logs all data sharing events** (external API calls, database writes, etc.)
4. **Maintains complete provenance records** for audit and compliance

## Architecture

### Core Components

1. **`runtime_tracking.py`**: Main runtime instrumentation module
   - `ProvenanceTracker`: Core tracking engine
   - `DataTag`: Represents tagged data with provenance metadata
   - Automatic instrumentation hooks for:
     - Flask request data
     - SQLAlchemy database operations
     - HTTP requests (requests library)
     - OpenAI/Groq API clients

2. **`models.py`**: Database models for provenance storage
   - `DataTag`: Stores data tags
   - `DataSharingEvent`: Audit log of sharing events
   - `DataLineage`: Tracks data derivation relationships

3. **`provenance_utils.py`**: Utility functions for querying provenance data

4. **`templates/provenance.html`**: Web interface for viewing tracking logs

## How It Works

### Automatic Data Tagging

The system automatically tags PII fields when they enter the system:

- **From HTTP requests**: Form data, JSON, URL parameters containing PII fields (email, name, income, etc.)
- **From database reads**: User and Expense model fields are tagged when loaded
- **From database writes**: PII data is tagged before being written to database

### Data Propagation Tracking

When tagged data is used in operations:
- The system tracks which operations processed the data
- Derived data inherits tags from parent data
- Data lineage relationships are maintained

### Sharing Event Detection

The system automatically detects and logs:

1. **External API Calls**: 
   - All `requests.post()`, `requests.get()`, `requests.request()` calls
   - OpenAI/Groq API calls via `client.responses.create()`
   - Logs destination URL, data sent, and associated tags

2. **Database Writes**:
   - SQLAlchemy INSERT/UPDATE operations
   - Logs table name, data written, and associated tags

### Integration

**Minimal code changes required** - just 2 lines added to `app.py`:

```python
from runtime_tracking import setup_runtime_instrumentation

# ... existing code ...

with app.app_context():
    db.create_all()
    setup_runtime_instrumentation(app, db)  # Initialize tracking
```

That's it! The system automatically instruments:
- Flask request/response cycle
- SQLAlchemy operations
- HTTP libraries
- AI API clients

## Usage

### Viewing Provenance Data

1. **Via Web Interface**: Navigate to `/provenance` route (requires login)
   - View all data sharing events
   - Filter by event type (API calls, database writes)
   - See data lineage and tags

2. **Via Python API**:

```python
from provenance_utils import (
    get_sharing_events_for_user,
    get_sst_summary,
    get_tags_for_identifier,
    detect_suspicious_sharing,
    export_provenance_report
)

# Get all sharing events for a user
events = get_sharing_events_for_user(user_id=1)

# Get summary statistics
summary = get_sst_summary(user_id=1, days=30)

# Get all tags for an identifier
tags = get_tags_for_identifier("user_1")

# Detect suspicious patterns
suspicious = detect_suspicious_sharing(user_id=1, threshold=5)

# Export complete report
report = export_provenance_report(user_id=1, format='json')
```

## PII Field Detection

The system automatically detects PII fields by name patterns:
- `email`, `name`, `password`, `birthday`, `birth_date`, `date_of_birth`
- `phone`, `address`, `ssn`, `income`, `gender`, `age`
- `user_id`, `id`

## Data Privacy

- Actual data values are **hashed** before storage in `DataTag` model
- Only truncated/anonymized data is stored in sharing event logs
- Full audit trail maintained without exposing sensitive values

## Event Types

- `api_call`: External API requests (e.g., Groq API, third-party services)
- `database_write`: Database INSERT/UPDATE operations
- `email`: Email sending (if implemented)
- `file_export`: Data exports (if implemented)

## Database Schema

### DataTag
- `tag_id`: Unique tag identifier
- `identifier`: User identifier (e.g., "user_1", "email_user@example.com")
- `data_type`: Type of data (email, name, income, etc.)
- `data_value_hash`: SHA-256 hash of the actual value
- `source`: Where data came from
- `operations_json`: JSON array of operations this data went through
- `derived_from_json`: JSON array of parent tag IDs

### DataSharingEvent
- `event_id`: Unique event identifier
- `timestamp`: When the event occurred
- `event_type`: Type of sharing event
- `destination`: Where data was sent (URL, table name, etc.)
- `data_json`: JSON of shared data (truncated)
- `tags_json`: JSON array of associated tags
- `identifiers_json`: JSON array of user identifiers
- `metadata_json`: Additional metadata (headers, SQL, etc.)
- `user_id`: Associated user ID

### DataLineage
- `parent_tag_id`: Source tag ID
- `child_tag_id`: Derived tag ID
- `operation`: Operation that created the relationship
- `timestamp`: When the relationship was created

## Performance Considerations

- Runtime instrumentation adds minimal overhead
- Database writes are asynchronous where possible
- In-memory caching of tags for fast lookups
- Thread-safe implementation for concurrent requests

## Compliance & Auditing

This system supports:
- **GDPR compliance**: Complete audit trail of data processing
- **CCPA compliance**: Track data sharing with third parties
- **Internal auditing**: Detect unauthorized data sharing
- **Data subject requests**: Export complete provenance for a user

## Future Enhancements

- Real-time alerts for suspicious sharing patterns
- Integration with privacy policy enforcement
- Automated compliance reporting
- Data retention policy enforcement
- User notification system for data sharing events

## Testing

To test the system:

1. Start the Flask app
2. Register a new user (data will be tagged automatically)
3. Add expenses (data will be tagged)
4. View AI insights (API call will be logged)
5. Navigate to `/provenance` to see all tracking events

## References

Based on the research proposal: "Detecting Server-Side Tracking (SST) via Runtime-Level Instrumentation Approach" by Enas Batarfi, Boston University.

Inspired by:
- PASS (Provenance-Aware Storage System)
- CamFlow (Kernel-level information flow tracking)
- Resin (Provenance-inspired web framework)
- W3C PROV (Provenance standard)
- OpenLineage (Data lineage standard)
