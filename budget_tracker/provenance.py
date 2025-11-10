"""
Provenance Tracking Module
Tags personal data with unique identifiers and propagates metadata through operations.
"""
import uuid
import time
from typing import Any, Dict, Set, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import copy


class DataType(Enum):
    """Types of personal data"""
    EMAIL = "email"
    NAME = "name"
    BIRTHDAY = "birthday"
    GENDER = "gender"
    INCOME = "income"
    LOCATION = "location"
    PHONE = "phone"
    DERIVED = "derived"  # Data derived from personal data
    UNKNOWN = "unknown"


@dataclass
class ProvenanceTag:
    """Metadata tag attached to personal data"""
    tag_id: str  # Unique identifier for this tag
    owner_id: str  # User identifier (e.g., email, user_id)
    data_type: DataType
    source: str  # Where the data came from (e.g., "signup_form", "api_request")
    timestamp: float
    lineage: List[str] = field(default_factory=list)  # Chain of operations
    transformations: List[str] = field(default_factory=list)  # Operations applied
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            'tag_id': self.tag_id,
            'owner_id': self.owner_id,
            'data_type': self.data_type.value,
            'source': self.source,
            'timestamp': self.timestamp,
            'lineage': self.lineage,
            'transformations': self.transformations
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ProvenanceTag':
        """Create from dictionary"""
        return cls(
            tag_id=data['tag_id'],
            owner_id=data['owner_id'],
            data_type=DataType(data['data_type']),
            source=data['source'],
            timestamp=data['timestamp'],
            lineage=data.get('lineage', []),
            transformations=data.get('transformations', [])
        )


class TaggedData:
    """Wrapper for data with provenance metadata"""
    def __init__(self, value: Any, tag: ProvenanceTag):
        self.value = value
        self.tag = tag
        self._original_type = type(value)
    
    def __repr__(self):
        return f"TaggedData(value={self.value!r}, tag_id={self.tag.tag_id})"
    
    def __str__(self):
        return str(self.value)
    
    def __eq__(self, other):
        if isinstance(other, TaggedData):
            return self.value == other.value
        return self.value == other
    
    def __hash__(self):
        return hash(self.value)
    
    def unwrap(self):
        """Get the underlying value"""
        return self.value


class ProvenanceTracker:
    """Tracks provenance of personal data through operations"""
    
    def __init__(self):
        self._tagged_objects: Dict[int, ProvenanceTag] = {}  # id(obj) -> tag
        self._tag_registry: Dict[str, ProvenanceTag] = {}  # tag_id -> tag
        self._operation_history: List[Dict] = []
    
    def tag_data(self, value: Any, owner_id: str, data_type: DataType, 
                 source: str = "unknown") -> TaggedData:
        """Tag personal data with provenance metadata"""
        tag = ProvenanceTag(
            tag_id=str(uuid.uuid4()),
            owner_id=owner_id,
            data_type=data_type,
            source=source,
            timestamp=time.time()
        )
        
        tagged = TaggedData(value, tag)
        self._tagged_objects[id(value)] = tag
        self._tag_registry[tag.tag_id] = tag
        
        return tagged
    
    def tag_object(self, obj: Any, owner_id: str, data_type: DataType, 
                   source: str = "unknown"):
        """Tag an object in-place (for mutable objects)"""
        tag = ProvenanceTag(
            tag_id=str(uuid.uuid4()),
            owner_id=owner_id,
            data_type=data_type,
            source=source,
            timestamp=time.time()
        )
        self._tagged_objects[id(obj)] = tag
        self._tag_registry[tag.tag_id] = tag
        return tag
    
    def get_tag(self, obj: Any) -> Optional[ProvenanceTag]:
        """Get provenance tag for an object"""
        obj_id = id(obj)
        return self._tagged_objects.get(obj_id)
    
    def has_tag(self, obj: Any) -> bool:
        """Check if object has provenance tag"""
        return id(obj) in self._tagged_objects
    
    def propagate_tag(self, source_obj: Any, dest_obj: Any, operation: str = "unknown"):
        """Propagate tag from source to destination (for derived data)"""
        source_tag = self.get_tag(source_obj)
        if source_tag:
            # Create new tag with lineage
            new_tag = ProvenanceTag(
                tag_id=str(uuid.uuid4()),
                owner_id=source_tag.owner_id,
                data_type=DataType.DERIVED,
                source=source_tag.source,
                timestamp=time.time(),
                lineage=source_tag.lineage + [source_tag.tag_id],
                transformations=source_tag.transformations + [operation]
            )
            self._tagged_objects[id(dest_obj)] = new_tag
            self._tag_registry[new_tag.tag_id] = new_tag
            return new_tag
        return None
    
    def record_operation(self, operation: str, inputs: List[Any], output: Any):
        """Record an operation on tagged data"""
        input_tags = [self.get_tag(inp) for inp in inputs if self.has_tag(inp)]
        output_tag = self.get_tag(output)
        
        if input_tags or output_tag:
            self._operation_history.append({
                'operation': operation,
                'timestamp': time.time(),
                'input_tags': [t.tag_id for t in input_tags if t],
                'output_tag': output_tag.tag_id if output_tag else None
            })
    
    def get_all_tags(self) -> List[ProvenanceTag]:
        """Get all registered tags"""
        return list(self._tag_registry.values())
    
    def get_tags_by_owner(self, owner_id: str) -> List[ProvenanceTag]:
        """Get all tags for a specific owner"""
        return [tag for tag in self._tag_registry.values() if tag.owner_id == owner_id]
    
    def clear(self):
        """Clear all tracking data"""
        self._tagged_objects.clear()
        self._tag_registry.clear()
        self._operation_history.clear()


# Global instance
_tracker = ProvenanceTracker()


def get_tracker() -> ProvenanceTracker:
    """Get the global provenance tracker instance"""
    return _tracker


def tag_personal_data(value: Any, owner_id: str, data_type: DataType, 
                     source: str = "unknown") -> TaggedData:
    """Convenience function to tag personal data"""
    return _tracker.tag_data(value, owner_id, data_type, source)


def detect_personal_data(value: Any) -> Optional[DataType]:
    """Heuristically detect if value contains personal data"""
    if not isinstance(value, str):
        return None
    
    value_lower = value.lower().strip()
    
    # Email detection
    if '@' in value and '.' in value:
        return DataType.EMAIL
    
    # Name detection (simple heuristic - could be improved)
    if len(value.split()) >= 2 and value.replace(' ', '').isalpha():
        return DataType.NAME
    
    # Phone detection
    if value.replace('-', '').replace(' ', '').replace('(', '').replace(')', '').isdigit():
        if len(value.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')) >= 10:
            return DataType.PHONE
    
    return None
