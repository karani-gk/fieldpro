"""The technician's job lists: today, open, and finished (Done or Cancelled, latest first)."""

import frappe
from frappe.utils import add_to_date, now_datetime

from fieldpro.access import AccessProfile
from fieldpro.services.jobs import JobService
from fieldpro.tests import factories
from fieldpro.tests.base import FieldproTestCase


class TestTechnicianJobLists(FieldproTestCase):
	def ids(self, scope: str, user: str | None = None) -> list[str]:
		user = user or self.tech_a_user

		def run():
			return [
				r.name for r in JobService(AccessProfile(user)).technician_jobs(scope=scope, limit=100).rows
			]

		return factories.as_user(user, run)

	def finish(self, job: str, state: str, minutes_ago: int) -> None:
		# The list only reads the state and when the job last changed; how it got there is the
		# workflow's business, tested elsewhere.
		frappe.db.set_value(
			"Service Job",
			job,
			{"workflow_state": state, "modified": add_to_date(now_datetime(), minutes=-minutes_ago)},
			update_modified=False,
		)

	def test_finished_lists_my_done_and_cancelled_jobs_latest_first(self):
		open_job = factories.job(self.cust_x, technician_name=self.tech_a)
		done_earlier = factories.job(self.cust_x, technician_name=self.tech_a)
		cancelled_later = factories.job(self.cust_x, technician_name=self.tech_a)
		someone_elses = factories.job(self.cust_x, technician_name=self.tech_b)
		self.finish(done_earlier, "Done", minutes_ago=30)
		self.finish(cancelled_later, "Cancelled", minutes_ago=5)
		self.finish(someone_elses, "Done", minutes_ago=1)

		finished = self.ids("finished")
		self.assertEqual(finished[:2], [cancelled_later, done_earlier])
		self.assertNotIn(open_job, finished)
		self.assertNotIn(someone_elses, finished)
		self.assertIn(open_job, self.ids("open"))
		self.assertNotIn(done_earlier, self.ids("open"))
