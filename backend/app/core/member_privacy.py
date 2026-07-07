"""Field-level privacy for member reads (GH-122 §2).

``member:read`` grants the roster; the medical bundle below additionally
requires ``member:read_medical``. The caller's household is exempt — a family
always sees the fields it can already edit interactively (the self/family
allowlist in ``PATCH /members/{id}``). Applied at the schema layer (never the
ORM) so redaction can't accidentally persist.
"""

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core.relationships import family_member_ids
from app.models.enums import Permission
from app.models.member import Member
from app.schemas.member import MemberRead

MEDICAL_FIELDS = (
    "medical_form_ab_date",
    "medical_form_c_date",
    "allergies",
    "dietary_restrictions",
    "emergency_contact_1_name",
    "emergency_contact_1_phone",
    "emergency_contact_2_name",
    "emergency_contact_2_phone",
)


def redact_medical[T: MemberRead](
    items: Sequence[T], caller: Member, permissions: frozenset[Permission], db: Session
) -> Sequence[T]:
    """Null the medical bundle on rows outside the caller's household.

    In-place on the Pydantic items; returns them for expression-style use.
    ``member:read_medical`` (and the ``is_admin`` short-circuit that implies
    it) sees everything.
    """
    if Permission.MEMBER_READ_MEDICAL in permissions:
        return items
    family = family_member_ids(caller.id, db)
    for item in items:
        if item.id in family:
            continue
        for field in MEDICAL_FIELDS:
            setattr(item, field, None)
    return items
