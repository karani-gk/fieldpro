"""Hooks on other apps' DocTypes (hooks.py doc_events)."""

import frappe


def invoice_cancelled(doc, method=None):
	"""A cancelled or deleted invoice no longer bills its job, so the job can be invoiced again."""
	job = doc.get("service_job")
	if job and frappe.db.get_value("Service Job", job, "sales_invoice") == doc.name:
		frappe.db.set_value("Service Job", job, "sales_invoice", None)
