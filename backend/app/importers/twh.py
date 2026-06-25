"""
TroopWebHost XML full-data import.

Maps TWH's flat table-per-element XML export onto OpenTroop's SQLAlchemy models.
All TWH integer IDs are tracked in local maps and converted to UUIDv7 during import;
the original IDs are never stored.

Supported record types
    Patrol          → Group  (group_type=PATROL); each scout's Patrol → GroupMember
    Person          → Member  (Adult_Flag, Alumni_Flag, Swim_Level, Patrol, OA fields)
    Relationship    → MemberRelationship  (only "Parent" seen in practice; extended types mapped)
    Location        → Location
    Event_Type      → EventType  (capability flags translated 1-to-1)
    Event           → Event  (linked_event_id resolved in a second pass)
    Event_Participant → EventParticipant

Usage:
    from xml.etree import ElementTree as ET
    from app.importers.twh import TwhImporter

    root = ET.parse("export.xml").getroot()
    result = TwhImporter(session, tenant_id).run(root)
"""

from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.enums import (
    GroupType,
    MemberStatus,
    MemberType,
    RelationshipType,
    RsvpStatus,
    SwimClassification,
)
from app.models.event import Event, EventParticipant
from app.models.event_type import EventType
from app.models.group import Group, GroupMember
from app.models.location import Location
from app.models.member import Member
from app.models.relationship import MemberRelationship


@dataclass
class TwhImportResult:
    patrols: int = 0
    members: int = 0
    relationships: int = 0
    locations: int = 0
    event_types: int = 0
    events: int = 0
    participants: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Low-level XML helpers
# ---------------------------------------------------------------------------


def _text(elem: ET.Element, tag: str, default: str = "") -> str:
    child = elem.find(tag)
    if child is None or not child.text:
        return default
    return child.text.strip()


def _flag(elem: ET.Element, tag: str) -> bool:
    """Return True when a TWH boolean flag field contains 'Y' (case-insensitive)."""
    return _text(elem, tag).upper() == "Y"


def _parse_date(value: str) -> date | None:
    """Parse a TWH date string (M/D/YYYY H:MM:SS AM) into a :class:`date`."""
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y %I:%M:%S %p").date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_datetime(value: str) -> datetime | None:
    """Parse a TWH datetime string (M/D/YYYY H:MM:SS AM) into a UTC-aware datetime."""
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=UTC)
    except ValueError:
        return None


def _parse_decimal(elem: ET.Element, tag: str) -> Decimal | None:
    v = _text(elem, tag)
    if not v:
        return None
    try:
        return Decimal(v)
    except InvalidOperation:
        return None


def _parse_int(elem: ET.Element, tag: str) -> int | None:
    v = _text(elem, tag)
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _valid_email(value: str) -> str | None:
    """Return *value* if it looks like an email address, else None.

    Guards against placeholder strings (e.g. ``[email]``) that can appear in
    XML exports if a pre-processing step scrubs free-text PII aggressively.
    """
    if not value or "@" not in value:
        return None
    return value


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------


class TwhImporter:
    """Imports a parsed TWH XML tree into the current tenant.

    Creates ORM objects and flushes them to the session without committing.
    The caller is responsible for ``session.commit()`` (or rollback on error).
    """

    def __init__(self, session: Session, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.result = TwhImportResult()

        # TWH string ID → OpenTroop UUID  (built during import, used for FK resolution)
        self._patrol_map: dict[str, uuid.UUID] = {}
        self._person_map: dict[str, uuid.UUID] = {}
        self._location_map: dict[str, uuid.UUID] = {}
        self._event_type_map: dict[str, uuid.UUID] = {}
        self._event_map: dict[str, uuid.UUID] = {}
        # Guard against duplicate (event_id, member_id) participant rows in the XML
        self._participant_seen: set[tuple[uuid.UUID, uuid.UUID]] = set()

    def run(self, root: ET.Element) -> TwhImportResult:
        """Import all supported record types from *root* in dependency order."""
        self._import_patrols(root)
        self._import_members(root)
        self._import_relationships(root)
        self._import_locations(root)
        self._import_event_types(root)
        self._import_events(root)
        self._import_participants(root)
        self.session.flush()
        return self.result

    # ------------------------------------------------------------------
    # Patrols
    # ------------------------------------------------------------------

    def _import_patrols(self, root: ET.Element) -> None:
        for elem in root.findall("Patrol"):
            twh_id = _text(elem, "i")
            if not twh_id:
                continue
            name = _text(elem, "Patrol_Name") or f"Patrol {twh_id}"
            # Patrols are folded into the general Group model as PATROL-type groups.
            patrol = Group(tenant_id=self.tenant_id, name=name, group_type=GroupType.PATROL)
            self.session.add(patrol)
            self.session.flush()
            self._patrol_map[twh_id] = patrol.id
            self.result.patrols += 1

    # ------------------------------------------------------------------
    # Members  (TWH: Person)
    # ------------------------------------------------------------------

    def _import_members(self, root: ET.Element) -> None:
        for elem in root.findall("Person"):
            twh_id = _text(elem, "i")
            if not twh_id:
                continue

            first_name = _text(elem, "Name_First")
            last_name = _text(elem, "Name_Last")
            if not first_name and not last_name:
                self.result.skipped += 1
                continue

            is_adult = _text(elem, "Adult_Flag").upper() in ("Y", "1")
            is_alumni = _flag(elem, "Alumni_Flag")
            is_troop_member = _text(elem, "Troop_Member_Flag").upper() != "N"

            if is_alumni:
                status = MemberStatus.ALUMNI
            elif not is_troop_member:
                status = MemberStatus.INACTIVE
            else:
                status = MemberStatus.ACTIVE

            swim_raw = _text(elem, "Swim_Level").lower()
            if "non" in swim_raw:
                swim = SwimClassification.NONSWIMMER
            elif "beginner" in swim_raw:
                swim = SwimClassification.BEGINNER
            elif "swimmer" in swim_raw:
                swim = SwimClassification.SWIMMER
            else:
                swim = SwimClassification.NONSWIMMER

            patrol_twh = _text(elem, "Patrol")
            patrol_group_id = self._patrol_map.get(patrol_twh) if patrol_twh else None

            # Combine first + last for emergency contact names
            ec1_name = (
                " ".join(
                    filter(
                        None,
                        [
                            _text(elem, "Emergency_Contact_1_Name_First"),
                            _text(elem, "Emergency_Contact_1_Name_Last"),
                        ],
                    )
                )
                or None
            )
            ec2_name = (
                " ".join(
                    filter(
                        None,
                        [
                            _text(elem, "Emergency_Contact_2_Name_First"),
                            _text(elem, "Emergency_Contact_2_Name_Last"),
                        ],
                    )
                )
                or None
            )

            # Medical form: TWH Part A+B = our ab_date; Part C = c_date
            ab_raw = _text(elem, "Class_1_Medical_Form_Date") or _text(
                elem, "Class_2_Medical_Form_Date"
            )

            member = Member(
                tenant_id=self.tenant_id,
                first_name=first_name,
                middle_name=_text(elem, "Name_Middle") or None,
                last_name=last_name,
                name_suffix=_text(elem, "Name_Suffix") or None,
                nickname=_text(elem, "Nickname") or None,
                bsa_id=_text(elem, "BSA_Membership_Number") or None,
                member_type=MemberType.ADULT if is_adult else MemberType.SCOUT,
                membership_status=status,
                swim_classification=swim,
                date_of_birth=_parse_date(_text(elem, "Date_Of_Birth")),
                email=_valid_email(_text(elem, "Email_Address")),
                phone=_text(elem, "Cell_Phone") or _text(elem, "Home_Phone") or None,
                address_line1=_text(elem, "Mailing_Address_Line_1") or None,
                address_line2=_text(elem, "Mailing_Address_Line_2") or None,
                city=_text(elem, "Mailing_Address_City") or None,
                state=_text(elem, "Mailing_Address_State") or None,
                postal_code=_text(elem, "Mailing_Address_Zip") or None,
                country=_text(elem, "Mailing_Address_Country") or None,
                troop_membership_start_date=_parse_date(_text(elem, "Troop_Membership_Start_Date")),
                troop_membership_end_date=_parse_date(_text(elem, "Troop_Membership_End_Date")),
                swim_date=_parse_date(_text(elem, "Swim_Date")),
                medical_form_ab_date=_parse_date(ab_raw),
                medical_form_c_date=_parse_date(_text(elem, "Class_3_Medical_Form_Date")),
                allergies=_text(elem, "Allergies") or None,
                dietary_restrictions=_text(elem, "Dietary_Restrictions") or None,
                emergency_contact_1_name=ec1_name,
                emergency_contact_1_phone=_text(elem, "Emergency_Contact_1_Phone") or None,
                emergency_contact_2_name=ec2_name,
                emergency_contact_2_phone=_text(elem, "Emergency_Contact_2_Phone") or None,
                oa_member=_flag(elem, "OA_Member_Flag"),
                oa_active=_flag(elem, "OA_Active_Flag"),
                oa_election_date=_parse_date(_text(elem, "OA_Election_Date")),
                oa_call_out_date=_parse_date(_text(elem, "OA_Call_Out_Date")),
                oa_ordeal_date=_parse_date(_text(elem, "OA_Ordeal_Date")),
                oa_brotherhood_date=_parse_date(_text(elem, "OA_Brotherhood_Date")),
                oa_vigil_date=_parse_date(_text(elem, "OA_Vigil_Date")),
                oa_vigil_name=_text(elem, "OA_Vigil_Name") or None,
            )
            self.session.add(member)
            self.session.flush()
            self._person_map[twh_id] = member.id
            self.result.members += 1

            # Patrol assignment is now a membership in the PATROL-type group.
            if patrol_group_id is not None:
                self.session.add(
                    GroupMember(
                        tenant_id=self.tenant_id,
                        group_id=patrol_group_id,
                        member_id=member.id,
                    )
                )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    def _import_relationships(self, root: ET.Element) -> None:
        for elem in root.findall("Relationship"):
            twh_id = _text(elem, "i")
            scout_twh = _text(elem, "Person_ID_Scout")
            adult_twh = _text(elem, "Person_ID_Adult")

            scout_id = self._person_map.get(scout_twh)
            adult_id = self._person_map.get(adult_twh)
            if not scout_id or not adult_id:
                self.result.warnings.append(
                    f"Relationship {twh_id}: "
                    f"person {scout_twh!r} or {adult_twh!r} not found — skipped"
                )
                self.result.skipped += 1
                continue

            rel_raw = _text(elem, "Relationship_Type").lower()
            if "parent" in rel_raw:
                rel_type = RelationshipType.PARENT_OF
            elif "guardian" in rel_raw:
                rel_type = RelationshipType.GUARDIAN_OF
            elif "sibling" in rel_raw:
                rel_type = RelationshipType.SIBLING_OF
            else:
                rel_type = RelationshipType.OTHER

            self.session.add(
                MemberRelationship(
                    tenant_id=self.tenant_id,
                    from_member_id=adult_id,  # adult is "from" (holds the named role)
                    to_member_id=scout_id,
                    relationship_type=rel_type,
                )
            )
            self.result.relationships += 1

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------

    def _import_locations(self, root: ET.Element) -> None:
        for elem in root.findall("Location"):
            twh_id = _text(elem, "i")
            if not twh_id:
                continue
            if _flag(elem, "Disabled_Flag"):
                continue

            dist_raw = _text(elem, "Distance")
            distance: float | None = None
            with contextlib.suppress(ValueError):
                distance = float(dist_raw) if dist_raw else None

            location = Location(
                tenant_id=self.tenant_id,
                name=_text(elem, "Location_Name") or f"Location {twh_id}",
                street1=_text(elem, "Address_Line_1") or None,
                street2=_text(elem, "Address_Line_2") or None,
                city=_text(elem, "Address_City") or None,
                state=_text(elem, "Address_State") or None,
                postal_code=_text(elem, "Address_Zip") or None,
                country=_text(elem, "Address_Country") or None,
                phone=_text(elem, "Telephone_Number") or None,
                website_url=_text(elem, "Website_URL") or None,
                directions=_text(elem, "Directions") or None,
                description=_text(elem, "Description") or None,
                distance_miles=distance,
            )
            self.session.add(location)
            self.session.flush()
            self._location_map[twh_id] = location.id
            self.result.locations += 1

    # ------------------------------------------------------------------
    # Event types
    # ------------------------------------------------------------------

    def _import_event_types(self, root: ET.Element) -> None:
        from sqlalchemy import select

        for elem in root.findall("Event_Type"):
            twh_id = _text(elem, "i")
            if not twh_id:
                continue
            name = _text(elem, "Event_Type_Name") or f"Event Type {twh_id}"

            # If a system event type with this name was already seeded (e.g. by
            # provision_tenant), reuse it so we don't violate the tenant+name unique index.
            existing = self.session.scalar(
                select(EventType).where(
                    EventType.tenant_id == self.tenant_id,
                    EventType.name == name,
                    EventType.is_deleted.is_(False),
                )
            )
            if existing:
                self._event_type_map[twh_id] = existing.id
                continue

            is_active = not _flag(elem, "Event_Type_Disabled_Flag")
            color_raw = _text(elem, "Display_Color").lstrip("#")
            color = f"#{color_raw}" if color_raw else None

            et = EventType(
                tenant_id=self.tenant_id,
                name=name,
                is_active=is_active,
                is_system=False,
                color=color,
                tracks_camping_nights=_flag(elem, "Camping_Nights_Flag"),
                tracks_service_hours=_flag(elem, "Service_Hours_Flag"),
                tracks_mileage=_flag(elem, "Hiking_Miles_Flag"),
                allow_signups=_flag(elem, "SignUp_Flag"),
                require_permission_slip=_flag(elem, "Permission_Slip_Flag"),
                is_online=_flag(elem, "Online_Meeting_Flag"),
            )
            self.session.add(et)
            self.session.flush()
            self._event_type_map[twh_id] = et.id
            self.result.event_types += 1

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _import_events(self, root: ET.Element) -> None:
        # Collect linked_event relationships for a second pass after all events exist.
        pending_links: dict[uuid.UUID, str] = {}  # ot_event_id → twh_linked_id

        for elem in root.findall("Event"):
            twh_id = _text(elem, "i")
            if not twh_id:
                continue

            event_type_twh = _text(elem, "Event_Type_ID")
            event_type_id = self._event_type_map.get(event_type_twh)
            if event_type_id is None:
                self.result.warnings.append(
                    f"Event {twh_id!r}: unknown event_type_id {event_type_twh!r} — skipped"
                )
                self.result.skipped += 1
                continue

            scheduled_start = _parse_datetime(_text(elem, "Scheduled_Start"))
            scheduled_end = _parse_datetime(_text(elem, "Scheduled_End"))
            if scheduled_start is None or scheduled_end is None:
                self.result.warnings.append(
                    f"Event {twh_id!r}: missing/invalid start or end datetime — skipped"
                )
                self.result.skipped += 1
                continue

            location_twh = _text(elem, "Location")
            location_id = self._location_map.get(location_twh) if location_twh else None

            tour_raw = _text(elem, "Tour_Permit_Submitted_Flag").upper()
            if tour_raw == "Y":
                tour_permit: bool | None = True
            elif tour_raw == "N":
                tour_permit = False
            else:
                tour_permit = None

            description = (
                _text(elem, "Description_Future") or _text(elem, "Description_Past") or None
            )

            event = Event(
                tenant_id=self.tenant_id,
                name=_text(elem, "Event_Name") or f"Event {twh_id}",
                event_type_id=event_type_id,
                location_id=location_id,
                location_notes=_text(elem, "New_Location_Name") or None,
                departure_location=_text(elem, "Departure_Location") or None,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                all_day=_text(elem, "Scheduled_All_Day_Flag").upper() == "Y",
                signup_start=_parse_date(_text(elem, "SignUp_Start_Date")),
                signup_deadline=_parse_date(_text(elem, "SignUp_Deadline")),
                signup_limit_scouts=_parse_int(elem, "Signup_Limit_Scouts"),
                signup_limit_adults=_parse_int(elem, "Signup_Limit_Adults"),
                cost_youth=_parse_decimal(elem, "Estimated_Cost_Per_Person"),
                video_conference_url=_text(elem, "Video_Conference_URL") or None,
                description=description,
                agenda=_text(elem, "Agenda") or None,
                tour_permit_submitted=tour_permit,
                attendance_taken=_flag(elem, "Attendance_Taken_Flag"),
                community_service_hours=_parse_decimal(elem, "Community_Service_Hours"),
                conservation_hours=_parse_decimal(elem, "Conservation_Hours"),
                hiking_miles=_parse_decimal(elem, "Hiking_Miles"),
                backpacking_miles=_parse_decimal(elem, "Backpacking_Miles"),
                paddling_miles=_parse_decimal(elem, "Paddling_Miles"),
                cycling_miles=_parse_decimal(elem, "Cycling_Miles"),
                water_hours=_parse_decimal(elem, "Water_Hours"),
            )
            self.session.add(event)
            self.session.flush()
            self._event_map[twh_id] = event.id
            self.result.events += 1

            linked_twh = _text(elem, "Linked_Event_ID")
            if linked_twh:
                pending_links[event.id] = linked_twh

        # Resolve linked_event_id now that all events are flushed.
        for ot_id, linked_twh in pending_links.items():
            linked_ot_id = self._event_map.get(linked_twh)
            if linked_ot_id:
                self.session.execute(
                    update(Event).where(Event.id == ot_id).values(linked_event_id=linked_ot_id)
                )
            else:
                self.result.warnings.append(
                    f"Event (OT id {ot_id}): linked_event_id {linked_twh!r} not found — link skipped"
                )

    # ------------------------------------------------------------------
    # Event participants
    # ------------------------------------------------------------------

    def _import_participants(self, root: ET.Element) -> None:
        for elem in root.findall("Event_Participant"):
            event_twh = _text(elem, "Event_ID")
            person_twh = _text(elem, "Person_ID")

            event_id = self._event_map.get(event_twh)
            member_id = self._person_map.get(person_twh)
            if not event_id or not member_id:
                self.result.skipped += 1
                continue

            pair = (event_id, member_id)
            if pair in self._participant_seen:
                self.result.warnings.append(
                    f"Duplicate participant: event {event_twh!r} person {person_twh!r} — skipped"
                )
                self.result.skipped += 1
                continue
            self._participant_seen.add(pair)

            # '?' = unknown/pre-import state — treat as signed up, attendance unknown
            sign_up_raw = _text(elem, "Sign_Up_Flag").upper()
            signed_up = sign_up_raw != "N"
            if sign_up_raw == "N":
                rsvp_status = RsvpStatus.DECLINED
            elif sign_up_raw in ("", "?"):
                rsvp_status = RsvpStatus.NO_RESPONSE
            else:
                rsvp_status = RsvpStatus.GOING

            part_raw = _text(elem, "Participation_Flag").upper()
            if part_raw == "Y":
                attended: bool | None = True
            elif part_raw == "N":
                attended = False
            else:
                attended = None

            self.session.add(
                EventParticipant(
                    tenant_id=self.tenant_id,
                    event_id=event_id,
                    member_id=member_id,
                    signed_up=signed_up,
                    rsvp_status=rsvp_status,
                    attended=attended,
                    driver=_flag(elem, "Driver_Flag"),
                    seat_count=_parse_int(elem, "Seat_Count"),
                    guest_count=_parse_int(elem, "Number_Of_Guests") or 0,
                    comment=_text(elem, "Comment") or None,
                    signed_up_at=_parse_datetime(_text(elem, "Signup_Date_Time")),
                    hiking_miles_override=_parse_decimal(elem, "Hiking_Miles_Override"),
                    backpacking_miles_override=_parse_decimal(elem, "Backpacking_Miles_Override"),
                    paddling_miles_override=_parse_decimal(elem, "Paddling_Miles_Override"),
                    cycling_miles_override=_parse_decimal(elem, "Cycling_Miles_Override"),
                    community_service_hours_override=_parse_decimal(
                        elem, "Community_Service_Hours_Override"
                    ),
                    conservation_hours_override=_parse_decimal(elem, "Conservation_Hours_Override"),
                    water_hours_override=_parse_decimal(elem, "Water_Hours_Override"),
                    camping_nights_override=_parse_int(elem, "Camping_Nights_Override"),
                    permission_slip_submitted=_flag(elem, "Permission_Slip_Submitted_Flag"),
                    electronic_permission=_flag(elem, "Electronic_Permission_Flag"),
                    electronic_permission_at=_parse_datetime(
                        _text(elem, "Electronic_Permission_Date_Time")
                    ),
                )
            )
            self.result.participants += 1
