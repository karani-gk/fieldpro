"""Visits, parts and offline sync: nothing lost, nothing duplicated."""

import frappe
from frappe.utils import now_datetime

from fieldpro.access import AccessProfile
from fieldpro.api.errors import ApiError, Conflict
from fieldpro.services.job_flow import JobFlow
from fieldpro.services.sync import SyncService
from fieldpro.services.visits import VisitService
from fieldpro.tests import factories
from fieldpro.tests.base import FieldproTestCase
from fieldpro.utils import to_iso


class TestVisits(FieldproTestCase):
	def service(self):
		return VisitService(AccessProfile(self.tech_a_user))

	def test_starting_a_visit_moves_the_job_to_in_progress(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		factories.as_user(self.tech_a_user, lambda: self.service().start(job))
		self.assertEqual(frappe.db.get_value("Service Job", job, "workflow_state"), "In Progress")

	def test_one_open_visit_at_a_time(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		factories.as_user(self.tech_a_user, lambda: self.service().start(job))
		self.assertRaises(Conflict, factories.as_user, self.tech_a_user, lambda: self.service().start(job))

	def test_parts_are_priced_and_totals_reach_the_job(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		factories.finished_visit(job, self.tech_a_user, hours=2, parts=((factories.PART, 2),))
		row = frappe.db.get_value("Service Job", job, ["total_hours", "parts_total"], as_dict=True)
		self.assertAlmostEqual(row.total_hours, 2, places=1)
		self.assertEqual(row.parts_total, 2 * 650)

	def test_another_technician_cannot_record_on_the_job(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		other = VisitService(AccessProfile(self.tech_b_user))
		self.assertRaises(ApiError, factories.as_user, self.tech_b_user, lambda: other.start(job))


class TestOfflineSync(FieldproTestCase):
	def sync(self):
		return SyncService(AccessProfile(self.tech_a_user))

	def push(self, ops):
		return factories.as_user(self.tech_a_user, lambda: self.sync().push(ops))

	def ops(self, job):
		at = to_iso(now_datetime())
		visit_id = f"v-{factories.suffix()}"
		return [
			{"client_id": visit_id, "op": "start_visit", "job": job, "at": at},
			{
				"client_id": f"p-{factories.suffix()}",
				"op": "add_part",
				"visit_client_id": visit_id,
				"item_code": factories.PART,
				"qty": 1,
			},
			{
				"client_id": f"e-{factories.suffix()}",
				"op": "end_visit",
				"visit_client_id": visit_id,
				"at": at,
			},
		]

	def test_a_batch_sent_twice_is_applied_once(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		ops = self.ops(job)
		first = self.push(ops)
		second = self.push(ops)
		self.assertEqual([r["status"] for r in first], ["ok", "ok", "ok"])
		self.assertEqual([r["status"] for r in second], ["duplicate", "duplicate", "duplicate"])
		self.assertEqual(frappe.db.count("Job Visit", {"service_job": job}), 1)
		visit = frappe.db.get_value("Job Visit", {"service_job": job}, "name")
		self.assertEqual(frappe.db.count("Parts Used", {"parent": visit}), 1)

	def test_the_server_wins_when_the_job_was_cancelled_offline(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		factories.as_user(self.manager, lambda: JobFlow().apply(job, "Cancel"))
		result = self.push(self.ops(job)[:1])[0]
		self.assertEqual(result["status"], "conflict")
		self.assertEqual(result["server"]["status"], "Cancelled")

	def test_one_bad_operation_does_not_undo_the_others(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		ops = self.ops(job)
		ops.insert(
			1,
			{
				"client_id": "bad-1",
				"op": "add_part",
				"visit_client_id": ops[0]["client_id"],
				"item_code": "NO-SUCH-ITEM",
				"qty": 1,
			},
		)
		statuses = [r["status"] for r in self.push(ops)]
		self.assertEqual(statuses, ["ok", "error", "ok", "ok"])

	def test_pull_returns_only_what_changed_after_the_cursor(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		first = factories.as_user(self.tech_a_user, lambda: self.sync().pull())
		self.assertIn(job, [j["id"] for j in first["jobs"]])
		again = factories.as_user(self.tech_a_user, lambda: self.sync().pull(cursor=first["cursor"]))
		self.assertNotIn(job, [j["id"] for j in again["jobs"]])
		factories.finished_visit(job, self.tech_a_user)
		after = factories.as_user(self.tech_a_user, lambda: self.sync().pull(cursor=first["cursor"]))
		self.assertEqual([j["id"] for j in after["jobs"]], [job])
