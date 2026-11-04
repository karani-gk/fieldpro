"""Visits and parts: what a technician does on site.

The rules live here and in VisitRules, never in the endpoints, so the online API, the offline
sync and Desk all behave the same. Each method that a phone may retry takes a `client_id`: a
second call with the same id returns the first result instead of doing the work twice.
"""

import base64

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from fieldpro.access import AccessProfile
from fieldpro.api.errors import Conflict, Forbidden, Invalid, NotFound
from fieldpro.services.job_flow import START, JobFlow
from fieldpro.services.job_rules import ASSIGNED, IN_PROGRESS, REWORK

STARTABLE_STATES = frozenset({ASSIGNED, IN_PROGRESS, REWORK})
MAX_PHOTO_BYTES = 5_000_000


class VisitService:
	def __init__(self, profile: AccessProfile | None = None, flow: JobFlow | None = None):
		self.profile = profile or AccessProfile()
		self.flow = flow or JobFlow()

	def start(self, job: str, *, client_id: str | None = None, started_at=None):
		if client_id and (existing := frappe.db.get_value("Job Visit", {"client_id": client_id}, "name")):
			return frappe.get_doc("Job Visit", existing)
		technician = self._technician()
		job_doc = self._job(job)
		if job_doc.technician != technician:
			raise Forbidden(_("This job is assigned to someone else."))
		if job_doc.workflow_state not in STARTABLE_STATES:
			raise Conflict(
				_("This job is {0}. Visits can be started on assigned jobs only.").format(
					job_doc.workflow_state
				),
				code="job_not_startable",
			)
		if frappe.db.exists("Job Visit", {"service_job": job, "technician": technician, "status": "Open"}):
			raise Conflict(_("A visit is already open on this job. End it first."), code="visit_open")
		visit = frappe.get_doc(
			{
				"doctype": "Job Visit",
				"service_job": job,
				"technician": technician,
				"status": "Open",
				"started_at": started_at or now_datetime(),
				"client_id": client_id,
			}
		).insert()
		if job_doc.workflow_state != IN_PROGRESS:
			self.flow.apply(job, START)
		return visit

	def end(self, visit: str, *, ended_at=None, notes: str | None = None):
		doc = self._own_visit(visit)
		if doc.status == "Closed":
			return doc  # ending twice (a retried request) changes nothing
		doc.status = "Closed"
		doc.ended_at = ended_at or now_datetime()
		if notes:
			doc.notes = notes
		doc.save()
		return doc

	def add_part(self, visit: str, *, item_code: str, qty, client_id: str | None = None):
		doc = self._own_visit(visit)
		if client_id and any(p.client_id == client_id for p in doc.parts):
			return doc
		if doc.status == "Closed":
			raise Conflict(_("This visit has ended. Add parts to an open visit."), code="visit_closed")
		if flt(qty) <= 0:
			raise Invalid(_("Quantity must be more than zero."), fields={"qty": "must be positive"})
		if not frappe.db.exists("Item", {"name": item_code, "disabled": 0}):
			raise Invalid(
				_("{0} is not an item we stock.").format(item_code), fields={"item_code": "unknown"}
			)
		doc.append("parts", {"item_code": item_code, "qty": flt(qty), "client_id": client_id})
		doc.save()
		return doc

	def add_photo(self, visit: str, *, file_name: str, content: str):
		doc = self._own_visit(visit)
		try:
			data = base64.b64decode(content.split(",", 1)[-1], validate=True)
		except Exception:
			raise Invalid(_("The photo must be base64 encoded."), fields={"content": "invalid"})
		if len(data) > MAX_PHOTO_BYTES:
			raise Invalid(_("Photos must be under 5 MB."), fields={"content": "too large"})
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name or f"{doc.name}.jpg",
				"attached_to_doctype": "Job Visit",
				"attached_to_name": doc.name,
				# Private: served only to users who can read the visit, never by a public URL.
				"is_private": 1,
				"content": data,
			}
		)
		# _own_visit has proved this is the technician's visit; the file needs no further check.
		file.flags.ignore_permissions = True
		file.insert()
		return file

	def _technician(self) -> str:
		if not self.profile.technician:
			raise Forbidden(_("Only technicians record visits."))
		return self.profile.technician

	@staticmethod
	def _job(job: str):
		from fieldpro.services.jobs import JobService

		# Same answer as reading the job: someone else's job is "not found".
		return JobService().get(job)

	def _own_visit(self, visit: str):
		technician = self._technician()
		if not frappe.db.exists("Job Visit", visit):
			raise NotFound(_("Visit {0} not found.").format(visit))
		doc = frappe.get_doc("Job Visit", visit)
		if doc.technician != technician:
			raise NotFound(_("Visit {0} not found.").format(visit))
		return doc
