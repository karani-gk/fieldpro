"""Cursor (keyset) pagination over frappe.get_list.

Offsets break on a phone: a new job arrives, every row shifts by one, and page 2 repeats a job or
skips one. A cursor says "after this row" instead: the sort value and name of the last row seen,
encoded so the client treats it as an opaque string.

The query stays frappe.get_list, so permission hooks still apply to every page.
"""

import base64
import json
from dataclasses import dataclass

import frappe

from fieldpro.api.errors import Invalid

MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class Page:
	rows: list
	next_cursor: str | None

	@property
	def has_more(self) -> bool:
		return self.next_cursor is not None


def encode(sort_value, name: str) -> str:
	raw = json.dumps([str(sort_value), name]).encode()
	return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode(cursor: str) -> tuple[str, str]:
	try:
		padded = cursor + "=" * (-len(cursor) % 4)
		value, name = json.loads(base64.urlsafe_b64decode(padded.encode()))
		return str(value), str(name)
	except Exception:
		raise Invalid("The cursor is not one this API issued.", fields={"cursor": "invalid"})


def page_size(value, default: int = 20) -> int:
	try:
		size = int(value or default)
	except TypeError, ValueError:
		raise Invalid("limit must be a number.", fields={"limit": "not a number"})
	return max(1, min(size, MAX_PAGE_SIZE))


def fetch_page(
	doctype: str,
	*,
	fields: list[str],
	sort_field: str,
	descending: bool = False,
	filters: list | None = None,
	cursor: str | None = None,
	limit: int = 20,
) -> Page:
	"""One page sorted by (sort_field, name), starting after `cursor`.

	"After (v, n)" is (sort_field > v) OR (sort_field = v AND name > n), written as
	sort_field >= v AND (sort_field > v OR name > n), which get_list can express."""
	filters = list(filters or [])
	or_filters = None
	if cursor:
		value, name = decode(cursor)
		gt, ge = ("<", "<=") if descending else (">", ">=")
		filters.append([doctype, sort_field, ge, value])
		or_filters = [[doctype, sort_field, gt, value], [doctype, "name", gt, name]]
	direction = "desc" if descending else "asc"
	rows = frappe.get_list(
		doctype,
		fields=list({*fields, sort_field, "name"}),
		filters=filters,
		or_filters=or_filters,
		order_by=f"{sort_field} {direction}, name {direction}",
		limit_page_length=limit + 1,
	)
	next_cursor = None
	if len(rows) > limit:
		rows = rows[:limit]
		last = rows[-1]
		next_cursor = encode(last[sort_field], last["name"])
	return Page(rows, next_cursor)
