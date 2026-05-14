// @ts-check
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://nayo126.github.io",
  base: "/ai-tools-review",
  trailingSlash: "always",
  build: {
    format: "directory",
  },
});
