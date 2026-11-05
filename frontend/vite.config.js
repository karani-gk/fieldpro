// Builds the manager's app into fieldpro/public/manage, which Frappe serves at
// /assets/fieldpro/manage/. www/manage.py reads Vite's manifest to find the hashed file names.
import { fileURLToPath } from "node:url";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
	plugins: [vue()],
	base: "/assets/fieldpro/manage/",
	build: {
		outDir: fileURLToPath(new URL("../fieldpro/public/manage", import.meta.url)),
		emptyOutDir: true,
		manifest: true,
		// No index.html: Frappe renders the page (www/manage.html), so the entry is the script.
		rolldownOptions: { input: "src/main.js" },
	},
	test: { environment: "node" },
});
