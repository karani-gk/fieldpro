// A screen's data: loading, the result, the error, and reload(). Reloads quietly when the
// manager comes back to the tab, and every `refreshSeconds` if set, so numbers stay current.
import { onBeforeUnmount, onMounted, ref, shallowRef } from "vue";

export function useRequest(load, { refreshSeconds = 0, immediate = true } = {}) {
	const data = shallowRef(null);
	const error = ref(null);
	const loading = ref(false);

	async function reload() {
		loading.value = true;
		try {
			data.value = await load();
			error.value = null;
		} catch (exc) {
			error.value = exc;
			console.error("fieldpro: request failed", exc);
		} finally {
			loading.value = false;
		}
	}

	let timer = null;
	const onVisible = () => document.visibilityState === "visible" && reload();
	onMounted(() => {
		if (immediate) reload();
		document.addEventListener("visibilitychange", onVisible);
		if (refreshSeconds) timer = setInterval(onVisible, refreshSeconds * 1000);
	});
	onBeforeUnmount(() => {
		document.removeEventListener("visibilitychange", onVisible);
		clearInterval(timer);
	});

	return { data, error, loading, reload };
}
