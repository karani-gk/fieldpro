"""Where a field manager lands: the Vue app at /manage instead of ERPNext Desk.

A Desk page the manager app replaces (the Desk home, the Field Service workspace, the job list,
board and form, the technicians list) sends a field manager to the matching /manage screen.
Everything else in Desk (invoices, stock, reports) opens as usual, so links from the app to an
invoice still work.

The way back to Desk: any Desk URL with ?desk=1 sets a browser-session cookie, and while it is
there nothing is redirected. Opening /manage again removes it. System Managers are never
redirected: they run the whole system from Desk.
"""

import re
from urllib.parse import quote

from fieldpro.access import AccessProfile
from fieldpro.settings import AppSettings

DESK_CHOICE_COOKIE = "fieldpro_desk"
STAY_IN_DESK_PARAM = "desk"
FIELD_MANAGER = "Field Manager"

# Desk path (after /desk or /app) to the /manage screen that replaces it. First match wins.
ROUTES = (
	(re.compile(r"^/?$"), lambda m: "/manage"),
	(re.compile(r"^/field-service/?$"), lambda m: "/manage"),
	(re.compile(r"^/service-job/view/kanban(/.*)?$"), lambda m: "/manage/board"),
	(re.compile(r"^/service-job(/view/[^/]+(/.*)?)?/?$"), lambda m: "/manage/jobs"),
	(re.compile(r"^/service-job/new(-[^/]*)?/?$"), lambda m: "/manage/jobs/new"),
	(re.compile(r"^/service-job/([^/]+)/?$"), lambda m: "/manage/jobs/" + quote(m.group(1))),
	(re.compile(r"^/technician/?$"), lambda m: "/manage/team"),
)
DESK_PREFIX = re.compile(r"^/(desk|app)(?=/|$)")


class ManagerLanding:
	def __init__(self, profile: AccessProfile | None = None, settings: AppSettings | None = None):
		self.profile = profile or AccessProfile()
		self.settings = settings or AppSettings()

	def applies(self) -> bool:
		"""Field managers only: not System Managers or Administrator, and only while the setting is on."""
		if not self.settings.open_manager_app:
			return False
		if self.profile.user in ("Administrator", "Guest"):
			return False
		roles = self.profile.roles
		return FIELD_MANAGER in roles and "System Manager" not in roles

	def field_service_opens_app(self) -> bool:
		"""Opening Field Service from inside Desk (its icon, sidebar or search) goes to the app for
		every manager, Administrator and System Managers included: that click asks for Field
		Service, and the app is Field Service. Unlike applies(), which also moves page loads and
		sign-ins, this leaves the rest of Desk alone for System Managers."""
		return self.settings.open_manager_app and self.profile.is_manager

	@staticmethod
	def target(path: str) -> str | None:
		"""The /manage screen for a Desk path, or None when the manager app has no such screen."""
		prefix = DESK_PREFIX.match(path or "")
		if not prefix:
			return None
		rest = path[prefix.end() :]
		for pattern, to in ROUTES:
			match = pattern.match(rest)
			if match:
				return to(match)
		return None
