from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json



db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    birthday = db.Column(db.Date, nullable=False)
    income = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), nullable=False, default='SAR')
    budget_style = db.Column(db.String(50), default='Balanced')
    goals = db.Column(db.String(500))
    week_start = db.Column(db.String(20), default='Monday')
    gender = db.Column(db.String(20), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('expenses', lazy=True))


# Provenance and SST Detection Models
class DataTag(db.Model):
    """Stores data tags for personal information."""
    __tablename__ = 'data_tags'
    
    id = db.Column(db.Integer, primary_key=True)
    tag_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    identifier = db.Column(db.String(200), nullable=False, index=True)  # user_id, email, etc.
    data_type = db.Column(db.String(100), nullable=False)  # email, name, income, etc.
    data_value_hash = db.Column(db.String(64), nullable=False, index=True)  # Hash of actual value for privacy
    source = db.Column(db.String(200), nullable=False)  # Where data came from
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    operations_json = db.Column(db.Text)  # JSON array of operations
    derived_from_json = db.Column(db.Text)  # JSON array of parent tag IDs
    
    def to_dict(self):
        return {
            'tag_id': self.tag_id,
            'identifier': self.identifier,
            'data_type': self.data_type,
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'operations': json.loads(self.operations_json) if self.operations_json else [],
            'derived_from': json.loads(self.derived_from_json) if self.derived_from_json else []
        }


class DataSharingEvent(db.Model):
    """Stores audit logs of data sharing events (SST detection)."""
    __tablename__ = 'data_sharing_events'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)  # api_call, database_write, email, etc.
    destination = db.Column(db.String(500), nullable=False)  # URL, table name, email address, etc.
    data_json = db.Column(db.Text)  # JSON of shared data (truncated/anonymized)
    tags_json = db.Column(db.Text)  # JSON array of associated tags
    identifiers_json = db.Column(db.Text)  # JSON array of user identifiers
    metadata_json = db.Column(db.Text)  # Additional metadata (headers, SQL, etc.)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    request_id = db.Column(db.String(100), nullable=True, index=True)
    
    user = db.relationship('User', backref=db.backref('sharing_events', lazy=True))
    
    def to_dict(self):
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'destination': self.destination,
            'data': json.loads(self.data_json) if self.data_json else {},
            'tags': json.loads(self.tags_json) if self.tags_json else [],
            'identifiers': json.loads(self.identifiers_json) if self.identifiers_json else [],
            'metadata': json.loads(self.metadata_json) if self.metadata_json else {},
            'user_id': self.user_id,
            'request_id': self.request_id
        }


class DataLineage(db.Model):
    """Stores data lineage relationships between tags."""
    __tablename__ = 'data_lineage'
    
    id = db.Column(db.Integer, primary_key=True)
    parent_tag_id = db.Column(db.String(100), nullable=False, index=True)
    child_tag_id = db.Column(db.String(100), nullable=False, index=True)
    operation = db.Column(db.String(200), nullable=False)  # Operation that created the relationship
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (db.UniqueConstraint('parent_tag_id', 'child_tag_id', name='_parent_child_uc'),)
