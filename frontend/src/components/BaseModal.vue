<script setup>
// A dialog that fades and rises in, and plays the same in reverse when it closes. It emits
// "close" only after the closing animation, so a parent can unmount it with v-if then. Close it
// with the `close` slot prop (Cancel buttons) or close() through a template ref (after a save).
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";

defineProps({
	title: { type: String, required: true },
	wide: { type: Boolean, default: false },
});
const emit = defineEmits(["close"]);

const shown = ref(false);
const panel = ref(null);

function close() {
	shown.value = false;
}

function onKey(event) {
	if (event.key === "Escape") close();
}

onMounted(async () => {
	shown.value = true;
	window.addEventListener("keydown", onKey);
	// Focus the first field, so the manager can type at once.
	await nextTick();
	panel.value?.querySelector("input, select, textarea, button.btn-primary")?.focus();
});
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));

defineExpose({ close });
</script>

<template>
	<Teleport to="body">
		<!-- Explicit durations: the panel animates longer than the backdrop Vue would time. -->
		<Transition name="modal" appear :duration="{ enter: 320, leave: 200 }" @after-leave="emit('close')">
			<div v-if="shown" class="backdrop" @mousedown.self="close">
				<div
					ref="panel"
					class="modal card"
					:class="{ wide }"
					role="dialog"
					aria-modal="true"
					:aria-label="title"
				>
					<header>
						<h2>{{ title }}</h2>
						<button class="btn btn-ghost btn-sm close" aria-label="Close" @click="close">✕</button>
					</header>
					<div class="body"><slot :close="close" /></div>
					<footer v-if="$slots.footer"><slot name="footer" :close="close" /></footer>
				</div>
			</div>
		</Transition>
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
	background: rgb(15 42 36 / 0.4);
	backdrop-filter: blur(3px);
	overflow-y: auto;
}

.modal {
	width: min(480px, 100%);
	max-height: calc(100vh - 32px);
	display: flex;
	flex-direction: column;
	box-shadow: var(--shadow-lift);
}

.modal.wide {
	width: min(680px, 100%);
}

header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 18px 20px 0;
}

h2 {
	font-size: 17px;
	font-weight: 650;
}

.close {
	color: var(--text-muted);
}

.body {
	padding: 16px 20px;
	display: flex;
	flex-direction: column;
	gap: 14px;
	overflow-y: auto;
}

footer {
	display: flex;
	justify-content: flex-end;
	gap: 8px;
	padding: 12px 20px 16px;
	border-top: 1px solid var(--border);
}

/* The backdrop fades; the panel rises and grows a little, with a soft overshoot on the way in. */
.modal-enter-active,
.modal-leave-active {
	transition: opacity 0.22s ease;
}

.modal-enter-active .modal {
	transition:
		transform 0.32s cubic-bezier(0.34, 1.4, 0.64, 1),
		opacity 0.22s ease;
}

.modal-leave-active .modal {
	transition:
		transform 0.18s ease-in,
		opacity 0.18s ease-in;
}

.modal-enter-from,
.modal-leave-to {
	opacity: 0;
}

.modal-enter-from .modal,
.modal-leave-to .modal {
	opacity: 0;
	transform: translateY(16px) scale(0.96);
}

@media (prefers-reduced-motion: reduce) {
	.modal-enter-active,
	.modal-leave-active,
	.modal-enter-active .modal,
	.modal-leave-active .modal {
		transition: opacity 0.12s linear;
	}

	.modal-enter-from .modal,
	.modal-leave-to .modal {
		transform: none;
	}
}
</style>
