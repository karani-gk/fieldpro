"""The dispatch desk: what the manager's Vue app (/manage) reads and changes.

Managers can do all of this in ERPNext Desk too. These classes give the Vue app one call per
decision ("assign Otieno for Friday") instead of several raw /api/resource writes, and they reuse
what Desk already has: the Number Cards for the dashboard counts, JobService for booking and
reading, JobFlow for workflow actions. So Desk and the Vue app always agree.

Every class starts with ManagerOnly: the row-level hooks let managers see every job, so a
technician or customer calling these must be stopped before any query runs.
"""

import frappe
from frappe import _
from frappe.desk.doctype.number_card.number_card import get_result
from frappe.utils import add_days, cint, flt, getdate, today

from fieldpro.access import AccessProfile
from fieldpro.api import shapes
from fieldpro.api.errors import Forbidden, Invalid, InvalidTransition
from fieldpro.api.pagination import Page, fetch_page
from fieldpro.services.job_flow import JobFlow
from fieldpro.services.job_rules import ASSIGNED, BOOKED, CLOSED_STATES, DONE, REWORK
from fieldpro.services.jobs import JobService
from fieldpro.services.reports import performance

# The dashboard shows the same Number Cards as the Field Service workspace, in this order.
DASHBOARD_CARDS = (
	"Jobs Booked Today",
	"Waiting for a Technician",
	"Jobs In Progress",
	"Waiting for Approval",
	"Done This Week",
	"Done but Not Invoiced",
)
# A job may change technician only before the work starts (or when it comes back for rework).
REASSIGNABLE_STATES = frozenset({BOOKED, ASSIGNED, REWORK})
# Fields a manager edits from the job screen. The workflow and the technician have their own calls.
EDITABLE_FIELDS = (
	"issue",
	"description",
	"priority",
	"scheduled_date",
	"site_address",
	"contact_phone",
	"estimated_value",
)
ATTENTION_LIMIT = 8
BOARD_LIMIT = 300
RECENT_DONE_DAYS = 7
SEARCH_LIMIT = 500


class ManagerOnly:
	"""The one gate in front of every dispatch call."""

	def __init__(self, profile: AccessProfile | None = None):
		self.profile = profile or AccessProfile()
		if not self.profile.is_manager:
			raise Forbidden(_("This is for field service managers."))


class DispatchOverview(ManagerOnly):
	"""The dashboard: today's numbers and the jobs that need a manager now."""

	def summary(self) -> dict:
		return {"cards": self.cards(), "attention": self.attention()}

	def cards(self) -> list[dict]:
		return [{"label": name, "value": self._count(name)} for name in DASHBOARD_CARDS]

	def attention(self) -> dict:
		return {
			"unassigned": self._jobs([["workflow_state", "=", BOOKED]], "creation asc"),
			"waiting_approval": self._jobs([["workflow_state", "=", "Pending Approval"]], "modified asc"),
			"overdue": self._jobs(
				[
					["workflow_state", "not in", [*CLOSED_STATES, BOOKED]],
					["scheduled_date", "<", today()],
				],
				"scheduled_date asc",
			),
			"rework": self._jobs([["workflow_state", "=", REWORK]], "modified asc"),
		}

	@staticmethod
	def _count(card: str) -> int:
		# The card's own filters, so a change to a card in Desk changes the Vue dashboard too.
		doc = frappe.get_cached_doc("Number Card", card)
		return cint(get_result(doc.as_json(), doc.filters_json))

	@staticmethod
	def _jobs(filters: list, order_by: str) -> list[dict]:
		rows = frappe.get_list(
			"Service Job",
			fields=shapes.JOB_LIST_FIELDS,
			filters=filters,
			order_by=order_by,
			limit_page_length=ATTENTION_LIMIT,
		)
		return [shapes.job_summary(r) for r in rows]


class JobQueue(ManagerOnly):
	"""Every job, as a filtered list or as board columns."""

	def page(
		self,
		*,
		status: str | None = None,
		technician: str | None = None,
		priority: str | None = None,
		search: str | None = None,
		cursor: str | None = None,
		limit: int = 20,
		customer: str | None = None,
	) -> Page:
		filters = []
		if customer:
			filters.append(["Service Job", "customer", "=", customer])
		if status:
			filters.append(["Service Job", "workflow_state", "=", status])
		if technician:
			filters.append(["Service Job", "technician", "=", technician])
		if priority:
			filters.append(["Service Job", "priority", "=", priority])
		if (search or "").strip():
			# fetch_page uses or_filters for its cursor, so the search finds names first.
			filters.append(["Service Job", "name", "in", self._matching(search.strip()) or [""]])
		return fetch_page(
			"Service Job",
			fields=shapes.JOB_LIST_FIELDS,
			sort_field="creation",
			descending=True,
			filters=filters,
			cursor=cursor,
			limit=limit,
		)

	def board(self) -> list[dict]:
		"""One column per workflow state, in the workflow's order. Done shows only the last week,
		Cancelled not at all: the board is for work in flight."""
		rows = frappe.get_list(
			"Service Job",
			fields=shapes.JOB_LIST_FIELDS,
			filters=[["workflow_state", "not in", list(CLOSED_STATES)]],
			order_by="scheduled_date asc, creation asc",
			limit_page_length=BOARD_LIMIT,
		)
		rows += frappe.get_list(
			"Service Job",
			fields=shapes.JOB_LIST_FIELDS,
			filters=[
				["workflow_state", "=", DONE],
				["signed_off_at", ">=", add_days(today(), -RECENT_DONE_DAYS)],
			],
			order_by="signed_off_at desc",
			limit_page_length=BOARD_LIMIT,
		)
		columns = {state: [] for state in self.states() if state not in CLOSED_STATES or state == DONE}
		for row in rows:
			columns.setdefault(row.workflow_state, []).append(shapes.job_summary(row))
		return [{"status": state, "jobs": jobs} for state, jobs in columns.items()]

	@staticmethod
	def states() -> list[str]:
		return [row.state for row in frappe.get_cached_doc("Workflow", "Service Job").states]

	@staticmethod
	def _matching(search: str) -> list[str]:
		like = f"%{search}%"
		return frappe.get_list(
			"Service Job",
			or_filters=[
				["name", "like", like],
				["issue", "like", like],
				["customer_name", "like", like],
				["technician_name", "like", like],
			],
			pluck="name",
			limit_page_length=SEARCH_LIMIT,
		)


class Dispatcher(ManagerOnly):
	"""The manager's changes to a job: book, assign, edit, and workflow actions."""

	def __init__(
		self,
		profile: AccessProfile | None = None,
		jobs: JobService | None = None,
		flow: JobFlow | None = None,
	):
		super().__init__(profile)
		self.jobs = jobs or JobService(self.profile)
		self.flow = flow or JobFlow()

	def detail(self, job: str) -> dict:
		doc = self.jobs.get(job)
		return shapes.manager_job(self.jobs.detail(job), doc)

	def book(self, *, customer: str | None, issue: str, technician: str | None = None, **fields) -> str:
		"""A job taken over the phone. With a technician it is assigned straight away."""
		if not customer:
			raise Invalid(_("Choose the customer."), fields={"customer": "required"})
		if not frappe.db.exists("Customer", customer):
			raise Invalid(_("Customer {0} not found.").format(customer), fields={"customer": "not found"})
		doc = self.jobs.book(customer=customer, issue=issue, source="Desk", **fields)
		if technician:
			self.assign(doc.name, technician)
		return doc.name

	def assign(self, job: str, technician: str, scheduled_date: str | None = None) -> None:
		"""Give a Booked job to a technician (the Assign action), or hand an assigned job to
		someone else before the work starts."""
		doc = self.jobs.get(job)
		if doc.workflow_state not in REASSIGNABLE_STATES:
			raise InvalidTransition(
				_("A job that is {0} keeps its technician.").format(doc.workflow_state),
				fields={"technician": "locked"},
			)
		if not frappe.db.get_value("Technician", {"name": technician, "is_active": 1}):
			raise Invalid(_("Choose an active technician."), fields={"technician": "invalid"})
		doc.technician = technician
		if scheduled_date:
			doc.scheduled_date = self._valid_date(scheduled_date)
		# Save first: the Assign action reloads the job and checks it has a technician.
		doc.save()
		if doc.workflow_state == BOOKED:
			self.flow.apply(job, "Assign")

	def update(self, job: str, changes: dict) -> None:
		doc = self.jobs.get(job)
		unknown = sorted(set(changes) - set(EDITABLE_FIELDS))
		if unknown:
			raise Invalid(
				_("These cannot be changed here: {0}").format(", ".join(unknown)),
				fields={f: "not editable" for f in unknown},
			)
		if "issue" in changes and not (changes["issue"] or "").strip():
			raise Invalid(_("A job needs an issue."), fields={"issue": "required"})
		if changes.get("scheduled_date"):
			changes["scheduled_date"] = self._valid_date(changes["scheduled_date"], allow_past=True)
		if "estimated_value" in changes:
			changes["estimated_value"] = flt(changes["estimated_value"])
		doc.update(changes)
		doc.save()

	def act(self, job: str, action: str, reason: str | None = None) -> None:
		"""A workflow action (Approve, Send Back, Cancel). JobFlow checks it is allowed now."""
		self.jobs.get(job)  # not found before anything else
		self.flow.apply(job, action, reason=reason)

	@staticmethod
	def _valid_date(value: str, allow_past: bool = False) -> str:
		try:
			day = getdate(value)
		except Exception:
			raise Invalid(_("That is not a date."), fields={"scheduled_date": "invalid"})
		if not allow_past and day < getdate(today()):
			raise Invalid(_("Pick today or a later date."), fields={"scheduled_date": "in the past"})
		return day.isoformat()


class TeamLoad(ManagerOnly):
	"""Each active technician's open work and recent hours, for choosing who gets a job."""

	def technicians(self) -> list[dict]:
		people = frappe.get_list(
			"Technician",
			fields=["name", "full_name", "mobile_no", "user"],
			filters={"is_active": 1},
			order_by="full_name asc",
		)
		open_jobs = self._open_jobs()
		hours = {r.technician: r for r in performance(add_days(today(), -6), today())}
		return [self._row(p, open_jobs.get(p.name, []), hours.get(p.name)) for p in people]

	@staticmethod
	def _open_jobs() -> dict[str, list]:
		rows = frappe.get_list(
			"Service Job",
			fields=["name", "technician", "scheduled_date", "workflow_state"],
			filters=[["workflow_state", "not in", list(CLOSED_STATES)], ["technician", "is", "set"]],
			limit_page_length=0,
		)
		by_technician: dict[str, list] = {}
		for row in rows:
			by_technician.setdefault(row.technician, []).append(row)
		return by_technician

	@staticmethod
	def _row(person, jobs: list, week) -> dict:
		now = getdate(today())
		return {
			"id": person.name,
			"name": person.full_name,
			"mobile_no": person.mobile_no or "",
			"email": person.user or "",
			"open_jobs": len(jobs),
			"today": sum(1 for j in jobs if j.scheduled_date and getdate(j.scheduled_date) == now),
			"overdue": sum(1 for j in jobs if j.scheduled_date and getdate(j.scheduled_date) < now),
			"in_progress": sum(1 for j in jobs if j.workflow_state == "In Progress"),
			"week": {
				"jobs_done": cint(week.jobs_done) if week else 0,
				"visits": cint(week.visits) if week else 0,
				"hours": flt(week.hours, 2) if week else 0,
			},
		}


class CustomerPicker(ManagerOnly):
	"""Customers to book a job for, found by name."""

	def search(self, text: str | None = None, limit: int = 20) -> list[dict]:
		like = f"%{(text or '').strip()}%"
		# get_all, not get_list: Field Manager alone has no read permission on Customer, yet
		# booking jobs for customers is its work. Only the id and name leave, and only to managers
		# (ManagerOnly), who already see every job's customer name.
		rows = frappe.get_all(
			"Customer",
			fields=["name", "customer_name"],
			filters={"disabled": 0},
			or_filters=[["name", "like", like], ["customer_name", "like", like]],
			order_by="customer_name asc",
			limit_page_length=limit,
		)
		return [{"id": r.name, "name": r.customer_name} for r in rows]
