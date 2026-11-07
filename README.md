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
published to host loopback only. The dashboard loads its cards and summary from
the local generated JSON endpoint described below.

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

## Parser preview

The parser can validate and normalize either accepted source file:

```sh
sh scripts/generate_data.sh
python3 parser/parse_projects.py projects.md -o /tmp/projects.json
python3 -m unittest discover -s parser/tests -v
```

The generated file is ignored at `generated/projects.json`. To run the same
parser inside the development container, build the dependency image once and
run the bind-mounted parser service:

```sh
docker compose build parser
docker compose run --rm parser
```

The parser service reads the host `projects.md` through the bind mount and
writes only `generated/projects.json`; source edits do not require another image
build. The Nginx preview can then serve the generated file at
`http://127.0.0.1:8080/generated/projects.json`.

## Build static release assets

After regenerating the JSON, create the deployment-ready static output with:

```sh
sh scripts/build_static.sh
```

This writes ignored `dist/` assets only: the continuity-baseline HTML, CSS,
JavaScript, and local `data/projects.json`. The generated page uses the
relative `data/projects.json` path and has no runtime dependency on Docker,
Python, Node.js, a backend, a CDN, or external network services.

The JSON-backed dashboard is available at
`http://127.0.0.1:8080/manual-preview/index.html`. It loads
`../generated/projects.json`, keeping the preview independent of external
services.

JSON regeneration is explicit rather than automatic: after editing
`projects.md`, run `sh scripts/generate_data.sh`, then refresh the preview.
The running Nginx container does not need to be rebuilt or restarted because
both the Markdown source and generated directory are bind-mounted from the
host. The parser service follows the same workflow with
`docker compose run --rm parser`.

## Release and deployment preparation

Use [`docs/deployment.md`](docs/deployment.md) and the local pipeline before
any server transfer:

```sh
sh scripts/deploy.sh validate
sh scripts/deploy.sh dry-run
```

To test HTTP content hashes without SSH or activation, point `DASHBOARD_URL`
at a static server and run `sh scripts/deploy.sh verify-http`.

The dry run is the default-safe deployment mode. A repository-root `.env` is
loaded automatically for `KEY=value` configuration, while already-exported
shell variables take precedence. Live deployment requires the explicit
`deploy` argument, verified server values, an explicit `SERVER_IDENTITY_FILE`,
and `DEPLOY_APPROVED=YES`. The identity file is passed directly to SSH/SCP and
must be mounted read-only when the command runs in Docker. Running the script
with no argument only performs the dry run. The script defaults to
`SERVER_SCP_MODE=legacy` for embedded servers; set `DEPLOY_DEBUG=1` for
verbose, local-only SSH/SCP diagnostics. The final HTTP check hashes every
served static file and compares it with the local build, rather than checking
only the response status.
