# Project memory — sample

- [Deploy ports](./project_deploy_ports.md) — the dev server is pinned to 5174 because the browser profile the checks drive has that origin whitelisted; a free-port fallback silently breaks them
- [Queue retries](project_queue_retries.md) — the worker retries three times with a jittered backoff and then parks the job; a parked job is invisible until someone reads the parked table
