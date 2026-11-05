<script setup>
import { computed } from "vue";
import { dayLabel, initials, isOverdue } from "../lib/format.js";
import AppIcon from "./AppIcon.vue";
import StatusBadge from "./StatusBadge.vue";

const props = defineProps({
	job: { type: Object, required: true },
	showStatus: { type: Boolean, default: false },
	draggable: { type: Boolean, default: false },
});
const overdue = computed(() => isOverdue(props.job));
</script>

<template>
	<RouterLink
		:to="`/jobs/${job.id}`"
		class="job-card"
		:class="{ urgent: job.priority === 'Urgent' }"
		:draggable="draggable"
	>
		<div class="top">
			<span class="id">{{ job.id }}</span>
			<span v-if="job.priority === 'Urgent'" class="flag">Urgent</span>
			<StatusBadge v-if="showStatus" :status="job.status" class="status" />
		</div>
		<div class="issue">{{ job.issue }}</div>
		<div class="customer">{{ job.customer.name }}</div>
		<div class="meta">
			<span class="date" :class="{ overdue }">
				<AppIcon :name="overdue ? 'alert' : 'calendar'" :size="14" />
				{{ dayLabel(job.scheduled_date) }}
			</span>
			<span v-if="job.technician" class="tech" :title="job.technician.name">
				<span class="avatar">{{ initials(job.technician.name) }}</span>
				{{ job.technician.name.split(" ")[0] }}
			</span>
			<span v-else class="tech unassigned">Unassigned</span>
		</div>
	</RouterLink>
</template>

<style scoped>
.job-card {
	display: block;
	padding: 12px 12px 10px;
	background: var(--surface);
	border: 1px solid var(--border);
	border-radius: var(--radius-sm);
	color: var(--text);
	box-shadow: 0 1px 2px rgb(15 42 36 / 0.04);
	transition: box-shadow 0.15s, border-color 0.15s, transform 0.15s;
}

.job-card:hover {
	text-decoration: none;
	border-color: var(--border-strong);
	box-shadow: var(--shadow);
}

.job-card[draggable="true"] {
	cursor: grab;
}

.job-card.urgent {
	border-left: 3px solid var(--red-dot);
}

.top {
	display: flex;
	align-items: center;
	gap: 6px;
	margin-bottom: 4px;
}

.id {
	font-size: 11px;
	font-weight: 600;
	color: var(--text-faint);
	letter-spacing: 0.02em;
}

.flag {
	font-size: 11px;
	font-weight: 600;
	color: var(--red-fg);
}

.status {
	margin-left: auto;
}

.issue {
	font-weight: 600;
	line-height: 1.3;
}

.customer {
	color: var(--text-muted);
	font-size: 13px;
	margin-top: 2px;
}

.meta {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 8px;
	margin-top: 10px;
	font-size: 12px;
	color: var(--text-muted);
}

.date {
	display: inline-flex;
	align-items: center;
	gap: 4px;
}

.date.overdue {
	color: var(--red-fg);
	font-weight: 600;
}

.tech {
	display: inline-flex;
	align-items: center;
	gap: 5px;
}

.unassigned {
	color: var(--orange-fg);
	font-weight: 550;
}

.avatar {
	display: grid;
	place-items: center;
	width: 20px;
	height: 20px;
	border-radius: 50%;
	background: var(--mint-soft);
	color: var(--brand-dark);
	font-size: 10px;
	font-weight: 700;
}
</style>
