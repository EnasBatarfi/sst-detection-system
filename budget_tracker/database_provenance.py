"""
Database Models for Provenance and Audit Logging
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

# Import the existing db instance
from models import db


class ProvenanceRecord(db.Model):
    """Stores provenance metadata for tagged data"""
    __tablename__ = 'provenance_records'
    
    id = db.Column(db.Integer, primary_key=True)
    tag_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    owner_id = db.Column(db.String(255), nullable=False, index=True)
    data_type = db.Column(db.String(50), nullable=False)
    source = db.Column(db.String(255))
    timestamp = db.Column(db.Float, nullable=False)
    lineage = db.Column(db.Text)  # JSON array of tag IDs
    transformations = db.Column(db.Text)  # JSON array of operations
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'tag_id': self.tag_id,
            'owner_id': self.owner_id,
            'data_type': self.data_type,
            'source': self.source,
            'timestamp': self.timestamp,
            'lineage': json.loads(self.lineage) if self.lineage else [],
            'transformations': json.loads(self.transformations) if self.transformations else [],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class AuditLog(db.Model):
    """Stores audit logs for data sharing events"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    timestamp = db.Column(db.Float, nullable=False, index=True)
    owner_id = db.Column(db.String(255), nullable=False, index=True)
    destination = db.Column(db.String(500), nullable=False, index=True)
    data_types = db.Column(db.Text)  # JSON array
    tag_ids = db.Column(db.Text)  # JSON array
    metadata = db.Column(db.Text)  # JSON object
    stack_trace = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'event_type': self.event_type,
            'timestamp': self.timestamp,
            'owner_id': self.owner_id,
            'destination': self.destination,
            'data_types': json.loads(self.data_types) if self.data_types else [],
            'tag_ids': json.loads(self.tag_ids) if self.tag_ids else [],
            'metadata': json.loads(self.metadata) if self.metadata else {},
            'stack_trace': self.stack_trace,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


def store_provenance_record(tag):
    """Store a provenance tag in the database"""
    try:
        record = ProvenanceRecord(
            tag_id=tag.tag_id,
            owner_id=tag.owner_id,
            data_type=tag.data_type.value,
            source=tag.source,
            timestamp=tag.timestamp,
            lineage=json.dumps(tag.lineage),
            transformations=json.dumps(tag.transformations)
        )
        db.session.add(record)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error storing provenance record: {e}")


def store_audit_event(event):
    """Store an audit event in the database"""
    try:
        log = AuditLog(
            event_id=event.event_id,
            event_type=event.event_type.value,
            timestamp=event.timestamp,
            owner_id=event.owner_id,
            destination=event.destination,
            data_types=json.dumps(event.data_types),
            tag_ids=json.dumps(event.tag_ids),
            metadata=json.dumps(event.metadata),
            stack_trace=event.stack_trace
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error storing audit event: {e}")
