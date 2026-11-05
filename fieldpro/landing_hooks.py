"""Sending field managers to the Vue app (hooks.py). The rules are in services/manager_landing.py."""

import frappe
from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect

from fieldpro.services.manager_landing import DESK_CHOICE_COOKIE, STAY_IN_DESK_PARAM, ManagerLanding


def send_managers_to_app():
	"""before_request: a field manager opening a Desk page the app replaces goes to /manage.

	Only full page loads (GET of /desk or /app) are looked at, so API calls pay one string check.
	frappe.Redirect is only handled while a web page renders; this runs earlier, so it raises a
	werkzeug HTTPException carrying the redirect, which Frappe's request handler returns as is."""
	request = getattr(frappe.local, "request", None)
	if not request or request.method != "GET":
		return
	target = ManagerLanding.target(request.path)
	if not target:
		return
	if request.args.get(STAY_IN_DESK_PARAM) == "1":
		# The manager chose Desk: remember it for this browser session (no expiry).
		frappe.local.cookie_manager.set_cookie(DESK_CHOICE_COOKIE, "1")
		return
	if request.cookies.get(DESK_CHOICE_COOKIE) == "1" or not ManagerLanding().applies():
		return
	# 302: browsers keep a 301, and the redirect must stop when the manager chooses Desk.
	raise HTTPException(response=redirect(target, 302))


def forget_desk_choice(login_manager=None):
	"""on_login, on_logout: choosing Desk lasts one sign-in. The cookie is a browser-session one,
	so without this a manager who chose Desk, signed out and signed in again stayed in Desk."""
	frappe.local.cookie_manager.delete_cookie(DESK_CHOICE_COOKIE)


def add_manager_app_to_boot(bootinfo):
	"""boot_session: tell Desk (public/js/manager_app.js) to open Field Service in the manager app
	for this user: any manager (ManagerLanding.field_service_opens_app); never set otherwise."""
	if ManagerLanding().field_service_opens_app():
		bootinfo.fieldpro_manager_app = "/manage"
