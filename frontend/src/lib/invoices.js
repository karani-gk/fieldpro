// How invoices read on screen. The status is ERPNext's own; this only picks its colour.

/** The status tabs on the Invoices screen, matching invoice_desk.py STATUS_FILTERS. */
export const INVOICE_TABS = ["Draft", "Unpaid", "Overdue", "Paid", "Cancelled"];

const INVOICE_TONES = {
	Draft: "slate",
	Unpaid: "blue",
	"Partly Paid": "amber",
	Overdue: "red",
	"Overdue and Discounted": "red",
	Paid: "green",
	"Credit Note Issued": "violet",
	Return: "violet",
	Cancelled: "gray",
};

export function invoiceTone(status) {
	return INVOICE_TONES[status] || "gray";
}

/** The due date to offer when submitting: the draft's own, unless it is before the day the
 * invoice will post (`posts_on`, from the server), which ERPNext refuses. Dates are YYYY-MM-DD. */
export function suggestedDueDate(invoice) {
	if (invoice.due_date && invoice.due_date >= invoice.posts_on) return invoice.due_date;
	return invoice.posts_on;
}
