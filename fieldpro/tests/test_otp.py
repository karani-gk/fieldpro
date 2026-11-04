"""Technician sign-in by a code sent by SMS or email."""

import frappe

from fieldpro.api.errors import RateLimited, Unauthorized
from fieldpro.services.otp import (
	MAX_GUESSES,
	EmailDelivery,
	OtpService,
	SmsDelivery,
	default_delivery,
)
from fieldpro.settings import AppSettings
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


class FakeEmail:
	def __init__(self):
		self.sent = []

	def send(self, email, message):
		self.sent.append((email, message))


class TestOtpByEmail(FieldproTestCase):
	"""The default for a course taken in many countries: the code goes to the technician's email."""

	def setUp(self):
		self.email = FakeEmail()
		self.otp = OtpService(delivery=EmailDelivery(self.email))
		self.mobile = frappe.db.get_value("Technician", self.tech_a, "mobile_no")
		frappe.cache.delete_value(f"fieldpro:otp_sends:{self.mobile}")

	def test_the_code_goes_to_the_technicians_email_and_signs_in(self):
		self.otp.request(self.mobile)
		((to, message),) = self.email.sent
		self.assertEqual(to, frappe.db.get_value("User", self.tech_a_user, "email"))
		code = "".join(c for c in message if c.isdigit())[:6]
		self.assertEqual(self.otp.verify(self.mobile, code)["user"], self.tech_a_user)

	def test_an_unknown_number_gets_no_email(self):
		self.otp.request("+254799999992")
		self.assertEqual(self.email.sent, [])

	def test_with_an_email_account_the_code_is_queued_as_email(self):
		# Muted emails give Frappe a dummy outgoing account: queued, never sent.
		self._email_account(muted=True)
		recipient = frappe.db.get_value("User", self.tech_a_user, "email")
		OtpService(delivery=EmailDelivery()).request(self.mobile)
		queued = frappe.get_last_doc("Email Queue")
		self.assertIn(recipient, [r.recipient for r in queued.recipients])
		self.assertIn("sign-in code", queued.message)

	def test_without_an_email_account_the_code_is_in_sms_log(self):
		self._email_account(muted=False)
		recipient = frappe.db.get_value("User", self.tech_a_user, "email")
		OtpService(delivery=EmailDelivery()).request(self.mobile)
		log = frappe.get_last_doc("SMS Log")
		self.assertEqual(log.requested_numbers, recipient)
		self.assertIn("sign-in code", log.message)

	def _email_account(self, muted: bool):
		if frappe.db.exists("Email Account", {"enable_outgoing": 1}):
			self.skipTest("This site has a real outgoing Email Account.")
		previous = frappe.flags.mute_emails
		frappe.flags.mute_emails = muted
		self.addCleanup(setattr, frappe.flags, "mute_emails", previous)
		# Frappe caches the outgoing account per request.
		frappe.local.outgoing_email_account = {}
		self.addCleanup(setattr, frappe.local, "outgoing_email_account", {})


class TestSignInCodeChannel(FieldproTestCase):
	def test_email_is_the_default_when_the_setting_is_blank(self):
		settings = AppSettings(doc=frappe._dict(sign_in_code_channel=None))
		self.assertIsInstance(default_delivery(settings), EmailDelivery)

	def test_sms_when_the_manager_chooses_it(self):
		settings = AppSettings(doc=frappe._dict(sign_in_code_channel="SMS"))
		self.assertIsInstance(default_delivery(settings), SmsDelivery)
