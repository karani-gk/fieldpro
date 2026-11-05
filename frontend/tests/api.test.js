import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "../src/lib/api.js";

function reply(status, body) {
	return vi.fn(async () => ({ ok: status < 400, status, json: async () => body }));
}

describe("ApiClient", () => {
	it("unwraps Frappe's message and drops empty params", async () => {
		const fetch = reply(200, { message: { data: [1], next_cursor: "c" } });
		const body = await new ApiClient({ fetch }).get("manage.jobs", { status: "Booked", q: "", technician: null });
		expect(body).toEqual({ data: [1], next_cursor: "c" });
		expect(fetch.mock.calls[0][0]).toBe("/api/method/fieldpro.api.v1.manage.jobs?status=Booked");
	});

	it("sends changes as JSON with the CSRF token", async () => {
		const fetch = reply(200, { message: { data: {} } });
		await new ApiClient({ fetch, csrfToken: () => "tok" }).post("manage.assign", { job: "J1" });
		const [, init] = fetch.mock.calls[0];
		expect(init.method).toBe("POST");
		expect(init.headers["X-Frappe-CSRF-Token"]).toBe("tok");
		expect(JSON.parse(init.body)).toEqual({ job: "J1" });
	});

	it("signs out through Frappe's logout with the CSRF token", async () => {
		const fetch = reply(200, {});
		await new ApiClient({ fetch, csrfToken: () => "tok" }).signOut();
		const [url, init] = fetch.mock.calls[0];
		expect([url, init.method, init.headers["X-Frappe-CSRF-Token"]]).toEqual(["/api/method/logout", "POST", "tok"]);
	});

	it("turns the error format into an ApiError", async () => {
		const fetch = reply(422, { error: { code: "invalid", message: "Pick a date", fields: { scheduled_date: "x" } } });
		const error = await new ApiClient({ fetch }).post("manage.assign").catch((e) => e);
		expect(error).toBeInstanceOf(ApiError);
		expect([error.status, error.code, error.message]).toEqual([422, "invalid", "Pick a date"]);
		expect(error.fields).toEqual({ scheduled_date: "x" });
	});

	it("sends a signed-out manager back to sign in", async () => {
		const onSignedOut = vi.fn();
		const fetch = reply(401, { error: { code: "unauthorized", message: "Sign in" } });
		await expect(new ApiClient({ fetch, onSignedOut }).get("manage.board")).rejects.toThrow("Sign in");
		expect(onSignedOut).toHaveBeenCalledOnce();
	});

	it("explains Frappe's own CSRF refusal and a lost connection", async () => {
		const csrf = reply(400, { exc_type: "CSRFTokenError" });
		expect((await new ApiClient({ fetch: csrf }).post("manage.act").catch((e) => e)).code).toBe("csrf");
		const offline = vi.fn(async () => {
			throw new TypeError("Failed to fetch");
		});
		expect((await new ApiClient({ fetch: offline }).get("manage.board").catch((e) => e)).code).toBe("network");
	});
});
