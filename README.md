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

### Bind-mount acceptance check

Run this after `docker compose up -d` to verify that the running container sees
the same host file without a rebuild:

```sh
cmp ./projects.md <(docker compose exec -T preview cat /usr/share/nginx/html/projects.md)
```

Then make a temporary, reversible host edit and confirm it is immediately
visible through the bind mount:

```sh
cp ./projects.md /tmp/projects.md.dashboard-backup
printf '\n<!-- bind-mount test -->\n' >> ./projects.md
docker compose exec -T preview tail -n 2 /usr/share/nginx/html/projects.md
mv /tmp/projects.md.dashboard-backup ./projects.md
```

The test is complete only when the temporary marker appears inside the running
container and the host file is restored afterward.

## Create a valid projects.md

Use the mock file to create a copy and then edit as needed:
```sh
cp ./project_status_mock.md ./projects.md
```

NOTE: do not commit your projects.md, this is your private information 
