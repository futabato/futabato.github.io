import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://futabato.github.io",
  build: {
    assets: "_assets",
  },
  redirects: {
    "/rss": "/rss/index.html",
  },
});
