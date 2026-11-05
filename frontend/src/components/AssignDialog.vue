<script setup>
// Choose who does a job and when. Each technician shows their open work, so the manager can
// spread the load. The server applies the Assign action (services/dispatch.py Dispatcher.assign).
import { computed, onMounted, ref } from "vue";
import { isoDay } from "../lib/format.js";
import { api } from "../lib/server.js";
import BaseModal from "./BaseModal.vue";

const props = defineProps({ job: { type: Object, required: true } });
const emit = defineEmits(["close", "assigned"]);

const technicians = ref([]);
const chosen = ref(props.job.technician?.id || "");
const date = ref(props.job.scheduled_date && props.job.scheduled_date >= isoDay() ? props.job.scheduled_date : isoDay());
const saving = ref(false);
const error = ref("");

const reassigning = computed(() => Boolean(props.job.technician));

onMounted(async () => {
	try {
		technicians.value = (await api.get("manage.technicians")).data;
	} catch (exc) {
		error.value = exc.message;
	}
});

async function save() {
	saving.value = true;
	error.value = "";
	try {
		const { data } = await api.post("manage.assign", {
			job: props.job.id,
			technician: chosen.value,
			scheduled_date: date.value,
		});
		emit("assigned", data);
	} catch (exc) {
		error.value = exc.message;
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<BaseModal :title="reassigning ? 'Reassign job' : 'Assign job'" @close="emit('close')">
		<p class="muted job">{{ job.id }} · {{ job.issue }} · {{ job.customer.name }}</p>
		<div class="field">
			<label>Technician</label>
			<div class="people" role="radiogroup">
				<label
					v-for="tech in technicians"
					:key="tech.id"
					class="person"
					:class="{ chosen: chosen === tech.id }"
				>
					<input v-model="chosen" type="radio" name="technician" :value="tech.id" />
					<span class="name">{{ tech.name }}</span>
					<span class="load">
						{{ tech.open_jobs }} open · {{ tech.today }} today
						<span v-if="tech.overdue" class="late">· {{ tech.overdue }} late</span>
					</span>
				</label>
				<p v-if="!technicians.length && !error" class="faint">Loading technicians…</p>
			</div>
		</div>
		<div class="field">
			<label for="assign-date">Date</label>
			<input id="assign-date" v-model="date" class="input" type="date" :min="isoDay()" />
		</div>
		<p v-if="error" class="field-error">{{ error }}</p>
		<template #footer>
			<button class="btn" @click="emit('close')">Cancel</button>
			<button class="btn btn-primary" :disabled="!chosen || saving" @click="save">
				{{ saving ? "Saving…" : reassigning ? "Reassign" : "Assign" }}
			</button>
		</template>
	</BaseModal>
</template>

<style scoped>
.job {
	margin: 0;
	font-size: 13px;
}

.people {
	display: flex;
	flex-direction: column;
	gap: 6px;
	max-height: 260px;
	overflow-y: auto;
}

.person {
	display: grid;
	grid-template-columns: auto 1fr;
	grid-template-rows: auto auto;
	column-gap: 10px;
	align-items: center;
	padding: 8px 10px;
	border: 1px solid var(--border);
	border-radius: var(--radius-sm);
	cursor: pointer;
	color: var(--text) !important;
	font-size: 14px !important;
}

.person input {
	grid-row: span 2;
	accent-color: var(--brand);
}

.person.chosen {
	border-color: var(--brand);
	background: var(--mint-soft);
}

.name {
	font-weight: 600;
}

.load {
	font-size: 12px;
	color: var(--text-muted);
	font-weight: 400;
}

.late {
	color: var(--red-fg);
}
</style>
