"""One user can never reach another's data: the most important tests in the app."""

import frappe

from fieldpro.access import AccessProfile
from fieldpro.services.jobs import JobService
from fieldpro.tests import factories
from fieldpro.tests.base import FieldproTestCase


class TestRowLevelSecurity(FieldproTestCase):
	def setUp(self):
		self.job_ax = factories.job(self.cust_x, technician_name=self.tech_a)
		self.job_by = factories.job(self.cust_y, technician_name=self.tech_b)

	def visible(self, user):
		return set(factories.as_user(user, lambda: frappe.get_list("Service Job", pluck="name")))

	def test_a_technician_lists_only_their_own_jobs(self):
		seen = self.visible(self.tech_a_user)
		self.assertIn(self.job_ax, seen)
		self.assertNotIn(self.job_by, seen)

	def test_a_customer_lists_only_their_company_jobs(self):
		seen = self.visible(self.cust_y_user)
		self.assertIn(self.job_by, seen)
		self.assertNotIn(self.job_ax, seen)

	def test_reading_someone_elses_job_is_refused(self):
		doc = frappe.get_doc("Service Job", self.job_by)
		self.assertFalse(frappe.has_permission("Service Job", "read", doc, user=self.tech_a_user))
		self.assertFalse(frappe.has_permission("Service Job", "read", doc, user=self.cust_x_user))

	def test_the_api_answers_not_found_for_someone_elses_job(self):
		from fieldpro.api.errors import NotFound

		self.assertRaises(
			NotFound, factories.as_user, self.cust_x_user, lambda: JobService().get(self.job_by)
		)

	def test_a_manager_sees_everything(self):
		seen = self.visible(self.manager)
		self.assertTrue({self.job_ax, self.job_by} <= seen)

	def test_visits_follow_the_same_rule(self):
		factories.finished_visit(self.job_ax, self.tech_a_user)
		visits = factories.as_user(
			self.tech_b_user, lambda: frappe.get_list("Job Visit", filters={"service_job": self.job_ax})
		)
		self.assertEqual(visits, [])


class TestEditGuard(FieldproTestCase):
	def test_a_customer_cannot_change_the_price_of_their_job(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)

		def cheat():
			doc = frappe.get_doc("Service Job", job)
			doc.estimated_value = 1
			doc.save()

		self.assertRaises(frappe.PermissionError, factories.as_user, self.cust_x_user, cheat)

	def test_a_customer_books_only_for_their_own_company(self):
		def book():
			return JobService(AccessProfile(self.cust_x_user)).book(issue="Leak", customer=self.cust_y)

		self.assertRaises(frappe.PermissionError, factories.as_user, self.cust_x_user, book)

	def test_a_customer_cannot_assign_a_technician_on_booking(self):
		def book():
			frappe.get_doc(
				{"doctype": "Service Job", "customer": self.cust_x, "issue": "x", "technician": self.tech_a}
			).insert()

		self.assertRaises(frappe.PermissionError, factories.as_user, self.cust_x_user, book)

	def test_a_technician_cannot_book_jobs(self):
		def book():
			frappe.get_doc({"doctype": "Service Job", "customer": self.cust_x, "issue": "x"}).insert()

		self.assertRaises(frappe.PermissionError, factories.as_user, self.tech_a_user, book)

	def test_a_booking_starts_in_booked_from_the_portal(self):
		doc = factories.as_user(
			self.cust_x_user, lambda: JobService(AccessProfile(self.cust_x_user)).book(issue="Fridge warm")
		)
		self.assertEqual((doc.workflow_state, doc.source, doc.customer), ("Booked", "Portal", self.cust_x))
