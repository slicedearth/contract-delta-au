import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

const deployingToPages = process.env.GITHUB_ACTIONS === "true";

export default defineConfig({
  site: "https://slicedearth.github.io",
  base: deployingToPages ? "/contract-delta-au" : "/",
  output: "static",
  integrations: [sitemap()],
  trailingSlash: "always",
  build: {
    format: "directory"
  }
});
