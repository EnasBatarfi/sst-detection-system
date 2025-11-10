"""
Server-Side Tracking (SST) Detector
Main integration module that ties all tracking components together
Minimal changes required to existing Flask application
"""

from flask import Flask
from runtime_tracker import get_tracker
from provenance_logger import get_logger
from flask_interceptor import create_interceptor
from database_tracker import create_database_tracker
from api_tracker import get_api_tracker
import os

class SSTDetector:
    """
    Server-Side Tracking Detector
    Implements runtime-level instrumentation for detecting data sharing
    """
    
    def __init__(self, app: Flask = None, db = None, console_output: bool = True, 
                 log_dir: str = None, db_path: str = None):
        self.app = app
        self.db = db
        self.console_output = console_output
        self.log_dir = log_dir or os.path.join(os.path.dirname(__file__), 'provenance_logs')
        self.db_path = db_path
        
        # Initialize components
        self.tracker = get_tracker()
        self.logger = get_logger()
        self.api_tracker = get_api_tracker()
        self.flask_interceptor = None
        self.db_tracker = None
        
        if app and db:
            self.init_app(app, db)
    
    def init_app(self, app: Flask, db):
        """
        Initialize SST detector with Flask app
        This is the main integration point - minimal changes needed!
        """
        self.app = app
        self.db = db
        
        # Configure logger
        self.logger.__init__(
            db_path=self.db_path,
            log_dir=self.log_dir,
            console_output=self.console_output
        )
        
        # Connect logger to tracker
        self.tracker.set_logger(self.logger)
        
        # Activate tracking
        self.tracker.activate()
        
        # Initialize Flask interceptor
        self.flask_interceptor = create_interceptor(app)
        
        # Initialize database tracker
        self.db_tracker = create_database_tracker(db)
        
        # Patch external API calls
        self.api_tracker.patch_requests_library()
        
        # Register shutdown handler
        @app.teardown_appcontext
        def shutdown_tracking(exception=None):
            self.tracker.clear_context()
        
        # Add CLI commands for querying provenance
        self._register_cli_commands(app)
        
        print("\n" + "="*80)
        print("🔍 SERVER-SIDE TRACKING (SST) DETECTOR ACTIVATED")
        print("="*80)
        print(f"📊 Provenance Database: {self.logger.db_path}")
        print(f"📁 Log Directory: {self.log_dir}")
        print(f"🎯 Tracking: HTTP Requests, Database Ops, External APIs")
        print("="*80 + "\n")
    
    def _register_cli_commands(self, app: Flask):
        """Register CLI commands for querying provenance data"""
        
        @app.cli.command('provenance-user')
        def query_user_provenance():
            """Query provenance data for a specific user"""
            import click
            user_id = click.prompt('Enter user ID', type=str)
            owner_id = f"user_{user_id}"
            
            data_flow = self.logger.query_user_data_flow(owner_id)
            
            print(f"\n{'='*80}")
            print(f"DATA FLOW REPORT FOR {owner_id}")
            print(f"{'='*80}")
            print(f"\n📥 Data Collections: {data_flow['summary']['total_collections']}")
            print(f"🔄 Database Operations: {data_flow['summary']['total_db_operations']}")
            print(f"📤 Sharing Events: {data_flow['summary']['total_sharing_events']}")
            print(f"\n🎯 Destinations:")
            for dest in data_flow['summary']['destinations']:
                print(f"   - {dest}")
            print(f"\n{'='*80}")
            
            # Export to JSON
            import json
            export_file = f"provenance_user_{user_id}.json"
            with open(export_file, 'w') as f:
                json.dump(data_flow, f, indent=2, default=str)
            print(f"\n✅ Full report exported to: {export_file}\n")
        
        @app.cli.command('provenance-summary')
        def provenance_summary():
            """Get summary of all data sharing events"""
            import click
            from datetime import datetime, timedelta
            
            days = click.prompt('Show last N days', type=int, default=7)
            start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            events = self.logger.get_sharing_summary(start_date=start_date)
            
            print(f"\n{'='*80}")
            print(f"DATA SHARING SUMMARY (Last {days} days)")
            print(f"{'='*80}")
            print(f"\nTotal sharing events: {len(events)}")
            
            # Group by destination
            by_destination = {}
            for event in events:
                dest = event['destination']
                by_destination[dest] = by_destination.get(dest, 0) + 1
            
            print(f"\n📤 By Destination:")
            for dest, count in sorted(by_destination.items(), key=lambda x: x[1], reverse=True):
                print(f"   {count:4d} events -> {dest}")
            
            print(f"\n{'='*80}\n")
    
    def deactivate(self):
        """Deactivate tracking (for testing or debugging)"""
        self.tracker.deactivate()
        self.api_tracker.unpatch_requests_library()
        print("🛑 SST Detector deactivated")
    
    def get_status(self) -> dict:
        """Get current tracking status"""
        return {
            'active': self.tracker.is_active(),
            'provenance_db': self.logger.db_path,
            'log_dir': self.log_dir,
            'console_output': self.console_output
        }


def init_sst_detector(app: Flask, db, console_output: bool = True) -> SSTDetector:
    """
    Factory function to initialize SST detector
    
    Usage in your Flask app:
        from sst_detector import init_sst_detector
        detector = init_sst_detector(app, db)
    """
    return SSTDetector(app=app, db=db, console_output=console_output)
