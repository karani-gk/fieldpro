"""Technician sign-in with a password, beside the one-time code (otp.py).

The technician types their email or mobile number and their Frappe password, and gets the same
API token the code gives: the app does not care which way they proved who they are. Frappe's own
checks do the work: `User.find_by_credentials` checks the password, and the login attempt tracker
locks an account after the failures System Settings allows, exactly as Desk login does.

A wrong email and a wrong password get the same answer, so the endpoint cannot be used to find
out who has an account.
"""

import frappe
from frappe import _
from frappe.auth import get_login_attempt_tracker
from frappe.core.doctype.user.user import User

from fieldpro.api.errors import RateLimited, Unauthorized
from fieldpro.services.otp import TokenIssuer
from fieldpro.utils import normalise_mobile


class PasswordSignIn:
	def __init__(self, tokens: TokenIssuer | None = None):
		self.tokens = tokens or TokenIssuer()

	def sign_in(self, login: str, password: str) -> dict:
		user_name = self._user_for(login)
		user = User.find_by_credentials(user_name, password or "") if user_name and password else None
		tracker = self._tracker(user["name"]) if user else None
		if not user or not user["is_authenticated"] or not user["enabled"]:
			if tracker:
				tracker.add_failure_attempt()
			raise Unauthorized(_("That email or password is not right."), code="wrong_password")
		technician = frappe.db.get_value(
			"Technician", {"user": user["name"], "is_active": 1}, ["name", "full_name"], as_dict=True
		)
		if not technician:
			raise Unauthorized(
				_("This sign-in is for technicians. Customers use the portal; staff use Desk."),
				code="not_a_technician",
			)
		tracker.add_success_attempt()
		# The same shape as OtpService.verify: the app stores either sign-in the same way.
		return {
			"token": self.tokens.issue(user["name"]),
			"user": user["name"],
			"technician": {"id": technician.name, "name": technician.full_name},
		}

	@staticmethod
	def _user_for(login: str) -> str | None:
		"""An email as it is; anything else is read as the technician's mobile number."""
		login = (login or "").strip()
		if "@" in login or not login:
			return login or None
		try:
			mobile = normalise_mobile(login)
		except frappe.ValidationError:
			return None
		return frappe.db.get_value("Technician", {"mobile_no": mobile}, "user")

	@staticmethod
	def _tracker(user_name: str):
		try:
			return get_login_attempt_tracker(user_name)
		except frappe.SecurityException as exc:
			raise RateLimited(str(exc)) from None
