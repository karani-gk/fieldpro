"""Activating this installation with the access code from the course (services/activation.py).

Both endpoints are open to guests: before activation nobody can sign in, so nobody could call them
otherwise."""

from frappe.rate_limiter import rate_limit

from fieldpro.api.endpoint import api, ok
from fieldpro.services.activation import Activation


@api(methods=["GET"], allow_guest=True)
def status():
	return ok(Activation().status())


@api(methods=["POST"], allow_guest=True)
@rate_limit(limit=10, seconds=3600)
def activate(code: str):
	return ok(Activation().activate(code))
