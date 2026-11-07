<script setup>
import { computed } from "vue";
import { statusTone } from "../lib/format.js";

// `tone` is for statuses that are not a job's (an invoice's "Overdue"); a job's comes from its status.
const props = defineProps({ status: { type: String, required: true }, tone: { type: String, default: "" } });
const tone = computed(() => props.tone || statusTone(props.status));
</script>

<template>
	<span
		class="badge"
		:style="{ color: `var(--${tone}-fg)`, background: `var(--${tone}-bg)` }"
	>
		<span class="dot" :style="{ background: `var(--${tone}-dot)` }" />
		{{ status }}
	</span>
</template>

<style scoped>
.badge {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	padding: 2px 9px 2px 8px;
	border-radius: 999px;
	font-size: 12px;
	font-weight: 550;
	white-space: nowrap;
}

.dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
}
</style>
