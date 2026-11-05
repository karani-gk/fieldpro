// Dialogs any screen can open, rendered once by App.vue. "New job" opens from the sidebar, the
// Jobs page and the /manage/jobs/new URL (where Desk's "new Service Job" is redirected).
import { reactive } from "vue";

export const dialogs = reactive({ newJob: false });

export function openNewJob() {
	dialogs.newJob = true;
}
