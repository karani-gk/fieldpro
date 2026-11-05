// How dates, money and statuses read on screen. No business rules here: those are the server's.

/** Each workflow state's colour family, matching the job's place in the work. */
const STATUS_TONES = {
	Booked: "slate",
	Assigned: "blue",
	"In Progress": "amber",
	"Pending Approval": "orange",
	"Awaiting Sign-off": "violet",
	Rework: "red",
	Done: "green",
	Cancelled: "gray",
};

export function statusTone(status) {
	return STATUS_TONES[status] || "gray";
}

/** A local calendar date as YYYY-MM-DD (not toISOString, which is UTC and can be yesterday). */
export function isoDay(date = new Date()) {
	const pad = (n) => String(n).padStart(2, "0");
	return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** "Today", "Tomorrow", "Yesterday", or "Fri 7 Nov" for a YYYY-MM-DD date. */
export function dayLabel(value, today = new Date()) {
	if (!value) return "No date";
	const [y, m, d] = value.split("-").map(Number);
	const date = new Date(y, m - 1, d);
	const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
	const days = Math.round((date - start) / 86_400_000);
	if (days === 0) return "Today";
	if (days === 1) return "Tomorrow";
	if (days === -1) return "Yesterday";
	const sameYear = date.getFullYear() === today.getFullYear();
	return date.toLocaleDateString("en-GB", {
		weekday: "short",
		day: "numeric",
		month: "short",
		...(sameYear ? {} : { year: "numeric" }),
	});
}

/** True when an open job's date has passed. */
export function isOverdue(job, today = new Date()) {
	if (!job.scheduled_date || ["Done", "Cancelled", "Booked"].includes(job.status)) return false;
	return job.scheduled_date < isoDay(today);
}

/** A UTC ISO timestamp from the API in the manager's own time zone. */
export function dateTime(value) {
	if (!value) return "";
	return new Date(value).toLocaleString("en-GB", {
		day: "numeric",
		month: "short",
		hour: "2-digit",
		minute: "2-digit",
	});
}

/** {amount: "1500.00", currency: "KES"} as "KES 1,500.00". */
export function money(value) {
	if (!value) return "";
	const amount = Number(value.amount).toLocaleString("en-GB", {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	});
	return value.currency ? `${value.currency} ${amount}` : amount;
}

export function initials(name) {
	return (name || "?")
		.split(/\s+/)
		.filter(Boolean)
		.slice(0, 2)
		.map((part) => part[0].toUpperCase())
		.join("");
}
