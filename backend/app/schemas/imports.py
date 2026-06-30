from pydantic import BaseModel


class TwhImportRead(BaseModel):
    """Summary returned by POST /import/twh."""

    patrols: int
    members: int
    relationships: int
    positions: int
    position_assignments: int
    locations: int
    event_types: int
    events: int
    participants: int
    skipped: int
    warnings: list[str]
