"""What happens after a job changes (Service Job on_update).

The request that changed the job only records the change. Everything slow or external - the
invoice, the push notification, the partner webhook - goes to a background queue, after the
transaction commits, so the technician's tap returns in milliseconds and nothing is sent for a
change that was rolled back.
"""

import frappe

from fieldpro.services.job_rules import DONE
from fieldpro.services.realtime import JobBroadcast


class JobEvents:
	def __init__(self, doc):
		self.doc = doc
		self.before = doc.get_doc_before_save()

	def after_save(self) -> None:
		JobBroadcast().publish(self.doc.name)
		if self._changed("technician") and self.doc.technician_user:
			self._push_new_job()
		if self._changed("workflow_state") and self.doc.workflow_state == DONE:
			self._job_done()

	def _changed(self, field: str) -> bool:
		return self.doc.get(field) != (self.before.get(field) if self.before else None)

	def _push_new_job(self) -> None:
		frappe.enqueue(
			"fieldpro.services.push.notify_user",
			user=self.doc.technician_user,
			title="New job",
			body=f"{self.doc.customer_name}: {self.doc.issue}",
			data={"job": self.doc.name},
			enqueue_after_commit=True,
		)

	def _job_done(self) -> None:
		# The job id makes the invoice job unique: a second "Done" while one is queued adds nothing.
		frappe.enqueue(
			"fieldpro.services.invoicing.create_invoice_for_job",
			job=self.doc.name,
			job_id=f"fieldpro-invoice-{self.doc.name}",
			deduplicate=True,
			enqueue_after_commit=True,
		)
		from fieldpro.services.partner_webhooks import PartnerWebhooks

		PartnerWebhooks().queue("job.done", "Service Job", self.doc.name, job_payload(self.doc))


def job_payload(doc) -> dict:
	from fieldpro.api.shapes import money
	from fieldpro.utils import to_iso

	return {
		"job": doc.name,
		"customer": doc.customer,
		"issue": doc.issue,
		"technician": doc.technician_name,
		"hours": doc.total_hours,
		"parts_total": money(doc.parts_total, doc.currency),
		"signed_off_by": doc.signed_off_by,
		"done_at": to_iso(doc.modified),
	}
