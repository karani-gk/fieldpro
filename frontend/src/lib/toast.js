// Short messages after an action ("Job assigned"), shown by ToastHost in the corner.
import { reactive } from "vue";

export const toasts = reactive([]);
let nextId = 1;

export function notify(text, kind = "success") {
	const id = nextId++;
	toasts.push({ id, text, kind });
	setTimeout(() => {
		const index = toasts.findIndex((t) => t.id === id);
		if (index >= 0) toasts.splice(index, 1);
	}, kind === "error" ? 6000 : 3500);
}
