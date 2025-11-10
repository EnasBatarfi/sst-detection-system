"""
Provenance Viewer - Web Interface
Provides a web UI to view provenance data and audit trails
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from provenance_logger import get_logger
import json
from datetime import datetime, timedelta

provenance_bp = Blueprint('provenance', __name__, url_prefix='/provenance')

@provenance_bp.route('/')
def index():
    """Main provenance viewer page"""
    if 'user_id' not in session:
        return redirect('/login')
    
    logger = get_logger()
    user_id = session['user_id']
    owner_id = f"user_{user_id}"
    
    # Get user's data flow
    data_flow = logger.query_user_data_flow(owner_id)
    
    return render_template('provenance_viewer.html', 
                          data_flow=data_flow,
                          user_id=user_id)

@provenance_bp.route('/api/user-flow/<int:user_id>')
def api_user_flow(user_id):
    """API endpoint to get user data flow"""
    # Only allow users to see their own data
    if 'user_id' not in session or session['user_id'] != user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    logger = get_logger()
    owner_id = f"user_{user_id}"
    data_flow = logger.query_user_data_flow(owner_id)
    
    return jsonify(data_flow)

@provenance_bp.route('/api/sharing-events')
def api_sharing_events():
    """API endpoint to get sharing events"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    logger = get_logger()
    days = request.args.get('days', 7, type=int)
    start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
    
    user_id = session['user_id']
    owner_id = f"user_{user_id}"
    
    # Get all sharing events
    all_events = logger.get_sharing_summary(start_date=start_date)
    
    # Filter to current user only
    user_events = [e for e in all_events if e.get('owner_id') == owner_id]
    
    return jsonify(user_events)

@provenance_bp.route('/export')
def export_data():
    """Export user's provenance data as JSON"""
    if 'user_id' not in session:
        return redirect('/login')
    
    logger = get_logger()
    user_id = session['user_id']
    owner_id = f"user_{user_id}"
    
    data_flow = logger.query_user_data_flow(owner_id)
    
    # Return as downloadable JSON
    from flask import make_response
    response = make_response(json.dumps(data_flow, indent=2, default=str))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = f'attachment; filename=provenance_user_{user_id}.json'
    
    return response
