"""Re-export MemberRelationship from member module for backward compatibility."""

from app.models.member import MemberRelationship

__all__ = ["MemberRelationship"]
