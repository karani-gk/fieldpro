"""Field managers land in the Vue app (services/manager_landing.py, landing_hooks.py), can choose
Desk instead, and everyone else's Desk is left alone."""

import frappe
from frappe.auth import CookieManager
from frappe.tests import UnitTestCase
from werkzeug.exceptions import HTTPException

from fieldpro import landing_hooks
from fieldpro.access import AccessProfile
from fieldpro.services.manager_landing import DESK_CHOICE_COOKIE, ManagerLanding
from fieldpro.settings import AppSettings
from fieldpro.tests import factories
from fieldpro.tests.base import FieldproTestCase


class TestDeskRoutes(UnitTestCase):
	def test_desk_pages_the_app_replaces(self):
		cases = {
			"/desk": "/manage",
			"/app/": "/manage",
			"/desk/field-service": "/manage",
			"/app/service-job": "/manage/jobs",
			"/desk/service-job/view/list": "/manage/jobs",
			"/desk/service-job/view/kanban/Job Board": "/manage/board",
			"/desk/service-job/new": "/manage/jobs/new",
			"/desk/service-job/new-service-job-abc123": "/manage/jobs/new",
			"/desk/service-job/JOB-2026-00001": "/manage/jobs/JOB-2026-00001",
			"/desk/technician": "/manage/team",
		}
		for path, target in cases.items():
			self.assertEqual(ManagerLanding.target(path), target, path)

	def test_other_pages_stay_in_desk(self):
		for path in (
			"/desk/sales-invoice/ACC-SINV-2026-00001",
			"/app/stock-entry",
			"/desk/query-report/Technician Performance",
			"/desk/technician/TECH-0001",
			"/desktop",
			"/manage",
			"/api/method/fieldpro.api.v1.manage.board",
		):
			self.assertIsNone(ManagerLanding.target(path), path)


class FakeRequest(frappe._dict):
	"""What the hook reads from Frappe's request."""


class TestManagerLanding(FieldproTestCase):
	def setUp(self):
		self.previous_request = getattr(frappe.local, "request", None)
		self.previous_cookies = getattr(frappe.local, "cookie_manager", None)
		frappe.local.cookie_manager = CookieManager()

	def tearDown(self):
		frappe.local.request = self.previous_request
		frappe.local.cookie_manager = self.previous_cookies
		super().tearDown()

	def visit(self, user: str, path: str, *, method="GET", args=None, cookies=None) -> str | None:
		"""Where the hook sends `user` for this request: a URL, or None to carry on."""
		frappe.local.request = FakeRequest(method=method, path=path, args=args or {}, cookies=cookies or {})
		try:
			factories.as_user(user, landing_hooks.send_managers_to_app)
		except HTTPException as redirect:
			self.assertEqual(redirect.response.status_code, 302)
			return redirect.response.headers["Location"]
		return None

	def test_a_field_manager_opening_desk_lands_in_the_app(self):
		self.assertEqual(self.visit(self.manager, "/desk"), "/manage")
		self.assertEqual(self.visit(self.manager, "/app/service-job/JOB-1"), "/manage/jobs/JOB-1")

	def test_desk_pages_the_app_lacks_still_open(self):
		self.assertIsNone(self.visit(self.manager, "/desk/sales-invoice/ACC-SINV-1"))

	def test_choosing_desk_keeps_the_manager_there_for_the_session(self):
		self.assertIsNone(self.visit(self.manager, "/desk/field-service", args={"desk": "1"}))
		cookie = frappe.local.cookie_manager.cookies[DESK_CHOICE_COOKIE]
		self.assertEqual(cookie["value"], "1")
		self.assertIsNone(cookie.get("expires"), "a browser-session cookie, gone when the browser closes")
		self.assertIsNone(self.visit(self.manager, "/desk", cookies={DESK_CHOICE_COOKIE: "1"}))

	def test_only_page_loads_are_redirected(self):
		self.assertIsNone(self.visit(self.manager, "/desk", method="POST"))

	def test_everyone_else_keeps_desk(self):
		system_manager = factories.user(["Field Manager", "System Manager"], website=False)
		accountant = factories.user(["Accounts User"], website=False)
		for user in ("Administrator", system_manager, accountant, self.tech_a_user, "Guest"):
			self.assertIsNone(self.visit(user, "/desk"), user)

	def test_the_setting_switches_it_off(self):
		settings = AppSettings(frappe._dict(keep_managers_in_desk=1))
		self.assertFalse(ManagerLanding(AccessProfile(self.manager), settings).applies())
		blank = AppSettings(frappe._dict(keep_managers_in_desk=0))
		self.assertTrue(ManagerLanding(AccessProfile(self.manager), blank).applies())

	def test_opening_the_app_again_forgets_the_desk_choice(self):
		from fieldpro.www import manage as page

		frappe.local.request = FakeRequest(method="GET", path="/manage", args={}, cookies={})
		factories.as_user(self.manager, lambda: page.get_context(frappe._dict()))
		self.assertIn(DESK_CHOICE_COOKIE, frappe.local.cookie_manager.to_delete)


class TestWayBackFromDesk(FieldproTestCase):
	def test_the_field_service_workspace_links_to_the_app(self):
		workspace = frappe.get_doc("Workspace", "Field Service")
		self.assertIn(("URL", "/manage"), [(s.type, s.url) for s in workspace.shortcuts])


class TestDeskChoiceEndsWithTheSession(FieldproTestCase):
	"""Choosing Desk lasts for one sign-in: signing in or out again brings back the app."""

	def test_signing_in_or_out_forgets_the_desk_choice(self):
		self.assertIn("fieldpro.landing_hooks.forget_desk_choice", frappe.get_hooks("on_login"))
		self.assertIn("fieldpro.landing_hooks.forget_desk_choice", frappe.get_hooks("on_logout"))
		previous = getattr(frappe.local, "cookie_manager", None)
		frappe.local.cookie_manager = CookieManager()
		try:
			landing_hooks.forget_desk_choice()
			self.assertIn(DESK_CHOICE_COOKIE, frappe.local.cookie_manager.to_delete)
		finally:
			frappe.local.cookie_manager = previous


class TestFieldServiceIconOpensTheApp(FieldproTestCase):
	"""Desk opens the Field Service workspace in the browser, so the boot tells it who goes to /manage."""

	def boot_for(self, user: str) -> frappe._dict:
		bootinfo = frappe._dict()
		factories.as_user(user, lambda: landing_hooks.add_manager_app_to_boot(bootinfo))
		return bootinfo

	def test_a_field_manager_is_sent_to_the_app(self):
		self.assertIn("fieldpro.landing_hooks.add_manager_app_to_boot", frappe.get_hooks("boot_session"))
		self.assertIn("/assets/fieldpro/js/manager_app.js", frappe.get_hooks("app_include_js"))
		self.assertEqual(self.boot_for(self.manager).fieldpro_manager_app, "/manage")

	def test_everyone_else_opens_the_workspace(self):
		system_manager = factories.user(["Field Manager", "System Manager"], website=False)
		accountant = factories.user(["Accounts User"], website=False)
		for user in ("Administrator", system_manager, accountant):
			self.assertNotIn("fieldpro_manager_app", self.boot_for(user), user)
