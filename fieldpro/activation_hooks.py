"""Sign-in gates for activation (hooks.py). The rule itself is in services/activation.py."""

import frappe

from fieldpro.services.activation import Activation, not_activated_message


def refuse_sign_in(login_manager=None):
	"""on_login: runs for every sign-in (password, social, login_as), but not for API tokens.
	Frappe's login page shows its own "Invalid Login" for any error, so people are sent to
	/activate before they reach it (redirect_login_page). A Frappe error, not an API one: this runs
	inside Frappe's own login, which turns any other exception into a 500."""
	if not Activation().is_active():
		frappe.throw(not_activated_message(), frappe.AuthenticationError)


def redirect_login_page(context):
	"""update_website_context: on an installation that is not activated, /login goes to /activate."""
	request = getattr(frappe.local, "request", None)
	if request and request.path.rstrip("/") == "/login" and not Activation().is_active():
		frappe.local.flags.redirect_location = "/activate"
		# 302, not Frappe's default 301: browsers keep a 301 and would skip /login after activation.
		raise frappe.Redirect(302)
