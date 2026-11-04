"""Small helpers with no business rules: phone numbers and time zones."""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_datetime, get_system_timezone

KENYA_CODE = "254"


def normalise_mobile(number: str | None) -> str:
	"""+254712345678 from 0712 345 678, 254712345678 or +254 712-345-678.

	One format in the database, so a sign-in code is found whichever way it was typed."""
	digits = re.sub(r"\D", "", number or "")
	if digits.startswith("0") and len(digits) == 10:
		digits = KENYA_CODE + digits[1:]
	if len(digits) < 9:
		frappe.throw(frappe._("Enter a mobile number with its country code, e.g. +254712345678."))
	return "+" + digits


def to_iso(value) -> str | None:
	"""A stored datetime (naive, in the system time zone) as UTC ISO 8601: 2026-11-04T05:30:00Z.

	Clients in any time zone read the same instant; they convert to local time for display."""
	if not value:
		return None
	local = get_datetime(value).replace(tzinfo=ZoneInfo(get_system_timezone()))
	return local.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def from_iso(value: str | None) -> datetime | None:
	"""A client's ISO 8601 timestamp (with an offset, or Z) as a naive system-time datetime, the
	way Frappe stores it. A timestamp without an offset is refused: we cannot know its zone."""
	if not value:
		return None
	try:
		parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
	except ValueError:
		frappe.throw(frappe._("{0} is not an ISO 8601 date and time.").format(value))
	if parsed.tzinfo is None:
		frappe.throw(frappe._("{0} has no time zone. Send UTC, e.g. 2026-11-04T05:30:00Z.").format(value))
	return parsed.astimezone(ZoneInfo(get_system_timezone())).replace(tzinfo=None)
