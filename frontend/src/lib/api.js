// Talks to fieldpro's API with the manager's Desk session (a cookie), the way Desk itself does.
// Changes are POSTs carrying the CSRF token the page was rendered with (www/manage.py).
// Every answer is {"message": {"data": ...}} or the one error format in fieldpro/api/errors.py.

export class ApiError extends Error {
	constructor(status, error = {}) {
		super(error.message || `The server answered ${status}.`);
		this.status = status;
		this.code = error.code || "unknown";
		this.fields = error.fields || {};
	}
}

const NETWORK_ERROR = { code: "network", message: "Cannot reach the server. Check your connection." };
const CSRF_ERROR = { code: "csrf", message: "Your session changed. Reload the page and try again." };

export class ApiClient {
	constructor({ fetch, csrfToken, onSignedOut, prefix = "/api/method/fieldpro.api.v1." } = {}) {
		this.fetch = fetch || ((...args) => globalThis.fetch(...args));
		this.csrfToken = csrfToken || (() => globalThis.csrf_token || "");
		this.onSignedOut = onSignedOut || (() => {});
		this.prefix = prefix;
	}

	/** GET a read endpoint, e.g. get("manage.jobs", { status: "Booked" }). Empty params are dropped. */
	async get(method, params = {}) {
		const query = new URLSearchParams(withoutEmpty(params)).toString();
		return this.send(this.prefix + method + (query ? `?${query}` : ""), { method: "GET" });
	}

	/** POST a change as JSON. */
	async post(method, body = {}) {
		return this.send(this.prefix + method, {
			method: "POST",
			headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": this.csrfToken() },
			body: JSON.stringify(body),
		});
	}

	/** End the session with Frappe's own logout: the manager is signed out of Desk too. */
	async signOut() {
		return this.send("/api/method/logout", {
			method: "POST",
			headers: { "X-Frappe-CSRF-Token": this.csrfToken() },
		});
	}

	/** The whole body ({data, next_cursor, has_more}), or an ApiError. */
	async send(url, init) {
		let response;
		try {
			response = await this.fetch(url, {
				...init,
				credentials: "same-origin",
				headers: { Accept: "application/json", ...init.headers },
			});
		} catch {
			throw new ApiError(0, NETWORK_ERROR);
		}
		const body = await response.json().catch(() => ({}));
		if (response.ok) return body.message ?? {};
		if (response.status === 401) this.onSignedOut();
		// Frappe refuses a bad CSRF token before our code runs, so it has Frappe's own shape.
		if (body.exc_type === "CSRFTokenError") throw new ApiError(response.status, CSRF_ERROR);
		throw new ApiError(response.status, body.error);
	}
}

function withoutEmpty(params) {
	return Object.fromEntries(
		Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""),
	);
}
