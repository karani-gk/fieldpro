"""The manager's Vue app (/manage). Managers only: each service class refuses anyone else.

Reads are GET and changes are POST, so Frappe checks the CSRF token on every change made from
the browser session.
"""

import frappe

from fieldpro.api import shapes
from fieldpro.api.endpoint import api, ok
from fieldpro.api.pagination import page_size
from fieldpro.services.dispatch import (
	CustomerPicker,
	Dispatcher,
	DispatchOverview,
	JobQueue,
	TeamLoad,
)


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
):
	"""Every job, newest first, filtered. q searches the job id, issue, customer and technician."""
	page = JobQueue().page(
		status=status,
		technician=technician,
		priority=priority,
		search=q,
		cursor=cursor,
		limit=page_size(limit),
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
