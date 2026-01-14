"""Utilities for OWASP project level normalization and mapping."""

import re
from decimal import Decimal, InvalidOperation

from apps.owasp.models.enums.project import ProjectLevel

LEVEL_MAP: dict[Decimal, str] = {
    Decimal(4): str(ProjectLevel.FLAGSHIP),
    Decimal("3.5"): str(ProjectLevel.FLAGSHIP),
    Decimal(3): str(ProjectLevel.PRODUCTION),
    Decimal(2): str(ProjectLevel.INCUBATOR),
    Decimal(1): str(ProjectLevel.LAB),
    Decimal(0): str(ProjectLevel.OTHER),
}


def normalize_project_name(name: str) -> str:
    """Normalize names: lowercase, remove 'owasp', and strip special chars."""
    if not name:
        return ""
    return re.sub(r"[^a-z0-9]+", "", name.lower().replace("owasp", ""))


def map_level(level_value) -> str | None:
    """Safely map raw JSON level to ProjectLevel value."""
    try:
        return LEVEL_MAP.get(Decimal(str(level_value)))
    except (InvalidOperation, TypeError, ValueError):
        return None
