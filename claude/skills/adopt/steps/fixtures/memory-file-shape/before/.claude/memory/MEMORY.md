# Project memory — sample

- [Deploy ports](project_deploy_ports.md) — the dev server is pinned to 5174 because the browser profile the checks drive has that origin whitelisted; a free-port fallback silently breaks them
- [Import pipeline](./project_import_pipeline.md) — the nightly importer reads the export bucket, not the API; the API's page cursor repeats the last row on every third page and the dedupe key is the source id
- [Render cache](~/.claude/memory/project_render_cache.md) — thumbnails are keyed on content hash plus width, so a re-crop invalidates one entry rather than the folder
- [Browser checks](memory/project_browser_checks.md) — drive the headless profile in `tmp/profile`, never the user's own Chrome; the run leaves a GPU process behind unless the whole tree is killed
