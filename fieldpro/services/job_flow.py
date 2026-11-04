"""Moving a job through its workflow (fixtures/workflow.json) from any client.

The server owns the state. A client never sends "status: Done"; it asks for an action ("Accept",
"Sign Off On Site") and the server checks it is one this user may take now, with the workflow's
roles and conditions, then applies it. `actions()` tells a client which buttons to show.
"""

import base64
import re

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow, get_transitions
from frappe.utils import now_datetime

from fieldpro.api.errors import Invalid, InvalidTransition

START = "Start"
COMPLETE = "Complete"
SIGN_OFF = "Sign Off On Site"
ACCEPT = "Accept"
REJECT = "Reject"

DATA_URL = re.compile(r"^data:image/(png|jpeg);base64,(.+)$", re.DOTALL)
MAX_SIGNATURE_BYTES = 500_000


class JobFlow:
	def actions(self, doc) -> list:
		if doc.is_new() or not doc.workflow_state:
			return []
		return [frappe._dict(t) for t in get_transitions(doc)]

	def apply(
		self,
		name: str,
		action: str,
		*,
		signature: str | None = None,
		signed_by: str | None = None,
		reason: str | None = None,
	):
		doc = frappe.get_doc("Service Job", name)
		if not any(t.action == action for t in self.actions(doc)):
			raise InvalidTransition(
				_("{0} is not possible while the job is {1}.").format(action, doc.workflow_state),
				fields={"action": action},
			)
		# apply_workflow reloads the job from the database, so anything the action needs
		# (a signature, a reason) is saved first, in the same transaction.
		if self._prepare(doc, action, signature=signature, signed_by=signed_by, reason=reason):
			doc.save()
		return apply_workflow(doc, action)

	def _prepare(self, doc, action, *, signature, signed_by, reason) -> bool:
		if action == SIGN_OFF:
			if not signature or not (signed_by or "").strip():
				raise Invalid(
					_("The customer's signature and name are needed to sign off."),
					fields={"signature": "required", "signed_by": "required"},
				)
			doc.customer_signoff = SignatureStore().save(doc.name, signature)
			doc.signed_off_by = signed_by.strip()
			doc.signed_off_at = now_datetime()
			return True
		if action == ACCEPT:
			doc.signed_off_by = frappe.utils.get_fullname(frappe.session.user)
			doc.signed_off_at = now_datetime()
			return True
		if action == REJECT:
			if not (reason or "").strip():
				raise Invalid(_("Say what is wrong with the work."), fields={"reason": "required"})
			doc.rejection_reason = reason.strip()
			return True
		return False


class SignatureStore:
	"""A signature drawn on the phone arrives as a PNG data URL and is kept as a private file."""

	def save(self, job: str, data_url: str) -> str:
		match = DATA_URL.match(data_url or "")
		if not match:
			raise Invalid(_("The signature must be a PNG or JPEG image."), fields={"signature": "invalid"})
		content = base64.b64decode(match.group(2))
		if len(content) > MAX_SIGNATURE_BYTES:
			raise Invalid(_("The signature image is too large."), fields={"signature": "too large"})
		extension = "jpg" if match.group(1) == "jpeg" else "png"
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"signature-{job}.{extension}",
				"attached_to_doctype": "Service Job",
				"attached_to_name": job,
				"attached_to_field": "customer_signoff",
				"is_private": 1,
				"content": content,
			}
		)
		file.flags.ignore_permissions = True
		file.insert()
		return file.file_url
