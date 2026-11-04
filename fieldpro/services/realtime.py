"""Live job updates over Socket.io.

Frappe's socket.io server puts every signed-in user in a room named after them, so publishing
with `user=` reaches exactly the people allowed to see the job: its technician and the
customer's portal users. Desk users get document updates on their own. `after_commit=True`
matters: a client told "the job changed" must find the change when it fetches the job.
"""

import frappe

from fieldpro.utils import to_iso

JOB_EVENT = "fieldpro_job"


class JobBroadcast:
	def publish(self, job: str) -> None:
		row = frappe.db.get_value(
			"Service Job",
			job,
			["name", "workflow_state", "technician_user", "technician_name", "customer", "modified"],
			as_dict=True,
		)
		if not row:
			return
		payload = {
			"id": row.name,
			"status": row.workflow_state,
			"technician": row.technician_name,
			"updated_at": to_iso(row.modified),
		}
		for user in self.recipients(row):
			frappe.publish_realtime(JOB_EVENT, payload, user=user, after_commit=True)

	@staticmethod
	def recipients(row) -> set[str]:
		users = set(
			frappe.get_all(
				"Portal User", filters={"parent": row.customer, "parenttype": "Customer"}, pluck="user"
			)
		)
		if row.technician_user:
			users.add(row.technician_user)
		return users
