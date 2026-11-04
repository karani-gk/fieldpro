"""Rules every Job Visit obeys on save, and the job totals that follow from its visits."""

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, now_datetime, time_diff_in_hours

from fieldpro.access import AccessProfile
from fieldpro.services.realtime import JobBroadcast

PRICE_LIST = "Standard Selling"


class VisitRules:
	def __init__(self, doc, profile: AccessProfile | None = None):
		self.doc = doc
		self.profile = profile or AccessProfile()

	def validate(self) -> None:
		self._check_technician()
		self._check_times()
		self._price_parts()

	def _check_technician(self) -> None:
		job_technician = frappe.db.get_value("Service Job", self.doc.service_job, "technician")
		if self.doc.technician != job_technician:
			frappe.throw(_("A visit is recorded by the job's own technician."))
		before = self.doc.get_doc_before_save()
		if before and before.status == "Closed" and not self.profile.is_manager:
			frappe.throw(_("This visit has ended and can no longer be changed."), frappe.PermissionError)

	def _check_times(self) -> None:
		doc = self.doc
		if doc.status == "Closed" and not doc.ended_at:
			doc.ended_at = now_datetime()
		if doc.ended_at and get_datetime(doc.ended_at) < get_datetime(doc.started_at):
			frappe.throw(_("A visit cannot end before it started."))
		doc.duration_hours = flt(time_diff_in_hours(doc.ended_at, doc.started_at), 2) if doc.ended_at else 0

	def _price_parts(self) -> None:
		warehouse = frappe.db.get_value("Technician", self.doc.technician, "warehouse")
		for row in self.doc.parts:
			row.warehouse = row.warehouse or warehouse
			if not flt(row.rate):
				row.rate = selling_rate(row.item_code)
			row.amount = flt(row.qty) * flt(row.rate)


def selling_rate(item_code: str) -> float:
	"""The item's price on the Standard Selling list, else its standard rate."""
	rate = frappe.db.get_value(
		"Item Price", {"item_code": item_code, "price_list": PRICE_LIST}, "price_list_rate"
	)
	return flt(rate) or flt(frappe.db.get_value("Item", item_code, "standard_rate"))


class JobTotals:
	"""Hours and parts on a job, summed from its closed visits."""

	def refresh(self, job: str) -> None:
		visits = frappe.get_all(
			"Job Visit",
			filters={"service_job": job, "status": "Closed"},
			fields=["name", "duration_hours"],
			ignore_permissions=True,
		)
		parts_total = 0.0
		if visits:
			parts_total = flt(
				frappe.db.sql(
					"select sum(amount) from `tabParts Used` where parenttype='Job Visit' and parent in %(v)s",
					{"v": [v.name for v in visits]},
				)[0][0]
			)
		# db.set_value also moves `modified`, which is what tells offline clients to pull the job.
		frappe.db.set_value(
			"Service Job",
			job,
			{
				"total_hours": sum(flt(v.duration_hours) for v in visits),
				"parts_total": parts_total,
				"last_activity_at": now_datetime(),
			},
		)
		JobBroadcast().publish(job)
