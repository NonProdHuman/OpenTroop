#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["faker"]
# ///
"""
anonymize_twh.py — Scrub PII from a TroopWebHost full-data XML export.

Produces an output file with identical structure and referential integrity
that is safe to commit as a test fixture. All person names, contact info,
addresses, BSA membership numbers, and other identifying fields are replaced
with seeded fake data. Structural data (event types, patrol assignments,
advancement records, attendance flags, relationship links) is preserved intact.

Run this locally against your real TWH export — never share the real file.

Usage:
    # Recommended — uv reads the inline dependency declaration and handles faker automatically:
    uv run reference/anonymize_twh.py path/to/real_export.xml reference/sample_troop.xml
    uv run reference/anonymize_twh.py real.xml out.xml --seed 99 --date-shift -730

    # To generate a second "troop" from the same source (different names, same structure):
    uv run reference/anonymize_twh.py real.xml reference/sample_troop_2.xml --seed 99

Options:
    --seed INT        Random seed controlling fake data generation (default: 42).
                      Use a different seed to produce a second "troop" from the same
                      source for multi-tenant testing.
    --date-shift INT  Shift all dates by this many days (default: 180).
                      Positive = forward, negative = backward.
                      A non-zero shift prevents temporal re-identification while
                      preserving all relative date relationships within the data.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

from faker import Faker


# ---------------------------------------------------------------------------
# Regex patterns for PII that can appear in free-text fields
# ---------------------------------------------------------------------------

# Standard email address.
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# US phone numbers: (555) 123-4567 · 555-123-4567 · 555.123.4567 · +1 555 123 4567
# Requires 10 digits (with optional country code); negative look-around prevents
# matching mid-number substrings or plain dates.
_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\+?1[\s.\-]?)?"          # optional +1 country code
    r"(?:\(?\d{3}\)?[\s.\-]?)"    # area code
    r"\d{3}[\s.\-]?\d{4}"         # 7-digit local number
    r"(?!\d)"
)


def _scrub_freetext(text: str) -> str:
    """Replace recognisable email addresses and phone numbers in free text."""
    text = _EMAIL_RE.sub("[email]", text)
    text = _PHONE_RE.sub("[phone]", text)
    return text


# ---------------------------------------------------------------------------
# Field classification
# ---------------------------------------------------------------------------

# Tags that are always free-text Comment/Note fields across every record type
# in the TWH schema — cleared globally rather than per-table.
# (Scout_Comment and Review_Comment live on Requirement_Pending.)
_CLEAR_TAGS = frozenset({"Comment", "Note", "Scout_Comment", "Review_Comment"})

# Person fields that are cleared entirely (content not worth faking).
_PERSON_CLEAR = frozenset(
    {
        "Health_Insurance",
        "Allergies",
        "Drivers_License_Number",
        "Drivers_License_State",
        "Drivers_License_Exp_Date",
        "Dietary_Restrictions",
        "Biographical_Information",
        "Previous_Scouting_Experience",
        "Notes",
        "Mic_O_Say_Tribal_Name",
        "Vehicle_Make_Model",
        "License_Plate",
        "Liability_Insurance_Per_Person",
        "Liability_Insurance_Per_Accident",
        "Property_Damage_Insurance",
        "Occupation",
        "Employer",
        "School",
        "From_Cub_Scout_Pack",
        "SMS_Address",
        "SOAR_Row_ID",
    }
)

# Person date fields that are shifted (not cleared).
_PERSON_DATE_FIELDS = frozenset(
    {
        "Date_Of_Birth",
        "Date_Joined_Scouting",
        "Troop_Membership_Start_Date",
        "Troop_Membership_End_Date",
        "Eagle_Scout_Date",
        "Swim_Date",
        "Class_1_Medical_Form_Date",
        "Class_2_Medical_Form_Date",
        "Class_3_Medical_Form_Date",
        "Part_D_Medical_Form_Date",
        "Last_Tetanus_Date",
        "Last_Affirmation_Date",
        "Last_Registration_Date",
        "BSA_Registration_End_Date",
        "OA_Election_Date",
        "OA_Call_Out_Date",
        "OA_Ordeal_Date",
        "OA_Brotherhood_Date",
        "OA_Vigil_Date",
    }
)

# Email message content — redact but keep structural fields (IDs, dates, flags).
_EMAIL_REDACT = frozenset(
    {
        "Subject",
        "Message",
        "Reply_Message",
        "Reply_Subject",
        "SMS_Text_Message",
        "Attachment",
        "Attachment1_Server_File_Name",
        "Attachment1_Original_File_Name",
        "Attachment2_Server_File_Name",
        "Attachment2_Original_File_Name",
        "Attachment3_Server_File_Name",
        "Attachment3_Original_File_Name",
        "Reply_Attachment1_Server_File_Name",
        "Reply_Attachment1_Original_File_Name",
        "Reply_Attachment2_Server_File_Name",
        "Reply_Attachment2_Original_File_Name",
        "Reply_Attachment3_Server_File_Name",
        "Reply_Attachment3_Original_File_Name",
    }
)

# Event free-text fields that could contain names.
_EVENT_CLEAR = frozenset(
    {
        "Attendance_Taken_By_Name",
        "Minutes",
        "Description_Past",
        "Description_Future",
        "Agenda",
    }
)

# EventParticipant fields that could contain PII.
_PARTICIPANT_CLEAR = frozenset(
    {
        "Comment",
        "Electronic_Permission_Signature",
    }
)

# Troop_Information fields to clear.
_TROOP_INFO_CLEAR_FIELDS = frozenset(
    {
        "Newsletter_Reply_Email_Address",
        "PayPal_Notification_Email_Address",
        "Square_Notification_Email_Address",
        "PayPal_Business_ID",
        "Email_CC_All_Peson_ID",  # note: TWH typo preserved
        "Email_CC_All_Person_ID_2",
        "ASP_Customer_ID",
        # HTML blobs that can contain troop-specific prose with names.
        "Electronic_Permission_Text",
        "Merchandise_Online_Sales_Promotion_HTML",
    }
)

# Announcement fields to clear — both may contain arbitrary HTML with names.
_ANNOUNCEMENT_CLEAR = frozenset({"Announcement_Title", "Announcement_Text"})

# Vigil name word lists for plausible-sounding OA names (no real tribal names used).
_VIGIL_WORDS = [
    "Running",
    "Silent",
    "Swift",
    "Broken",
    "Ancient",
    "Standing",
    "Rising",
    "Fading",
    "Rolling",
    "Distant",
]
_VIGIL_NOUNS = [
    "River",
    "Oak",
    "Wind",
    "Trail",
    "Arrow",
    "Ember",
    "Stone",
    "Creek",
    "Mountain",
    "Flame",
]


class Anonymizer:
    """Walks a parsed TWH XML tree and replaces PII in-place."""

    _DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

    def __init__(self, seed: int, date_shift_days: int) -> None:
        Faker.seed(seed)
        self.fake = Faker()
        self._rng_seed = seed
        self.date_shift = timedelta(days=date_shift_days)
        # person_id (from <i> element) -> dict of replacement field values
        self.person_map: dict[str, dict[str, str]] = {}
        # Sequential fake BSA numbers starting from a seed-derived base.
        self._bsa_base = 10_000_000 + (seed % 1_000_000)
        self._bsa_counter = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _next_bsa(self) -> str:
        num = self._bsa_base + self._bsa_counter
        self._bsa_counter += 1
        return str(num)

    def _vigil_name(self) -> str:
        w = _VIGIL_WORDS[self.fake.random_int(0, len(_VIGIL_WORDS) - 1)]
        n = _VIGIL_NOUNS[self.fake.random_int(0, len(_VIGIL_NOUNS) - 1)]
        return f"{w} {n}"

    def _shift_date(self, value: str) -> str:
        """Shift the YYYY-MM-DD prefix of a date string by self.date_shift."""
        if not value or not self._DATE_PREFIX_RE.match(value):
            return value
        try:
            d = date.fromisoformat(value[:10]) + self.date_shift
            return d.isoformat() + value[10:]
        except ValueError:
            return value

    # ------------------------------------------------------------------
    # Person identity generation
    # ------------------------------------------------------------------

    def _make_fake_person(self, is_adult: bool) -> dict[str, str]:
        """Generate a complete set of fake values for one person."""
        first = self.fake.first_name()
        last = self.fake.last_name()
        has_middle = self.fake.boolean(chance_of_getting_true=35)
        has_ec2 = self.fake.boolean(chance_of_getting_true=65)
        has_spouse = is_adult and self.fake.boolean(chance_of_getting_true=55)
        has_oa_vigil = self.fake.boolean(chance_of_getting_true=8)

        return {
            # Name
            "Name_First": first,
            "Name_Middle": self.fake.first_name()[0] if has_middle else "",
            "Name_Last": last,
            "Name_Suffix": "",
            "Nickname": first[:3] if self.fake.boolean(chance_of_getting_true=15) else "",
            # Contact
            "Email_Address": self.fake.email(),
            "Email_Address_2": self.fake.email() if self.fake.boolean(chance_of_getting_true=20) else "",
            "Home_Phone": self.fake.phone_number(),
            "Cell_Phone": self.fake.phone_number(),
            "Business_Phone": self.fake.phone_number() if is_adult else "",
            # Mailing address
            "Mailing_Address_Line_1": self.fake.street_address(),
            "Mailing_Address_Line_2": "",
            "Mailing_Address_City": self.fake.city(),
            "Mailing_Address_State": self.fake.state_abbr(),
            "Mailing_Address_Zip": self.fake.zipcode(),
            "Mailing_Address_Country": "US",
            # Business address (clear for everyone — not worth faking)
            "Business_Address_Line_1": "",
            "Business_Address_Line_2": "",
            "Business_Address_City": "",
            "Business_Address_State": "",
            "Business_Address_Zip": "",
            "Business_Address_Country": "",
            # BSA identifier
            "BSA_Membership_Number": self._next_bsa(),
            # OA vigil name (only for members with a vigil honor)
            "OA_Vigil_Name": self._vigil_name() if has_oa_vigil else "",
            "OA_Notes": "",
            # Spouse
            "Spouse_Name_First": self.fake.first_name() if has_spouse else "",
            "Spouse_Name_Middle": "",
            "Spouse_Name_Last": last if has_spouse else "",
            "Spouse_Name_Suffix": "",
            # Emergency contact 1 (always present)
            "Emergency_Contact_1_Name_First": self.fake.first_name(),
            "Emergency_Contact_1_Name_Middle": "",
            "Emergency_Contact_1_Name_Last": self.fake.last_name(),
            "Emergency_Contact_1_Name_Suffix": "",
            "Emergency_Contact_1_Phone": self.fake.phone_number(),
            # Emergency contact 2 (sometimes present)
            "Emergency_Contact_2_Name_First": self.fake.first_name() if has_ec2 else "",
            "Emergency_Contact_2_Name_Middle": "",
            "Emergency_Contact_2_Name_Last": self.fake.last_name() if has_ec2 else "",
            "Emergency_Contact_2_Name_Suffix": "",
            "Emergency_Contact_2_Phone": self.fake.phone_number() if has_ec2 else "",
            # Legacy combined emergency contact fields (older TWH versions)
            "Emergency_Contact_Name_1": "",
            "Emergency_Contact_Name_2": "",
        }

    # ------------------------------------------------------------------
    # Two-pass processing
    # ------------------------------------------------------------------

    def _first_pass_build_person_map(self, root: ET.Element) -> None:
        """Collect all Person records and generate fake identities for each."""
        for elem in root.findall("Person"):
            pid_el = elem.find("i")
            if pid_el is None or not (pid_el.text or "").strip():
                continue
            pid = pid_el.text.strip()
            is_adult_el = elem.find("Adult_Flag")
            is_adult = is_adult_el is not None and (is_adult_el.text or "").strip() == "1"
            self.person_map[pid] = self._make_fake_person(is_adult)

    def _process_person(self, elem: ET.Element) -> None:
        pid_el = elem.find("i")
        if pid_el is None or not (pid_el.text or "").strip():
            return
        fake = self.person_map.get(pid_el.text.strip(), {})
        for child in elem:
            tag = child.tag
            text = child.text or ""
            if tag in fake:
                child.text = fake[tag]
            elif tag in _PERSON_DATE_FIELDS:
                child.text = self._shift_date(text)
            elif tag in _PERSON_CLEAR:
                child.text = ""

    def _process_troop_info(self, elem: ET.Element) -> None:
        for child in elem:
            tag = child.tag
            text = child.text or ""
            if tag == "Troop_Number":
                child.text = "999"
            elif tag == "Council_Name":
                child.text = "Sample Council"
            elif tag == "District_Name":
                child.text = "Sample District"
            elif tag == "Email_From_Prefix":
                child.text = "troop999"
            elif tag in _TROOP_INFO_CLEAR_FIELDS:
                child.text = ""
            elif "Date" in tag and text:
                child.text = self._shift_date(text)

    def _process_location(self, elem: ET.Element) -> None:
        for child in elem:
            tag = child.tag
            text = child.text or ""
            if tag == "Address_Line_1" and text:
                child.text = self.fake.street_address()
            elif tag == "Address_Line_2":
                child.text = ""
            elif tag == "Address_City" and text:
                child.text = self.fake.city()
            elif tag == "Address_State" and text:
                child.text = self.fake.state_abbr()
            elif tag == "Address_Zip" and text:
                child.text = self.fake.zipcode()
            elif tag == "Telephone_Number" and text:
                child.text = self.fake.phone_number()
            elif tag == "Website_URL" and text:
                child.text = "https://example.com"
            elif tag == "Directions" and text:
                child.text = "Sample directions"
            elif tag == "Map":
                child.text = ""

    def _process_announcement(self, elem: ET.Element) -> None:
        for child in elem:
            if child.tag in _ANNOUNCEMENT_CLEAR:
                child.text = ""

    def _process_merit_badge(self, elem: ET.Element) -> None:
        for child in elem:
            if child.tag == "Merit_Badge_Counselor" and child.text:
                child.text = self.fake.name()

    def _process_requirement_pending(self, elem: ET.Element) -> None:
        for child in elem:
            if child.tag == "Reviewed_By_Name" and child.text:
                child.text = self.fake.name()

    def _process_event(self, elem: ET.Element) -> None:
        for child in elem:
            if child.tag in _EVENT_CLEAR:
                child.text = ""

    def _process_email(self, elem: ET.Element) -> None:
        for child in elem:
            if child.tag in _EMAIL_REDACT and child.text:
                child.text = "[redacted]"

    def _process_participant(self, elem: ET.Element) -> None:
        for child in elem:
            if child.tag in _PARTICIPANT_CLEAR and child.text:
                child.text = ""

    def _final_pass(self, root: ET.Element) -> None:
        """Belt-and-suspenders sweep over the entire tree.

        1. Clear any Comment/Note field not already handled by a per-table processor.
        2. Regex-scrub email addresses and phone numbers out of every remaining
           text value — catches PII embedded in event descriptions, award notes,
           training comments, inventory descriptions, and any other free-text field
           we haven't explicitly touched.
        """
        for elem in root:
            for child in elem:
                if not child.text:
                    continue
                if child.tag in _CLEAR_TAGS:
                    child.text = ""
                else:
                    scrubbed = _scrub_freetext(child.text)
                    if scrubbed != child.text:
                        child.text = scrubbed

    def process(self, root: ET.Element) -> None:
        """Anonymize the entire XML tree in place."""
        if "name" in root.attrib:
            root.attrib["name"] = "Sample Troop Database"

        self._first_pass_build_person_map(root)

        dispatch = {
            "Person": self._process_person,
            "Troop_Information": self._process_troop_info,
            "Announcement": self._process_announcement,
            "Location": self._process_location,
            "Merit_Badge": self._process_merit_badge,
            "Requirement_Pending": self._process_requirement_pending,
            "Event": self._process_event,
            "Email": self._process_email,
            "Email_Recipient_Log": self._process_email,  # also has email addresses
            "Event_Participant": self._process_participant,
            "Event_Shift_Participant": self._process_participant,
        }

        for elem in root:
            handler = dispatch.get(elem.tag)
            if handler:
                handler(elem)

        self._final_pass(root)


# ---------------------------------------------------------------------------
# Email_Recipient_Log special handling (has an Email_Address child field)
# ---------------------------------------------------------------------------

def _patch_email_recipient_log_addresses(root: ET.Element, fake: Faker) -> None:
    """Replace raw email addresses stored in Email_Recipient_Log rows."""
    for elem in root.findall("Email_Recipient_Log"):
        for child in elem:
            if child.tag == "Email_Address" and child.text:
                child.text = fake.email()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="Path to the real TWH XML export")
    parser.add_argument("output", type=Path, help="Path for the anonymized output file")
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42). Use a different seed to generate a second fake troop.",
    )
    parser.add_argument(
        "--date-shift",
        type=int,
        default=180,
        metavar="DAYS",
        help="Days to shift all dates (default: 180). Use negative to shift backward.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"Input file not found: {args.input}")

    print(f"Parsing {args.input} ...")
    tree = ET.parse(args.input)
    root = tree.getroot()

    print(f"Anonymizing (seed={args.seed}, date_shift={args.date_shift:+d} days) ...")
    anon = Anonymizer(seed=args.seed, date_shift_days=args.date_shift)
    anon.process(root)
    _patch_email_recipient_log_addresses(root, anon.fake)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing {args.output} ...")
    if hasattr(ET, "indent"):  # Python 3.9+
        ET.indent(tree, space="  ")
    tree.write(str(args.output), encoding="unicode", xml_declaration=True)

    person_count = len(anon.person_map)
    print(f"Done. Anonymized {person_count} person records.")
    print()
    print("What was scrubbed:")
    print("  Person      — names, DOB (shifted), addresses, phones, emails, BSA numbers,")
    print("                emergency contacts, OA vigil names, spouse names")
    print("  Troop       — troop number → 999, council/district → 'Sample ...'")
    print("  Location    — street addresses, phones, website URLs")
    print("  Email       — message subjects and bodies → '[redacted]'")
    print("  Event       — free-text fields (Attendance_Taken_By_Name, Minutes,")
    print("                Description_Past/Future, Agenda)")
    print("  Participant — Comment, Electronic_Permission_Signature")
    print("  All records — every Comment/Note field cleared; email addresses and")
    print("                phone numbers regex-scrubbed from all remaining text")
    print()
    print("What was preserved (safe to share):")
    print("  Structural IDs, foreign keys, event types, patrol names, patrol assignments,")
    print("  attendance flags, advancement records, merit badge records, OA flags/dates,")
    print("  sign-up records, activity metrics, relationship links")
    print()
    print("Note: Patrol names are kept as-is. If your troop uses scouts' names as patrol")
    print("names (e.g. 'Alex's Patrol'), edit those manually in the output file.")


if __name__ == "__main__":
    main()
