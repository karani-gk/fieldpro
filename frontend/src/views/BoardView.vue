<script setup>
// One column per workflow state. Drag a card to another column to take the action that leads
// there; the server says which actions this manager may take on the job now, so only those
// columns light up. Assign asks for a technician and date first.
import { computed, ref } from "vue";
import AppIcon from "../components/AppIcon.vue";
import AssignDialog from "../components/AssignDialog.vue";
import JobCard from "../components/JobCard.vue";
import { dropAction, moveCard, needsAssignDialog } from "../lib/board.js";
import { statusTone } from "../lib/format.js";
import { api } from "../lib/server.js";
import { notify } from "../lib/toast.js";
import { useRequest } from "../lib/useRequest.js";

const { data, error, loading, reload } = useRequest(async () => (await api.get("manage.board")).data, {
	refreshSeconds: 60,
});

const search = ref("");
const dragging = ref(null); // { job, actions, ready }
const hovered = ref("");
const assigning = ref(null);

const columns = computed(() => {
	const text = search.value.trim().toLowerCase();
	if (!data.value) return [];
	if (!text) return data.value;
	const matches = (job) =>
		[job.id, job.issue, job.customer.name, job.technician?.name || ""].some((v) =>
			v.toLowerCase().includes(text),
		);
	return data.value.map((column) => ({ ...column, jobs: column.jobs.filter(matches) }));
});

async function onDragStart(event, job) {
	event.dataTransfer.effectAllowed = "move";
	event.dataTransfer.setData("text/plain", job.id);
	// A quick drag can drop before the server answers, so the drop waits for `ready`.
	const ready = api
		.get("workflow.actions", { job: job.id })
		.then(({ data }) => data)
		.catch((exc) => {
			notify(exc.message, "error");
			return [];
		});
	dragging.value = { job, actions: [], ready };
	const actions = await ready;
	if (dragging.value?.job.id === job.id) dragging.value = { job, actions, ready };
}

function onDragEnd() {
	dragging.value = null;
	hovered.value = "";
}

function canDrop(status) {
	return Boolean(dragging.value && dropAction(dragging.value.job, status, dragging.value.actions));
}

async function onDrop(status) {
	const drag = dragging.value;
	onDragEnd();
	if (!drag) return;
	const action = dropAction(drag.job, status, await drag.ready);
	if (!action) return;
	if (needsAssignDialog(action)) {
		assigning.value = drag.job;
		return;
	}
	const before = data.value;
	data.value = moveCard(before, drag.job.id, status);
	try {
		await api.post("manage.act", { job: drag.job.id, action: action.action });
		notify(`${drag.job.id}: ${action.action} done`);
	} catch (exc) {
		data.value = before;
		notify(exc.message, "error");
	}
	reload();
}

function onAssigned(job) {
	assigning.value = null;
	notify(`${job.id} assigned to ${job.technician.name}`);
	reload();
}
</script>

<template>
	<div class="page page-wide board-page">
		<div class="page-head">
			<div>
				<h1>Job board</h1>
				<p>Drag a card to move the job on: assign, approve or send back.</p>
			</div>
			<div class="tools">
				<label class="search">
					<AppIcon name="search" :size="16" />
					<input v-model="search" class="input" placeholder="Filter cards" />
				</label>
				<button class="btn" :disabled="loading" @click="reload">
					<AppIcon name="refresh" :size="16" /> Refresh
				</button>
			</div>
		</div>

		<div v-if="error" class="error-banner">{{ error.message }}</div>

		<div class="columns">
			<section
				v-for="column in columns"
				:key="column.status"
				class="column"
				:class="{
					droppable: canDrop(column.status),
					hovered: hovered === column.status && canDrop(column.status),
					dimmed: dragging && !canDrop(column.status) && dragging.job.status !== column.status,
				}"
				@dragover.prevent="hovered = column.status"
				@dragleave="hovered = ''"
				@drop.prevent="onDrop(column.status)"
			>
				<header>
					<span class="dot" :style="{ background: `var(--${statusTone(column.status)}-dot)` }" />
					<h2>{{ column.status }}</h2>
					<span class="count">{{ column.jobs.length }}</span>
				</header>
				<div class="cards">
					<JobCard
						v-for="job in column.jobs"
						:key="job.id"
						:job="job"
						draggable
						@dragstart="onDragStart($event, job)"
						@dragend="onDragEnd"
					/>
					<p v-if="!column.jobs.length" class="none">No jobs</p>
					<p v-if="column.status === 'Done' && column.jobs.length" class="note">Last 7 days</p>
				</div>
			</section>
		</div>

		<AssignDialog v-if="assigning" :job="assigning" @close="assigning = null" @assigned="onAssigned" />
	</div>
</template>

<style scoped>
.board-page {
	display: flex;
	flex-direction: column;
	height: 100vh;
	padding-bottom: 16px;
}

.tools {
	display: flex;
	gap: 8px;
}

.search {
	position: relative;
	display: flex;
	align-items: center;
	color: var(--text-faint);
}

.search svg {
	position: absolute;
	left: 10px;
}

.search .input {
	width: 220px;
	padding-left: 32px;
}

.columns {
	display: grid;
	grid-auto-flow: column;
	grid-auto-columns: minmax(260px, 1fr);
	gap: 14px;
	flex: 1;
	min-height: 0;
	overflow-x: auto;
	padding-bottom: 8px;
}

.column {
	display: flex;
	flex-direction: column;
	min-height: 0;
	background: #eaf0ee;
	border: 2px solid transparent;
	border-radius: var(--radius);
	transition: border-color 0.15s, background 0.15s, opacity 0.15s;
}

.column.droppable {
	border-color: var(--mint);
	border-style: dashed;
}

.column.hovered {
	background: var(--mint-soft);
	border-color: var(--brand);
}

.column.dimmed {
	opacity: 0.5;
}

.column header {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 12px 12px 8px;
}

.column h2 {
	font-size: 13px;
	font-weight: 650;
}

.dot {
	width: 8px;
	height: 8px;
	border-radius: 50%;
}

.count {
	margin-left: auto;
	font-size: 12px;
	font-weight: 600;
	color: var(--text-muted);
}

.cards {
	display: flex;
	flex-direction: column;
	gap: 8px;
	padding: 0 8px 10px;
	overflow-y: auto;
}

.none,
.note {
	margin: 4px 0;
	text-align: center;
	font-size: 12px;
	color: var(--text-faint);
}

@media (max-width: 760px) {
	.board-page {
		height: auto;
	}

	.search .input {
		width: 160px;
	}
}
</style>
