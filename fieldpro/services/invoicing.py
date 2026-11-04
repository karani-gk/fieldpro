"""An invoice for every finished job, made in the background and safe to run twice.

A queued job can run twice (a retry after a timeout, two workers, someone re-queuing it). So
create_for_job locks the job row, then checks whether an invoice already exists before making
one. Running it ten times makes one invoice.

The invoice is a draft: accounts reviews and submits it. On submit, update_stock takes the
parts out of the technician's van warehouse.
"""

import frappe
from frappe import _
from frappe.utils import flt, today

from fieldpro.services.job_rules import DONE
from fieldpro.settings import AppSettings


class InvoiceService:
	def __init__(self, settings: AppSettings | None = None):
		self.settings = settings or AppSettings()

	def create_for_job(self, job_name: str) -> str | None:
		job = frappe.get_doc("Service Job", job_name, for_update=True)
		if job.workflow_state != DONE:
			return None
		if job.sales_invoice:
			return job.sales_invoice
		existing = frappe.db.get_value(
			"Sales Invoice", {"service_job": job.name, "docstatus": ["<", 2]}, "name"
		)
		invoice = existing or self._make(job)
		frappe.db.set_value("Service Job", job.name, "sales_invoice", invoice, update_modified=False)
		if not existing:
			from fieldpro.services.partner_webhooks import PartnerWebhooks

			PartnerWebhooks().queue(
				"invoice.created",
				"Sales Invoice",
				invoice,
				{"invoice": invoice, "job": job.name, "customer": job.customer},
			)
		return invoice

	def _make(self, job) -> str:
		invoice = frappe.new_doc("Sales Invoice")
		invoice.update(
			{
				"company": self.settings.company,
				"customer": job.customer,
				"posting_date": today(),
				"service_job": job.name,
				"technician": job.technician,
				"update_stock": 1,
				"remarks": _("Service job {0}: {1}").format(job.name, job.issue),
			}
		)
		if flt(job.total_hours) and self.settings.labour_item:
			invoice.append(
				"items",
				{
					"item_code": self.settings.labour_item,
					"qty": flt(job.total_hours, 2),
					"rate": self.settings.labour_rate,
					"description": _("Labour: {0} hours").format(flt(job.total_hours, 2)),
				},
			)
		for part in self._parts(job.name):
			invoice.append(
				"items",
				{
					"item_code": part.item_code,
					"qty": part.qty,
					"rate": part.rate,
					"warehouse": part.warehouse,
				},
			)
		if not invoice.items:
			frappe.throw(_("Job {0} has no hours or parts to invoice.").format(job.name))
		invoice.set_missing_values()
		invoice.flags.ignore_permissions = True
		invoice.insert()
		return invoice.name

	@staticmethod
	def _parts(job: str):
		return frappe.db.sql(
			"""
			select p.item_code, p.qty, p.rate, p.warehouse
			from `tabParts Used` p join `tabJob Visit` v on v.name = p.parent and p.parenttype = 'Job Visit'
			where v.service_job = %s and v.status = 'Closed'
			order by v.started_at, p.idx
			""",
			job,
			as_dict=True,
		)


def create_invoice_for_job(job: str) -> None:
	"""Background job entry point (job_events.py).

	A queued job runs as the user who queued it - often the customer who accepted the work. An
	invoice is the company's work, not the customer's, so it is made with the system's rights."""
	frappe.set_user("Administrator")
	InvoiceService().create_for_job(job)
