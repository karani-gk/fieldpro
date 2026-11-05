// Calendar view of Service Jobs by the day they are booked for (Desk: Field Service > Calendar).
// A job has one date, not a start and an end, so both ends map to scheduled_date and every job
// is an all-day event. Dragging a job to another day saves it, so JobRules still apply.
frappe.views.calendar["Service Job"] = {
	field_map: {
		start: "scheduled_date",
		end: "scheduled_date",
		id: "name",
		title: "issue",
		allDay: "allDay",
	},
	fields: ["name", "issue", "scheduled_date", "workflow_state"],
	// Colour each job like its workflow state, so a glance shows what is late or waiting.
	get_css_class(job) {
		const colours = {
			Booked: "purple",
			Assigned: "blue",
			"In Progress": "orange",
			"Pending Approval": "red",
			"Awaiting Sign-off": "yellow",
			Done: "green",
			Rework: "red",
			Cancelled: "gray",
		};
		return colours[job.workflow_state] || "blue";
	},
	filters: [
		{
			fieldtype: "Link",
			fieldname: "technician",
			options: "Technician",
			label: __("Technician"),
		},
	],
	get_events_method: "frappe.desk.calendar.get_events",
};
