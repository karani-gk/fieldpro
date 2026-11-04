"""Reading and booking jobs. Every query goes through frappe.get_list / get_doc with the caller's
permissions, so the row-level rules in permissions.py apply here too."""

import frappe
from frappe import _
from frappe.utils import getdate, today

from fieldpro.access import AccessProfile
from fieldpro.api import shapes
from fieldpro.api.errors import Forbidden, Invalid, NotFound
from fieldpro.api.pagination import Page, fetch_page
from fieldpro.services.job_flow import JobFlow
from fieldpro.services.job_rules import CLOSED_STATES

SCOPES = ("today", "open", "all")


class JobService:
	def __init__(self, profile: AccessProfile | None = None, flow: JobFlow | None = None):
		self.profile = profile or AccessProfile()
		self.flow = flow or JobFlow()

	def technician_jobs(self, scope: str = "today", cursor: str | None = None, limit: int = 20) -> Page:
		"""Today: open jobs scheduled today or earlier (overdue ones stay on the list).
		Open: every open job. All: everything assigned to the technician."""
		if scope not in SCOPES:
			raise Invalid(
				_("scope must be one of {0}.").format(", ".join(SCOPES)), fields={"scope": "invalid"}
			)
		filters = []
		if self.profile.technician:
			filters.append(["Service Job", "technician", "=", self.profile.technician])
		elif not self.profile.is_manager:
			raise Forbidden(_("This list is for technicians."))
		if scope in ("today", "open"):
			filters.append(["Service Job", "workflow_state", "not in", list(CLOSED_STATES)])
		if scope == "today":
			filters.append(["Service Job", "scheduled_date", "<=", today()])
		return fetch_page(
			"Service Job",
			fields=shapes.JOB_LIST_FIELDS,
			sort_field="scheduled_date",
			filters=filters,
			cursor=cursor,
			limit=limit,
		)

	def customer_jobs(self, status: str | None = None, cursor: str | None = None, limit: int = 20) -> Page:
		if not (self.profile.customers or self.profile.is_manager):
			raise Forbidden(_("This list is for customers."))
		filters = [["Service Job", "workflow_state", "=", status]] if status else []
		return fetch_page(
			"Service Job",
			fields=shapes.JOB_LIST_FIELDS,
			sort_field="creation",
			descending=True,
			filters=filters,
			cursor=cursor,
			limit=limit,
		)

	def get(self, name: str):
		if not frappe.db.exists("Service Job", name):
			raise NotFound(_("Service Job {0} not found.").format(name))
		doc = frappe.get_doc("Service Job", name)
		# Someone else's job answers "not found", not "forbidden": we do not confirm it exists.
		if not doc.has_permission("read"):
			raise NotFound(_("Service Job {0} not found.").format(name))
		return doc

	def detail(self, name: str) -> dict:
		doc = self.get(name)
		visits = [shapes.visit(v, photos, doc.currency) for v, photos in self._visits(doc.name)]
		actions = [shapes.action(t) for t in self.flow.actions(doc)]
		return shapes.job_detail(doc, visits, actions)

	def book(
		self,
		*,
		issue: str,
		customer: str | None = None,
		description: str | None = None,
		site_address: str | None = None,
		contact_phone: str | None = None,
		preferred_date: str | None = None,
		source: str = "Portal",
	):
		customer = customer or self._only_customer()
		if not (issue or "").strip():
			raise Invalid(_("Tell us what is wrong."), fields={"issue": "required"})
		if preferred_date and getdate(preferred_date) < getdate(today()):
			raise Invalid(_("Pick today or a later date."), fields={"preferred_date": "in the past"})
		doc = frappe.get_doc(
			{
				"doctype": "Service Job",
				"customer": customer,
				"issue": issue.strip(),
				"description": description,
				"site_address": site_address,
				"contact_phone": contact_phone,
				"scheduled_date": preferred_date,
				"source": source,
			}
		)
		doc.insert()
		return doc

	def _only_customer(self) -> str:
		if len(self.profile.customers) == 1:
			return self.profile.customers[0]
		if not self.profile.customers:
			raise Forbidden(_("Your account is not linked to a customer."))
		raise Invalid(_("Choose which company the job is for."), fields={"customer": "required"})

	@staticmethod
	def _visits(job: str):
		names = frappe.get_all(
			"Job Visit", filters={"service_job": job}, order_by="started_at asc", pluck="name"
		)
		photos = VisitPhotos.for_visits(names)
		return [(frappe.get_doc("Job Visit", n), photos.get(n, [])) for n in names]


class VisitPhotos:
	@staticmethod
	def for_visits(names: list[str]) -> dict[str, list]:
		if not names:
			return {}
		files = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Job Visit", "attached_to_name": ["in", names]},
			fields=["name", "file_name", "file_url", "attached_to_name"],
			order_by="creation asc",
		)
		out: dict[str, list] = {}
		for f in files:
			out.setdefault(f.attached_to_name, []).append(
				{"id": f.name, "name": f.file_name, "url": f.file_url}
			)
		return out
