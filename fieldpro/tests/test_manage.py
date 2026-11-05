"""The manager's Vue app (/manage): its API (services/dispatch.py) and the page that serves it.

Managers only, the same counts as the Desk workspace, and the workflow's rules on every change.
"""

import json
import os
import tempfile

import frappe
from frappe.desk.doctype.number_card.number_card import get_result
from frappe.utils import add_days, today

from fieldpro.access import AccessProfile
from fieldpro.api.errors import Forbidden, Invalid, InvalidTransition
from fieldpro.api.v1 import manage as endpoints
from fieldpro.services.dispatch import (
	DASHBOARD_CARDS,
	CustomerPicker,
	Dispatcher,
	DispatchOverview,
	JobQueue,
	TeamLoad,
)
from fieldpro.services.visits import VisitService
from fieldpro.tests import factories
from fieldpro.tests.base import FieldproTestCase
from fieldpro.www import manage as page


class ManageTestCase(FieldproTestCase):
	def as_manager(self, fn):
		return factories.as_user(self.manager, fn)

	def state(self, job: str) -> str:
		return frappe.db.get_value("Service Job", job, "workflow_state")

	def start(self, job: str, tech_email: str) -> None:
		factories.as_user(tech_email, lambda: VisitService(AccessProfile(tech_email)).start(job))


class TestOnlyManagers(ManageTestCase):
	def test_technicians_and_customers_are_refused(self):
		calls = [
			DispatchOverview,
			JobQueue,
			Dispatcher,
			TeamLoad,
			CustomerPicker,
		]
		for user in (self.tech_a_user, self.cust_x_user):
			for make in calls:
				with self.assertRaises(Forbidden, msg=f"{user} {make.__name__}"):
					factories.as_user(user, make)

	def test_the_endpoint_answers_403_in_the_one_error_format(self):
		def call():
			frappe.local.response = frappe._dict()
			endpoints.overview()
			return frappe.local.response

		response = factories.as_user(self.tech_a_user, call)
		self.assertEqual(response.http_status_code, 403)
		self.assertEqual(response["error"]["code"], "forbidden")


class TestOverview(ManageTestCase):
	def test_cards_count_what_the_workspace_cards_count(self):
		factories.job(self.cust_x)

		def both():
			ours = {c["label"]: c["value"] for c in DispatchOverview().cards()}
			desk = {}
			for name in DASHBOARD_CARDS:
				card = frappe.get_doc("Number Card", name)
				desk[name] = get_result(card.as_json(), card.filters_json)
			return ours, desk

		ours, desk = self.as_manager(both)
		self.assertEqual(ours, desk)
		self.assertGreaterEqual(ours["Waiting for a Technician"], 1)

	def test_attention_lists_unassigned_and_overdue_jobs(self):
		booked = factories.job(self.cust_x)
		late = factories.job(self.cust_x, technician_name=self.tech_a)
		frappe.db.set_value("Service Job", late, "scheduled_date", add_days(today(), -3))
		# The lists are short; push these two to the front by making them the oldest.
		frappe.db.set_value("Service Job", booked, "creation", "2000-01-01")

		attention = self.as_manager(lambda: DispatchOverview().attention())
		self.assertIn(booked, [j["id"] for j in attention["unassigned"]])
		self.assertIn(late, [j["id"] for j in attention["overdue"]])


class TestJobQueue(ManageTestCase):
	def test_the_board_follows_the_workflow_and_leaves_out_cancelled_jobs(self):
		booked = factories.job(self.cust_x)
		cancelled = factories.job(self.cust_x)
		self.as_manager(lambda: Dispatcher().act(cancelled, "Cancel"))

		board = self.as_manager(lambda: JobQueue().board())
		statuses = [c["status"] for c in board]
		self.assertEqual(statuses[:3], ["Booked", "Assigned", "In Progress"])
		self.assertNotIn("Cancelled", statuses)
		self.assertIn("Done", statuses)
		ids = {j["id"] for c in board for j in c["jobs"]}
		self.assertIn(booked, ids)
		self.assertNotIn(cancelled, ids)

	def test_the_list_filters_by_status_technician_and_search(self):
		assigned = factories.job(self.cust_y, technician_name=self.tech_b)
		booked = factories.job(self.cust_y)
		customer_name = frappe.db.get_value("Customer", self.cust_y, "customer_name")

		def ids(**filters):
			return [r.name for r in JobQueue().page(**filters, limit=100).rows]

		by_tech = self.as_manager(lambda: ids(technician=self.tech_b))
		self.assertIn(assigned, by_tech)
		self.assertNotIn(booked, by_tech)
		self.assertNotIn(assigned, self.as_manager(lambda: ids(status="Booked")))
		found = self.as_manager(lambda: ids(search=customer_name))
		self.assertEqual(set(found), {assigned, booked})
		self.assertEqual(self.as_manager(lambda: ids(search="no job has this text zq")), [])


class TestDispatcher(ManageTestCase):
	def test_booking_with_a_technician_assigns_the_job(self):
		name = self.as_manager(
			lambda: Dispatcher().book(customer=self.cust_x, issue="Fridge noisy", technician=self.tech_a)
		)
		job = frappe.get_doc("Service Job", name)
		self.assertEqual((job.workflow_state, job.technician, job.source), ("Assigned", self.tech_a, "Desk"))

	def test_booking_needs_a_real_customer(self):
		for customer in (None, "No Such Customer zq"):
			with self.assertRaises(Invalid):
				self.as_manager(lambda: Dispatcher().book(customer=customer, issue="x"))

	def test_assign_moves_a_booked_job_and_sets_the_date(self):
		job = factories.job(self.cust_x)
		friday = add_days(today(), 3)
		self.as_manager(lambda: Dispatcher().assign(job, self.tech_a, friday))
		row = frappe.db.get_value("Service Job", job, ["workflow_state", "technician", "scheduled_date"])
		self.assertEqual((row[0], row[1], str(row[2])), ("Assigned", self.tech_a, str(friday)))

	def test_an_assigned_job_can_go_to_someone_else_before_the_work_starts(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		self.as_manager(lambda: Dispatcher().assign(job, self.tech_b))
		self.assertEqual(frappe.db.get_value("Service Job", job, "technician"), self.tech_b)
		self.assertEqual(self.state(job), "Assigned")

	def test_a_started_job_keeps_its_technician(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		self.start(job, self.tech_a_user)
		with self.assertRaises(InvalidTransition):
			self.as_manager(lambda: Dispatcher().assign(job, self.tech_b))

	def test_assign_refuses_a_past_date_and_an_inactive_technician(self):
		job = factories.job(self.cust_x)
		with self.assertRaises(Invalid):
			self.as_manager(lambda: Dispatcher().assign(job, self.tech_a, add_days(today(), -1)))
		frappe.db.set_value("Technician", self.tech_b, "is_active", 0)
		try:
			with self.assertRaises(Invalid):
				self.as_manager(lambda: Dispatcher().assign(job, self.tech_b))
		finally:
			frappe.db.set_value("Technician", self.tech_b, "is_active", 1)
		self.assertEqual(self.state(job), "Booked")

	def test_update_changes_only_the_editable_fields(self):
		job = factories.job(self.cust_x)
		self.as_manager(lambda: Dispatcher().update(job, {"priority": "Urgent", "issue": " Lift stuck "}))
		self.assertEqual(frappe.db.get_value("Service Job", job, "priority"), "Urgent")
		with self.assertRaises(Invalid):
			self.as_manager(lambda: Dispatcher().update(job, {"payment_status": "Paid"}))
		with self.assertRaises(Invalid):
			self.as_manager(lambda: Dispatcher().update(job, {"issue": "  "}))

	def test_a_large_estimate_makes_the_job_need_approval(self):
		job = factories.job(self.cust_x)
		self.as_manager(lambda: Dispatcher().update(job, {"estimated_value": "1000000"}))
		self.assertEqual(frappe.db.get_value("Service Job", job, "needs_approval"), 1)

	def test_actions_follow_the_workflow(self):
		job = factories.job(self.cust_x)
		with self.assertRaises(InvalidTransition):
			self.as_manager(lambda: Dispatcher().act(job, "Approve"))
		self.as_manager(lambda: Dispatcher().act(job, "Cancel"))
		self.assertEqual(self.state(job), "Cancelled")

	def test_detail_has_the_manager_fields(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		detail = self.as_manager(lambda: Dispatcher().detail(job))
		self.assertEqual(detail["id"], job)
		self.assertIn("Cancel", [a["action"] for a in detail["actions"]])
		for key in ("estimated_value_raw", "signature_url", "created_at", "last_activity_at"):
			self.assertIn(key, detail)


class TestTeamAndCustomers(ManageTestCase):
	def test_technicians_show_their_open_work(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		frappe.db.set_value("Service Job", job, "scheduled_date", today())
		rows = {r["id"]: r for r in self.as_manager(lambda: TeamLoad().technicians())}
		self.assertGreaterEqual(rows[self.tech_a]["open_jobs"], 1)
		self.assertGreaterEqual(rows[self.tech_a]["today"], 1)
		self.assertEqual(set(rows[self.tech_a]["week"]), {"jobs_done", "visits", "hours"})

	def test_customers_are_found_by_name(self):
		name = frappe.db.get_value("Customer", self.cust_x, "customer_name")
		found = self.as_manager(lambda: CustomerPicker().search(name))
		self.assertEqual([c["id"] for c in found], [self.cust_x])


class TestPage(ManageTestCase):
	def context_for(self, user: str):
		def build():
			context = frappe._dict()
			page.get_context(context)
			return context

		return factories.as_user(user, build)

	def test_a_guest_is_sent_to_sign_in_and_back(self):
		previous = getattr(frappe.local, "request", None)
		frappe.local.request = frappe._dict(path="/manage/jobs/JOB-1")
		try:
			with self.assertRaises(frappe.Redirect) as caught:
				self.context_for("Guest")
		finally:
			frappe.local.request = previous
		self.assertEqual(caught.exception.http_status_code, 302)
		self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=%2Fmanage%2Fjobs%2FJOB-1")

	def test_only_managers_get_the_page(self):
		with self.assertRaises(frappe.PermissionError):
			self.context_for(self.tech_a_user)
		context = self.context_for(self.manager)
		boot = json.loads(context.boot)
		self.assertEqual(boot["user"], self.manager)
		self.assertTrue(context.csrf_token)

	def test_the_boot_cannot_close_the_script_tag(self):
		frappe.db.set_value("User", self.manager, "first_name", "</script><b>")
		frappe.local.fullnames = {}  # get_fullname caches names for the request
		try:
			context = self.context_for(self.manager)
		finally:
			frappe.db.set_value("User", self.manager, "first_name", "Test")
			frappe.local.fullnames = {}
		self.assertNotIn("</script>", context.boot)

	def test_assets_come_from_the_vite_manifest(self):
		manifest = {"src/main.js": {"file": "assets/main-abc.js", "css": ["assets/main-def.css"]}}
		with tempfile.TemporaryDirectory() as folder:
			path = os.path.join(folder, "manifest.json")
			self.assertEqual(page.ViteAssets(path).for_entry(page.ENTRY), {"script": None, "styles": []})
			with open(path, "w") as f:
				json.dump(manifest, f)
			assets = page.ViteAssets(path).for_entry(page.ENTRY)
		self.assertEqual(assets["script"], "/assets/fieldpro/manage/assets/main-abc.js")
		self.assertEqual(assets["styles"], ["/assets/fieldpro/manage/assets/main-def.css"])
