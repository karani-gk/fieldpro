// Every screen lives under /manage; Frappe sends all of those paths to www/manage.py, so a
// bookmarked or reloaded URL opens the right screen.
import { createRouter, createWebHistory } from "vue-router";

export const routes = [
	{ path: "/", name: "dashboard", component: () => import("./views/DashboardView.vue"), meta: { title: "Dashboard" } },
	{ path: "/board", name: "board", component: () => import("./views/BoardView.vue"), meta: { title: "Job board" } },
	{ path: "/jobs", name: "jobs", component: () => import("./views/JobsView.vue"), meta: { title: "Jobs" } },
	{ path: "/jobs/new", name: "new-job", component: () => import("./views/NewJobView.vue"), meta: { title: "New job" } },
	{ path: "/jobs/:id", name: "job", component: () => import("./views/JobDetailView.vue"), props: true, meta: { title: "Job" } },
	{ path: "/team", name: "team", component: () => import("./views/TeamView.vue"), meta: { title: "Technicians" } },
	{ path: "/:rest(.*)*", redirect: "/" },
];

export const router = createRouter({ history: createWebHistory("/manage/"), routes });

router.afterEach((to) => {
	document.title = `${to.meta.title || "Field Service"} · Field Service`;
});
