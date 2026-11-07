import { describe, expect, it } from "vitest";
import { invoiceTone, INVOICE_TABS, suggestedDueDate } from "../src/lib/invoices.js";
import { dialogs, openNewJob } from "../src/lib/dialogs.js";

describe("invoices", () => {
	it("colours ERPNext's statuses and falls back to gray", () => {
		expect(invoiceTone("Overdue")).toBe("red");
		expect(invoiceTone("Paid")).toBe("green");
		expect(invoiceTone("Something new")).toBe("gray");
	});

	it("offers the tabs the server knows", () => {
		expect(INVOICE_TABS).toEqual(["Draft", "Unpaid", "Overdue", "Paid", "Cancelled"]);
	});
});

describe("suggestedDueDate", () => {
	it("keeps a due date that is still valid", () => {
		expect(suggestedDueDate({ due_date: "2026-11-20", posts_on: "2026-11-07" })).toBe("2026-11-20");
	});

	it("moves a past due date to the day the invoice posts", () => {
		expect(suggestedDueDate({ due_date: "2026-11-04", posts_on: "2026-11-07" })).toBe("2026-11-07");
		expect(suggestedDueDate({ due_date: null, posts_on: "2026-11-07" })).toBe("2026-11-07");
	});
});

describe("openNewJob", () => {
	it("keeps a customer but not a click event", () => {
		openNewJob({ id: "C1", name: "Clinic" });
		expect(dialogs.customer).toEqual({ id: "C1", name: "Clinic" });
		openNewJob(new Event("click"));
		expect([dialogs.customer, dialogs.newJob]).toEqual([null, true]);
	});
});
