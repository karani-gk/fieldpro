"""Offline sync for the technician app.

Pull: "what changed since my cursor?" The cursor is the server's (modified, name) of the last job
the phone saw, never the phone's clock, which can be wrong by hours. Any change to a job, its
visits or its parts moves the job's `modified` (JobTotals), so one cursor covers all of them.

Push: the phone sends the work it did offline in small batches. Every operation carries a
client_id made on the phone, so a batch sent twice (the connection dropped before the answer
came back) is applied once. Each operation is applied on its own: one that fails does not undo
the others, and the answer lists a result per operation.

Conflicts: the server wins. If the manager cancelled or reassigned the job while the phone was
offline, the operation is refused with status "conflict" and the server's version of the job,
and the app shows it to the technician instead of overwriting it.
"""

import frappe
from frappe import _

from fieldpro.access import AccessProfile
from fieldpro.api import shapes
from fieldpro.api.errors import ApiError, Forbidden, Invalid
from fieldpro.api.pagination import fetch_page
from fieldpro.services.jobs import JobService
from fieldpro.services.visits import VisitService
from fieldpro.utils import from_iso

MAX_BATCH = 50
OPERATIONS = ("start_visit", "end_visit", "add_part")


class SyncService:
	def __init__(self, profile: AccessProfile | None = None):
		self.profile = profile or AccessProfile()
		self.jobs = JobService(self.profile)
		self.visits = VisitService(self.profile)

	def pull(self, cursor: str | None = None, limit: int = 50) -> dict:
		if not self.profile.technician:
			raise Forbidden(_("Sync is for technicians."))
		page = fetch_page(
			"Service Job",
			fields=["name"],
			sort_field="modified",
			filters=[["Service Job", "technician", "=", self.profile.technician]],
			cursor=cursor,
			limit=limit,
		)
		jobs = [self.jobs.detail(row.name) for row in page.rows]
		# The last row's cursor, even on the final page: next time, start after it.
		next_cursor = page.next_cursor
		if not next_cursor and page.rows:
			from fieldpro.api.pagination import encode

			last = page.rows[-1]
			next_cursor = encode(last.modified, last.name)
		return {"jobs": jobs, "cursor": next_cursor or cursor, "has_more": page.has_more}

	def push(self, operations: list) -> list[dict]:
		if not self.profile.technician:
			raise Forbidden(_("Sync is for technicians."))
		if not isinstance(operations, list):
			raise Invalid(_("operations must be a list."), fields={"operations": "not a list"})
		if len(operations) > MAX_BATCH:
			raise Invalid(
				_("Send at most {0} operations at a time.").format(MAX_BATCH),
				fields={"operations": "too many"},
			)
		return [self._apply_one(op) for op in operations]

	def _apply_one(self, op: dict) -> dict:
		client_id = (op or {}).get("client_id")
		if not client_id or op.get("op") not in OPERATIONS:
			return {
				"client_id": client_id,
				"status": "error",
				"error": {"code": "invalid", "message": "Unknown operation."},
			}
		savepoint = f"sync_{frappe.generate_hash(length=8)}"
		frappe.db.savepoint(savepoint)
		try:
			result = getattr(self, f"_{op['op']}")(op)
			frappe.db.release_savepoint(savepoint)
			return {"client_id": client_id, **result}
		except Exception as exc:
			frappe.db.rollback(save_point=savepoint)
			error = ApiError.from_exception(exc)
			if error is None:
				frappe.log_error(title=f"fieldpro sync: {op.get('op')}")
				return {
					"client_id": client_id,
					"status": "error",
					"error": {"code": "server_error", "message": "Server error."},
				}
			status = "conflict" if error.status in (403, 404, 409) else "error"
			result = {"client_id": client_id, "status": status, "error": error.as_dict()}
			if status == "conflict" and op.get("job"):
				result["server"] = self._server_job(op["job"])
			return result

	def _start_visit(self, op: dict) -> dict:
		existed = frappe.db.exists("Job Visit", {"client_id": op["client_id"]})
		visit = self.visits.start(op["job"], client_id=op["client_id"], started_at=from_iso(op.get("at")))
		return {"status": "duplicate" if existed else "ok", "visit": visit.name}

	def _end_visit(self, op: dict) -> dict:
		visit = self._visit_for(op)
		was_closed = frappe.db.get_value("Job Visit", visit, "status") == "Closed"
		self.visits.end(visit, ended_at=from_iso(op.get("at")), notes=op.get("notes"))
		return {"status": "duplicate" if was_closed else "ok", "visit": visit}

	def _add_part(self, op: dict) -> dict:
		visit = self._visit_for(op)
		existed = bool(frappe.db.exists("Parts Used", {"client_id": op["client_id"]}))
		self.visits.add_part(
			visit, item_code=op.get("item_code"), qty=op.get("qty"), client_id=op["client_id"]
		)
		return {"status": "duplicate" if existed else "ok", "visit": visit}

	@staticmethod
	def _visit_for(op: dict) -> str:
		"""An operation names its visit by server id, or by the client_id it was started with offline."""
		if op.get("visit"):
			return op["visit"]
		name = frappe.db.get_value("Job Visit", {"client_id": op.get("visit_client_id")}, "name")
		if not name:
			raise Invalid(
				_("The visit this belongs to has not been uploaded yet."),
				fields={"visit_client_id": "unknown"},
			)
		return name

	def _server_job(self, job: str) -> dict | None:
		try:
			return self.jobs.detail(job)
		except ApiError:
			return None
