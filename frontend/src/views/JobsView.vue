<script setup>
// Every job, newest first, filtered by status, technician, priority and text. The filters live in
// the URL, so a dashboard card can open the list already filtered and the back button works.
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { dayLabel, initials, isOverdue } from "../lib/format.js";
import { openNewJob } from "../lib/dialogs.js";
import { api } from "../lib/server.js";

// The workflow's states (fixtures/workflow.json). A wrong name here only filters to nothing.
const STATUSES = [
	"Booked",
	"Assigned",
	"In Progress",
	"Pending Approval",
	"Awaiting Sign-off",
	"Rework",
	"Done",
	"Cancelled",
];
const PRIORITIES = ["Urgent", "Normal", "Low"];

const route = useRoute();
const router = useRouter();

const filters = ref(fromQuery(route.query));
const jobs = ref([]);
const cursor = ref(null);
const loading = ref(false);
const error = ref(null);
const technicians = ref([]);

function fromQuery(query) {
	return {
		status: query.status || "",
		technician: query.technician || "",
		priority: query.priority || "",
		q: query.q || "",
		// Set by a customer's "Jobs" button on the Customers screen.
		customer: query.customer || "",
	};
}

async function load({ more = false } = {}) {
	loading.value = true;
	error.value = null;
	try {
		const body = await api.get("manage.jobs", {
			...filters.value,
			cursor: more ? cursor.value : null,
			limit: 30,
		});
		jobs.value = more ? [...jobs.value, ...body.data] : body.data;
		cursor.value = body.next_cursor;
	} catch (exc) {
		error.value = exc;
	} finally {
		loading.value = false;
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

function clear() {
	filters.value = fromQuery({});
}

onMounted(async () => {
	load();
	try {
		technicians.value = (await api.get("manage.technicians")).data;
	} catch (exc) {
		console.error("fieldpro: technicians for the filter", exc);
	}
});
</script>

<template>
	<div class="page">
		<div class="page-head">
			<div>
				<h1>Jobs</h1>
				<p>Every service job, newest first.</p>
			</div>
			<button class="btn btn-primary" @click="openNewJob"><AppIcon name="plus" :size="16" /> New job</button>
		</div>

		<div class="filters card">
			<label class="search">
				<AppIcon name="search" :size="16" />
				<input v-model="filters.q" class="input" placeholder="Search job, issue, customer or technician" />
			</label>
			<select v-model="filters.status" class="select" aria-label="Status">
				<option value="">All statuses</option>
				<option v-for="s in STATUSES" :key="s">{{ s }}</option>
			</select>
			<select v-model="filters.technician" class="select" aria-label="Technician">
				<option value="">All technicians</option>
				<option v-for="t in technicians" :key="t.id" :value="t.id">{{ t.name }}</option>
			</select>
			<select v-model="filters.priority" class="select" aria-label="Priority">
				<option value="">Any priority</option>
				<option v-for="p in PRIORITIES" :key="p">{{ p }}</option>
			</select>
			<span v-if="filters.customer" class="chip">
				Customer: {{ filters.customer }}
				<button class="chip-x" aria-label="Show every customer" @click="filters.customer = ''">
					<AppIcon name="x" :size="12" />
				</button>
			</span>
			<button
				v-if="Object.values(filters).some(Boolean)"
				class="btn btn-ghost btn-sm"
				@click="clear"
			>
				Clear
			</button>
		</div>

		<div v-if="error" class="error-banner">{{ error.message }}</div>

		<div class="card table-wrap">
			<table>
				<thead>
					<tr>
						<th>Job</th>
						<th>Customer</th>
						<th>Status</th>
						<th>Technician</th>
						<th>Date</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="job in jobs"
						:key="job.id"
						tabindex="0"
						@click="router.push(`/jobs/${job.id}`)"
						@keydown.enter="router.push(`/jobs/${job.id}`)"
					>
						<td>
							<div class="issue">
								<span v-if="job.priority === 'Urgent'" class="urgent" title="Urgent">●</span>
								{{ job.issue }}
							</div>
							<div class="faint small">{{ job.id }}</div>
						</td>
						<td>{{ job.customer.name }}</td>
						<td><StatusBadge :status="job.status" /></td>
						<td>
							<span v-if="job.technician" class="tech">
								<span class="avatar">{{ initials(job.technician.name) }}</span>
								{{ job.technician.name }}
							</span>
							<span v-else class="unassigned">Unassigned</span>
						</td>
						<td :class="{ overdue: isOverdue(job) }">{{ dayLabel(job.scheduled_date) }}</td>
					</tr>
					<tr v-if="!jobs.length && !loading" class="empty-row">
						<td colspan="5">No jobs match these filters.</td>
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
	</div>
</template>

<style scoped>
.filters {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 10px;
	padding: 12px;
	margin-bottom: 16px;
}

.filters .select {
	width: auto;
	min-width: 150px;
}

.search {
	position: relative;
	display: flex;
	align-items: center;
	flex: 1;
	min-width: 240px;
	color: var(--text-faint);
}

.search svg {
	position: absolute;
	left: 10px;
}

.search .input {
	padding-left: 32px;
}

.chip {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	padding: 4px 6px 4px 10px;
	border-radius: 999px;
	background: var(--mint-soft);
	color: var(--brand-dark);
	font-size: 13px;
	font-weight: 550;
}

.chip-x {
	display: grid;
	place-items: center;
	width: 18px;
	height: 18px;
	border: 0;
	border-radius: 50%;
	background: none;
	color: inherit;
	cursor: pointer;
}

.chip-x:hover {
	background: var(--brand-soft);
}

.table-wrap {
	overflow-x: auto;
}

table {
	width: 100%;
	border-collapse: collapse;
}

th {
	text-align: left;
	padding: 10px 16px;
	font-size: 12px;
	font-weight: 600;
	color: var(--text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
	border-bottom: 1px solid var(--border);
	background: var(--surface-muted);
}

td {
	padding: 12px 16px;
	border-bottom: 1px solid var(--border);
	vertical-align: middle;
}

tbody tr {
	cursor: pointer;
}

tbody tr:hover,
tbody tr:focus-visible {
	background: var(--surface-muted);
	outline: none;
}

tbody tr:last-child td {
	border-bottom: 0;
}

.issue {
	font-weight: 550;
}

.urgent {
	color: var(--red-dot);
	margin-right: 2px;
}

.small {
	font-size: 12px;
}

.tech {
	display: inline-flex;
	align-items: center;
	gap: 8px;
}

.avatar {
	display: grid;
	place-items: center;
	width: 24px;
	height: 24px;
	border-radius: 50%;
	background: var(--mint-soft);
	color: var(--brand-dark);
	font-size: 10px;
	font-weight: 700;
}

.unassigned {
	color: var(--orange-fg);
	font-weight: 550;
}

.overdue {
	color: var(--red-fg);
	font-weight: 600;
}

.empty-row td {
	text-align: center;
	color: var(--text-muted);
	padding: 32px;
	cursor: default;
}

.more {
	display: flex;
	justify-content: center;
	margin-top: 16px;
}
</style>
