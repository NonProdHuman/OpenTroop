"""
generate_twh_fixture.py — emit fully synthetic TroopWebHost XML export fixtures.

Every value in the output is generated from embedded word lists and a seeded
``random.Random`` — no real troop's people, events, messages, or dates appear,
so the files are safe to commit (unlike anonymized exports, which preserve a
real troop's structural history; see reference/.gitignore). The *schema* —
which record types exist and which fields each carries — comes from
``data/twh/export_schema.json``, a field-name inventory of a real export.

The generated troops are shaped to exercise the importer end to end
(GH-205): all 68 record types are present; advancement uses the shipped 2025
catalog's requirement numbering (guaranteed crosswalkable) plus deliberate
edge cases — a legacy-version rank award, Eagle Palms, a badge name with a
"(YYYY rqmts)" suffix, a badge missing from the global catalog, sub-lettered
codes for a bare-leaf requirement, and a container-level sign-off.

Determinism: same seed ⇒ byte-identical output on any machine (plain
``random``, fixed base dates, no faker). The two committed fixtures are:

    uv run generate-twh-fixture            # rewrites both .xml.gz files in tests/fixtures/
    uv run generate-twh-fixture --troop 2 --out /tmp/troop2.xml   # plain XML for eyeballing
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = BACKEND_DIR / "data" / "twh" / "export_schema.json"
ADVANCEMENT_DIR = BACKEND_DIR / "data" / "advancement"
FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures"

# All dates are anchored here, never to the wall clock, so output is stable.
TODAY = date(2026, 6, 20)
EXPORT_STAMP = "6/20/2026 7:00:00 AM"

# ---------------------------------------------------------------------------
# Synthetic word lists (no faker — deterministic across environments)
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "Avery",
    "Blake",
    "Casey",
    "Devon",
    "Elliot",
    "Finley",
    "Gray",
    "Harper",
    "Indigo",
    "Jules",
    "Kai",
    "Lane",
    "Marlow",
    "Noel",
    "Oakley",
    "Parker",
    "Quinn",
    "Reese",
    "Sawyer",
    "Tatum",
    "Umber",
    "Vale",
    "Wren",
    "Xen",
    "Yael",
    "Zephyr",
    "Arden",
    "Briar",
    "Cedar",
    "Dune",
    "Ember",
    "Fox",
]
LAST_NAMES = [
    "Ashford",
    "Birchwald",
    "Cravenmoor",
    "Dellwyn",
    "Everhart",
    "Fennimore",
    "Grimsley",
    "Hollowell",
    "Ironwood",
    "Juniper",
    "Kestrelbrook",
    "Larkspur",
    "Mossgrove",
    "Nightingale",
    "Oakhurst",
    "Pinewhistle",
    "Quillfeather",
    "Rowanfield",
    "Stonebridge",
    "Thistlewood",
]
STREETS = [
    "Maple Hollow Ln",
    "Granite Ridge Rd",
    "Fox Run Ct",
    "Willowbrook Dr",
    "Cedar Crest Ave",
    "Blue Heron Way",
    "Stonegate Blvd",
    "Timberline Trl",
]
CITIES = [
    ("Fairview Glen", "OH", "44399"),
    ("Mapleton Falls", "OH", "44398"),
    ("Cedar Hollow", "OH", "44397"),
]
PATROL_NAMES = [
    "Thunderbird Patrol",
    "Timberwolf Patrol",
    "Kingfisher Patrol",
    "Ridgeback Patrol",
    "Firefly Patrol",
    "Granite Patrol",
]
LOCATION_NAMES = [
    "Camp Silverpine",
    "Fairview Community Hall",
    "Granite Ridge Trailhead",
    "Riverbend Scout Cabin",
]
VIGIL_NAMES = ["Quiet Thunder", "Steady Compass", "Bright Ember"]

# Merit badges referenced by the fixtures. All but the last exist in the
# shipped global catalog (data/advancement/merit-badges.json) — verified at
# generation time. The last one is deliberately unknown to exercise the
# importer's unknown-badge warning.
BADGE_POOL = [
    ("First Aid", "2025", False),
    ("Swimming", "2024", False),
    ("Camping", "2024", False),
    ("Cooking", "2025", False),
    ("Environmental Science", "2025", False),
    ("Citizenship in the Community", "2022", False),
    ("Citizenship in the Nation", "2022", False),
    ("Citizenship in the World", "2016", False),
    ("Citizenship in Society", "2021", False),
    ("Personal Fitness", "2023", True),  # emitted as "Personal Fitness (2023 rqmts)"
    ("Personal Management", "2025", False),
    ("Communication", "2025", False),
    ("Emergency Preparedness", "2025", True),
    ("Hiking", "2024", False),
    ("Canoeing", "2024", False),
    ("Fingerprinting", "2025", False),
    ("Art", "2014", False),
    ("Wood Carving", "2015", False),
]
UNKNOWN_BADGE = "Sample Legacy Badge"

# TWH rank award ids (arbitrary but stable), rank order matches the catalog.
RANK_CODES = ["RN", "RT", "R2", "R1", "RS", "RL", "RE"]
RANK_CATALOG_CODES = [
    "scout",
    "tenderfoot",
    "second_class",
    "first_class",
    "star",
    "life",
    "eagle",
]
RANK_NAMES = [
    "Scout",
    "Tenderfoot",
    "Second Class",
    "First Class",
    "Star",
    "Life",
    "Eagle",
]
CURRENT_RANK_AWARD_BASE = 501  # 501..507 = Current versions of the 7 ranks
LEGACY_SCOUT_AWARD = 401  # a "2012"-version Scout award (legacy numbering)
PALM_AWARDS = [(601, "Bronze Palm", "RZ"), (602, "Gold Palm", "RD")]
BADGE_AWARD_BASE = 701
UNKNOWN_BADGE_AWARD = 799
SERVICE_STAR_AWARD = 801

POSITIONS = [
    # (id, name, code, adult, seq)
    (1, "Scoutmaster", "SM", True, 1),
    (2, "Assistant Scoutmaster", "SA", True, 2),
    (3, "Committee Chairman", "CC", True, 3),
    (4, "Committee Member", "MC", True, 4),
    (5, "Chartered Organization Rep", "CR", True, 5),
    (6, "Senior Patrol Leader", "SPL", False, 10),
    (7, "Assistant Senior Patrol Leader", "ASPL", False, 11),
    (8, "Patrol Leader", "PL", False, 12),
    (9, "Scribe", "SCR", False, 13),
    (10, "Quartermaster", "QM", False, 14),
]

ACTIVITY_TYPES = [
    ("Service Hours", (1, 6)),
    ("Camping Nights", (1, 3)),
    ("Hiking Miles", (2, 10)),
    ("Conservation Service Hours", (1, 4)),
]


def _d(value: date | None) -> str:
    """A TWH date field: ``M/D/YYYY 12:00:00 AM`` (dates carry a midnight time)."""
    if value is None:
        return ""
    return f"{value.month}/{value.day}/{value.year} 12:00:00 AM"


def _dt(value: datetime | None) -> str:
    """A TWH datetime field: ``M/D/YYYY H:MM:SS AM`` (no zero-padding on M/D/H)."""
    if value is None:
        return ""
    hour = value.strftime("%I").lstrip("0")
    return f"{value.month}/{value.day}/{value.year} {hour}:{value.strftime('%M:%S %p')}"


@dataclass
class _Person:
    pid: int
    first: str
    last: str
    adult: bool
    join: date
    dob: date
    patrol_id: int | None = None
    alumni: bool = False
    end: date | None = None
    ranks_earned: int = 0  # count of ranks with an earned date
    rank_dates: list[date] = field(default_factory=list)


class FixtureBuilder:
    """Builds one synthetic troop's export tree deterministically from a seed."""

    def __init__(self, troop: int, seed: int) -> None:
        self.troop = troop
        self.rng = random.Random(seed)  # noqa: S311 — deterministic fixture data, not crypto
        self.schema: dict[str, list[str]] = json.loads(SCHEMA_PATH.read_text())["record_types"]
        self.rows: dict[str, list[dict[str, object]]] = {t: [] for t in self.schema}
        self.catalog = json.loads((ADVANCEMENT_DIR / "ranks-2025.json").read_text())
        badge_names = {
            b["name"]
            for b in json.loads((ADVANCEMENT_DIR / "merit-badges.json").read_text())["badges"]
        }
        missing = {name for name, _, _ in BADGE_POOL} - badge_names
        if missing:
            raise SystemExit(f"BADGE_POOL names missing from merit-badges.json: {missing}")
        if UNKNOWN_BADGE in badge_names:
            raise SystemExit(f"{UNKNOWN_BADGE!r} must NOT exist in merit-badges.json")

        self.people: list[_Person] = []
        # (award_id) -> list of (requirement_id, code); filled by _advancement_catalog
        self.award_reqs: dict[int, list[tuple[int, str]]] = {}
        self.scout_award_ids: dict[str, int] = {}  # catalog rank code -> Current award id
        self.events: list[tuple[int, str, datetime, bool]] = []  # (id, kind, start, past)

    # -- row plumbing --------------------------------------------------

    def row(self, table: str, **fields: object) -> int:
        """Append a row, auto-assigning ``i``; unknown field names fail loudly."""
        unknown = set(fields) - set(self.schema[table])
        if unknown:
            raise SystemExit(f"{table}: unknown fields {sorted(unknown)}")
        rid = int(str(fields.get("i", len(self.rows[table]) + 1)))
        fields["i"] = rid
        self.rows[table].append(fields)
        return rid

    def _stamp(self, day: date) -> str:
        """A plausible Last_Update_UTC shortly after *day*."""
        minute = self.rng.randint(0, 59)
        return _dt(datetime.combine(day, time(hour=self.rng.randint(0, 23), minute=minute)))

    # -- people ---------------------------------------------------------

    def _address(self) -> tuple[str, str, str, str]:
        city, state, zipc = self.rng.choice(CITIES)
        return f"{self.rng.randint(10, 9899)} {self.rng.choice(STREETS)}", city, state, zipc

    def _phone(self) -> str:
        return f"555-01{self.rng.randint(10, 99)}"

    def build_people(self) -> None:
        """Eight families (some with sibling scouts), plus one unaffiliated leader."""
        used_names: set[tuple[str, str]] = set()
        family_shapes = [(1, 2), (2, 1), (1, 1), (1, 2), (2, 2), (1, 1), (1, 2), (1, 1)]
        pid = 0
        for fam_index, (n_scouts, n_parents) in enumerate(family_shapes):
            last = LAST_NAMES[(fam_index * 2 + self.troop) % len(LAST_NAMES)]
            street, city, state, zipc = self._address()
            scouts: list[_Person] = []
            for _ in range(n_scouts):
                pid += 1
                first = self._fresh_first(last, used_names)
                dob = date(
                    self.rng.randint(2008, 2013), self.rng.randint(1, 12), self.rng.randint(1, 28)
                )
                join = dob + timedelta(days=self.rng.randint(11 * 365, 12 * 365))
                join = min(join, TODAY - timedelta(days=120))
                person = _Person(pid, first, last, adult=False, join=join, dob=dob)
                scouts.append(person)
                self.people.append(person)
            for _ in range(n_parents):
                pid += 1
                first = self._fresh_first(last, used_names)
                dob = date(
                    self.rng.randint(1972, 1988), self.rng.randint(1, 12), self.rng.randint(1, 28)
                )
                join = min(s.join for s in scouts)
                self.people.append(_Person(pid, first, last, adult=True, join=join, dob=dob))
            for scout in scouts:
                scout.patrol_id = (fam_index % 3) + 1
                self._family_rows(scout, street, city, state, zipc)
            for parent in self.people[-n_parents:]:
                self._family_rows(parent, street, city, state, zipc)
        # The first family's first scout is an Eagle alumni with a closed membership.
        alum = self.people[0]
        alum.alumni = True
        alum.patrol_id = None
        alum.join = date(2018, 6, 10)
        alum.dob = date(2006, 3, 14)
        alum.end = date(2024, 9, 1)
        # One adult leader with no scout in the troop.
        pid += 1
        first = self._fresh_first("Wexlerby", used_names)
        self.people.append(
            _Person(
                pid, first, "Wexlerby", adult=True, join=date(2019, 1, 15), dob=date(1975, 7, 4)
            )
        )

    def _fresh_first(self, last: str, used: set[tuple[str, str]]) -> str:
        while True:
            first = self.rng.choice(FIRST_NAMES)
            if (first, last) not in used:
                used.add((first, last))
                return first

    def _family_rows(self, person: _Person, street: str, city: str, state: str, zipc: str) -> None:
        person.street, person.city, person.state, person.zip = street, city, state, zipc  # type: ignore[attr-defined]

    def emit_people(self) -> None:
        swim_levels = ["Swimmer", "Swimmer", "Beginner", "Nonswimmer"]
        for idx, person in enumerate(self.people):
            oa = (not person.adult and idx in (0, 3)) or (person.adult and idx == 2)
            oa_election = person.join + timedelta(days=500) if oa else None
            email = f"{person.first.lower()}.{person.last.lower()}@example.com"
            self.row(
                "Person",
                i=person.pid,
                Name_First=person.first,
                Name_Middle=self.rng.choice(["", "", "J", "K", "R"]),
                Name_Last=person.last,
                Nickname=person.first[:3] if self.rng.random() < 0.2 else "",
                Date_Of_Birth=_d(person.dob),
                Sex=self.rng.choice(["M", "F"]),
                Adult_Flag="1" if person.adult else "0",
                Alumni_Flag="Y" if person.alumni else "N",
                Troop_Member_Flag="N" if person.alumni else "Y",
                Patrol=str(person.patrol_id) if person.patrol_id else "",
                BSA_Membership_Number=str(13_500_000 + self.troop * 10_000 + person.pid)
                if not (person.adult and person.pid % 5 == 0)
                else "",
                Email_Address=email,
                Cell_Phone=self._phone(),
                Home_Phone=self._phone() if self.rng.random() < 0.5 else "",
                Mailing_Address_Line_1=getattr(person, "street", ""),
                Mailing_Address_City=getattr(person, "city", ""),
                Mailing_Address_State=getattr(person, "state", ""),
                Mailing_Address_Zip=getattr(person, "zip", ""),
                Mailing_Address_Country="US",
                Troop_Membership_Start_Date=_d(person.join),
                Troop_Membership_End_Date=_d(person.end),
                Swim_Level="" if person.adult else self.rng.choice(swim_levels),
                Swim_Date=_d(date(2025, 6, self.rng.randint(1, 28))) if not person.adult else "",
                Class_1_Medical_Form_Date=_d(date(2025, self.rng.randint(1, 8), 15)),
                Class_3_Medical_Form_Date=_d(date(2025, self.rng.randint(1, 8), 15))
                if self.rng.random() < 0.6
                else "",
                Allergies=self.rng.choice(["", "", "Peanuts", "Bee stings"]),
                Dietary_Restrictions=self.rng.choice(["", "", "", "Vegetarian"]),
                Emergency_Contact_1_Name_First=self.rng.choice(FIRST_NAMES),
                Emergency_Contact_1_Name_Last=person.last,
                Emergency_Contact_1_Phone=self._phone(),
                Emergency_Contact_2_Name_First=self.rng.choice(FIRST_NAMES)
                if self.rng.random() < 0.6
                else "",
                Emergency_Contact_2_Phone=self._phone() if self.rng.random() < 0.6 else "",
                OA_Member_Flag="Y" if oa else "N",
                OA_Active_Flag="Y" if oa and not person.alumni else "N",
                OA_Election_Date=_d(oa_election),
                OA_Ordeal_Date=_d(oa_election + timedelta(days=90)) if oa_election else "",
                OA_Vigil_Name=VIGIL_NAMES[person.pid % len(VIGIL_NAMES)]
                if oa and person.pid % 4 == 0
                else "",
                Eagle_Scout="Y" if person.alumni else "",
                Eagle_Scout_Date=_d(person.rank_dates[6])
                if person.alumni and len(person.rank_dates) == 7
                else "",
                Last_Update_UTC=self._stamp(TODAY - timedelta(days=self.rng.randint(1, 200))),
            )

    def emit_patrols_and_relationships(self) -> None:
        for i in range(3):
            self.row(
                "Patrol",
                Patrol_Name=PATROL_NAMES[(i + self.troop) % len(PATROL_NAMES)],
                Last_Update_UTC=self._stamp(date(2025, 8, 1)),
            )
        scouts = [p for p in self.people if not p.adult]
        for scout in scouts:
            for person in self.people:
                if person.adult and person.last == scout.last:
                    self.row(
                        "Relationship",
                        Person_ID_Scout=scout.pid,
                        Person_ID_Adult=person.pid,
                        Relationship_Type="Parent",
                        Last_Update_UTC=self._stamp(scout.join),
                    )

    def emit_leadership(self) -> None:
        for pos_id, name, code, adult, seq in POSITIONS:
            common = {
                "i": pos_id,
                "Adult_Flag": "Y" if adult else "N",
                "Position": name,
                "Position_Code": code,
                "Display_Sequence": seq,
            }
            self.row("BSA_Leadership_Position", **common)
            self.row("Leadership_Position", **common, Committee_Member_Flag="N")
        adults = [p for p in self.people if p.adult]
        scouts = [p for p in self.people if not p.adult and not p.alumni]
        # Current adult terms: SM, CC, CR, and two MCs; plus one ended ASM term.
        current = [(adults[0], 1), (adults[1], 3), (adults[-1], 5), (adults[2], 4), (adults[3], 4)]
        for person, pos_id in current:
            self.row(
                "Adult_Leadership_History",
                Person_ID=person.pid,
                BSA_Leadership_Position_ID=pos_id,
                Start_Date=_d(person.join + timedelta(days=200)),
                End_Date="",
                Last_Update_UTC=self._stamp(person.join + timedelta(days=201)),
            )
        self.row(
            "Adult_Leadership_History",
            Person_ID=adults[4].pid,
            BSA_Leadership_Position_ID=2,
            Start_Date=_d(date(2023, 3, 1)),
            End_Date=_d(date(2025, 2, 28)),
            Last_Update_UTC=self._stamp(date(2025, 3, 1)),
        )
        # Scout terms: current SPL + a PL per patrol + one ended Scribe term.
        self.row(
            "Scout_Leadership_History",
            Person_ID=scouts[0].pid,
            BSA_Leadership_Position_ID=6,
            Start_Date=_d(date(2026, 3, 1)),
            End_Date="",
            Last_Update_UTC=self._stamp(date(2026, 3, 1)),
        )
        for patrol_index in range(3):
            leader = next((s for s in scouts[1:] if s.patrol_id == patrol_index + 1), None)
            if leader is not None:
                self.row(
                    "Scout_Leadership_History",
                    Person_ID=leader.pid,
                    BSA_Leadership_Position_ID=8,
                    Start_Date=_d(date(2026, 3, 1)),
                    End_Date="",
                    Last_Update_UTC=self._stamp(date(2026, 3, 1)),
                )
        self.row(
            "Scout_Leadership_History",
            Person_ID=scouts[1].pid,
            BSA_Leadership_Position_ID=9,
            Start_Date=_d(date(2025, 3, 1)),
            End_Date=_d(date(2026, 2, 28)),
            Last_Update_UTC=self._stamp(date(2026, 3, 1)),
        )

    # -- locations / events ----------------------------------------------

    def emit_locations(self) -> None:
        for index, name in enumerate(LOCATION_NAMES):
            street, city, state, zipc = self._address()
            self.row(
                "Location",
                Location_Name=name,
                Address_Line_1=street,
                Address_City=city,
                Address_State=state,
                Address_Zip=zipc,
                Address_Country="US",
                Telephone_Number=self._phone(),
                Website_URL="https://example.com" if index % 2 == 0 else "",
                Directions="Synthetic directions text.",
                Description="Synthetic location description.",
                Distance=str(self.rng.randint(2, 45)),
                Disabled_Flag="N",
                Last_Update_UTC=self._stamp(date(2025, 9, 1)),
            )
        self.row(
            "Location",
            Location_Name="Old Annex (Closed)",
            Disabled_Flag="Y",
            Last_Update_UTC=self._stamp(date(2024, 1, 1)),
        )

    _EVENT_TYPES = [
        # (name, color, camping, service, hiking, signup, permission, online, disabled)
        ("Troop Meeting", "#3498DB", False, False, False, False, False, False, False),
        ("Campout", "#2ECC71", True, False, True, True, True, False, False),
        ("Hike", "#E67E22", False, False, True, True, True, False, False),
        ("Service Project", "#9B59B6", False, True, False, True, False, False, False),
        ("Court of Honor", "#F1C40F", False, False, False, False, False, False, False),
        ("Online Meeting", "#1ABC9C", False, False, False, False, False, True, False),
        ("Old Category", "", False, False, False, False, False, False, True),
    ]

    def emit_event_types(self) -> None:
        for (
            name,
            color,
            camp,
            service,
            hike,
            signup,
            permission,
            online,
            disabled,
        ) in self._EVENT_TYPES:
            self.row(
                "Event_Type",
                Event_Type_Name=name,
                Display_Color=color,
                Camping_Nights_Flag="Y" if camp else "N",
                Service_Hours_Flag="Y" if service else "N",
                Hiking_Miles_Flag="Y" if hike else "N",
                SignUp_Flag="Y" if signup else "N",
                Permission_Slip_Flag="Y" if permission else "N",
                Online_Meeting_Flag="Y" if online else "N",
                Event_Type_Disabled_Flag="Y" if disabled else "N",
                Include_On_Calendar_Flag="Y",
                Last_Update_UTC=self._stamp(date(2025, 8, 15)),
            )

    def emit_events(self) -> None:
        type_ids = {name: i + 1 for i, (name, *_rest) in enumerate(self._EVENT_TYPES)}
        # Monthly meetings, Sep 2025 – Jun 2026 (first Tuesday, 7pm).
        meeting_ids = []
        for month_offset in range(10):
            month = (9 + month_offset - 1) % 12 + 1
            year = 2025 if month >= 9 else 2026
            day = 7 - date(year, month, 1).weekday() or 7  # first Tuesday-ish
            start = datetime(year, month, min(day + 1, 28), 19, 0)
            eid = self.row(
                "Event",
                Event_Name=f"Troop Meeting — {start.strftime('%B %Y')}",
                Event_Type_ID=type_ids["Troop Meeting"],
                Location=2,
                Scheduled_Start=_dt(start),
                Scheduled_End=_dt(start + timedelta(hours=1, minutes=30)),
                Scheduled_All_Day_Flag="N",
                Attendance_Taken_Flag="Y" if start.date() < TODAY else "N",
                Description_Past="Synthetic meeting recap." if start.date() < TODAY else "",
                Description_Future="" if start.date() < TODAY else "Synthetic meeting plan.",
                Last_Update_UTC=self._stamp(start.date()),
            )
            meeting_ids.append(eid)
            self.events.append((eid, "meeting", start, start.date() < TODAY))
        # Campouts (one in the future with a signup window), hikes, service, COH.
        campout_months = [(2025, 10), (2025, 12), (2026, 2), (2026, 4), (2026, 7)]
        for year, month in campout_months:
            start = datetime(year, month, self.rng.randint(6, 20), 17, 0)
            past = start.date() < TODAY
            eid = self.row(
                "Event",
                Event_Name=f"{LOCATION_NAMES[0]} Campout — {start.strftime('%b %Y')}",
                Event_Type_ID=type_ids["Campout"],
                Location=1,
                Departure_Location="Fairview Community Hall parking lot",
                Scheduled_Start=_dt(start),
                Scheduled_End=_dt(start + timedelta(days=2, hours=-6)),
                Scheduled_All_Day_Flag="N",
                SignUp_Start_Date=_d(start.date() - timedelta(days=45)),
                SignUp_Deadline=_d(start.date() - timedelta(days=7)),
                Signup_Limit_Scouts=20,
                Signup_Limit_Adults=8,
                Estimated_Cost_Per_Person="35.00",
                Tour_Permit_Submitted_Flag="Y" if past else "N",
                Attendance_Taken_Flag="Y" if past else "N",
                Hiking_Miles="3.5" if month % 2 == 0 else "",
                Last_Update_UTC=self._stamp(min(start.date(), TODAY)),
            )
            self.events.append((eid, "campout", start, past))
        hike_start = datetime(2026, 5, 16, 8, 30)
        eid = self.row(
            "Event",
            Event_Name="Granite Ridge Day Hike",
            Event_Type_ID=type_ids["Hike"],
            Location=3,
            Scheduled_Start=_dt(hike_start),
            Scheduled_End=_dt(hike_start + timedelta(hours=7)),
            Scheduled_All_Day_Flag="N",
            Hiking_Miles="8.2",
            Tour_Permit_Submitted_Flag="Y",
            Attendance_Taken_Flag="Y",
            Last_Update_UTC=self._stamp(hike_start.date()),
        )
        self.events.append((eid, "hike", hike_start, True))
        for year, month, hours in [(2025, 11, "4.0"), (2026, 3, "3.0"), (2026, 5, "5.0")]:
            start = datetime(year, month, self.rng.randint(5, 25), 9, 0)
            eid = self.row(
                "Event",
                Event_Name=f"Service Project — {start.strftime('%b %Y')}",
                Event_Type_ID=type_ids["Service Project"],
                Location=4,
                Scheduled_Start=_dt(start),
                Scheduled_End=_dt(start + timedelta(hours=4)),
                Scheduled_All_Day_Flag="N",
                Community_Service_Hours=hours,
                Attendance_Taken_Flag="Y",
                Last_Update_UTC=self._stamp(start.date()),
            )
            self.events.append((eid, "service", start, True))
        for year, month in [(2025, 10), (2026, 4)]:
            start = datetime(year, month, 28, 18, 30)
            eid = self.row(
                "Event",
                Event_Name=f"Court of Honor — {start.strftime('%b %Y')}",
                Event_Type_ID=type_ids["Court of Honor"],
                Location=2,
                Scheduled_Start=_dt(start),
                Scheduled_End=_dt(start + timedelta(hours=2)),
                Scheduled_All_Day_Flag="Y",
                Attendance_Taken_Flag="Y",
                Linked_Event_ID=meeting_ids[0] if year == 2025 else "",
                Last_Update_UTC=self._stamp(start.date()),
            )
            self.events.append((eid, "coh", start, True))
        online = datetime(2026, 1, 13, 19, 0)
        eid = self.row(
            "Event",
            Event_Name="PLC Planning (Online)",
            Event_Type_ID=type_ids["Online Meeting"],
            Video_Conference_URL="https://meet.example.com/synthetic",
            Scheduled_Start=_dt(online),
            Scheduled_End=_dt(online + timedelta(hours=1)),
            Scheduled_All_Day_Flag="N",
            Attendance_Taken_Flag="Y",
            Agenda="Synthetic agenda.",
            Last_Update_UTC=self._stamp(online.date()),
        )
        self.events.append((eid, "meeting", online, True))

    def emit_participants(self) -> None:
        scouts = [p for p in self.people if not p.adult and not p.alumni]
        adults = [p for p in self.people if p.adult]
        for event_id, kind, start, past in self.events:
            share = 0.75 if kind in ("campout", "coh") else 0.55
            going_scouts = [
                s for s in scouts if s.join <= start.date() and self.rng.random() < share
            ]
            going_adults = [
                a for a in adults if self.rng.random() < (0.5 if kind == "campout" else 0.25)
            ]
            for person in going_scouts + going_adults:
                if past:
                    sign_up = self.rng.choice(["Y", "Y", "Y", "N", "?"])
                    participation = (
                        "?"
                        if sign_up == "?"
                        else ("Y" if sign_up == "Y" and self.rng.random() < 0.9 else "N")
                    )
                else:
                    sign_up = self.rng.choice(["Y", "Y", "N", "?"])
                    participation = "?"
                driver = (
                    person.adult
                    and kind == "campout"
                    and sign_up == "Y"
                    and self.rng.random() < 0.6
                )
                self.row(
                    "Event_Participant",
                    Event_ID=event_id,
                    Person_ID=person.pid,
                    Sign_Up_Flag=sign_up,
                    Participation_Flag=participation,
                    Driver_Flag="Y" if driver else "N",
                    Seat_Count=str(self.rng.randint(3, 6)) if driver else "",
                    Number_Of_Guests=str(1) if self.rng.random() < 0.05 else "0",
                    Camping_Nights_Override="2"
                    if kind == "campout" and participation == "Y"
                    else "",
                    Permission_Slip_Submitted_Flag="Y"
                    if kind in ("campout", "hike") and sign_up == "Y"
                    else "N",
                    Signup_Date_Time=_dt(start - timedelta(days=self.rng.randint(8, 30)))
                    if sign_up == "Y"
                    else "",
                    Comment="Arriving late" if self.rng.random() < 0.04 else "",
                    Last_Update_UTC=self._stamp(min(start.date(), TODAY)),
                )

    # -- advancement ------------------------------------------------------

    def _rank_labels(self, rank_code: str) -> list[str]:
        for rank in self.catalog["ranks"]:
            if rank["code"] == rank_code:
                return [f"{q['number']}{q['letter'] or ''}" for q in rank["requirements"]]
        raise SystemExit(f"rank {rank_code} not in ranks-2025.json")

    @staticmethod
    def _twh_code(label: str) -> str:
        number = "".join(ch for ch in label if ch.isdigit())
        letter = label[len(number) :]
        return f"{int(number):02d}." + letter

    def emit_advancement_catalog(self) -> None:
        for i, name in enumerate(RANK_NAMES):
            self.row("BSA_Rank_Name", Rank_Name=name, Rank_Seq=i + 1)
        req_id = 1000
        for index, (code, catalog_code, name) in enumerate(
            zip(RANK_CODES, RANK_CATALOG_CODES, RANK_NAMES, strict=True)
        ):
            award_id = CURRENT_RANK_AWARD_BASE + index
            self.scout_award_ids[catalog_code] = award_id
            self.row(
                "BSA_Award",
                i=award_id,
                Award_Name=name,
                Award_Type="Rank",
                Rank_Code=code,
                Rank_Seq=index + 1,
                Requirements_Version="Current",
                Effective_Start_Date=_d(date(2016, 1, 1)),
                Eagle_Requirement_Flag="N",
            )
            labels = self._rank_labels(catalog_code)
            if catalog_code == "scout":
                # Mirror real TWH numbering drift: sub-letter the catalog's bare
                # leaf "6" so imports exercise the letter→bare-leaf fallback.
                labels = [lbl for lbl in labels if lbl != "6"] + ["6a", "6b"]
            reqs = []
            for label in sorted(
                labels, key=lambda v: (int("".join(c for c in v if c.isdigit())), v)
            ):
                req_id += 1
                code_str = self._twh_code(label)
                self.row(
                    "BSA_Requirement",
                    i=req_id,
                    BSA_Award_ID=award_id,
                    Requirement_Code=code_str,
                    Requirement_Description=str(4000 + req_id),  # text-blob ref, like real exports
                    Requirement_Description_Short="",
                )
                reqs.append((req_id, code_str))
            self.award_reqs[award_id] = reqs
        # A legacy-numbered Scout award (2012 rqmts) — bare codes, some unmatched.
        self.row(
            "BSA_Award",
            i=LEGACY_SCOUT_AWARD,
            Award_Name="Scout",
            Award_Type="Rank",
            Rank_Code="RN",
            Rank_Seq=1,
            Requirements_Version="2012",
        )
        legacy = []
        for n in range(1, 8):
            req_id += 1
            code_str = f"{n:02d}."
            self.row(
                "BSA_Requirement",
                i=req_id,
                BSA_Award_ID=LEGACY_SCOUT_AWARD,
                Requirement_Code=code_str,
                Requirement_Description=str(4000 + req_id),
                Requirement_Description_Short="",
            )
            legacy.append((req_id, code_str))
        self.award_reqs[LEGACY_SCOUT_AWARD] = legacy
        for award_id, name, code in PALM_AWARDS:
            self.row(
                "BSA_Award",
                i=award_id,
                Award_Name=name,
                Award_Type="Rank",
                Rank_Code=code,
                Rank_Seq=8,
                Requirements_Version="Current",
            )
        for offset, (name, version, suffixed) in enumerate(BADGE_POOL):
            display = f"{name} ({version} rqmts)" if suffixed else name
            self.row(
                "BSA_Award",
                i=BADGE_AWARD_BASE + offset,
                Award_Name=display,
                Award_Type="Merit Badge",
                Requirements_Version=version,
                Eagle_Requirement_Flag="Y"
                if "Citizenship" in name or name in ("First Aid", "Camping")
                else "N",
            )
        self.row(
            "BSA_Award",
            i=UNKNOWN_BADGE_AWARD,
            Award_Name=UNKNOWN_BADGE,
            Award_Type="Merit Badge",
            Requirements_Version="1995",
        )
        self.row(
            "BSA_Award",
            i=SERVICE_STAR_AWARD,
            Award_Name="5-Year Service Star",
            Award_Type="Award",
        )

    def plan_rank_progression(self) -> None:
        for person in self.people:
            if person.adult:
                continue
            horizon = person.end or TODAY
            earned_until = person.join + timedelta(days=90)
            dates: list[date] = []
            while len(dates) < 7 and earned_until < horizon:
                dates.append(earned_until)
                earned_until += timedelta(days=self.rng.randint(200, 320))
            if person.alumni:
                # Force a full run to Eagle inside the alumni window.
                span = (person.end or TODAY) - person.join - timedelta(days=120)
                step = span // 7
                dates = [person.join + timedelta(days=60) + step * i for i in range(7)]
            person.rank_dates = dates
            person.ranks_earned = len(dates)

    def emit_rank_awards(self) -> None:
        coh_dates = [date(2025, 10, 28), date(2026, 4, 28)]
        for person in self.people:
            for index, earned in enumerate(person.rank_dates):
                award_id = CURRENT_RANK_AWARD_BASE + index
                if person.alumni and index == 0:
                    award_id = LEGACY_SCOUT_AWARD  # legacy-version election path
                coh = next((c for c in coh_dates if c > earned), None)
                awarded = earned + timedelta(days=45)
                self.row(
                    "Advancement_Earned",
                    Person_ID=person.pid,
                    BSA_Award_ID=award_id,
                    Date_Earned=_d(earned),
                    # Sometimes blank → importer falls back to COH_Date.
                    Date_Awarded="" if index % 3 == 2 else _d(awarded),
                    COH_Date=_d(coh),
                    Date_Submitted_To_Council=_d(coh),
                    Last_Update_UTC=self._stamp(min(earned + timedelta(days=2), TODAY)),
                )
            if person.alumni:
                for award_id, _name, _code in PALM_AWARDS:
                    self.row(
                        "Advancement_Earned",
                        Person_ID=person.pid,
                        BSA_Award_ID=award_id,
                        Date_Earned=_d(person.rank_dates[-1] + timedelta(days=100)),
                        Last_Update_UTC=self._stamp(TODAY - timedelta(days=400)),
                    )

    def emit_requirement_signoffs(self) -> None:
        """Sign-offs for each active scout's in-progress rank (~half its items)."""
        self._pending_candidates: list[tuple[int, int, int, str]] = []
        for person in self.people:
            if person.adult or person.alumni or person.ranks_earned >= 7:
                continue
            rank_index = person.ranks_earned
            award_id = CURRENT_RANK_AWARD_BASE + rank_index
            reqs = self.award_reqs[award_id]
            base = person.rank_dates[-1] if person.rank_dates else person.join
            picked = self.rng.sample(reqs, k=max(1, int(len(reqs) * 0.55)))
            for req_id, _code in picked:
                earned = base + timedelta(days=self.rng.randint(30, 340))
                earned = min(earned, TODAY - timedelta(days=5))
                self.row(
                    "Advancement_Requirement_Earned",
                    Person_ID=person.pid,
                    BSA_Award_ID=award_id,
                    BSA_Requirement_ID=req_id,
                    Date_Earned=_d(earned),
                    Inserted_Date_Time=_dt(datetime.combine(earned, time(20, 15))),
                    Last_Update_UTC=self._stamp(earned),
                )
            leftovers = [(award_id, r, c) for r, c in reqs if (r, c) not in picked]
            for award, req_id, code in leftovers[:2]:
                self._pending_candidates.append((person.pid, award, req_id, code))
        # One ancient legacy sign-off (unmatched bare "03." → warned + skipped).
        alum = self.people[0]
        legacy_req = self.award_reqs[LEGACY_SCOUT_AWARD][2]
        self.row(
            "Advancement_Requirement_Earned",
            Person_ID=alum.pid,
            BSA_Award_ID=LEGACY_SCOUT_AWARD,
            BSA_Requirement_ID=legacy_req[0],
            Date_Earned=_d(alum.join + timedelta(days=70)),
            Last_Update_UTC=self._stamp(alum.join + timedelta(days=71)),
        )

    def emit_merit_badges(self) -> None:
        for person in self.people:
            if person.adult:
                continue
            count = min(len(BADGE_POOL), person.ranks_earned * 2 + self.rng.randint(0, 2))
            chosen = self.rng.sample(range(len(BADGE_POOL)), k=count)
            base = person.join + timedelta(days=300)
            horizon = person.end or TODAY
            for order, badge_index in enumerate(chosen):
                started = base + timedelta(days=order * 60 + self.rng.randint(0, 30))
                if started >= horizon:
                    break
                partial = order == len(chosen) - 1 and self.rng.random() < 0.5 and not person.alumni
                earned = None if partial else started + timedelta(days=self.rng.randint(20, 120))
                if earned is not None and earned >= horizon:
                    earned = horizon - timedelta(days=10)
                self.row(
                    "Merit_Badge",
                    Person_ID=person.pid,
                    BSA_Award_ID=BADGE_AWARD_BASE + badge_index,
                    Date_Started=_d(started),
                    Date_Earned=_d(earned),
                    Date_Awarded=_d(earned + timedelta(days=40))
                    if earned and order % 2 == 0
                    else "",
                    Merit_Badge_Counselor=f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}"
                    if self.rng.random() < 0.6
                    else "",
                    Last_Update_UTC=self._stamp(min((earned or started), TODAY)),
                )
        # One reference to a badge that is not in the global catalog (warn path).
        veteran = next(p for p in self.people if not p.adult and p.ranks_earned >= 3)
        self.row(
            "Merit_Badge",
            Person_ID=veteran.pid,
            BSA_Award_ID=UNKNOWN_BADGE_AWARD,
            Date_Earned=_d(date(2024, 8, 1)),
            Last_Update_UTC=self._stamp(date(2024, 8, 2)),
        )
        # A couple of per-requirement merit-badge rows (importer skips the type).
        first_aid_reqs = [(9001, "01."), (9002, "02.a")]
        for req_id, code in first_aid_reqs:
            self.row(
                "BSA_Requirement",
                i=req_id,
                BSA_Award_ID=BADGE_AWARD_BASE,
                Requirement_Code=code,
                Requirement_Description=str(4000 + req_id),
                Requirement_Description_Short="",
            )
            self.row(
                "Merit_Badge_Requirement_Earned",
                Person_ID=veteran.pid,
                BSA_Award_ID=BADGE_AWARD_BASE,
                BSA_Requirement_ID=req_id,
                Date_Earned=_d(date(2026, 2, 10)),
                Merit_Badge_ID=1,
                Last_Update_UTC=self._stamp(date(2026, 2, 10)),
            )

    def emit_pending(self) -> None:
        statuses = ["Pending", "Rejected", "Approved"]
        for (pid, award_id, req_id, _code), status in zip(
            self._pending_candidates, statuses, strict=False
        ):
            self.row(
                "Requirement_Pending",
                Person_ID=pid,
                BSA_Award_ID=award_id,
                BSA_Requirement_ID=req_id,
                Date_Completed=_d(TODAY - timedelta(days=12)),
                Submitted_Date_Time=_dt(datetime.combine(TODAY - timedelta(days=12), time(14, 4))),
                Review_Status=status,
                Resubmit_Flag="N",
                Approve_Flag="N",
                Reject_Flag="N",
                Last_Update_UTC=self._stamp(TODAY - timedelta(days=11)),
            )
        # One merit-badge-scoped pending row (importer skips it).
        self.row(
            "Requirement_Pending",
            Person_ID=self._pending_candidates[0][0],
            BSA_Award_ID=BADGE_AWARD_BASE,
            BSA_Requirement_ID=9001,
            Merit_Badge_ID=1,
            Date_Completed=_d(TODAY - timedelta(days=9)),
            Review_Status="Pending",
            Last_Update_UTC=self._stamp(TODAY - timedelta(days=9)),
        )

    # -- everything else (deliberately-skipped types, small generic rows) --

    def emit_misc(self) -> None:
        scouts = [p for p in self.people if not p.adult]
        adults = [p for p in self.people if p.adult]
        first_event = self.events[0][0]

        self.row(
            "Troop_Information",
            Troop_Number=str(700 + self.troop),
            Council_Name="Sample Council",
            District_Name="Sample District",
            Email_From_Prefix=f"troop{700 + self.troop}",
            Troop_Meeting_Day_Of_Week="Tuesday",
            Troop_Meeting_Time="7:00 PM",
            Charter_Expiration_Date=_d(date(2026, 12, 31)),
        )
        self.row(
            "Fiscal_Year",
            Fiscal_Year_Name="2025-2026",
            Start_Date=_d(date(2025, 9, 1)),
            End_Date=_d(date(2026, 8, 31)),
        )
        for i, size in enumerate(["Youth L", "Adult M", "Adult L"]):
            self.row("Shirt_Size", Size=size, Seq=i + 1)
        for name in ("Class A", "Class B"):
            self.row("Dress_Code", Dress_Code_Name=name, Description="Synthetic dress code.")
        self.row(
            "Award_Type",
            Award_Name="5-Year Service Star",
            Service_Star_Years=5,
            Allow_Multiple_Flag="N",
            Last_Update_UTC=self._stamp(date(2024, 1, 1)),
        )
        self.row(
            "Award_Type",
            Award_Name="Mile Swim",
            Allow_Multiple_Flag="N",
            Last_Update_UTC=self._stamp(date(2024, 1, 1)),
        )
        for person in adults[:2]:
            self.row(
                "Award",
                Person_ID=person.pid,
                BSA_Award_ID=SERVICE_STAR_AWARD,
                Date_Earned=_d(person.join + timedelta(days=5 * 365)),
                Last_Update_UTC=self._stamp(TODAY - timedelta(days=90)),
            )
        for i, code in enumerate(["A", "B"]):
            self.row(
                "BSA_Award_Selection_Type",
                Sequence_Number=(i + 1) * 10,
                Selection_Type_Code=f"SYNTHETIC {code}",
                Selection_Type_Description=f"Synthetic selection type {code}.",
                Date_Range_Flag="N",
            )
        for scout in scouts[:6]:
            for activity, (lo, hi) in self.rng.sample(ACTIVITY_TYPES, k=2):
                self.row(
                    "Other_Activity",
                    Person_ID=scout.pid,
                    Activity_Type=activity,
                    Date_Completed=_d(TODAY - timedelta(days=self.rng.randint(30, 700))),
                    Amount=f"{self.rng.randint(lo, hi)}.00",
                    Last_Update_UTC=self._stamp(TODAY - timedelta(days=20)),
                )
        # Training (blocked on GH-122 importer-side; present for schema coverage).
        self.row(
            "BSA_Adult_Training",
            Training_Name="Youth Protection Training",
            Training_Description="Synthetic description.",
        )
        self.row(
            "BSA_Adult_Training",
            Training_Name="Hazardous Weather Training",
            Training_Description="Synthetic description.",
        )
        for person in adults[:4]:
            self.row(
                "Adult_Training",
                Person_ID=person.pid,
                BSA_Adult_Training_ID=1,
                Date_Completed=_d(TODAY - timedelta(days=self.rng.randint(60, 600))),
            )
        self.row(
            "Training_Course",
            Training_Name="Intro to Leadership Skills",
            Adult_Flag="N",
            Expiration_Months="",
        )
        self.row(
            "Training_Course",
            Training_Name="Wilderness First Aid",
            Adult_Flag="Y",
            Expiration_Months="24",
        )
        for scout in scouts[1:3]:
            self.row(
                "Scout_Training",
                Person_ID=scout.pid,
                Training_Course_ID=1,
                Date_Completed=_d(TODAY - timedelta(days=self.rng.randint(60, 400))),
            )
        # Comms (importer skips; OpenTroop has its own messaging layer).
        for i in range(2):
            email_id = self.row(
                "Email",
                Subject=f"Synthetic subject {i + 1}",
                Message="Synthetic message body.",
                Date_Time_Sent=_dt(datetime(2026, 3 + i, 10, 18, 30)),
                Person_ID_Sender=adults[0].pid,
                Last_Update_UTC=self._stamp(date(2026, 3 + i, 10)),
            )
            for person in (scouts[0], adults[1]):
                rid = self.row(
                    "Email_Recipient",
                    Email_ID=email_id,
                    Person_ID=person.pid,
                    Viewed_Flag=self.rng.choice(["Y", "N"]),
                    Last_Update_UTC=self._stamp(date(2026, 3 + i, 11)),
                )
                self.row(
                    "Email_Recipient_Log",
                    Email_ID=email_id,
                    Email_Recipient_ID=rid,
                    Person_ID=person.pid,
                    Date_Time_Sent=_dt(datetime(2026, 3 + i, 10, 18, 31)),
                    Email_Address=f"{person.first.lower()}.{person.last.lower()}@example.com",
                    Error_Flag="N",
                )
        self.row("Email_Group", Email_Group_Name="Synthetic Committee List")
        for person in adults[:2]:
            self.row("Email_Group_Member", Email_Group_ID=1, Person_ID=person.pid)
        for i in range(2):
            aid = self.row(
                "Announcement",
                Announcement_Title=f"Synthetic announcement {i + 1}",
                Announcement_Text="Synthetic announcement text.",
                Start_Date=_d(date(2026, 5, 1)),
                End_Date=_d(date(2026, 6, 30)),
                Display_On_Home_Page_Flag="Y",
                Last_Update_UTC=self._stamp(date(2026, 5, 1)),
            )
            self.row(
                "Announcement_Person_Opened",
                Announcement_ID=aid,
                Person_ID=adults[i].pid,
                Last_Update_UTC=self._stamp(date(2026, 5, 2)),
            )
        self.row("Newsletter_Section_Order", Newsletter_Section_ID=1, Display_Sequence=1)
        self.row("Newsletter_Section_Order", Newsletter_Section_ID=2, Display_Sequence=2)
        self.row(
            "Local_Text",
            Language_ID=1,
            Local_Text="Synthetic local text.",
            Date_Modified=_d(date(2025, 9, 1)),
        )
        # Dynamic groups (TWH's rule-based groups; import deferred — see GH-205).
        self.row(
            "Dynamic_Group",
            Dynamic_Group_Name="Active OA Members",
            OA_Member_Flag="Y",
            OA_Active_Flag="Y",
            Include_Parents_of_Selected_Scouts_Flag="N",
            Disabled_Flag="N",
            Last_Update_UTC=self._stamp(date(2025, 9, 15)),
        )
        self.row(
            "Dynamic_Group",
            Dynamic_Group_Name="Patrol Leaders Council",
            Include_Parents_of_Selected_Scouts_Flag="N",
            Disabled_Flag="N",
            Last_Update_UTC=self._stamp(date(2025, 9, 15)),
        )
        self.row("Dynamic_Group_Leadership", Dynamic_Group_ID=2, Leadership_ID=6)
        self.row("Dynamic_Group_Leadership", Dynamic_Group_ID=2, Leadership_ID=8)
        self.row("Dynamic_Group_Patrol", Dynamic_Group_ID=1, Patrol_ID=1)
        self.row(
            "Person_Category",
            Category_Name="Synthetic Category",
            Category_Description="Synthetic.",
            Youth_Information_Flag="N",
        )
        for scout in scouts[:2]:
            self.row(
                "Person_Leadership_Mass_Update", Person_ID=scout.pid, New_Leadership_Position_ID=8
            )
        recharter = self.row(
            "Recharter_Year",
            Charter_Expiration_Date=_d(date(2026, 12, 31)),
            New_Charter_Expiration_Date=_d(date(2027, 12, 31)),
            Charter_Term_In_Months=12,
        )
        self.row(
            "Recharter_Year_Member",
            Recharter_Year_ID=recharter,
            Person_ID=scouts[1].pid,
            Adult_Flag="N",
            Recharter_Status="Renewing",
        )
        # Finance / inventory / merchandise (future pillar; importer skips).
        self.row(
            "BSA_Transaction_Type",
            Transaction_Name="Synthetic Payment",
            Troop_Credit_Flag="Y",
            Person_Debit_Flag="Y",
        )
        self.row(
            "Monetary_Transaction_Type",
            Transaction_Name="Synthetic Deposit",
            Troop_Credit_Flag="Y",
            Disabled_Flag="N",
        )
        self.row("Monetary_Fund_Category", Category_Name="General Fund", Display_Sequence=1)
        self.row(
            "Subaccount_Type",
            Subaccount_Name="Scout Account",
            Default_Flag="Y",
            Include_In_Main_Balance_Flag="Y",
        )
        self.row(
            "Monetary_Transaction_Audit",
            Monetary_Transaction_ID=1,
            Database_Action="INSERT",
            Server_Datetime=_dt(datetime(2026, 4, 2, 12, 0)),
            Transaction_Date=_d(date(2026, 4, 1)),
            Transaction_Desc="Synthetic dues payment",
            Transaction_Amount="50.00",
            Payment_Type="Check",
        )
        budget = self.row(
            "Budget_Item",
            Budget_Item_Type="Expense",
            Budget_Item_Name="Synthetic Supplies",
            Display_Sequence=1,
            Disabled_Flag="N",
        )
        self.row("Budget_Value", Budget_Item_ID=budget, Fiscal_Year_ID=1, Budget_Amount="250.00")
        self.row(
            "Merchandise_Inventory_Transaction_Type",
            Transaction_Type="Order",
            Effect_On_Quantity_On_Order="+",
        )
        self.row("Merchandise_Payment_Type", Payment_Type="Cash", Display_Sequence_Number=1)
        category = self.row(
            "Inventory_Category",
            Inventory_Type="Equipment",
            Inventory_Category_Name="Camping Gear",
            Last_Update_UTC=self._stamp(date(2025, 7, 1)),
        )
        item = self.row(
            "Inventory_Item",
            Description="Synthetic 4-person tent",
            Inventory_Type="Equipment",
            Inventory_Category_ID=category,
            Serial_Number=f"SYN-{self.troop}-001",
            Purchase_Date=_d(date(2023, 5, 1)),
            Retired_Flag="N",
            Last_Update_UTC=self._stamp(date(2025, 7, 1)),
        )
        self.row(
            "Inventory_Checkout",
            Inventory_Item_ID=item,
            Person_ID=scouts[0].pid,
            Date_Checked_Out=_d(date(2026, 4, 10)),
            Date_Returned=_d(date(2026, 4, 14)),
            Last_Update_UTC=self._stamp(date(2026, 4, 14)),
        )
        # Forms / custom UI config.
        form = self.row(
            "Custom_Form", Menu_Title="Synthetic Form", Public_Access_Flag="N", Menu_Seq=1
        )
        self.row(
            "Custom_Form_Section", Custom_Form_ID=form, Seq=1, Section_Type="Text", Local_Text_ID=1
        )
        self.row(
            "Troop_Form",
            Document_Title="Synthetic Permission Form",
            Document_Type="URL",
            Document_URL="https://example.com/form",
        )
        # Event extras.
        self.row(
            "Event_Photo",
            Event_ID=first_event,
            Photo_File_Name="synthetic.jpg",
            Caption="Synthetic photo caption.",
            Sequence_Number=1,
            Last_Update_UTC=self._stamp(date(2025, 10, 1)),
        )
        shift_event = self.events[-4][0]
        shift = self.row(
            "Event_Shift",
            Event_ID=shift_event,
            Shift_Name="Morning Shift",
            Shift_Start=_dt(datetime(2026, 3, 14, 9, 0)),
            Shift_End=_dt(datetime(2026, 3, 14, 12, 0)),
            Service_Hours_Flag="Y",
            Last_Update_UTC=self._stamp(date(2026, 3, 1)),
        )
        for scout in scouts[2:4]:
            self.row(
                "Event_Shift_Participant",
                Event_Shift_ID=shift,
                Person_ID=scout.pid,
                Signup_Date_Time=_dt(datetime(2026, 3, 1, 19, 5)),
                Last_Update_UTC=self._stamp(date(2026, 3, 1)),
            )
        self.row(
            "Event_Shift_Participant_Delete_Audit",
            Event_ID=shift_event,
            Event_Shift_ID=shift,
            Person_ID=scouts[4].pid,
            Delete_Date_Time=_dt(datetime(2026, 3, 5, 8, 0)),
        )
        # Audit shadows (importer skips; OpenTroop keeps its own timestamps).
        for i, (event_id, _kind, start, _past) in enumerate(self.events[:3]):
            self.row(
                "Event_Participant_Audit",
                Audit_Date_Time=_dt(start - timedelta(days=10)),
                Database_Action="INSERT",
                Event_ID=event_id,
                Person_ID=scouts[i].pid,
                Sign_Up_Flag="Y",
                Participation_Flag="?",
                Event_Participant_ID=i + 1,
            )
        self.row(
            "Delete_Audit",
            Table_Name="Event_Participant",
            Row_ID=999,
            Delete_UTC=_dt(datetime(2026, 1, 20, 3, 15)),
        )
        self.row(
            "Delete_Audit",
            Table_Name="Person",
            Row_ID=998,
            Delete_UTC=_dt(datetime(2025, 11, 2, 4, 40)),
        )

    # -- assembly ---------------------------------------------------------

    def build(self) -> ET.ElementTree:
        self.build_people()
        self.plan_rank_progression()
        self.emit_patrols_and_relationships()
        self.emit_people()
        self.emit_leadership()
        self.emit_locations()
        self.emit_event_types()
        self.emit_events()
        self.emit_participants()
        self.emit_advancement_catalog()
        self.emit_rank_awards()
        self.emit_requirement_signoffs()
        self.emit_merit_badges()
        self.emit_pending()
        self.emit_misc()

        missing = [t for t, rows in self.rows.items() if not rows]
        if missing:
            raise SystemExit(f"record types with no rows (schema coverage broken): {missing}")

        root = ET.Element(
            "database",
            name=f"Synthetic Troop {700 + self.troop} Database",
            date=EXPORT_STAMP,
        )
        for table in sorted(self.rows):
            for fields in self.rows[table]:
                elem = ET.SubElement(root, table)
                for name in self.schema[table]:
                    child = ET.SubElement(elem, name)
                    value = fields.get(name, "")
                    if value not in ("", None):
                        child.text = str(value)
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        return tree


def generate_xml(troop: int) -> bytes:
    """The troop's export as XML bytes (the unit the drift test compares)."""
    tree = FixtureBuilder(troop=troop, seed=1000 + troop).build()
    buffer = io.StringIO()
    tree.write(buffer, encoding="unicode", xml_declaration=True)
    return buffer.getvalue().encode()


def generate(troop: int, out: Path) -> None:
    data = generate_xml(troop)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".gz":
        # mtime=0 keeps the archive header stable; the drift test compares
        # *decompressed* bytes anyway, so zlib-version differences can't bite.
        with out.open("wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(data)
    else:
        out.write_bytes(data)
    print(
        f"Wrote {out} ({out.stat().st_size / 1024:.0f} KiB, {len(data) / 1024:.0f} KiB uncompressed)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--troop", type=int, choices=(1, 2), help="Generate only one troop (default: both)"
    )
    parser.add_argument("--out", type=Path, help="Output path (only with --troop)")
    args = parser.parse_args()

    if args.out and not args.troop:
        parser.error("--out requires --troop")
    troops = [args.troop] if args.troop else [1, 2]
    for troop in troops:
        out = args.out if args.out else FIXTURES_DIR / f"synthetic_troop{troop}.xml.gz"
        generate(troop, out)


if __name__ == "__main__":
    main()
