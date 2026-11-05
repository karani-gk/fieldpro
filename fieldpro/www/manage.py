"""/manage: the field service manager's Vue app (frontend/ in this repo, built by `bench build`).

This page only hands the browser the built files, the CSRF token and who is signed in; the
app talks to fieldpro.api.v1.manage for everything else. Every /manage/<path> URL lands here
(hooks.py website_route_rules) so the Vue router can own the paths.
"""

import json
from urllib.parse import urlencode

import frappe
from frappe import _

from fieldpro.access import AccessProfile
from fieldpro.services.manager_landing import DESK_CHOICE_COOKIE
from fieldpro.settings import AppSettings

no_cache = 1

ASSET_BASE = "/assets/fieldpro/manage/"
ENTRY = "src/main.js"


def get_context(context):
	context.no_cache = 1
	if frappe.session.user == "Guest":
		# Back to the screen they asked for (/manage/board, /manage/jobs/JOB-...) after signing in.
		frappe.local.flags.redirect_location = "/login?" + urlencode({"redirect-to": frappe.request.path})
		raise frappe.Redirect(302)
	if not AccessProfile().is_manager:
		raise frappe.PermissionError(_("This is for field service managers."))
	# Back in the app: Desk pages it replaces send this manager here again (manager_landing.py).
	frappe.local.cookie_manager.delete_cookie(DESK_CHOICE_COOKIE)
	context.title = _("Field Service")
	context.csrf_token = frappe.sessions.get_csrf_token()
	# "<" escaped, so a name containing </script> cannot end the inline script early.
	context.boot = json.dumps(boot()).replace("<", "\\u003c")
	context.update(ViteAssets().for_entry(ENTRY))


def boot() -> dict:
	settings = AppSettings()
	return {
		"user": frappe.session.user,
		"full_name": frappe.utils.get_fullname(frappe.session.user),
		"currency": settings.currency,
		"company": settings.company,
	}


class ViteAssets:
	"""The script and stylesheets Vite built for an entry, read from Vite's manifest.json."""

	def __init__(self, manifest_path: str | None = None):
		self.manifest_path = manifest_path or frappe.get_app_path(
			"fieldpro", "public", "manage", ".vite", "manifest.json"
		)

	def for_entry(self, entry: str) -> dict:
		manifest = self._manifest()
		if not manifest or entry not in manifest:
			# Not built yet: the page says how to build it instead of showing a blank screen.
			return {"script": None, "styles": []}
		chunk = manifest[entry]
		return {
			"script": ASSET_BASE + chunk["file"],
			"styles": [ASSET_BASE + css for css in chunk.get("css", [])],
		}

	def _manifest(self) -> dict | None:
		try:
			with open(self.manifest_path) as f:
				return json.load(f)
		except FileNotFoundError:
			return None
