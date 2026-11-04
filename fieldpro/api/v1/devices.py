"""Push notification tokens for the signed-in user's devices."""

import frappe

from fieldpro.api.endpoint import api, ok
from fieldpro.api.errors import Invalid
from fieldpro.services.push import DeviceRegistry

PLATFORMS = ("web", "android", "ios")


@api(methods=["POST"])
def register(token: str, platform: str = "web"):
	if platform not in PLATFORMS:
		raise Invalid("platform must be web, android or ios.", fields={"platform": "invalid"})
	DeviceRegistry().register(frappe.session.user, token, platform)
	return ok({"registered": True})


@api(methods=["POST"])
def unregister(token: str):
	DeviceRegistry().unregister(frappe.session.user, token)
	return ok({"registered": False})
