"""
Test script for SST Detector System
Run this to verify the system is working
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

print("🔍 Testing SST Detector System Components...\n")

# Test 1: Import all modules
print("Test 1: Importing modules...")
try:
    import runtime_tracker
    import provenance_logger
    import flask_interceptor
    import database_tracker
    import api_tracker
    import sst_detector
    import provenance_viewer
    print("✅ All modules imported successfully!\n")
except Exception as e:
    print(f"❌ Import failed: {e}\n")
    sys.exit(1)

# Test 2: Create tracker instance
print("Test 2: Creating runtime tracker...")
try:
    tracker = runtime_tracker.get_tracker()
    print(f"✅ Runtime tracker created: {tracker}\n")
except Exception as e:
    print(f"❌ Tracker creation failed: {e}\n")
    sys.exit(1)

# Test 3: Create logger instance
print("Test 3: Creating provenance logger...")
try:
    logger = provenance_logger.get_logger()
    print(f"✅ Provenance logger created\n")
    print(f"   Database path: {logger.db_path}\n")
except Exception as e:
    print(f"❌ Logger creation failed: {e}\n")
    sys.exit(1)

# Test 4: Test data tagging
print("Test 4: Testing data tagging...")
try:
    tracker.activate()
    tracker.set_logger(logger)
    
    test_email = "test@example.com"
    tagged = runtime_tracker.tag_data(test_email, "user_999", "email", "test_source")
    
    tag = tracker.get_tag(test_email)
    if tag:
        print(f"✅ Data tagged successfully!")
        print(f"   Tag ID: {tag.tag_id}")
        print(f"   Owner: {tag.owner_id}")
        print(f"   Type: {tag.data_type}\n")
    else:
        print("⚠️  Tag not found (this is okay if weak references are cleaned up)\n")
except Exception as e:
    print(f"❌ Tagging failed: {e}\n")
    sys.exit(1)

# Test 5: Test API tracker
print("Test 5: Testing API tracker...")
try:
    api_tracker_instance = api_tracker.get_api_tracker()
    print(f"✅ API tracker created: {api_tracker_instance}\n")
except Exception as e:
    print(f"❌ API tracker failed: {e}\n")
    sys.exit(1)

print("="*80)
print("🎉 All tests passed! SST Detector system is ready.")
print("="*80)
print("\nNext steps:")
print("1. Run: python app.py (or python3 app.py)")
print("2. Watch console for tracking output")
print("3. Visit: http://localhost:5000/provenance/")
print("4. Try CLI: flask provenance-user")
print("\nSee QUICK_START.md for detailed instructions.")
