// Managers keep Field Service in the manager app. Opening the Field Service workspace in Desk
// (the home icon, the sidebar, the search bar) happens inside Desk's single-page app, where no
// request reaches the server's redirect (landing_hooks.py), so this sends them to /manage.
// The server says who in the boot (landing_hooks.add_manager_app_to_boot). The workspace itself
// stays reachable with ?desk=1 (/desk/field-service?desk=1), e.g. to edit its cards.
(function () {
	const WORKSPACE = "Field Service";

	function opens_field_service() {
		const route = frappe.get_route() || [];
		return route[0] === "Workspaces" && route[route.length - 1] === WORKSPACE;
	}

	frappe.router.on("change", () => {
		const app = frappe.boot.fieldpro_manager_app;
		const stay = new URLSearchParams(window.location.search).get("desk") === "1";
		if (app && !stay && opens_field_service()) window.location.assign(app);
	});
})();
