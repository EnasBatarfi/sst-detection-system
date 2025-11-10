# 🚀 Quick Start Guide - SST Detector

## What You Get

A **complete runtime tracking system** that automatically detects and logs:
- 📥 When personal data is collected
- 🔄 How data is processed
- 📤 **When data is shared with third parties (SST Detection)**
- 🗄️ Database operations
- 🌐 External API calls

## Installation

No additional packages needed! All components are pure Python with existing dependencies.

## Integration (Already Done!)

The system is **already integrated** into your Flask app with just these lines in `app.py`:

```python
from sst_detector import init_sst_detector
from provenance_viewer import provenance_bp

with app.app_context():
    detector = init_sst_detector(app, db, console_output=True)
    app.register_blueprint(provenance_bp)
```

That's it! **No other changes needed** to your application code.

## Running the App

```bash
cd budget_tracker
python app.py
```

You'll see:

```
================================================================================
🔍 SERVER-SIDE TRACKING (SST) DETECTOR ACTIVATED
================================================================================
📊 Provenance Database: /workspace/budget_tracker/provenance.db
📁 Log Directory: /workspace/budget_tracker/provenance_logs
🎯 Tracking: HTTP Requests, Database Ops, External APIs
================================================================================
```

## Usage

### 1. Use Your App Normally

Just use your budget tracker as usual:
- Sign up a new user
- Add expenses
- Generate AI insights

### 2. Watch the Console

Every time data is shared, you'll see:

```
================================================================================
[PROVENANCE-WARNING] 🚨 DATA SHARING DETECTED 🚨
  Timestamp: 2025-11-10T15:30:45.123456
  Owner: user_1
  Data Type: email
  Destination: database_user
  Method: SQL_WRITE
  Preview: john@example.com
================================================================================
```

### 3. View Your Privacy Dashboard

Navigate to: **http://localhost:5000/provenance/**

You'll see:
- ✅ How many times your data was collected
- ✅ How many database operations occurred
- ✅ **Most importantly: All third-party sharing events**
- ✅ Export button to download your full data flow

### 4. CLI Commands

**Query a user's complete data flow:**
```bash
flask provenance-user
# Enter user ID (e.g., 1)
# Creates: provenance_user_1.json
```

**Get sharing summary:**
```bash
flask provenance-summary
# Enter days (e.g., 7)
# Shows all sharing events in last N days
```

## What's Being Tracked?

### Personal Data
- Name, email, birthday, gender
- Income, currency, budget preferences
- Expense amounts, categories, descriptions

### Destinations Detected
- **Database writes** (all your data storage)
- **Groq AI API** (when generating AI insights)
- **Any other external API** you might add

### Example Scenario

1. **User signs up** → Data collection logged
2. **Data saved to database** → Logged as: "destination: database_user"
3. **AI insights generated** → Logged as: "destination: Groq AI (Third-Party LLM)"
4. **User views privacy dashboard** → Sees all sharing events

## Verify It's Working

### ✅ Checklist
- [ ] See startup message when running `python app.py`
- [ ] See console output when submitting forms
- [ ] Can access `/provenance/` route
- [ ] See `provenance.db` file created
- [ ] See `provenance_logs/` directory created
- [ ] CLI commands work (`flask provenance-user`)

### Test Flow

1. **Start the app:**
   ```bash
   python app.py
   ```

2. **Sign up a new user** (use email: test@example.com)

3. **Check console** - you should see multiple "DATA SHARING DETECTED" messages

4. **Add an expense** - watch for more tracking output

5. **Generate AI insights** - this will trigger Groq API tracking

6. **Visit** `http://localhost:5000/provenance/`

7. **See all events** tracked for your user

## Files Created

After running, these files appear:

```
budget_tracker/
├── provenance.db              # SQLite audit database ✨ NEW
└── provenance_logs/           # JSON log files ✨ NEW
    └── provenance_2025-11-10.jsonl
```

## Key Findings

The system will detect:

### ✅ Expected Sharing
- Database writes (normal app behavior)
- Session storage (authentication)

### ⚠️ Third-Party Sharing
- **Groq AI API** - Sends expense data + income for AI insights
- Any analytics you might add
- Any tracking pixels
- Any advertising networks

## Privacy Compliance

This system helps with:
- ✅ **GDPR Article 15** - Right of access (users can see their data flow)
- ✅ **GDPR Article 30** - Records of processing activities
- ✅ **CCPA § 1798.100** - Right to know what personal information is collected
- ✅ **Transparency** - Users see exactly where data goes

## Disable Tracking (Optional)

If you need to disable tracking:

```python
detector.deactivate()
```

Or set `console_output=False` to silence console logs:

```python
detector = init_sst_detector(app, db, console_output=False)
```

## Example Output

When you generate AI insights, you'll see something like:

```
================================================================================
[PROVENANCE-WARNING] 🚨 DATA SHARING DETECTED 🚨
  Timestamp: 2025-11-10T15:32:18.123456
  Owner: user_1
  Data Type: derived_expense_amount
  Destination: Groq AI (Third-Party LLM)
  Method: HTTP_POST
  Preview: {"expenses": [{"amount": 50.0, "category": "Food"}, ...], "income": 5000.0}
================================================================================
```

This is **server-side tracking detection** in action! 🎉

## Questions?

See `SST_DETECTOR_README.md` for full documentation.

---

**🎯 You now have a complete runtime SST detection system with zero code changes to your application logic!**
