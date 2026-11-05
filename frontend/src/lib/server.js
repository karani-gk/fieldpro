// The one API client the screens share, and what the page told us about the signed-in manager.
import { ApiClient } from "./api.js";

export const boot = globalThis.fieldpro_boot || { user: "", full_name: "", currency: "", company: "" };

export const api = new ApiClient({
	// A session that ended (signed out in another tab, expired) goes back to the sign-in page.
	onSignedOut: () => {
		const here = window.location.pathname + window.location.search;
		window.location.href = `/login?redirect-to=${encodeURIComponent(here)}`;
	},
});
