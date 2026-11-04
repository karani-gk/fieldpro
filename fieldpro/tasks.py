"""Scheduled work (hooks.py scheduler_events). Each task is safe to run twice: it reads the
current state and sends what is due, so a rerun after a crash repeats at most one message."""

import frappe
from frappe.utils import add_days, today

from fieldpro.services.job_rules import CLOSED_STATES
from fieldpro.services.push import PushMessage, PushService
from fieldpro.services.reports import performance


def remind_tomorrows_jobs() -> None:
	tomorrow = add_days(today(), 1)
	jobs = frappe.get_all(
		"Service Job",
		filters={
			"scheduled_date": tomorrow,
			"workflow_state": ["not in", list(CLOSED_STATES)],
			"technician_user": ["is", "set"],
		},
		fields=["technician_user", "count(name) as jobs"],
		group_by="technician_user",
	)
	push = PushService()
	for row in jobs:
		push.notify_user(
			row.technician_user,
			PushMessage(
				"Tomorrow",
				f"You have {row.jobs} job{'s' if row.jobs != 1 else ''} tomorrow.",
				{"screen": "today"},
			),
		)


def send_daily_summary() -> None:
	"""Yesterday's numbers to every Field Manager, as a Desk notification."""
	yesterday = add_days(today(), -1)
	rows = performance(yesterday, yesterday)
	if not rows:
		return
	lines = "".join(
		f"<li>{r.technician_name}: {r.visits} visits, {r.hours:.1f} hours, {r.jobs_done} done</li>"
		for r in rows
	)
	managers = frappe.get_all(
		"Has Role", filters={"role": "Field Manager", "parenttype": "User"}, pluck="parent"
	)
	for user in set(managers):
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"type": "Alert",
				"subject": f"Field work on {yesterday}",
				"email_content": f"<ul>{lines}</ul>",
			}
		).insert(ignore_permissions=True)


def invoice_finished_jobs() -> None:
	"""The safety net under job_events: a queued invoice job can be lost (redis restarted, a worker
	killed). Every hour, any Done job without an invoice gets one. create_for_job is safe to run
	twice, so a job that was only slow is not invoiced again."""
	from fieldpro.services.invoicing import InvoiceService

	service = InvoiceService()
	for job in frappe.get_all(
		"Service Job", filters={"workflow_state": "Done", "sales_invoice": ["is", "not set"]}, pluck="name"
	):
		try:
			service.create_for_job(job)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"fieldpro: could not invoice {job}")
