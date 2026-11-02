# Project status dashboard

This repository is developing a static dashboard whose initial human-edited
source is [`projects.md`](projects.md). The Markdown format is documented in
[`docs/schema.md`](docs/schema.md). `project_status_mock.md` is retained as the
provided mock input; `projects.md` is the canonical Phase 1 sample and uses
headings that exactly match the metadata names.

## Local Docker preview

Docker is a development convenience only. The Compose service bind-mounts the
repository read-only into Nginx, so host edits are visible without rebuilding:

```sh
docker compose up -d
open http://127.0.0.1:8080/projects.md
docker compose down
```

On systems without `open`, visit the URL in a browser manually. The preview is
published to host loopback only. Phase 1 has no parser or generated JSON yet.
