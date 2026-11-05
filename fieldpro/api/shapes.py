"""Response shapes: what a job, a visit or an amount looks like to a client, in one place.

The shape is the API contract, not the DocType. Field names are the client's (`status`, not
`workflow_state`), dates are ISO 8601 (datetimes in UTC with Z), money is a string amount with
its currency (floats lose cents), and nothing internal leaks out. Adding a key is safe for
clients; renaming or removing one is a new API version.
"""

from frappe.utils import cstr, flt, getdate

from fieldpro.utils import to_iso

# The columns a list of jobs needs: summary() reads only these.
JOB_LIST_FIELDS = [
	"name",
	"issue",
	"customer",
	"customer_name",
	"workflow_state",
	"priority",
	"scheduled_date",
	"technician",
	"technician_name",
	"site_address",
	"modified",
]


def money(amount, currency: str | None) -> dict:
	return {"amount": f"{flt(amount):.2f}", "currency": currency or ""}


def date(value) -> str | None:
	return getdate(value).isoformat() if value else None


def job_summary(row) -> dict:
	return {
		"id": row.name,
		"issue": row.issue,
		"customer": {"id": row.customer, "name": row.customer_name},
		"status": row.workflow_state,
		"priority": row.priority,
		"scheduled_date": date(row.scheduled_date),
		"technician": {"id": row.technician, "name": row.technician_name} if row.technician else None,
		"site_address": cstr(row.site_address),
		"updated_at": to_iso(row.modified),
	}


def job_detail(doc, visits: list, actions: list) -> dict:
	return {
		**job_summary(doc),
		"description": cstr(doc.description),
		"contact_phone": cstr(doc.contact_phone),
		"source": doc.source,
		"estimated_value": money(doc.estimated_value, doc.currency),
		"needs_approval": bool(doc.needs_approval),
		"total_hours": flt(doc.total_hours, 2),
		"parts_total": money(doc.parts_total, doc.currency),
		"signed_off": {"by": doc.signed_off_by, "at": to_iso(doc.signed_off_at)}
		if doc.signed_off_by
		else None,
		"rejection_reason": doc.rejection_reason or None,
		"invoice": doc.sales_invoice or None,
		"payment_status": doc.payment_status,
		"visits": visits,
		"actions": actions,
	}


def visit(doc, photos: list | None = None, currency: str | None = None) -> dict:
	return {
		"id": doc.name,
		"job": doc.service_job,
		"technician": doc.technician,
		"status": doc.status,
		"started_at": to_iso(doc.started_at),
		"ended_at": to_iso(doc.ended_at),
		"hours": flt(doc.duration_hours, 2),
		"notes": cstr(doc.notes),
		"client_id": doc.client_id or None,
		"parts": [part(p, currency) for p in doc.parts],
		"photos": photos or [],
	}


def part(row, currency: str | None = None) -> dict:
	return {
		"id": row.name,
		"item": {"code": row.item_code, "name": row.item_name},
		"qty": flt(row.qty),
		"uom": row.uom,
		"rate": money(row.rate, currency),
		"amount": money(row.amount, currency),
		"client_id": row.client_id or None,
	}


def action(transition) -> dict:
	return {"action": transition.action, "next_status": transition.next_state}


def manager_job(detail: dict, doc) -> dict:
	"""A job as the manager's screens see it: the client detail plus what only managers need."""
	return {
		**detail,
		"estimated_value_raw": flt(doc.estimated_value),
		"signature_url": doc.customer_signoff or None,
		"created_at": to_iso(doc.creation),
		"last_activity_at": to_iso(doc.last_activity_at),
	}
