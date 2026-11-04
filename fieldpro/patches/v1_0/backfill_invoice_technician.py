"""Fill Sales Invoice.technician (a custom field added after the first invoices were made) from
each invoice's job. Safe to run twice: it touches only invoices whose technician is still empty."""

import frappe


def execute():
	if not frappe.db.has_column("Sales Invoice", "technician"):
		return
	frappe.db.sql(
		"""
		update `tabSales Invoice` si
		join `tabService Job` j on j.name = si.service_job
		set si.technician = j.technician
		where ifnull(si.technician, '') = '' and ifnull(j.technician, '') != ''
		"""
	)
