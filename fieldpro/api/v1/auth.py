"""Signing in, per kind of client.

- Technician app (the mobile pattern): request_otp, then verify_otp returns a token. Every call
  after that sends `Authorization: token <key>:<secret>`. No cookie, no CSRF.
- Customer portal (the browser pattern): Frappe's own /api/method/login sets a session cookie.
  session() then returns the CSRF token the browser sends as X-Frappe-CSRF-Token on every POST.
- Partner systems: OAuth2 (Frappe is the provider; see docs/AUTH.md) and send `Bearer <token>`.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from fieldpro.access import AccessProfile
from fieldpro.api.endpoint import api, ok
from fieldpro.api.errors import Unauthorized
from fieldpro.services.otp import OtpService, TokenIssuer


@api(methods=["POST"], allow_guest=True)
@rate_limit(limit=10, seconds=600)
def request_otp(mobile_no: str):
	OtpService().request(mobile_no)
	return ok({"sent": True, "message": _("If this number belongs to a technician, a code is on its way.")})


@api(methods=["POST"], allow_guest=True)
@rate_limit(limit=20, seconds=600)
def verify_otp(mobile_no: str, code: str):
	return ok(OtpService().verify(mobile_no, code))


@api(methods=["GET"])
def session():
	"""Who am I? Works with a cookie or a token. Browsers keep the csrf_token for POSTs."""
	profile = AccessProfile()
	return ok(
		{
			"user": profile.user,
			"full_name": frappe.utils.get_fullname(profile.user),
			"kind": profile.kind,
			"technician": profile.technician,
			"customers": [
				{"id": c, "name": frappe.db.get_value("Customer", c, "customer_name")}
				for c in profile.customers
			],
			"csrf_token": frappe.sessions.get_csrf_token() if frappe.local.session.sid else None,
		}
	)


@api(methods=["POST"])
def sign_out_device():
	"""Technician sign-out: the token stops working on every device that has it."""
	if frappe.session.user == "Guest":
		raise Unauthorized()
	TokenIssuer().revoke(frappe.session.user)
	return ok({"signed_out": True})
