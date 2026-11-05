<script setup>
import { toasts } from "../lib/toast.js";
</script>

<template>
	<div class="toasts" aria-live="polite">
		<TransitionGroup name="toast">
			<div v-for="toast in toasts" :key="toast.id" class="toast" :class="toast.kind">
				{{ toast.text }}
			</div>
		</TransitionGroup>
	</div>
</template>

<style scoped>
.toasts {
	position: fixed;
	right: 20px;
	bottom: 20px;
	z-index: 60;
	display: flex;
	flex-direction: column;
	gap: 8px;
}

.toast {
	padding: 10px 14px;
	border-radius: var(--radius-sm);
	background: var(--ink);
	color: #fff;
	box-shadow: var(--shadow-lift);
	max-width: 360px;
}

.toast.error {
	background: var(--danger);
}

.toast-enter-active,
.toast-leave-active {
	transition: all 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
	opacity: 0;
	transform: translateY(8px);
}
</style>
