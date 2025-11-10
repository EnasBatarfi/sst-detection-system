"""
Provenance Viewer Module
Provides endpoints to view provenance and audit logs.
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect
from database_provenance import ProvenanceRecord, AuditLog
from models import db
from datetime import datetime

provenance_bp = Blueprint('provenance', __name__, url_prefix='/provenance')


@provenance_bp.route('/audit-logs')
def view_audit_logs():
    """View audit logs for the current user"""
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']
    
    # Get logs for this user
    logs = AuditLog.query.filter_by(owner_id=str(user_id)).order_by(
        AuditLog.timestamp.desc()
    ).limit(100).all()
    
    return render_template('audit_logs.html', logs=logs, user_id=user_id)


@provenance_bp.route('/api/audit-logs')
def api_audit_logs():
    """API endpoint for audit logs"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    logs = AuditLog.query.filter_by(owner_id=str(user_id)).order_by(
        AuditLog.timestamp.desc()
    ).limit(100).all()
    
    return jsonify({
        'logs': [log.to_dict() for log in logs]
    })


@provenance_bp.route('/api/provenance')
def api_provenance():
    """API endpoint for provenance records"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    records = ProvenanceRecord.query.filter_by(owner_id=str(user_id)).order_by(
        ProvenanceRecord.timestamp.desc()
    ).limit(100).all()
    
    return jsonify({
        'records': [record.to_dict() for record in records]
    })


@provenance_bp.route('/dashboard')
def provenance_dashboard():
    """Dashboard showing data sharing summary"""
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']
    
    # Get statistics
    total_shares = AuditLog.query.filter_by(owner_id=str(user_id)).count()
    external_apis = AuditLog.query.filter_by(
        owner_id=str(user_id),
        event_type='external_api'
    ).count()
    http_requests = AuditLog.query.filter_by(
        owner_id=str(user_id),
        event_type='http_request'
    ).count()
    
    # Get recent destinations
    recent_destinations = db.session.query(
        AuditLog.destination,
        db.func.count(AuditLog.id).label('count')
    ).filter_by(
        owner_id=str(user_id)
    ).group_by(
        AuditLog.destination
    ).order_by(
        db.func.count(AuditLog.id).desc()
    ).limit(10).all()
    
    return render_template(
        'provenance_dashboard.html',
        user_id=user_id,
        total_shares=total_shares,
        external_apis=external_apis,
        http_requests=http_requests,
        recent_destinations=recent_destinations
    )
