"""Jobs and hours per technician (Desk). The same query serves the app's "my week" screen."""

from frappe import _
from frappe.utils import add_days, today

from fieldpro.services.reports import performance


def execute(filters=None):
	filters = filters or {}
	from_date = filters.get("from_date") or add_days(today(), -30)
	to_date = filters.get("to_date") or today()
	columns = [
		{
			"fieldname": "technician",
			"label": _("Technician"),
			"fieldtype": "Link",
			"options": "Technician",
			"width": 140,
		},
		{"fieldname": "technician_name", "label": _("Name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "jobs_done", "label": _("Jobs Done"), "fieldtype": "Int", "width": 100},
		{"fieldname": "visits", "label": _("Visits"), "fieldtype": "Int", "width": 90},
		{"fieldname": "hours", "label": _("Hours"), "fieldtype": "Float", "precision": 2, "width": 90},
		{
			"fieldname": "hours_per_visit",
			"label": _("Hours per Visit"),
			"fieldtype": "Float",
			"precision": 2,
			"width": 130,
		},
		{"fieldname": "parts_value", "label": _("Parts Used"), "fieldtype": "Currency", "width": 130},
	]
	rows = performance(from_date, to_date, filters.get("technician"))
	for row in rows:
		row["hours_per_visit"] = row.hours / row.visits if row.visits else 0
	chart = {
		"data": {
			"labels": [r.technician_name for r in rows],
			"datasets": [{"name": _("Hours"), "values": [r.hours for r in rows]}],
		},
		"type": "bar",
	}
	return columns, rows, None, chart
