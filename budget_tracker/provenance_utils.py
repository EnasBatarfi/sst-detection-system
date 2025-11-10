"""
Utility functions for querying and analyzing provenance data and SST detection results.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from models import DataSharingEvent, DataTag, DataLineage, db, User


def get_sharing_events_for_user(user_id: int, limit: int = 100) -> List[Dict]:
    """Get all data sharing events for a specific user."""
    events = DataSharingEvent.query.filter_by(user_id=user_id)\
        .order_by(DataSharingEvent.timestamp.desc())\
        .limit(limit).all()
    return [event.to_dict() for event in events]


def get_sharing_events_by_type(event_type: str, limit: int = 100) -> List[Dict]:
    """Get all sharing events of a specific type (e.g., 'api_call', 'database_write')."""
    events = DataSharingEvent.query.filter_by(event_type=event_type)\
        .order_by(DataSharingEvent.timestamp.desc())\
        .limit(limit).all()
    return [event.to_dict() for event in events]


def get_sharing_events_by_destination(destination: str, limit: int = 100) -> List[Dict]:
    """Get all sharing events to a specific destination (e.g., API URL, database table)."""
    events = DataSharingEvent.query.filter(DataSharingEvent.destination.like(f"%{destination}%"))\
        .order_by(DataSharingEvent.timestamp.desc())\
        .limit(limit).all()
    return [event.to_dict() for event in events]


def get_tags_for_identifier(identifier: str) -> List[Dict]:
    """Get all data tags associated with an identifier."""
    tags = DataTag.query.filter_by(identifier=identifier)\
        .order_by(DataTag.timestamp.desc()).all()
    return [tag.to_dict() for tag in tags]


def get_data_lineage(tag_id: str, direction: str = 'both') -> Dict:
    """
    Get data lineage for a tag.
    direction: 'up' (parents), 'down' (children), or 'both'
    """
    result = {
        'tag_id': tag_id,
        'parents': [],
        'children': []
    }
    
    if direction in ['up', 'both']:
        lineages = DataLineage.query.filter_by(child_tag_id=tag_id).all()
        for lineage in lineages:
            parent_tag = DataTag.query.filter_by(tag_id=lineage.parent_tag_id).first()
            if parent_tag:
                result['parents'].append({
                    'tag': parent_tag.to_dict(),
                    'operation': lineage.operation,
                    'timestamp': lineage.timestamp.isoformat()
                })
    
    if direction in ['down', 'both']:
        lineages = DataLineage.query.filter_by(parent_tag_id=tag_id).all()
        for lineage in lineages:
            child_tag = DataTag.query.filter_by(tag_id=lineage.child_tag_id).first()
            if child_tag:
                result['children'].append({
                    'tag': child_tag.to_dict(),
                    'operation': lineage.operation,
                    'timestamp': lineage.timestamp.isoformat()
                })
    
    return result


def get_sst_summary(user_id: Optional[int] = None, days: int = 30) -> Dict:
    """Get a summary of server-side tracking events."""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = DataSharingEvent.query.filter(DataSharingEvent.timestamp >= start_date)
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    events = query.all()
    
    summary = {
        'total_events': len(events),
        'by_type': {},
        'by_destination': {},
        'unique_identifiers': set(),
        'time_range': {
            'start': start_date.isoformat(),
            'end': datetime.utcnow().isoformat()
        }
    }
    
    for event in events:
        # Count by type
        summary['by_type'][event.event_type] = summary['by_type'].get(event.event_type, 0) + 1
        
        # Count by destination
        dest = event.destination.split(':')[-1] if ':' in event.destination else event.destination
        summary['by_destination'][dest] = summary['by_destination'].get(dest, 0) + 1
        
        # Collect identifiers
        import json
        if event.identifiers_json:
            identifiers = json.loads(event.identifiers_json)
            summary['unique_identifiers'].update(identifiers)
    
    summary['unique_identifiers'] = list(summary['unique_identifiers'])
    
    return summary


def detect_suspicious_sharing(user_id: int, threshold: int = 5) -> List[Dict]:
    """
    Detect suspicious data sharing patterns (e.g., same data shared to many destinations).
    """
    events = DataSharingEvent.query.filter_by(user_id=user_id).all()
    
    # Group by data content hash or identifier
    sharing_counts = {}
    
    for event in events:
        import json
        identifiers = json.loads(event.identifiers_json) if event.identifiers_json else []
        key = (event.event_type, event.destination, tuple(identifiers))
        
        if key not in sharing_counts:
            sharing_counts[key] = {
                'event_type': event.event_type,
                'destination': event.destination,
                'identifiers': identifiers,
                'count': 0,
                'first_seen': event.timestamp,
                'last_seen': event.timestamp,
                'events': []
            }
        
        sharing_counts[key]['count'] += 1
        sharing_counts[key]['last_seen'] = max(sharing_counts[key]['last_seen'], event.timestamp)
        sharing_counts[key]['events'].append(event.to_dict())
    
    # Filter suspicious patterns
    suspicious = [
        info for info in sharing_counts.values()
        if info['count'] >= threshold
    ]
    
    return sorted(suspicious, key=lambda x: x['count'], reverse=True)


def export_provenance_report(user_id: int, format: str = 'json') -> str:
    """Export a complete provenance report for a user."""
    import json
    
    report = {
        'user_id': user_id,
        'generated_at': datetime.utcnow().isoformat(),
        'tags': get_tags_for_identifier(f"user_{user_id}"),
        'sharing_events': get_sharing_events_for_user(user_id, limit=1000),
        'summary': get_sst_summary(user_id=user_id),
        'suspicious_patterns': detect_suspicious_sharing(user_id)
    }
    
    if format == 'json':
        return json.dumps(report, indent=2, default=str)
    else:
        # Could add other formats (CSV, PDF, etc.)
        return json.dumps(report, indent=2, default=str)
