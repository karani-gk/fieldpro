"""Technician sign-in with email or mobile number and a password: the same token as the code."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.password import update_password

from fieldpro.api.errors import Unauthorized
from fieldpro.api.v1 import auth
from fieldpro.services.password_sign_in import PasswordSignIn
from fieldpro.tests.base import FieldproTestCase

PASSWORD = "Field-pro-2026!"


class TestPasswordSignIn(FieldproTestCase):
	def setUp(self):
		update_password(self.tech_a_user, PASSWORD)
		update_password(self.cust_x_user, PASSWORD)
		self.mobile = frappe.db.get_value("Technician", self.tech_a, "mobile_no")
		self.sign_in = PasswordSignIn()

	def test_email_and_password_return_a_working_token(self):
		result = self.sign_in.sign_in(self.tech_a_user, PASSWORD)
		key, _secret = result["token"].split(":")
		self.assertEqual(frappe.db.get_value("User", {"api_key": key}, "name"), self.tech_a_user)
		self.assertEqual(result["technician"]["id"], self.tech_a)

	def test_the_mobile_number_works_as_the_login(self):
		local = "0" + self.mobile[4:]  # +2547... typed as 07...
		self.assertEqual(self.sign_in.sign_in(local, PASSWORD)["user"], self.tech_a_user)

	def test_a_wrong_password_and_an_unknown_email_get_the_same_answer(self):
		for login, password in ((self.tech_a_user, "wrong"), ("nobody@example.com", PASSWORD), ("", "")):
			with self.assertRaises(Unauthorized) as refused:
				self.sign_in.sign_in(login, password)
			self.assertEqual(refused.exception.code, "wrong_password")

	def test_a_customer_cannot_sign_in_to_the_technician_app(self):
		with self.assertRaises(Unauthorized) as refused:
			self.sign_in.sign_in(self.cust_x_user, PASSWORD)
		self.assertEqual(refused.exception.code, "not_a_technician")


class TestPasswordSignInEndpoint(IntegrationTestCase):
	"""Its own class with no fixtures: an endpoint that answers with an error rolls back the whole
	transaction (api/endpoint.py), which would take a shared fixture with it."""

	def test_the_endpoint_needs_an_activated_installation(self):
		settings = frappe.get_single("Fieldpro Settings")
		activated_on = settings.activated_on
		settings.activated_on = None
		settings.flags.ignore_permissions = True
		settings.save()
		self.addCleanup(frappe.db.set_single_value, "Fieldpro Settings", "activated_on", activated_on)
		frappe.local.response = frappe._dict()
		auth.sign_in_with_password("someone@example.com", PASSWORD)
		self.assertEqual(frappe.local.response["error"]["code"], "not_activated")
