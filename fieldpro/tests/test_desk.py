"""The Field Service desk: the icon on the Desk home, its workspace, cards, charts and Job Board.

They ship as standard files (desktop_icon/, workspace_sidebar/, fieldpro/workspace/, number_card/,
dashboard_chart/) that install and migrate sync, plus the Job Board made in code. These tests
check they arrived, that every filter names a state the workflow really has (a renamed state
would otherwise leave a card silently counting nothing), and who gets the icon.
"""

import json

import frappe
from frappe.boot import get_sidebar_items
from frappe.desk.desktop import get_workspaces
from frappe.desk.doctype.desktop_icon.desktop_icon import clear_desktop_icons_cache, get_desktop_icons
from frappe.desk.doctype.number_card.number_card import get_result

from fieldpro.services.job_board import BOARD_NAME, JobBoard
from fieldpro.tests import factories
from fieldpro.tests.base import FieldproTestCase

DESK = "Field Service"
CARDS = [
	"Jobs Booked Today",
	"Waiting for a Technician",
	"Jobs In Progress",
	"Waiting for Approval",
	"Done This Week",
	"Done but Not Invoiced",
]
CHARTS = ["Jobs Booked per Day", "Jobs by Status", "Open Jobs per Technician"]


def workflow_states() -> set[str]:
	return {row.state for row in frappe.get_doc("Workflow", "Service Job").states}


def states_in(filters: list) -> set[str]:
	"""The workflow_state values a list of [doctype, field, operator, value] filters names."""
	found = set()
	for _doctype, field, _operator, value in filters:
		if field == "workflow_state":
			found.update(value if isinstance(value, list) else [value])
	return found


class TestFieldServiceDesk(FieldproTestCase):
	def test_the_icon_opens_the_field_service_sidebar(self):
		icon = frappe.get_doc("Desktop Icon", DESK)
		self.assertEqual((icon.app, icon.standard, icon.hidden), ("fieldpro", 1, 0))
		self.assertEqual((icon.link_type, icon.link_to), ("Workspace Sidebar", DESK))
		sidebar = frappe.get_doc("Workspace Sidebar", DESK)
		self.assertIn((DESK, "Workspace"), [(i.link_to, i.link_type) for i in sidebar.items])

	def test_the_workspace_has_its_cards_charts_and_shortcuts(self):
		workspace = frappe.get_doc("Workspace", DESK)
		self.assertEqual({r.number_card_name for r in workspace.number_cards}, set(CARDS))
		self.assertEqual({r.chart_name for r in workspace.charts}, set(CHARTS))
		for name in CARDS:
			self.assertTrue(frappe.db.get_value("Number Card", name, "is_standard"), name)
		for name in CHARTS:
			self.assertTrue(frappe.db.get_value("Dashboard Chart", name, "is_standard"), name)
		board = next(s for s in workspace.shortcuts if s.doc_view == "Kanban")
		self.assertTrue(frappe.db.exists("Kanban Board", board.kanban_board))

	def test_every_filter_names_a_real_workflow_state(self):
		real = workflow_states()
		workspace = frappe.get_doc("Workspace", DESK)
		sources = [frappe.db.get_value("Number Card", n, "filters_json") for n in CARDS]
		sources += [frappe.db.get_value("Dashboard Chart", n, "filters_json") for n in CHARTS]
		sources += [s.stats_filter for s in workspace.shortcuts if s.stats_filter]
		named = set()
		for source in sources:
			named |= states_in(json.loads(source or "[]"))
		self.assertTrue(named, "no filter names a state: the test would prove nothing")
		self.assertLessEqual(named, real)

	def test_the_job_board_has_a_column_for_every_state(self):
		board = frappe.get_doc("Kanban Board", BOARD_NAME)
		self.assertEqual(board.field_name, "workflow_state")
		self.assertEqual({c.column_name for c in board.columns}, workflow_states())

	def test_a_card_counts_the_jobs_in_its_state(self):
		before = self.count("Waiting for a Technician")
		factories.job(self.cust_x, assign=False)
		self.assertEqual(self.count("Waiting for a Technician"), before + 1)

	def test_creating_the_board_again_keeps_a_managers_changes(self):
		frappe.db.set_value(
			"Kanban Board Column", {"parent": BOARD_NAME, "column_name": "Booked"}, "indicator", "Pink"
		)
		self.assertFalse(JobBoard().ensure())
		self.assertEqual(
			frappe.db.get_value(
				"Kanban Board Column", {"parent": BOARD_NAME, "column_name": "Booked"}, "indicator"
			),
			"Pink",
		)

	def test_a_missing_board_is_created(self):
		frappe.delete_doc("Kanban Board", BOARD_NAME, force=True)
		self.assertTrue(JobBoard().ensure())
		self.assertTrue(frappe.db.exists("Kanban Board", BOARD_NAME))

	def test_a_manager_gets_the_icon(self):
		self.assertIn(DESK, self.icons_for(self.manager))

	def test_a_desk_user_outside_field_service_does_not(self):
		accountant = factories.user(["Accounts User"], website=False)
		icons = self.icons_for(accountant)
		self.assertTrue(icons, "an accountant should still see the Accounting icons")
		self.assertNotIn(DESK, icons)

	def count(self, card: str) -> int:
		return get_result(frappe.get_doc("Number Card", card).as_json(), None)

	def icons_for(self, user: str) -> set[str]:
		"""The Desk home icons, worked out the way the boot does it for this user."""

		def labels():
			clear_desktop_icons_cache(user)
			pages = [page.name for page in get_workspaces()["pages"]]
			boot = frappe._dict(workspace_sidebar_item=get_sidebar_items(pages))
			return {icon.label for icon in get_desktop_icons(user, bootinfo=boot)}

		return factories.as_user(user, labels)
