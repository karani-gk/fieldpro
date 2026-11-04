"""Technician sign-in by SMS code."""

import frappe

from fieldpro.api.errors import RateLimited, Unauthorized
from fieldpro.services.otp import MAX_GUESSES, OtpService
from fieldpro.tests.base import FieldproTestCase


class FakeSms:
	def __init__(self):
		self.sent = []

	def send(self, number, message):
		self.sent.append((number, message))

	@property
	def code(self):
		return "".join(c for c in self.sent[-1][1] if c.isdigit())[:6]


class TestOtp(FieldproTestCase):
	def setUp(self):
		self.sms = FakeSms()
		self.otp = OtpService(sms=self.sms)
		self.mobile = frappe.db.get_value("Technician", self.tech_a, "mobile_no")
		frappe.cache.delete_value(f"fieldpro:otp_sends:{self.mobile}")

	def test_the_right_code_returns_a_working_token(self):
		self.otp.request(self.mobile)
		result = self.otp.verify(self.mobile, self.sms.code)
		key, _secret = result["token"].split(":")
		self.assertEqual(frappe.db.get_value("User", {"api_key": key}, "name"), self.tech_a_user)
		self.assertEqual(result["technician"]["id"], self.tech_a)
		# Single use: the same code cannot sign in twice.
		self.assertRaises(Unauthorized, self.otp.verify, self.mobile, self.sms.code)

	def test_too_many_wrong_codes_end_the_attempt(self):
		self.otp.request(self.mobile)
		for _ in range(MAX_GUESSES):
			self.assertRaises(
				Unauthorized,
				self.otp.verify,
				self.mobile,
				"000000" if self.sms.code != "000000" else "111111",
			)
		self.assertRaises(RateLimited, self.otp.verify, self.mobile, self.sms.code)

	def test_an_unknown_number_gets_no_sms_and_no_hint(self):
		self.otp.request("+254799999991")
		self.assertEqual(self.sms.sent, [])
