"""Activating an installation with the access code from the course, once per installation.

Learners who buy "ERPNext as a Platform" at upeo.academy get an access code by email. Until a
code is entered (at /activate, or `bench --site <site> fieldpro-activate <code>`), nobody can sign
in: not in Desk, not on the portal, not on the technician app. After that, nobody is asked again.

A code looks like `UA1.<payload>.<signature>`. The payload names the course and the buyer's email;
the signature is Ed25519, made by the academy with a private key that never leaves its server.
The public key below can check a code but cannot make one, so it is safe in a public repository,
and checking needs no network: an installation on a laptop with no internet activates the same way.

The code in this repository is open, so anyone can remove this check. It is there to remind, not
to lock: it asks people to come in through the course.
"""

import base64
import binascii
import json
from dataclasses import dataclass

import frappe
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from frappe import _

from fieldpro.api.errors import Invalid, NotActivated

PREFIX = "UA1"
COURSE = "erpnext-as-platform-course"
# The academy's public key for system access codes (Ed25519, raw, base64).
PUBLIC_KEY = "SSmglZ9wozdlfpPazyJqU02be9GUF6Zh4lQ+g+otWDk="
COURSE_URL = "https://www.upeo.academy/courses/erpnext-as-platform-course"


@dataclass(frozen=True)
class AccessCode:
	email: str
	course: str
	issued: str
	raw: str


class AccessCodeVerifier:
	"""Reads a code and proves the academy signed it for this course."""

	def __init__(self, public_key: str = PUBLIC_KEY, course: str = COURSE):
		self._key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key))
		self._course = course

	def verify(self, code: str) -> AccessCode:
		raw = "".join((code or "").split())  # pasted from an email: drop line breaks and spaces
		parts = raw.split(".")
		if len(parts) != 3 or parts[0] != PREFIX:
			raise self._refused()
		try:
			self._key.verify(_unb64(parts[2]), f"{parts[0]}.{parts[1]}".encode())
			payload = json.loads(_unb64(parts[1]))
		except InvalidSignature, ValueError, binascii.Error:
			raise self._refused() from None
		if payload.get("course") != self._course:
			raise Invalid(_("This access code is for a different course."), code="invalid_access_code")
		return AccessCode(
			email=payload.get("email", ""),
			course=payload["course"],
			issued=payload.get("issued", ""),
			raw=raw,
		)

	@staticmethod
	def _refused() -> Invalid:
		return Invalid(
			_("That is not a valid access code. Copy the whole code from your course email."),
			code="invalid_access_code",
		)


class Activation:
	"""Whether this installation is activated, and activating it. Stored on Fieldpro Settings."""

	def __init__(self, verifier: AccessCodeVerifier | None = None):
		self._verifier = verifier
		self.settings = frappe.get_single("Fieldpro Settings")

	def is_active(self) -> bool:
		return bool(self.settings.activated_on)

	def status(self) -> dict:
		return {"activated": self.is_active(), "course_url": COURSE_URL}

	def require(self) -> None:
		if not self.is_active():
			raise NotActivated(not_activated_message())

	def activate(self, code: str) -> dict:
		"""Check the code and remember it. On an activated installation this changes nothing."""
		if self.is_active():
			return self.status()
		access = (self._verifier or AccessCodeVerifier()).verify(code)
		self.settings.access_code = access.raw
		self.settings.activated_for = access.email
		self.settings.activated_on = frappe.utils.now_datetime()
		# The whole doc is saved, not one value: set_single_value on a never-saved Single drops
		# every other field's default.
		self.settings.flags.ignore_permissions = True
		self.settings.save()
		return self.status()


def not_activated_message() -> str:
	return _(
		"This fieldpro installation is not activated yet. Open /activate and enter the access code "
		"from your course email."
	)


def _unb64(text: str) -> bytes:
	return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
