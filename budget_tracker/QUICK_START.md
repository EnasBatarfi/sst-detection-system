# Quick Start Guide - Runtime Tracking System

## What Was Added

A complete runtime-level instrumentation system for detecting Server-Side Tracking (SST) has been integrated into your Flask application with **minimal changes** to your existing code.

## Files Created

1. **`provenance.py`** - Core provenance tracking and data tagging
2. **`runtime_tracker.py`** - Runtime instrumentation and interception
3. **`audit_logger.py`** - Audit logging for data sharing events
4. **`database_provenance.py`** - Database models for storing provenance and audit logs
5. **`data_tagger.py`** - Automatic data tagging from Flask requests
6. **`provenance_viewer.py`** - Flask blueprint for viewing audit logs

## Changes to Existing Files

### `app.py`
- Added imports for runtime tracking modules
- Added `start_tracking()` call to initialize the system
- Added `@app.before_request` hook to auto-tag incoming data
- Added user tagging in signup and AI insights routes
- Registered provenance blueprint

### `ai_insights.py`
- Added data tagging before sending to external API
- Added `user_id` parameter to track data ownership

## How It Works

1. **Automatic Tagging**: When users submit forms, personal data is automatically tagged
2. **Runtime Interception**: When your code calls external APIs (like Groq), the system intercepts the call
3. **Audit Logging**: Every data sharing event is logged to the database
4. **Provenance Tracking**: Data lineage is tracked through all transformations

## Testing the System

1. **Start your Flask app**:
   ```bash
   python app.py
   ```

2. **Create a user account** - Personal data will be automatically tagged

3. **Use the AI insights feature** - This will trigger an external API call that will be logged

4. **View audit logs**:
   - Visit: `http://localhost:5000/provenance/dashboard`
   - Or API: `http://localhost:5000/provenance/api/audit-logs`

## What Gets Tracked

- ✅ User registration data (email, name, birthday, income, etc.)
- ✅ External API calls (OpenAI, Groq, etc.)
- ✅ HTTP requests with personal data
- ✅ Database operations involving personal data
- ✅ Data transformations and aggregations

## Example: AI Insights Call

When a user requests AI insights:

1. User data (income, expenses) is tagged
2. Data is aggregated into a prompt
3. Prompt is tagged as derived data
4. API call to Groq is intercepted
5. Audit log entry is created:
   ```
   Event Type: external_api
   Destination: OpenAI/Groq:responses.create(...)
   Data Types: [income, derived]
   Owner ID: <user_id>
   ```

## Database Tables

Two new tables are created automatically:

- **`provenance_records`**: Stores provenance metadata for tagged data
- **`audit_logs`**: Stores all data sharing events

## No Breaking Changes

- Your existing Flask app continues to work normally
- All tracking happens transparently in the background
- If tracking fails, your app continues to function (errors are caught)

## Next Steps

1. Run your app and test the tracking
2. Check the audit logs to see what's being tracked
3. Customize data types or detection patterns if needed
4. Add email notifications (optional enhancement)

## Troubleshooting

**No audit logs appearing?**
- Make sure `start_tracking()` is called in `app.py`
- Check that database tables are created
- Verify external API calls are being made

**Data not being tagged?**
- Check that the `@app.before_request` hook is active
- Verify form field names match detection patterns
- Ensure user is logged in (for owner_id)

For more details, see `RUNTIME_TRACKING_README.md`
