"""The API contract: one error format, cursors that never repeat a row, UTC times, phone numbers."""

import frappe
from frappe.tests import UnitTestCase

from fieldpro.api import errors
from fieldpro.api.pagination import decode, encode, fetch_page
from fieldpro.tests import factories
from fieldpro.tests.base import FieldproTestCase
from fieldpro.utils import from_iso, normalise_mobile, to_iso


class TestErrorFormat(UnitTestCase):
	def test_frappe_errors_map_to_stable_codes(self):
		cases = [
			(frappe.DoesNotExistError("x"), 404, "not_found"),
			(frappe.PermissionError("x"), 403, "forbidden"),
			(frappe.DuplicateEntryError("x"), 409, "conflict"),
			(frappe.MandatoryError("x"), 422, "invalid"),
			(frappe.TooManyRequestsError("x"), 429, "rate_limited"),
		]
		for exc, status, code in cases:
			error = errors.ApiError.from_exception(exc)
			self.assertEqual((error.status, error.code), (status, code), exc)

	def test_a_bug_is_not_dressed_up_as_a_client_error(self):
		self.assertIsNone(errors.ApiError.from_exception(KeyError("x")))

	def test_the_body_has_code_message_and_fields(self):
		body = errors.Invalid("Bad qty", fields={"qty": "must be positive"}).as_dict()
		self.assertEqual(
			body, {"code": "invalid", "message": "Bad qty", "fields": {"qty": "must be positive"}}
		)


class TestFormats(UnitTestCase):
	def test_cursor_round_trip(self):
		self.assertEqual(
			decode(encode("2026-11-04 10:00:00.123456", "JOB-1")), ("2026-11-04 10:00:00.123456", "JOB-1")
		)
		self.assertRaises(errors.Invalid, decode, "not-a-cursor")

	def test_times_go_out_in_utc_and_come_back_in_site_time(self):
		frappe.db.set_single_value("System Settings", "time_zone", "Africa/Nairobi")
		self.assertEqual(to_iso("2026-11-04 09:00:00"), "2026-11-04T06:00:00Z")
		self.assertEqual(str(from_iso("2026-11-04T06:00:00Z")), "2026-11-04 09:00:00")
		self.assertRaises(frappe.ValidationError, from_iso, "2026-11-04T06:00:00")

	def test_mobile_numbers_have_one_format(self):
		for raw in ("0712 345 678", "254712345678", "+254 712-345-678"):
			self.assertEqual(normalise_mobile(raw), "+254712345678")


class TestCursorPagination(FieldproTestCase):
	def test_pages_never_repeat_or_skip_a_row(self):
		jobs = {factories.job(self.cust_x, technician_name=self.tech_a) for _ in range(5)}
		seen, cursor = [], None

		def page():
			return fetch_page(
				"Service Job", fields=["name"], sort_field="scheduled_date", cursor=cursor, limit=2
			)

		while True:
			result = factories.as_user(self.tech_a_user, page)
			seen += [r.name for r in result.rows]
			cursor = result.next_cursor
			if not cursor:
				break
		self.assertEqual(len(seen), len(set(seen)))
		self.assertTrue(jobs <= set(seen))
