import { describe, expect, it } from "vitest";
import { actionInto, dropAction, moveCard, needsAssignDialog } from "../src/lib/board.js";

const actions = [
	{ action: "Assign", next_status: "Assigned" },
	{ action: "Cancel", next_status: "Cancelled" },
];

describe("board rules", () => {
	it("accepts a card only where an allowed action leads", () => {
		expect(actionInto("Assigned", actions).action).toBe("Assign");
		expect(actionInto("Done", actions)).toBeNull();
	});

	it("lets a Booked job be dropped on Assigned before the server can offer Assign", () => {
		const onlyCancel = [{ action: "Cancel", next_status: "Cancelled" }];
		expect(dropAction({ status: "Booked" }, "Assigned", onlyCancel).action).toBe("Assign");
		expect(dropAction({ status: "Pending Approval" }, "Assigned", onlyCancel)).toBeNull();
		expect(dropAction({ status: "Booked" }, "Done", onlyCancel)).toBeNull();
	});

	it("asks for a technician before assigning", () => {
		expect(needsAssignDialog(actions[0])).toBe(true);
		expect(needsAssignDialog({ action: "Approve" })).toBe(false);
	});

	it("moves a card to the top of its new column", () => {
		const columns = [
			{ status: "Pending Approval", jobs: [{ id: "J1", status: "Pending Approval" }] },
			{ status: "Awaiting Sign-off", jobs: [{ id: "J2", status: "Awaiting Sign-off" }] },
		];
		const after = moveCard(columns, "J1", "Awaiting Sign-off");
		expect(after[0].jobs).toEqual([]);
		expect(after[1].jobs.map((j) => [j.id, j.status])).toEqual([
			["J1", "Awaiting Sign-off"],
			["J2", "Awaiting Sign-off"],
		]);
		expect(columns[0].jobs).toHaveLength(1); // the original is untouched, for rolling back
		expect(moveCard(columns, "missing", "Done")).toBe(columns);
	});
});
