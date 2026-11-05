// What dropping a card on a column means. The server lists the actions this manager may take on
// the job now (workflow.actions); a column accepts the card only if one of them leads there.

/** The action that moves a job into `status`, or null when no allowed action does. */
export function actionInto(status, actions) {
	return actions.find((a) => a.next_status === status) || null;
}

/** The action a drop takes, or null. A Booked job dropped on Assigned means "assign it": the
 * workflow's Assign transition has the condition doc.technician, so the server cannot offer it
 * until the assign dialog has chosen someone. */
export function dropAction(job, status, actions) {
	if (job.status === "Booked" && status === "Assigned") return { action: "Assign", next_status: "Assigned" };
	return actionInto(status, actions);
}

/** Assign needs a technician (and maybe a date) first, so it opens a dialog; others apply at once. */
export function needsAssignDialog(action) {
	return action?.action === "Assign";
}

/** The board after moving one card, so the screen answers before the server does. */
export function moveCard(columns, jobId, toStatus) {
	let moved = null;
	const without = columns.map((column) => {
		const jobs = column.jobs.filter((job) => {
			if (job.id !== jobId) return true;
			moved = job;
			return false;
		});
		return { ...column, jobs };
	});
	if (!moved) return columns;
	return without.map((column) =>
		column.status === toStatus ? { ...column, jobs: [{ ...moved, status: toStatus }, ...column.jobs] } : column,
	);
}
