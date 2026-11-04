"""Activation with the access code from the course: once per installation, before anyone signs in."""

import base64
import json

import frappe
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from frappe.tests import IntegrationTestCase

from fieldpro.activation_hooks import redirect_login_page, refuse_sign_in
from fieldpro.api.errors import Invalid, NotActivated
from fieldpro.api.v1 import auth
from fieldpro.services.activation import COURSE, PREFIX, AccessCodeVerifier, Activation
from fieldpro.tests.base import FieldproTestCase


def b64(data: bytes) -> str:
	return base64.urlsafe_b64encode(data).decode().rstrip("=")


class TestAcademy:
	"""Signs codes the way the academy does, with a key made for the test."""

	def __init__(self):
		self.key = Ed25519PrivateKey.generate()

	@property
	def public_key(self) -> str:
		raw = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
		return base64.b64encode(raw).decode()

	def code(self, email="learner@example.com", course=COURSE) -> str:
		payload = b64(json.dumps({"course": course, "email": email, "issued": "2026-11-04"}).encode())
		signature = self.key.sign(f"{PREFIX}.{payload}".encode())
		return f"{PREFIX}.{payload}.{b64(signature)}"


class TestActivation(FieldproTestCase):
	def setUp(self):
		self.academy = TestAcademy()
		self.verifier = AccessCodeVerifier(public_key=self.academy.public_key)
		self._deactivate()
		self.addCleanup(self._deactivate)

	def test_a_signed_code_activates_the_installation_once(self):
		activation = Activation(self.verifier)
		self.assertFalse(activation.is_active())
		activation.activate(self.academy.code(email="amina@example.com"))
		settings = frappe.get_single("Fieldpro Settings")
		self.assertTrue(Activation().is_active())
		self.assertEqual(settings.activated_for, "amina@example.com")
		# Once per installation: another code changes nothing.
		Activation(self.verifier).activate(self.academy.code(email="other@example.com"))
		self.assertEqual(frappe.get_single("Fieldpro Settings").activated_for, "amina@example.com")

	def test_a_code_pasted_with_line_breaks_still_works(self):
		code = self.academy.code()
		Activation(self.verifier).activate(f"  {code[:40]}\n{code[40:]}  ")
		self.assertTrue(Activation().is_active())

	def test_a_changed_payload_is_refused(self):
		prefix, _payload, signature = self.academy.code().split(".")
		forged = b64(
			json.dumps({"course": COURSE, "email": "x@example.com", "issued": "2026-11-04"}).encode()
		)
		self._assert_refused(f"{prefix}.{forged}.{signature}")

	def test_a_code_signed_by_another_key_is_refused(self):
		self._assert_refused(TestAcademy().code())

	def test_a_code_for_another_course_is_refused(self):
		self._assert_refused(self.academy.code(course="linux-erpnext-running-platform"))

	def test_text_that_is_not_a_code_is_refused(self):
		for text in ("", "hello", "UA1.abc", "UA1.!!.!!", "XX1.a.b"):
			self._assert_refused(text)

	def test_the_real_public_key_refuses_a_test_code(self):
		with self.assertRaises(Invalid):
			Activation().activate(self.academy.code())

	def test_no_sign_in_before_activation(self):
		with self.assertRaises(frappe.AuthenticationError):
			refuse_sign_in()
		with self.assertRaises(NotActivated):
			Activation().require()

	def test_the_login_page_sends_people_to_activate_for_now_only(self):
		previous = getattr(frappe.local, "request", None)
		frappe.local.request = frappe._dict(path="/login")
		self.addCleanup(setattr, frappe.local, "request", previous)
		with self.assertRaises(frappe.Redirect) as redirect:
			redirect_login_page({})
		self.assertEqual(frappe.local.flags.redirect_location, "/activate")
		# Temporary (302): a browser keeps a 301 and would never reach /login after activation.
		self.assertEqual(redirect.exception.http_status_code, 302)
		Activation(self.verifier).activate(self.academy.code())
		redirect_login_page({})  # activated: no redirect

	def test_sign_in_works_after_activation(self):
		Activation(self.verifier).activate(self.academy.code())
		refuse_sign_in()  # no error
		Activation().require()

	def _assert_refused(self, code: str):
		with self.assertRaises(Invalid):
			Activation(self.verifier).activate(code)
		self.assertFalse(Activation().is_active())

	@staticmethod
	def _deactivate():
		settings = frappe.get_single("Fieldpro Settings")
		settings.access_code = settings.activated_for = settings.activated_on = None
		settings.flags.ignore_permissions = True
		settings.save()


class TestActivationEndpoints(IntegrationTestCase):
	"""Its own class with no fixtures: an endpoint that answers with an error rolls back the whole
	transaction (api/endpoint.py), which would take a shared fixture with it."""

	def setUp(self):
		TestActivation._deactivate()
		self.addCleanup(TestActivation._deactivate)

	def test_the_technician_sign_in_endpoint_answers_not_activated(self):
		frappe.local.response = frappe._dict()
		auth.request_otp("+254700100001")
		self.assertEqual(frappe.local.response.http_status_code, 403)
		self.assertEqual(frappe.local.response["error"]["code"], "not_activated")
