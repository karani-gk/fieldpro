"""The server owns the job's state."""

import frappe

from fieldpro.api.errors import Invalid, InvalidTransition
from fieldpro.services.job_flow import ACCEPT, COMPLETE, REJECT, SIGN_OFF, JobFlow
from fieldpro.tests import factories
from fieldpro.tests.base import FieldproTestCase


class TestJobWorkflow(FieldproTestCase):
	def apply(self, user, job, action, **kw):
		return factories.as_user(user, lambda: JobFlow().apply(job, action, **kw))

	def test_completing_needs_a_finished_visit(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		self.assertRaises(InvalidTransition, self.apply, self.tech_a_user, job, COMPLETE)  # not started yet

	def test_a_small_job_goes_to_sign_off_and_a_big_one_to_approval(self):
		small = factories.job(self.cust_x, technician_name=self.tech_a, estimated=1000)
		big = factories.job(self.cust_x, technician_name=self.tech_a, estimated=10**7)
		for job in (small, big):
			factories.finished_visit(job, self.tech_a_user)
			self.apply(self.tech_a_user, job, COMPLETE)
		self.assertEqual(frappe.db.get_value("Service Job", small, "workflow_state"), "Awaiting Sign-off")
		self.assertEqual(frappe.db.get_value("Service Job", big, "workflow_state"), "Pending Approval")

	def test_only_a_manager_approves_a_big_job(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a, estimated=10**7)
		factories.finished_visit(job, self.tech_a_user)
		self.apply(self.tech_a_user, job, COMPLETE)
		self.assertRaises(InvalidTransition, self.apply, self.tech_a_user, job, "Approve")
		self.apply(self.manager, job, "Approve")
		self.assertEqual(frappe.db.get_value("Service Job", job, "workflow_state"), "Awaiting Sign-off")

	def awaiting_signoff(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a, estimated=1000)
		factories.finished_visit(job, self.tech_a_user)
		self.apply(self.tech_a_user, job, COMPLETE)
		return job

	def test_sign_off_on_site_needs_the_signature_and_a_name(self):
		job = self.awaiting_signoff()
		self.assertRaises(Invalid, self.apply, self.tech_a_user, job, SIGN_OFF)
		self.apply(self.tech_a_user, job, SIGN_OFF, signature=factories.SIGNATURE, signed_by="Jane")
		row = frappe.db.get_value(
			"Service Job", job, ["workflow_state", "signed_off_by", "customer_signoff"], as_dict=True
		)
		self.assertEqual((row.workflow_state, row.signed_off_by), ("Done", "Jane"))
		self.assertTrue(row.customer_signoff.startswith("/private/files/"))

	def test_the_customer_accepts_or_rejects_with_a_reason(self):
		job = self.awaiting_signoff()
		self.assertRaises(Invalid, self.apply, self.cust_x_user, job, REJECT)
		self.apply(self.cust_x_user, job, REJECT, reason="Still warm")
		self.assertEqual(frappe.db.get_value("Service Job", job, "workflow_state"), "Rework")
		job2 = self.awaiting_signoff()
		self.apply(self.cust_x_user, job2, ACCEPT)
		self.assertEqual(frappe.db.get_value("Service Job", job2, "workflow_state"), "Done")

	def test_a_state_cannot_be_written_directly(self):
		job = self.awaiting_signoff()

		def jump():
			doc = frappe.get_doc("Service Job", job)
			doc.workflow_state = "Done"
			doc.save()

		self.assertRaises(frappe.ValidationError, factories.as_user, self.tech_a_user, jump)

	def test_the_actions_shown_depend_on_who_asks(self):
		job = self.awaiting_signoff()

		def actions(user):
			return [
				t.action
				for t in factories.as_user(
					user, lambda: JobFlow().actions(frappe.get_doc("Service Job", job))
				)
			]

		self.assertEqual(actions(self.tech_a_user), [SIGN_OFF])
		self.assertEqual(sorted(actions(self.cust_x_user)), [ACCEPT, REJECT])
