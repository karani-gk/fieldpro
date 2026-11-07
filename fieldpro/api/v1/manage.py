"""The manager's Vue app (/manage). Managers only: each service class refuses anyone else.

Reads are GET and changes are POST, so Frappe checks the CSRF token on every change made from
the browser session.
"""

import frappe

from fieldpro.api import shapes
from fieldpro.api.endpoint import api, ok
from fieldpro.api.pagination import page_size
from fieldpro.services.customer_directory import CustomerDirectory
from fieldpro.services.dispatch import (
	CustomerPicker,
	Dispatcher,
	DispatchOverview,
	JobQueue,
	TeamLoad,
)
from fieldpro.services.invoice_desk import InvoiceDesk
from fieldpro.services.settings_desk import SettingsDesk


@api(methods=["GET"])
def overview():
	"""Dashboard numbers (the workspace's Number Cards) and the jobs that need a manager."""
	return ok(DispatchOverview().summary())


@api(methods=["GET"])
def board():
	"""Open jobs, and jobs done in the last week, in one column per workflow state."""
	return ok(JobQueue().board())


@api(methods=["GET"])
def jobs(
	status: str | None = None,
	technician: str | None = None,
	priority: str | None = None,
	q: str | None = None,
	cursor: str | None = None,
	limit: int | None = None,
	customer: str | None = None,
):
	"""Every job, newest first, filtered. q searches the job id, issue, customer and technician."""
	page = JobQueue().page(
		status=status,
		technician=technician,
		priority=priority,
		search=q,
		cursor=cursor,
		limit=page_size(limit),
		customer=customer,
	)
	return ok(
		[shapes.job_summary(r) for r in page.rows], next_cursor=page.next_cursor, has_more=page.has_more
	)


@api(methods=["GET"])
def job(job: str):
	return ok(Dispatcher().detail(job))


@api(methods=["POST"])
def book_job(
	customer: str,
	issue: str,
	description: str | None = None,
	site_address: str | None = None,
	contact_phone: str | None = None,
	preferred_date: str | None = None,
	technician: str | None = None,
):
	"""Book a job for a customer (source Desk). With a technician it is assigned at once."""
	dispatcher = Dispatcher()
	name = dispatcher.book(
		customer=customer,
		issue=issue,
		description=description,
		site_address=site_address,
		contact_phone=contact_phone,
		preferred_date=preferred_date,
		technician=technician,
	)
	return ok(dispatcher.detail(name))


@api(methods=["POST"])
def assign(job: str, technician: str, scheduled_date: str | None = None):
	dispatcher = Dispatcher()
	dispatcher.assign(job, technician, scheduled_date)
	return ok(dispatcher.detail(job))


@api(methods=["POST"])
def update_job(job: str, changes: dict | str):
	"""Edit the job's details: issue, description, priority, date, site, phone, estimate."""
	dispatcher = Dispatcher()
	dispatcher.update(job, frappe.parse_json(changes))
	return ok(dispatcher.detail(job))


@api(methods=["POST"])
def act(job: str, action: str, reason: str | None = None):
	"""A workflow action a manager may take now: Approve, Send Back or Cancel."""
	dispatcher = Dispatcher()
	dispatcher.act(job, action, reason)
	return ok(dispatcher.detail(job))


@api(methods=["GET"])
def technicians():
	return ok(TeamLoad().technicians())


@api(methods=["GET"])
def customers(q: str | None = None):
	return ok(CustomerPicker().search(q))


@api(methods=["GET"])
def customer_directory(q: str | None = None):
	"""Customers with their open jobs and, for managers who may read invoices, what they owe."""
	return ok(CustomerDirectory().search(q))


@api(methods=["GET"])
def invoices(
	status: str | None = None,
	customer: str | None = None,
	q: str | None = None,
	cursor: str | None = None,
	limit: int | None = None,
):
	"""Invoices made from jobs, newest first. status: Draft, Unpaid, Overdue, Paid or Cancelled."""
	page = InvoiceDesk().page(
		status=status, customer=customer, search=q, cursor=cursor, limit=page_size(limit)
	)
	return ok(
		[shapes.invoice_summary(r) for r in page.rows], next_cursor=page.next_cursor, has_more=page.has_more
	)


@api(methods=["GET"])
def invoice(invoice: str):
	"""One job invoice with its lines, taxes and totals."""
	return ok(InvoiceDesk().detail(invoice))


@api(methods=["GET"])
def invoice_summary():
	"""Draft, unpaid and overdue totals, and the finished jobs that have no invoice yet."""
	return ok(InvoiceDesk().summary())


@api(methods=["POST"])
def make_invoice(job: str):
	"""Make a finished job's draft invoice now, instead of waiting for the background job."""
	desk = InvoiceDesk()
	return ok(desk.row(desk.make_for_job(job)))


@api(methods=["POST"])
def submit_invoice(invoice: str):
	desk = InvoiceDesk()
	desk.submit(invoice)
	return ok(desk.row(invoice))


@api(methods=["GET"])
def settings():
	return ok(SettingsDesk().read())


@api(methods=["POST"])
def update_settings(changes: dict | str):
	"""Change the everyday settings. Secrets and activation stay in Desk."""
	desk = SettingsDesk()
	desk.update(frappe.parse_json(changes))
	return ok(desk.read())
