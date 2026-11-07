<script setup>
// The jobs' invoices: what is drafted, owed and overdue, the finished jobs still waiting for an
// invoice, and every invoice filtered by status, customer and text. The filters live in the URL,
// like the Jobs list. ERPNext's permissions decide who sees this (invoice_desk.py).
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import BaseModal from "../components/BaseModal.vue";
import InvoiceDialog from "../components/InvoiceDialog.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { dayLabel, money } from "../lib/format.js";
import { INVOICE_TABS, invoiceTone } from "../lib/invoices.js";
import { api } from "../lib/server.js";
import { notify } from "../lib/toast.js";

const route = useRoute();
const router = useRouter();

const filters = ref(fromQuery(route.query));
const invoices = ref([]);
const cursor = ref(null);
const loading = ref(false);
const error = ref(null);
const summary = ref(null);
const making = ref(""); // the job whose invoice is being made
const submitting = ref(""); // the invoice being submitted
const confirming = ref(null); // the draft waiting for "Submit it?"
const confirmed = ref(null); // set when the manager said yes; acted on once the dialog has closed
const opened = ref(""); // the invoice shown in the details dialog

function fromQuery(query) {
	return { status: query.status || "", customer: query.customer || "", q: query.q || "" };
}

async function load({ more = false } = {}) {
	loading.value = true;
	error.value = null;
	try {
		const body = await api.get("manage.invoices", {
			...filters.value,
			cursor: more ? cursor.value : null,
			limit: 30,
		});
		invoices.value = more ? [...invoices.value, ...body.data] : body.data;
		cursor.value = body.next_cursor;
	} catch (exc) {
		error.value = exc;
	} finally {
		loading.value = false;
	}
}

async function loadSummary() {
	try {
		summary.value = (await api.get("manage.invoice_summary")).data;
	} catch (exc) {
		// The list shows the same error (usually "needs an accounts role"); log this one only.
		console.error("fieldpro: invoice summary", exc);
	}
}

// Typing in the search box waits for a pause before asking the server.
let typingTimer = null;
watch(
	filters,
	(value) => {
		clearTimeout(typingTimer);
		typingTimer = setTimeout(() => router.replace({ query: withoutEmpty(value) }), 250);
	},
	{ deep: true },
);
watch(
	() => route.query,
	(query) => {
		filters.value = fromQuery(query);
		load();
	},
);

function withoutEmpty(value) {
	return Object.fromEntries(Object.entries(value).filter(([, v]) => v));
}

function setStatus(status) {
	filters.value.status = filters.value.status === status ? "" : status;
}

async function makeInvoice(job) {
	making.value = job.id;
	try {
		const { data } = await api.post("manage.make_invoice", { job: job.id });
		notify(`${data.id} drafted for ${job.id}`);
		await Promise.all([load(), loadSummary()]);
	} catch (exc) {
		notify(exc.message, "error");
	} finally {
		making.value = "";
	}
}

async function submitInvoice(invoice) {
	submitting.value = invoice.id;
	try {
		const { data } = await api.post("manage.submit_invoice", { invoice: invoice.id });
		invoices.value = invoices.value.map((row) => (row.id === data.id ? data : row));
		notify(`${data.id} submitted`);
		loadSummary();
	} catch (exc) {
		notify(exc.message, "error");
	} finally {
		submitting.value = "";
	}
}

// The dialog submitted a draft: show the new status in the list and the totals.
function onChanged(row) {
	invoices.value = invoices.value.map((r) => (r.id === row.id ? row : r));
	loadSummary();
}

function onConfirmClosed() {
	const invoice = confirmed.value;
	confirming.value = null;
	confirmed.value = null;
	if (invoice) submitInvoice(invoice);
}

function refresh() {
	load();
	loadSummary();
}

onMounted(refresh);
</script>

<template>
	<div class="page">
		<div class="page-head">
			<div>
				<h1>Invoices</h1>
				<p>What the jobs have billed, and what customers still owe.</p>
			</div>
			<button class="btn" :disabled="loading" @click="refresh">
				<AppIcon name="refresh" :size="16" /> Refresh
			</button>
		</div>

		<div v-if="summary" class="totals">
			<button class="card total" :class="{ active: filters.status === 'Draft' }" @click="setStatus('Draft')">
				<span class="label">Drafts to submit</span>
				<strong>{{ summary.draft.count }}</strong>
				<span class="faint">{{ money(summary.draft.amount) || "Nothing" }}</span>
			</button>
			<button class="card total" :class="{ active: filters.status === 'Unpaid' }" @click="setStatus('Unpaid')">
				<span class="label">Owed by customers</span>
				<strong>{{ money(summary.unpaid.amount) || "0" }}</strong>
				<span class="faint">{{ summary.unpaid.count }} invoices</span>
			</button>
			<button
				class="card total"
				:class="{ active: filters.status === 'Overdue', late: summary.overdue.count }"
				@click="setStatus('Overdue')"
			>
				<span class="label">Overdue</span>
				<strong>{{ money(summary.overdue.amount) || "0" }}</strong>
				<span class="faint">{{ summary.overdue.count }} invoices</span>
			</button>
		</div>

		<section v-if="summary?.uninvoiced_jobs.length" class="card waiting">
			<header>
				<AppIcon name="alert" :size="18" />
				<div>
					<h2>Finished jobs with no invoice</h2>
					<p class="muted">The system drafts these within the hour. Draft one now if the customer is waiting.</p>
				</div>
			</header>
			<ul>
				<li v-for="job in summary.uninvoiced_jobs" :key="job.id">
					<RouterLink :to="`/jobs/${job.id}`">{{ job.id }}</RouterLink>
					<span>{{ job.customer.name }}</span>
					<span class="faint issue">{{ job.issue }}</span>
					<button class="btn btn-sm" :disabled="making === job.id" @click="makeInvoice(job)">
						{{ making === job.id ? "Drafting…" : "Draft invoice" }}
					</button>
				</li>
			</ul>
		</section>

		<div class="card toolbar">
			<label class="search-box">
				<AppIcon name="search" :size="16" />
				<input v-model="filters.q" class="input" placeholder="Search invoice, customer or job" />
			</label>
			<div class="tabs" role="tablist" aria-label="Status">
				<button
					class="tab"
					role="tab"
					:aria-selected="!filters.status"
					:class="{ active: !filters.status }"
					@click="filters.status = ''"
				>
					All
				</button>
				<button
					v-for="tab in INVOICE_TABS"
					:key="tab"
					class="tab"
					role="tab"
					:aria-selected="filters.status === tab"
					:class="{ active: filters.status === tab }"
					@click="filters.status = tab"
				>
					{{ tab }}
				</button>
			</div>
			<button v-if="filters.customer" class="btn btn-ghost btn-sm" @click="filters.customer = ''">
				<AppIcon name="x" :size="14" /> {{ filters.customer }}
			</button>
		</div>

		<div v-if="error" class="error-banner">{{ error.message }}</div>

		<div v-else class="card data-table-wrap">
			<table class="data-table">
				<thead>
					<tr>
						<th>Invoice</th>
						<th>Customer</th>
						<th>Job</th>
						<th>Date</th>
						<th>Status</th>
						<th class="num">Total</th>
						<th class="num">Owed</th>
						<th><span class="sr-only">Actions</span></th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="invoice in invoices"
						:key="invoice.id"
						class="clickable"
						tabindex="0"
						:title="`Open ${invoice.id}`"
						@click="opened = invoice.id"
						@keydown.enter.self="opened = invoice.id"
					>
						<td class="nowrap">
							<strong>{{ invoice.id }}</strong>
							<div v-if="invoice.due_date && !invoice.is_draft" class="faint small">
								Due {{ dayLabel(invoice.due_date) }}
							</div>
						</td>
						<td>{{ invoice.customer.name }}</td>
						<td class="nowrap"><RouterLink :to="`/jobs/${invoice.job}`" @click.stop>{{ invoice.job }}</RouterLink></td>
						<td class="nowrap">{{ dayLabel(invoice.posting_date) }}</td>
						<td><StatusBadge :status="invoice.status" :tone="invoiceTone(invoice.status)" /></td>
						<td class="num">{{ money(invoice.total) }}</td>
						<td class="num">{{ invoice.is_draft ? "" : money(invoice.outstanding) || "0" }}</td>
						<td>
							<!-- The row opens the invoice; its buttons do their own thing instead. -->
							<div class="row-actions" @click.stop>
								<button
									v-if="invoice.is_draft"
									class="btn btn-primary btn-sm"
									:disabled="submitting === invoice.id"
									@click="confirming = invoice"
								>
									{{ submitting === invoice.id ? "Submitting…" : "Submit" }}
								</button>
								<a :href="invoice.pdf_url" class="btn btn-sm" title="Download PDF" target="_blank">
									<AppIcon name="download" :size="15" /> PDF
								</a>
								<a :href="`/app/sales-invoice/${invoice.id}`" class="btn btn-ghost btn-sm" title="Open in Desk">
									<AppIcon name="external" :size="15" />
								</a>
							</div>
						</td>
					</tr>
					<tr v-if="!invoices.length && !loading" class="empty-row">
						<td colspan="8">No invoices match these filters.</td>
					</tr>
				</tbody>
			</table>
		</div>

		<div class="more">
			<button v-if="cursor" class="btn" :disabled="loading" @click="load({ more: true })">
				{{ loading ? "Loading…" : "Load more" }}
			</button>
			<span v-else-if="loading" class="faint">Loading…</span>
		</div>

		<InvoiceDialog v-if="opened" :id="opened" @close="opened = ''" @changed="onChanged" />

		<BaseModal v-if="confirming" :title="`Submit ${confirming.id}?`" @close="onConfirmClosed">
			<p class="muted">
				{{ money(confirming.total) }} to {{ confirming.customer.name }}. Submitting posts it to the accounts and
				takes the parts out of the technician's van. To change it afterwards, accounts must cancel it in Desk.
			</p>
			<template #footer="{ close }">
				<button class="btn" @click="close">Not yet</button>
				<button class="btn btn-primary" @click="confirmed = confirming; close()">Submit invoice</button>
			</template>
		</BaseModal>
	</div>
</template>

<style scoped>
.totals {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
	gap: 16px;
	margin-bottom: 16px;
}

.total {
	display: flex;
	flex-direction: column;
	gap: 4px;
	padding: 16px 18px;
	text-align: left;
	font: inherit;
	color: inherit;
	cursor: pointer;
	transition:
		border-color 0.15s ease,
		box-shadow 0.15s ease;
}

.total:hover {
	border-color: var(--border-strong);
	box-shadow: var(--shadow-lift);
}

.total.active {
	border-color: var(--brand);
	box-shadow: inset 0 0 0 1px var(--brand);
}

.total .label {
	font-size: 13px;
	font-weight: 500;
	color: var(--text-muted);
}

.total strong {
	font-size: 22px;
	font-variant-numeric: tabular-nums;
}

.total.late strong {
	color: var(--red-fg);
}

.waiting {
	padding: 16px 18px;
	margin-bottom: 16px;
	border-color: var(--orange-dot);
	background: var(--orange-bg);
}

.waiting header {
	display: flex;
	gap: 10px;
	color: var(--orange-fg);
}

.waiting h2 {
	font-size: 15px;
	font-weight: 600;
	color: var(--text);
}

.waiting p {
	margin: 2px 0 0;
	font-size: 13px;
}

.waiting ul {
	list-style: none;
	margin: 12px 0 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.waiting li {
	display: grid;
	grid-template-columns: 140px minmax(120px, 1fr) minmax(120px, 2fr) auto;
	align-items: center;
	gap: 12px;
	padding: 8px 10px;
	border-radius: var(--radius-sm);
	background: var(--surface);
}

.issue {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.tabs {
	display: flex;
	flex-wrap: wrap;
	gap: 4px;
	padding: 3px;
	border-radius: var(--radius-sm);
	background: var(--surface-muted);
	border: 1px solid var(--border);
}

.tab {
	padding: 5px 10px;
	border: 0;
	border-radius: 4px;
	background: none;
	color: var(--text-muted);
	font: inherit;
	font-size: 13px;
	font-weight: 500;
	cursor: pointer;
}

.tab:hover {
	color: var(--text);
}

.tab.active {
	background: var(--surface);
	color: var(--text);
	box-shadow: var(--shadow);
}

.clickable {
	cursor: pointer;
}

.clickable:focus-visible {
	outline: 2px solid var(--brand);
	outline-offset: -2px;
}

.nowrap {
	white-space: nowrap;
}

.small {
	font-size: 12px;
}

.more {
	display: flex;
	justify-content: center;
	margin-top: 16px;
}

@media (max-width: 760px) {
	.waiting li {
		grid-template-columns: 1fr auto;
	}

	.waiting li .issue,
	.waiting li span:not(.issue) {
		grid-column: 1;
	}
}
</style>
