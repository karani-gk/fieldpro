frappe.query_reports["Technician Performance"] = {
	filters: [
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), -30) },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "technician", label: __("Technician"), fieldtype: "Link", options: "Technician" },
	],
};
