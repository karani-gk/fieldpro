// Dialogs any screen can open, rendered once by App.vue. "New job" opens from the sidebar, the
// Jobs page and the /manage/jobs/new URL (where Desk's "new Service Job" is redirected).
import { reactive } from "vue";

// `customer` ({id, name}) is filled in when booking from a customer's row.
export const dialogs = reactive({ newJob: false, customer: null });

export function openNewJob(customer = null) {
	// A click handler passes its event; only a customer ({id, name}) is kept.
	dialogs.customer = customer?.id ? customer : null;
	dialogs.newJob = true;
}
