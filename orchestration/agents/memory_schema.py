"""
Structured customer memory schema for real estate sales.
Supports explicit vs inferred facts, strength levels, and merge rules.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

# --- Memory field keys ---
MEMORY_FIELDS = frozenset({
    "budget", "preferred_locations", "property_type", "bedrooms",
    "family_size", "investment_vs_residence", "urgency", "timeline",
    "rejected_options", "preferred_financing_style",
})

# --- Strength: strong > medium > weak. Strong never overwritten by weaker. ---
STRENGTH_LEVELS = frozenset({"strong", "medium", "weak"})

# --- Source: explicit = user said it; inferred = derived ---
FACT_SOURCES = frozenset({"explicit", "inferred"})


@dataclass
class MemoryFact:
    """Single fact with value, strength, and source."""
    value: Any  # str | int | float | dict | list
    strength: str = "medium"
    source: str = "inferred"

    def __post_init__(self) -> None:
        if self.strength not in STRENGTH_LEVELS:
            self.strength = "medium"
        if self.source not in FACT_SOURCES:
            self.source = "inferred"

    def to_dict(self) -> dict:
        return {"value": self.value, "strength": self.strength, "source": self.source}

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryFact":
        return cls(
            value=d.get("value"),
            strength=str(d.get("strength", "medium")).lower() or "medium",
            source=str(d.get("source", "inferred")).lower() or "inferred",
        )


def _strength_rank(s: str) -> int:
    """Higher = stronger. strong=3, medium=2, weak=1."""
    return {"strong": 3, "medium": 2, "weak": 1}.get(s, 1)


def _source_rank(s: str) -> int:
    """Explicit beats inferred."""
    return 2 if s == "explicit" else 1


def should_overwrite(existing: MemoryFact, incoming: MemoryFact) -> bool:
    """
    True if incoming should overwrite existing.
    Never overwrite strong with weak. Never overwrite explicit with inferred of same strength.
    """
    if incoming.strength == "strong" and existing.strength != "strong":
        return True
    if _strength_rank(incoming.strength) > _strength_rank(existing.strength):
        return True
    if (
        _strength_rank(incoming.strength) == _strength_rank(existing.strength)
        and _source_rank(incoming.source) > _source_rank(existing.source)
    ):
        return True
    return False


def merge_fact_value(existing_val: Any, incoming_val: Any, field: str) -> Any:
    """
    Merge values for fields that accumulate (e.g. preferred_locations, rejected_options).
    For scalar fields, incoming replaces if overwrite.
    """
    if field in ("preferred_locations", "rejected_options"):
        if not isinstance(incoming_val, list):
            incoming_val = [incoming_val] if incoming_val is not None else []
        if not isinstance(existing_val, list):
            existing_val = [existing_val] if existing_val is not None else []
        seen = set()
        out = []
        for x in existing_val + incoming_val:
            key = str(x).strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(x)
        return out[:20]  # cap
    return incoming_val if incoming_val is not None else existing_val


@dataclass
class CustomerMemoryProfile:
    """Structured customer memory profile - all tracked fields with facts."""
    budget: dict = field(default_factory=dict)  # {min, max} as Decimal/float
    preferred_locations: list = field(default_factory=list)
    property_type: str = ""
    bedrooms: Optional[int] = None
    family_size: Optional[int] = None
    investment_vs_residence: str = ""
    urgency: str = ""
    timeline: str = ""
    rejected_options: list = field(default_factory=list)
    preferred_financing_style: str = ""

    # Per-field metadata: strength, source (stored as _meta for serialization)
    _facts: dict = field(default_factory=dict)  # field -> MemoryFact

    def get_fact(self, field: str) -> Optional[MemoryFact]:
        return self._facts.get(field)

    def set_fact(
        self,
        field: str,
        value: Any,
        strength: str = "medium",
        source: str = "inferred",
        merge: bool = True,
    ) -> bool:
        """
        Set a fact. Returns True if updated.
        Uses should_overwrite to avoid overwriting strong with weak.
        List fields (preferred_locations, rejected_options) always accumulate.
        """
        if field not in MEMORY_FIELDS:
            return False
        is_list_field = field in ("preferred_locations", "rejected_options")
        incoming = MemoryFact(value=value, strength=strength, source=source)
        existing = self._facts.get(field)
        if existing and not is_list_field and not should_overwrite(existing, incoming):
            return False
        if is_list_field or (merge and existing):
            merged_val = merge_fact_value(
                existing.value if existing else None, value, field
            )
        else:
            merged_val = value
        self._facts[field] = MemoryFact(
            value=merged_val, strength=incoming.strength, source=incoming.source
        )
        # Sync to main attrs for easy access
        if field == "budget" and isinstance(merged_val, dict):
            self.budget = merged_val
        elif field == "preferred_locations":
            self.preferred_locations = merged_val if isinstance(merged_val, list) else [merged_val]
        elif field == "property_type":
            self.property_type = str(merged_val or "")
        elif field == "bedrooms":
            self.bedrooms = int(merged_val) if merged_val is not None else None
        elif field == "family_size":
            self.family_size = int(merged_val) if merged_val is not None else None
        elif field == "investment_vs_residence":
            self.investment_vs_residence = str(merged_val or "")
        elif field == "urgency":
            self.urgency = str(merged_val or "")
        elif field == "timeline":
            self.timeline = str(merged_val or "")
        elif field == "rejected_options":
            self.rejected_options = merged_val if isinstance(merged_val, list) else [merged_val]
        elif field == "preferred_financing_style":
            self.preferred_financing_style = str(merged_val or "")
        return True

    def to_dict(self) -> dict:
        """Serializable for persistence and downstream agents."""
        out = {
            "budget": self.budget,
            "preferred_locations": self.preferred_locations,
            "property_type": self.property_type,
            "bedrooms": self.bedrooms,
            "family_size": self.family_size,
            "investment_vs_residence": self.investment_vs_residence,
            "urgency": self.urgency,
            "timeline": self.timeline,
            "rejected_options": self.rejected_options,
            "preferred_financing_style": self.preferred_financing_style,
            "_facts": {
                k: v.to_dict() for k, v in self._facts.items()
            },
        }
        return out

    @classmethod
    def from_dict(cls, d: dict) -> "CustomerMemoryProfile":
        if not d:
            return cls()
        facts = {}
        for k, v in (d.get("_facts") or {}).items():
            if k in MEMORY_FIELDS and isinstance(v, dict):
                facts[k] = MemoryFact.from_dict(v)
        p = cls(
            budget=dict(d.get("budget") or {}),
            preferred_locations=list(d.get("preferred_locations") or []),
            property_type=str(d.get("property_type", "")),
            bedrooms=int(d["bedrooms"]) if d.get("bedrooms") is not None else None,
            family_size=int(d["family_size"]) if d.get("family_size") is not None else None,
            investment_vs_residence=str(d.get("investment_vs_residence", "")),
            urgency=str(d.get("urgency", "")),
            timeline=str(d.get("timeline", "")),
            rejected_options=list(d.get("rejected_options") or []),
            preferred_financing_style=str(d.get("preferred_financing_style", "")),
            _facts=facts,
        )
        # Sync _facts values into main attrs from stored facts
        for k, f in facts.items():
            if f.value is not None:
                if k == "budget":
                    p.budget = f.value if isinstance(f.value, dict) else {}
                elif k == "preferred_locations":
                    p.preferred_locations = f.value if isinstance(f.value, list) else []
                elif k == "rejected_options":
                    p.rejected_options = f.value if isinstance(f.value, list) else []
                elif k == "property_type":
                    p.property_type = str(f.value)
                elif k == "bedrooms":
                    p.bedrooms = int(f.value) if f.value is not None else None
                elif k == "family_size":
                    p.family_size = int(f.value) if f.value is not None else None
                elif k == "investment_vs_residence":
                    p.investment_vs_residence = str(f.value)
                elif k == "urgency":
                    p.urgency = str(f.value)
                elif k == "timeline":
                    p.timeline = str(f.value)
                elif k == "preferred_financing_style":
                    p.preferred_financing_style = str(f.value)
        return p
