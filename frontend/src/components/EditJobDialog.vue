<script setup>
// Edit what the job is and where: issue, description, priority, date, site, phone, estimate.
// The server decides what may change (services/dispatch.py Dispatcher.update).
import { ref } from "vue";
import { api } from "../lib/server.js";
import BaseModal from "./BaseModal.vue";

const PRIORITIES = ["Urgent", "Normal", "Low"];

const props = defineProps({ job: { type: Object, required: true } });
const emit = defineEmits(["close", "saved"]);

const form = ref({
	issue: props.job.issue,
	description: props.job.description,
	priority: props.job.priority,
	scheduled_date: props.job.scheduled_date || "",
	site_address: props.job.site_address,
	contact_phone: props.job.contact_phone,
	estimated_value: props.job.estimated_value_raw,
});
const saving = ref(false);
const error = ref(null);
const modal = ref(null);
let saved = null; // the updated job, handed over once the dialog has animated out

async function save() {
	saving.value = true;
	error.value = null;
	try {
		// An emptied date input gives "", which the server should store as no date.
		const changes = { ...form.value, scheduled_date: form.value.scheduled_date || null };
		saved = (await api.post("manage.update_job", { job: props.job.id, changes })).data;
		modal.value.close();
	} catch (exc) {
		error.value = exc;
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<BaseModal ref="modal" title="Edit job" wide @close="saved ? emit('saved', saved) : emit('close')">
		<form id="edit-job-form" class="form" @submit.prevent="save">
			<p class="muted wide intro">{{ job.id }} · {{ job.customer.name }}</p>
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
			<div v-if="error" class="error-banner wide">{{ error.message }}</div>
		</form>

		<template #footer="{ close }">
			<button type="button" class="btn" @click="close">Cancel</button>
			<button type="submit" form="edit-job-form" class="btn btn-primary" :disabled="saving">
				{{ saving ? "Saving…" : "Save changes" }}
			</button>
		</template>
	</BaseModal>
</template>

<style scoped>
.form {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 16px 20px;
}

.wide {
	grid-column: 1 / -1;
}

.intro {
	margin: -6px 0 0;
}

.error-banner {
	margin: 0;
}

@media (max-width: 600px) {
	.form {
		grid-template-columns: 1fr;
	}
}
</style>
