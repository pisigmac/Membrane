"""Session safety gates."""

from __future__ import annotations

from membrane.config import MembraneConfig
from membrane.models import Session


def is_session_safe(session: Session, config: MembraneConfig) -> bool:
    """Never construct memory from adversarial / jailbreak sessions."""
    if session.adversarial or session.jailbreak:
        return False
    if session.safety_score < config.construction.safety_score_threshold:
        return False
    return True
