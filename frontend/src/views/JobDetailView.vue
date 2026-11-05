<script setup>
// One job: what is wrong and where, who does it and when, the work recorded on each visit, the
// customer's sign-off and the invoice. The buttons are the workflow actions the server says this
// manager may take now, plus Assign, which needs a technician and a date first.
import { computed, ref, watch } from "vue";
import AppIcon from "../components/AppIcon.vue";
import AssignDialog from "../components/AssignDialog.vue";
import BaseModal from "../components/BaseModal.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { dateTime, dayLabel, initials, isOverdue, money } from "../lib/format.js";
import { api } from "../lib/server.js";
import { notify } from "../lib/toast.js";

const props = defineProps({ id: { type: String, required: true } });

const REASSIGNABLE = ["Booked", "Assigned", "Rework"];
const ACTION_LOOK = {
	Approve: { label: "Approve work", kind: "btn-primary", icon: "check" },
	"Send Back": { label: "Send back", kind: "", icon: "back" },
	Cancel: { label: "Cancel job", kind: "btn-danger", icon: "x" },
};
const PRIORITIES = ["Urgent", "Normal", "Low"];

const job = ref(null);
const error = ref(null);
const busy = ref(false);
const assigning = ref(false);
const confirming = ref(null); // the action waiting for "Are you sure?"
const editing = ref(false);
const form = ref({});
const formError = ref(null);

// Assign has its own dialog; the rest of the server's actions become buttons.
const actionButtons = computed(() => (job.value?.actions || []).filter((a) => a.action !== "Assign"));
const canAssign = computed(() => job.value && REASSIGNABLE.includes(job.value.status));
const pdfUrl = computed(
	() =>
		`/api/method/frappe.utils.print_format.download_pdf?doctype=Service%20Job&name=${encodeURIComponent(props.id)}&format=Job%20Card`,
);

async function load() {
	error.value = null;
	try {
		job.value = (await api.get("manage.job", { job: props.id })).data;
	} catch (exc) {
		error.value = exc;
	}
}
watch(() => props.id, load, { immediate: true });

async function act(action) {
	confirming.value = null;
	busy.value = true;
	try {
		job.value = (await api.post("manage.act", { job: props.id, action })).data;
		notify(`${action}: done`);
	} catch (exc) {
		notify(exc.message, "error");
	} finally {
		busy.value = false;
	}
}

function onAction(action) {
	if (action === "Cancel") confirming.value = action;
	else act(action);
}

function onAssigned(updated) {
	assigning.value = false;
	job.value = updated;
	notify(`Assigned to ${updated.technician.name}`);
}

function startEdit() {
	const j = job.value;
	form.value = {
		issue: j.issue,
		description: j.description,
		priority: j.priority,
		scheduled_date: j.scheduled_date || "",
		site_address: j.site_address,
		contact_phone: j.contact_phone,
		estimated_value: j.estimated_value_raw,
	};
	formError.value = null;
	editing.value = true;
}

async function saveEdit() {
	busy.value = true;
	formError.value = null;
	try {
		// An emptied date input gives "", which the server should store as no date.
		const changes = { ...form.value, scheduled_date: form.value.scheduled_date || null };
		job.value = (await api.post("manage.update_job", { job: props.id, changes })).data;
		editing.value = false;
		notify("Job updated");
	} catch (exc) {
		formError.value = exc;
	} finally {
		busy.value = false;
	}
}
</script>

<template>
	<div class="page">
		<RouterLink to="/jobs" class="back"><AppIcon name="back" :size="16" /> Jobs</RouterLink>

		<div v-if="error" class="error-banner">{{ error.message }}</div>
		<div v-else-if="!job" class="faint">Loading…</div>

		<template v-else>
			<div class="head">
				<div class="title">
					<div class="title-top">
						<span class="faint">{{ job.id }}</span>
						<StatusBadge :status="job.status" />
						<span v-if="job.priority === 'Urgent'" class="urgent">Urgent</span>
						<span v-if="job.needs_approval" class="tag">Needs approval</span>
					</div>
					<h1>{{ job.issue }}</h1>
					<p class="muted">{{ job.customer.name }} · booked {{ dateTime(job.created_at) }} via {{ job.source }}</p>
				</div>
				<div class="actions">
					<button v-if="canAssign" class="btn" :class="{ 'btn-primary': !job.technician }" @click="assigning = true">
						<AppIcon name="user" :size="16" /> {{ job.technician ? "Reassign" : "Assign" }}
					</button>
					<button
						v-for="a in actionButtons"
						:key="a.action"
						class="btn"
						:class="ACTION_LOOK[a.action]?.kind"
						:disabled="busy"
						@click="onAction(a.action)"
					>
						<AppIcon :name="ACTION_LOOK[a.action]?.icon || 'check'" :size="16" />
						{{ ACTION_LOOK[a.action]?.label || a.action }}
					</button>
				</div>
			</div>

			<div class="grid">
				<div class="main-col">
					<section class="card section">
						<header>
							<h2>Details</h2>
							<button v-if="!editing" class="btn btn-sm" @click="startEdit">Edit</button>
						</header>

						<form v-if="editing" class="edit" @submit.prevent="saveEdit">
							<div class="field wide">
								<label for="f-issue">Issue</label>
								<input id="f-issue" v-model="form.issue" class="input" required />
							</div>
							<div class="field wide">
								<label for="f-desc">Description</label>
								<textarea id="f-desc" v-model="form.description" class="input" />
							</div>
							<div class="field">
								<label for="f-priority">Priority</label>
								<select id="f-priority" v-model="form.priority" class="select">
									<option v-for="p in PRIORITIES" :key="p">{{ p }}</option>
								</select>
							</div>
							<div class="field">
								<label for="f-date">Date</label>
								<input id="f-date" v-model="form.scheduled_date" class="input" type="date" />
							</div>
							<div class="field">
								<label for="f-phone">Contact phone</label>
								<input id="f-phone" v-model="form.contact_phone" class="input" type="tel" />
							</div>
							<div class="field">
								<label for="f-value">Estimated value ({{ job.estimated_value.currency }})</label>
								<input id="f-value" v-model="form.estimated_value" class="input" type="number" min="0" step="0.01" />
							</div>
							<div class="field wide">
								<label for="f-site">Site address</label>
								<textarea id="f-site" v-model="form.site_address" class="input" rows="2" />
							</div>
							<p v-if="formError" class="field-error wide">{{ formError.message }}</p>
							<div class="edit-buttons wide">
								<button type="button" class="btn" @click="editing = false">Cancel</button>
								<button type="submit" class="btn btn-primary" :disabled="busy">Save</button>
							</div>
						</form>

						<dl v-else class="facts">
							<div class="wide">
								<dt>Description</dt>
								<dd>{{ job.description || "—" }}</dd>
							</div>
							<div>
								<dt><AppIcon name="pin" :size="14" /> Site</dt>
								<dd class="pre">{{ job.site_address || "—" }}</dd>
							</div>
							<div>
								<dt><AppIcon name="phone" :size="14" /> Contact</dt>
								<dd>
									<a v-if="job.contact_phone" :href="`tel:${job.contact_phone}`">{{ job.contact_phone }}</a>
									<template v-else>—</template>
								</dd>
							</div>
							<div>
								<dt>Priority</dt>
								<dd>{{ job.priority }}</dd>
							</div>
							<div>
								<dt>Estimated value</dt>
								<dd>{{ money(job.estimated_value) }}</dd>
							</div>
						</dl>
					</section>

					<section class="card section">
						<header>
							<h2>Work done</h2>
							<span class="muted small">{{ job.total_hours }} h · parts {{ money(job.parts_total) }}</span>
						</header>
						<p v-if="!job.visits.length" class="muted">No visits yet.</p>
						<ol v-else class="visits">
							<li v-for="visit in job.visits" :key="visit.id" class="visit">
								<div class="visit-head">
									<strong>{{ dateTime(visit.started_at) }}</strong>
									<span class="muted">
										→ {{ visit.ended_at ? dateTime(visit.ended_at) : "still on site" }} · {{ visit.hours }} h
									</span>
									<span v-if="visit.status === 'Open'" class="live">On site now</span>
								</div>
								<p v-if="visit.notes" class="notes">{{ visit.notes }}</p>
								<table v-if="visit.parts.length" class="parts">
									<tr v-for="part in visit.parts" :key="part.id">
										<td>{{ part.item.name }}</td>
										<td class="num">{{ part.qty }} {{ part.uom }}</td>
										<td class="num">{{ money(part.amount) }}</td>
									</tr>
								</table>
								<div v-if="visit.photos.length" class="photos">
									<a v-for="photo in visit.photos" :key="photo.id" :href="photo.url" target="_blank" rel="noopener">
										<img :src="photo.url" :alt="photo.name" loading="lazy" />
									</a>
								</div>
							</li>
						</ol>
					</section>
				</div>

				<aside class="side-col">
					<section class="card section">
						<h2>Assignment</h2>
						<div v-if="job.technician" class="person">
							<span class="avatar">{{ initials(job.technician.name) }}</span>
							<span>
								<strong>{{ job.technician.name }}</strong>
								<small class="muted">Technician</small>
							</span>
						</div>
						<p v-else class="unassigned">No technician yet</p>
						<div class="date-row" :class="{ overdue: isOverdue(job) }">
							<AppIcon :name="isOverdue(job) ? 'alert' : 'calendar'" :size="16" />
							{{ dayLabel(job.scheduled_date) }}
							<span v-if="job.scheduled_date" class="faint">({{ job.scheduled_date }})</span>
						</div>
					</section>

					<section v-if="job.signed_off || job.rejection_reason" class="card section">
						<h2>Customer sign-off</h2>
						<template v-if="job.signed_off">
							<p><strong>{{ job.signed_off.by }}</strong><br /><span class="muted small">{{ dateTime(job.signed_off.at) }}</span></p>
							<img v-if="job.signature_url" :src="job.signature_url" alt="Customer signature" class="signature" />
						</template>
						<div v-if="job.rejection_reason" class="rejected">
							<strong>Rejected:</strong> {{ job.rejection_reason }}
						</div>
					</section>

					<section class="card section">
						<h2>Billing</h2>
						<p v-if="job.invoice">
							<a :href="`/app/sales-invoice/${job.invoice}`">{{ job.invoice }}</a>
							<span class="tag" :class="job.payment_status === 'Paid' ? 'paid' : ''">{{ job.payment_status }}</span>
						</p>
						<p v-else class="muted small">A draft invoice is made when the job is done.</p>
					</section>

					<section class="card section links">
						<a :href="pdfUrl" target="_blank" rel="noopener"><AppIcon name="file" :size="16" /> Job card PDF</a>
						<a :href="`/app/service-job/${job.id}`"><AppIcon name="external" :size="16" /> Open in Desk</a>
					</section>
				</aside>
			</div>
		</template>

		<AssignDialog v-if="assigning" :job="job" @close="assigning = false" @assigned="onAssigned" />
		<BaseModal v-if="confirming" title="Cancel this job?" @close="confirming = null">
			<p class="muted">The customer and technician will see it as cancelled. This cannot be undone.</p>
			<template #footer>
				<button class="btn" @click="confirming = null">Keep job</button>
				<button class="btn btn-danger" @click="act(confirming)">Cancel job</button>
			</template>
		</BaseModal>
	</div>
</template>

<style scoped>
.back {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	margin-bottom: 14px;
	color: var(--text-muted);
	font-weight: 500;
}

.head {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 20px;
	flex-wrap: wrap;
	margin-bottom: 22px;
}

.title-top {
	display: flex;
	align-items: center;
	gap: 8px;
	margin-bottom: 6px;
	font-size: 13px;
}

.title h1 {
	font-size: 24px;
	font-weight: 650;
	letter-spacing: -0.01em;
}

.title p {
	margin: 6px 0 0;
}

.urgent {
	color: var(--red-fg);
	font-weight: 600;
}

.tag {
	display: inline-block;
	padding: 1px 8px;
	border-radius: 999px;
	background: var(--orange-bg);
	color: var(--orange-fg);
	font-size: 12px;
	font-weight: 550;
	margin-left: 6px;
}

.tag.paid {
	background: var(--green-bg);
	color: var(--green-fg);
}

.actions {
	display: flex;
	gap: 8px;
	flex-wrap: wrap;
}

.grid {
	display: grid;
	grid-template-columns: minmax(0, 1fr) 320px;
	gap: 16px;
	align-items: start;
}

.main-col,
.side-col {
	display: flex;
	flex-direction: column;
	gap: 16px;
}

.section {
	padding: 16px 18px;
}

.section header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 12px;
}

.section h2 {
	font-size: 15px;
	font-weight: 600;
	margin-bottom: 10px;
}

.section header h2 {
	margin: 0;
}

.section p {
	margin: 0;
}

.small {
	font-size: 12px;
}

.facts,
.edit {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 14px 20px;
	margin: 0;
}

.wide {
	grid-column: 1 / -1;
}

dt {
	display: flex;
	align-items: center;
	gap: 4px;
	font-size: 12px;
	font-weight: 500;
	color: var(--text-muted);
	margin-bottom: 2px;
}

dd {
	margin: 0;
}

.pre {
	white-space: pre-line;
}

.edit-buttons {
	display: flex;
	justify-content: flex-end;
	gap: 8px;
}

.visits {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	gap: 14px;
}

.visit {
	padding-left: 14px;
	border-left: 2px solid var(--mint);
}

.visit-head {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
	align-items: baseline;
}

.live {
	padding: 1px 8px;
	border-radius: 999px;
	background: var(--amber-bg);
	color: var(--amber-fg);
	font-size: 12px;
	font-weight: 600;
}

.notes {
	margin: 6px 0 0 !important;
	white-space: pre-line;
}

.parts {
	width: 100%;
	margin-top: 8px;
	border-collapse: collapse;
	font-size: 13px;
}

.parts td {
	padding: 4px 0;
	border-bottom: 1px dashed var(--border);
}

.num {
	text-align: right;
	white-space: nowrap;
	padding-left: 12px !important;
}

.photos {
	display: flex;
	flex-wrap: wrap;
	gap: 8px;
	margin-top: 10px;
}

.photos img {
	width: 88px;
	height: 88px;
	object-fit: cover;
	border-radius: var(--radius-sm);
	border: 1px solid var(--border);
}

.person {
	display: flex;
	align-items: center;
	gap: 10px;
}

.person small {
	display: block;
}

.avatar {
	display: grid;
	place-items: center;
	width: 36px;
	height: 36px;
	border-radius: 50%;
	background: var(--mint-soft);
	color: var(--brand-dark);
	font-weight: 700;
	font-size: 13px;
}

.unassigned {
	color: var(--orange-fg) !important;
	font-weight: 550;
}

.date-row {
	display: flex;
	align-items: center;
	gap: 6px;
	margin-top: 12px;
}

.date-row.overdue {
	color: var(--red-fg);
	font-weight: 600;
}

.signature {
	display: block;
	max-width: 100%;
	max-height: 110px;
	margin-top: 10px;
	padding: 6px;
	border: 1px solid var(--border);
	border-radius: var(--radius-sm);
	background: #fff;
}

.rejected {
	margin-top: 10px;
	padding: 8px 10px;
	border-radius: var(--radius-sm);
	background: var(--red-bg);
	color: var(--red-fg);
}

.links {
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.links a {
	display: inline-flex;
	align-items: center;
	gap: 8px;
	font-weight: 500;
}

@media (max-width: 960px) {
	.grid {
		grid-template-columns: 1fr;
	}
}

@media (max-width: 600px) {
	.facts,
	.edit {
		grid-template-columns: 1fr;
	}
}
</style>
