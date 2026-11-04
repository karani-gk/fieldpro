"""The rules a Service Job obeys on every save, whoever saves it: Desk, the API, /api/resource,
a background job. The controller calls these; nothing else may skip them.

Two kinds of rule:
- Edit guard: technicians and customers reach the same DocType as managers (role permissions
  must let them save for the workflow to work), so each may change only its own fields. Without
  this a customer could PUT /api/resource/Service Job/... and set their own price.
- State rules: a job cannot leave In Progress without finished work, cannot be assigned
  without a technician, and so on, whichever client asked.
"""

import frappe
from frappe import _
from frappe.utils import flt

from fieldpro.access import AccessProfile
from fieldpro.settings import AppSettings

BOOKED = "Booked"
ASSIGNED = "Assigned"
IN_PROGRESS = "In Progress"
PENDING_APPROVAL = "Pending Approval"
AWAITING_SIGNOFF = "Awaiting Sign-off"
DONE = "Done"
REWORK = "Rework"
CANCELLED = "Cancelled"
CLOSED_STATES = frozenset({DONE, CANCELLED})

# Fields a client could change. Anything else on the form is computed by the server.
GUARDED_FIELDS = (
	"customer",
	"issue",
	"description",
	"priority",
	"scheduled_date",
	"site_address",
	"contact_phone",
	"technician",
	"estimated_value",
	"workflow_state",
	"customer_signoff",
	"signed_off_by",
	"signed_off_at",
	"rejection_reason",
	"sales_invoice",
	"payment_status",
)
TECHNICIAN_MAY_CHANGE = frozenset({"workflow_state", "customer_signoff", "signed_off_by", "signed_off_at"})
CUSTOMER_MAY_CHANGE = frozenset({"workflow_state", "rejection_reason", "signed_off_by", "signed_off_at"})
CUSTOMER_MAY_SET_ON_BOOKING = frozenset(
	{"customer", "issue", "description", "priority", "scheduled_date", "site_address", "contact_phone"}
)


class JobRules:
	def __init__(self, doc, profile: AccessProfile | None = None, settings: AppSettings | None = None):
		self.doc = doc
		self.profile = profile or AccessProfile()
		self.settings = settings or AppSettings()

	def validate(self) -> None:
		self._guard_edits()
		self._set_defaults()
		self._check_state_change()

	# ---------------------------------------------------------------- edit guard

	def _guard_edits(self) -> None:
		if self.profile.is_manager or frappe.flags.in_install or frappe.flags.in_migrate:
			return
		if self.doc.is_new():
			self._guard_booking()
			return
		allowed = TECHNICIAN_MAY_CHANGE if self.profile.technician else CUSTOMER_MAY_CHANGE
		before = self.doc.get_doc_before_save()
		changed = [f for f in GUARDED_FIELDS if before and self.doc.get(f) != before.get(f)]
		refused = [f for f in changed if f not in allowed]
		if refused:
			frappe.throw(
				_("You cannot change {0} on a job.").format(", ".join(refused)),
				frappe.PermissionError,
			)

	def _guard_booking(self) -> None:
		if not self.profile.customers:
			frappe.throw(_("Only customers and managers can book jobs."), frappe.PermissionError)
		if self.doc.customer not in self.profile.customers:
			frappe.throw(_("You can only book jobs for your own company."), frappe.PermissionError)
		set_by_client = [
			f
			for f in GUARDED_FIELDS
			if f not in CUSTOMER_MAY_SET_ON_BOOKING and self._differs_from_default(f)
		]
		if set_by_client:
			frappe.throw(
				_("These are set by the service team, not on booking: {0}").format(", ".join(set_by_client)),
				frappe.PermissionError,
			)
		self.doc.source = "Portal" if self.doc.source in (None, "", "Desk") else self.doc.source

	def _differs_from_default(self, fieldname: str) -> bool:
		"""A new job carries the DocType's defaults (payment_status "Unpaid"); only other values count."""
		value = self.doc.get(fieldname)
		if not value:
			return False
		default = self.doc.meta.get_field(fieldname).default
		return str(value) != str(default or "")

	# ---------------------------------------------------------------- computed fields

	def _set_defaults(self) -> None:
		doc = self.doc
		if not doc.workflow_state:
			doc.workflow_state = BOOKED
		doc.currency = doc.currency or self.settings.currency
		doc.needs_approval = int(flt(doc.estimated_value) > self.settings.approval_threshold)

	# ---------------------------------------------------------------- state rules

	def _check_state_change(self) -> None:
		before = self.doc.get_doc_before_save()
		new, old = self.doc.workflow_state, before.workflow_state if before else None
		if new == old:
			return
		check = getattr(self, f"_entering_{new.lower().replace(' ', '_').replace('-', '_')}", None)
		if check:
			check()

	def _entering_assigned(self) -> None:
		if not self.doc.technician:
			frappe.throw(_("Choose a technician before assigning the job."))

	def _entering_pending_approval(self) -> None:
		self._require_finished_work()

	def _entering_awaiting_sign_off(self) -> None:
		self._require_finished_work()

	def _entering_done(self) -> None:
		if not self.doc.signed_off_by:
			frappe.throw(_("The customer must sign off before the job is done."))

	def _entering_rework(self) -> None:
		if not self.doc.rejection_reason:
			frappe.throw(_("Say why the work was rejected, so the technician knows what to fix."))

	def _require_finished_work(self) -> None:
		visits = frappe.get_all(
			"Job Visit", filters={"service_job": self.doc.name}, fields=["status"], ignore_permissions=True
		)
		if any(v.status == "Open" for v in visits):
			frappe.throw(_("End the open visit before completing the job."))
		if not any(v.status == "Closed" for v in visits):
			frappe.throw(_("Record at least one visit before completing the job."))
