"""The manager app's customers screen: who the customers are, their open work, and what they owe.

A field manager books jobs for customers but may have no read permission on Customer (ERPNext
gives it to sales roles), so the list uses get_all behind ManagerOnly, as the booking picker
does, and sends only contact details a dispatcher needs. What a customer owes is accounts data:
it is filled in only for managers who may read Sales Invoices, and None for everyone else.
"""

import frappe
from frappe.utils import flt

from fieldpro.api import shapes
from fieldpro.services.dispatch import ManagerOnly
from fieldpro.services.job_rules import CLOSED_STATES
from fieldpro.settings import AppSettings

CUSTOMER_LIMIT = 50


class CustomerDirectory(ManagerOnly):
	def search(self, text: str | None = None, limit: int = CUSTOMER_LIMIT) -> list[dict]:
		like = f"%{(text or '').strip()}%"
		rows = frappe.get_all(
			"Customer",
			fields=["name", "customer_name", "mobile_no", "email_id"],
			filters={"disabled": 0},
			or_filters=[["name", "like", like], ["customer_name", "like", like]],
			order_by="customer_name asc",
			limit_page_length=limit,
		)
		names = [r.name for r in rows]
		open_jobs = self._open_jobs(names)
		owed = self._owed(names)
		currency = AppSettings().currency
		return [
			{
				"id": r.name,
				"name": r.customer_name,
				"mobile_no": r.mobile_no or "",
				"email": r.email_id or "",
				"open_jobs": open_jobs.get(r.name, 0),
				"owed": None if owed is None else shapes.money(owed.get(r.name, 0), currency),
			}
			for r in rows
		]

	@staticmethod
	def _open_jobs(customers: list[str]) -> dict[str, int]:
		if not customers:
			return {}
		rows = frappe.get_list(
			"Service Job",
			fields=["customer", {"COUNT": "name", "as": "count"}],
			filters=[["customer", "in", customers], ["workflow_state", "not in", list(CLOSED_STATES)]],
			group_by="customer",
		)
		return {r.customer: r.count for r in rows}

	def _owed(self, customers: list[str]) -> dict[str, float] | None:
		if not frappe.has_permission("Sales Invoice", "read", user=self.profile.user):
			return None
		if not customers:
			return {}
		rows = frappe.get_list(
			"Sales Invoice",
			fields=["customer", {"SUM": "outstanding_amount", "as": "owed"}],
			filters=[["customer", "in", customers], ["docstatus", "=", 1], ["outstanding_amount", ">", 0]],
			group_by="customer",
		)
		return {r.customer: flt(r.owed) for r in rows}
