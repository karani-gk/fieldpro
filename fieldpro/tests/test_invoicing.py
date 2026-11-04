"""An invoice for every finished job, once."""

import frappe

from fieldpro.services.invoicing import InvoiceService
from fieldpro.services.job_flow import COMPLETE, SIGN_OFF, JobFlow
from fieldpro.tests import factories
from fieldpro.tests.base import FieldproTestCase


class TestInvoicing(FieldproTestCase):
	def done_job(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a, estimated=1000)
		factories.finished_visit(job, self.tech_a_user, hours=2, parts=((factories.PART, 3),))
		factories.as_user(self.tech_a_user, lambda: JobFlow().apply(job, COMPLETE))
		factories.as_user(
			self.tech_a_user,
			lambda: JobFlow().apply(job, SIGN_OFF, signature=factories.SIGNATURE, signed_by="X"),
		)
		return job

	def test_running_it_twice_makes_one_invoice(self):
		job = self.done_job()
		first = InvoiceService().create_for_job(job)
		second = InvoiceService().create_for_job(job)
		self.assertEqual(first, second)
		self.assertEqual(frappe.db.count("Sales Invoice", {"service_job": job}), 1)

	def test_the_invoice_bills_hours_and_parts_from_the_van(self):
		job = self.done_job()
		invoice = frappe.get_doc("Sales Invoice", InvoiceService().create_for_job(job))
		lines = {i.item_code: i for i in invoice.items}
		self.assertAlmostEqual(lines["SVC-LABOUR"].qty, 2, places=1)
		self.assertEqual(lines[factories.PART].qty, 3)
		self.assertTrue(lines[factories.PART].warehouse.startswith("Van "))
		self.assertEqual((invoice.service_job, invoice.technician, invoice.docstatus), (job, self.tech_a, 0))

	def test_an_unfinished_job_is_not_invoiced(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		self.assertIsNone(InvoiceService().create_for_job(job))
