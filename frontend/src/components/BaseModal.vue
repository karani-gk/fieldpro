<script setup>
import { onBeforeUnmount, onMounted } from "vue";

defineProps({ title: { type: String, required: true } });
const emit = defineEmits(["close"]);

function onKey(event) {
	if (event.key === "Escape") emit("close");
}
onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
</script>

<template>
	<Teleport to="body">
		<div class="backdrop" @mousedown.self="emit('close')">
			<div class="modal card" role="dialog" aria-modal="true" :aria-label="title">
				<header>
					<h2>{{ title }}</h2>
					<button class="btn btn-ghost btn-sm" aria-label="Close" @click="emit('close')">✕</button>
				</header>
				<div class="body"><slot /></div>
				<footer v-if="$slots.footer"><slot name="footer" /></footer>
			</div>
		</div>
	</Teleport>
</template>

<style scoped>
.backdrop {
	position: fixed;
	inset: 0;
	z-index: 50;
	display: grid;
	place-items: center;
	padding: 16px;
	background: rgb(15 42 36 / 0.35);
	backdrop-filter: blur(2px);
}

.modal {
	width: min(480px, 100%);
	box-shadow: var(--shadow-lift);
}

header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 16px 18px 0;
}

h2 {
	font-size: 16px;
	font-weight: 600;
}

.body {
	padding: 16px 18px;
	display: flex;
	flex-direction: column;
	gap: 14px;
}

footer {
	display: flex;
	justify-content: flex-end;
	gap: 8px;
	padding: 12px 18px 16px;
	border-top: 1px solid var(--border);
}
</style>
