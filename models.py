"""
Core data models for the Agentic AI Architectural Design Framework.

These dataclasses define the shared vocabulary used across all agents:
Requirement Agent → Spatial Planning Agent → Generator → Critic → Optimizer.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple
import json


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RelationshipType(str, Enum):
    """Spatial relationship types between rooms."""
    NEAR = "near"                    # rooms should be adjacent / close
    AWAY_FROM = "away_from"          # rooms should be far apart
    CONNECTED_TO = "connected_to"    # rooms must share an edge (door)


class RoomType(str, Enum):
    """Canonical room types used throughout the system."""
    BEDROOM = "bedroom"
    BATHROOM = "bathroom"
    KITCHEN = "kitchen"
    LIVING_ROOM = "living_room"
    DINING = "dining"
    ENTRANCE = "entrance"
    HALLWAY = "hallway"
    BALCONY = "balcony"
    STUDY = "study"
    POOJA = "pooja"
    UTILITY = "utility"
    GARAGE = "garage"
    STAIRCASE = "staircase"
    STORE = "store"


# ---------------------------------------------------------------------------
# Requirement models
# ---------------------------------------------------------------------------

@dataclass
class RoomRequirement:
    """A single room the user has requested."""
    name: str                          # e.g. "Bedroom 1"
    room_type: RoomType
    min_width: float = 0.0             # ft
    min_height: float = 0.0            # ft
    preferred_area: float = 0.0        # sq ft (0 = use defaults)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "room_type": self.room_type.value,
            "min_width": self.min_width,
            "min_height": self.min_height,
            "preferred_area": self.preferred_area,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RoomRequirement":
        return cls(
            name=d["name"],
            room_type=RoomType(d["room_type"]),
            min_width=d.get("min_width", 0.0),
            min_height=d.get("min_height", 0.0),
            preferred_area=d.get("preferred_area", 0.0),
        )


@dataclass
class SpatialRelationship:
    """A directed spatial constraint between two rooms."""
    room_a: str
    room_b: str
    relationship: RelationshipType

    def to_dict(self) -> dict:
        return {
            "room_a": self.room_a,
            "room_b": self.room_b,
            "relationship": self.relationship.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SpatialRelationship":
        return cls(
            room_a=d["room_a"],
            room_b=d["room_b"],
            relationship=RelationshipType(d["relationship"]),
        )


@dataclass
class DesignRequirements:
    """Complete structured output from the Requirement Agent."""
    plot_width: float                          # ft
    plot_height: float                         # ft
    rooms: List[RoomRequirement] = field(default_factory=list)
    relationships: List[SpatialRelationship] = field(default_factory=list)
    raw_input: str = ""

    def to_dict(self) -> dict:
        return {
            "plot_width": self.plot_width,
            "plot_height": self.plot_height,
            "rooms": [r.to_dict() for r in self.rooms],
            "relationships": [r.to_dict() for r in self.relationships],
            "raw_input": self.raw_input,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> "DesignRequirements":
        return cls(
            plot_width=d["plot_width"],
            plot_height=d["plot_height"],
            rooms=[RoomRequirement.from_dict(r) for r in d.get("rooms", [])],
            relationships=[SpatialRelationship.from_dict(r) for r in d.get("relationships", [])],
            raw_input=d.get("raw_input", ""),
        )

    @classmethod
    def from_json(cls, s: str) -> "DesignRequirements":
        return cls.from_dict(json.loads(s))


# ---------------------------------------------------------------------------
# Floor-plan geometry
# ---------------------------------------------------------------------------

@dataclass
class Room:
    """A placed room with concrete geometry."""
    name: str
    room_type: RoomType
    x: float            # left edge (ft)
    y: float            # bottom edge (ft)
    width: float        # ft
    height: float       # ft

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y + self.height

    def overlaps(self, other: "Room") -> bool:
        """True if this room geometrically overlaps another (excluding touching edges)."""
        if self.x >= other.right or other.x >= self.right:
            return False
        if self.y >= other.top or other.y >= self.top:
            return False
        return True

    def overlap_area(self, other: "Room") -> float:
        """Compute the overlap area between two rooms."""
        dx = min(self.right, other.right) - max(self.x, other.x)
        dy = min(self.top, other.top) - max(self.y, other.y)
        if dx <= 0 or dy <= 0:
            return 0.0
        return dx * dy

    def shares_edge(self, other: "Room", tolerance: float = 0.5) -> bool:
        """True if two rooms share a wall segment (adjacent)."""
        # Vertical adjacency (left/right walls touch)
        if abs(self.right - other.x) < tolerance or abs(other.right - self.x) < tolerance:
            overlap_start = max(self.y, other.y)
            overlap_end = min(self.top, other.top)
            if overlap_end - overlap_start > tolerance:
                return True
        # Horizontal adjacency (top/bottom walls touch)
        if abs(self.top - other.y) < tolerance or abs(other.top - self.y) < tolerance:
            overlap_start = max(self.x, other.x)
            overlap_end = min(self.right, other.right)
            if overlap_end - overlap_start > tolerance:
                return True
        return False

    def distance_to(self, other: "Room") -> float:
        """Euclidean distance between room centres."""
        cx1, cy1 = self.center
        cx2, cy2 = other.center
        return ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "room_type": self.room_type.value,
            "x": self.x, "y": self.y,
            "width": self.width, "height": self.height,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Room":
        return cls(
            name=d["name"],
            room_type=RoomType(d["room_type"]),
            x=d["x"], y=d["y"],
            width=d["width"], height=d["height"],
        )


@dataclass
class FloorPlan:
    """A complete candidate floor plan."""
    plot_width: float
    plot_height: float
    rooms: List[Room] = field(default_factory=list)
    score: Optional[float] = None
    score_details: Optional[Dict] = None

    @property
    def total_room_area(self) -> float:
        return sum(r.area for r in self.rooms)

    @property
    def utilization(self) -> float:
        plot_area = self.plot_width * self.plot_height
        return self.total_room_area / plot_area if plot_area > 0 else 0.0

    def get_room(self, name: str) -> Optional[Room]:
        for r in self.rooms:
            if r.name.lower() == name.lower():
                return r
        return None

    def to_dict(self) -> dict:
        return {
            "plot_width": self.plot_width,
            "plot_height": self.plot_height,
            "rooms": [r.to_dict() for r in self.rooms],
            "score": self.score,
            "score_details": self.score_details,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FloorPlan":
        fp = cls(
            plot_width=d["plot_width"],
            plot_height=d["plot_height"],
            rooms=[Room.from_dict(r) for r in d.get("rooms", [])],
            score=d.get("score"),
            score_details=d.get("score_details"),
        )
        return fp
