import { describe, expect, it } from "vitest";
import { dayLabel, initials, isoDay, isOverdue, money, statusTone } from "../src/lib/format.js";

const wednesday = new Date(2026, 10, 4, 15, 0);

describe("format", () => {
	it("names nearby days and dates the rest", () => {
		expect(dayLabel("2026-11-04", wednesday)).toBe("Today");
		expect(dayLabel("2026-11-05", wednesday)).toBe("Tomorrow");
		expect(dayLabel("2026-11-03", wednesday)).toBe("Yesterday");
		expect(dayLabel("2026-11-07", wednesday)).toBe("Sat 7 Nov");
		expect(dayLabel(null, wednesday)).toBe("No date");
	});

	it("uses the local calendar day", () => {
		expect(isoDay(new Date(2026, 0, 2, 23, 59))).toBe("2026-01-02");
	});

	it("calls only open, assigned jobs overdue", () => {
		const job = (status, scheduled_date) => ({ status, scheduled_date });
		expect(isOverdue(job("Assigned", "2026-11-03"), wednesday)).toBe(true);
		expect(isOverdue(job("Assigned", "2026-11-04"), wednesday)).toBe(false);
		expect(isOverdue(job("Done", "2026-11-01"), wednesday)).toBe(false);
		expect(isOverdue(job("Booked", "2026-11-01"), wednesday)).toBe(false);
	});

	it("shows money with its currency and people by initials", () => {
		expect(money({ amount: "1500.00", currency: "KES" })).toBe("KES 1,500.00");
		expect(initials("Achieng Odhiambo")).toBe("AO");
		expect(statusTone("Done")).toBe("green");
		expect(statusTone("Something new")).toBe("gray");
	});
});
