"""The manager app's invoices screen: what the jobs have billed, what is still owed, and the
finished jobs that have no invoice yet.

Invoices are ERPNext's Sales Invoices, so ERPNext's own permissions decide who sees and submits
them: a manager without an accounts role (Accounts User) is told so instead of being let past
them. Making a missing invoice reuses InvoiceService, the same code the background job runs, so
a draft made from this screen is the draft the job would have got.
"""

import frappe
from frappe import _
from frappe.utils import flt

from fieldpro.access import AccessProfile
from fieldpro.api import shapes
from fieldpro.api.errors import Forbidden, Invalid, InvalidTransition
from fieldpro.api.pagination import Page, fetch_page
from fieldpro.services.dispatch import ManagerOnly
from fieldpro.services.invoicing import InvoiceService
from fieldpro.services.job_rules import DONE
from fieldpro.services.jobs import JobService
from fieldpro.settings import AppSettings

INVOICE_FIELDS = [
	"name",
	"customer",
	"customer_name",
	"service_job",
	"posting_date",
	"due_date",
	"status",
	"docstatus",
	"grand_total",
	"outstanding_amount",
	"currency",
]
# The screen's status tabs, each as Sales Invoice filters. ERPNext keeps `status` current (it
# turns Unpaid into Overdue overnight), so the tabs read it rather than recomputing it.
STATUS_FILTERS = {
	"Draft": [["docstatus", "=", 0]],
	"Unpaid": [["docstatus", "=", 1], ["outstanding_amount", ">", 0]],
	"Overdue": [["docstatus", "=", 1], ["status", "in", ["Overdue", "Overdue and Discounted"]]],
	"Paid": [["docstatus", "=", 1], ["status", "=", "Paid"]],
	"Cancelled": [["docstatus", "=", 2]],
}
UNINVOICED_LIMIT = 20
SEARCH_LIMIT = 500


class InvoiceDesk(ManagerOnly):
	def __init__(
		self,
		profile: AccessProfile | None = None,
		invoicing: InvoiceService | None = None,
		settings: AppSettings | None = None,
	):
		super().__init__(profile)
		if not frappe.has_permission("Sales Invoice", "read", user=self.profile.user):
			raise Forbidden(_("Invoices need an accounts role (Accounts User). Ask your administrator."))
		self.invoicing = invoicing or InvoiceService()
		self.settings = settings or AppSettings()

	def page(
		self,
		*,
		status: str | None = None,
		customer: str | None = None,
		search: str | None = None,
		cursor: str | None = None,
		limit: int = 20,
	) -> Page:
		"""Invoices made from service jobs, newest first."""
		filters = [["Sales Invoice", "service_job", "is", "set"]]
		if status:
			if status not in STATUS_FILTERS:
				raise Invalid(_("Unknown invoice status {0}.").format(status), fields={"status": "invalid"})
			filters += [["Sales Invoice", *f] for f in STATUS_FILTERS[status]]
		if customer:
			filters.append(["Sales Invoice", "customer", "=", customer])
		if (search or "").strip():
			# fetch_page uses or_filters for its cursor, so the search finds names first.
			filters.append(["Sales Invoice", "name", "in", self._matching(search.strip()) or [""]])
		return fetch_page(
			"Sales Invoice",
			fields=INVOICE_FIELDS,
			sort_field="creation",
			descending=True,
			filters=filters,
			cursor=cursor,
			limit=limit,
		)

	def summary(self) -> dict:
		"""The three totals at the top of the screen, and the jobs still waiting for an invoice."""
		return {
			"draft": self._total(STATUS_FILTERS["Draft"], "grand_total"),
			"unpaid": self._total(STATUS_FILTERS["Unpaid"], "outstanding_amount"),
			"overdue": self._total(STATUS_FILTERS["Overdue"], "outstanding_amount"),
			"uninvoiced_jobs": self._uninvoiced_jobs(),
		}

	def make_for_job(self, job: str) -> str:
		"""The job's draft invoice, made now instead of waiting for the background job."""
		doc = JobService(self.profile).get(job)
		if doc.workflow_state != DONE:
			raise InvalidTransition(
				_("Only a finished job is invoiced. This one is {0}.").format(doc.workflow_state),
				fields={"job": "not done"},
			)
		return self.invoicing.create_for_job(job)

	def submit(self, invoice: str) -> None:
		"""Submit a draft. ERPNext checks the submit permission and posts the stock and ledger."""
		doc = self._job_invoice(invoice)
		if doc.docstatus != 0:
			raise InvalidTransition(_("Invoice {0} is already submitted.").format(invoice))
		doc.submit()

	def row(self, invoice: str) -> dict:
		return shapes.invoice_summary(frappe.get_doc("Sales Invoice", invoice))

	def _job_invoice(self, invoice: str):
		"""A Sales Invoice made from a job: other invoices belong to Desk, not this app."""
		if not frappe.db.exists("Sales Invoice", invoice):
			raise Invalid(_("Invoice {0} not found.").format(invoice), fields={"invoice": "not found"})
		doc = frappe.get_doc("Sales Invoice", invoice)
		doc.check_permission("read")
		if not doc.service_job:
			raise Invalid(_("Invoice {0} is not from a service job.").format(invoice))
		return doc

	def _total(self, filters: list, amount_field: str) -> dict:
		rows = frappe.get_list(
			"Sales Invoice",
			fields=[{"COUNT": "name", "as": "count"}, {"SUM": amount_field, "as": "amount"}],
			filters=[["service_job", "is", "set"], *filters],
		)
		row = rows[0] if rows else {}
		return {
			"count": row.get("count") or 0,
			"amount": shapes.money(flt(row.get("amount")), self.settings.currency),
		}

	@staticmethod
	def _uninvoiced_jobs() -> list[dict]:
		rows = frappe.get_list(
			"Service Job",
			fields=shapes.JOB_LIST_FIELDS,
			filters=[["workflow_state", "=", DONE], ["sales_invoice", "is", "not set"]],
			order_by="signed_off_at asc",
			limit_page_length=UNINVOICED_LIMIT,
		)
		return [shapes.job_summary(r) for r in rows]

	@staticmethod
	def _matching(search: str) -> list[str]:
		like = f"%{search}%"
		return frappe.get_list(
			"Sales Invoice",
			or_filters=[
				["name", "like", like],
				["customer_name", "like", like],
				["service_job", "like", like],
			],
			filters=[["service_job", "is", "set"]],
			pluck="name",
			limit_page_length=SEARCH_LIMIT,
		)
