# Local release and server deployment

The deployment command builds static frontend output and JSON; it does not run Python, Node.js,
Docker, a database, or an application backend.

## Local validation and build

These commands do not contact the server. If a repository-root `.env` exists, the
script loads its `KEY=value` entries automatically; variables already exported in
the shell take precedence. The file is ignored by Git and must not contain shell
commands or be committed.

```sh
sh scripts/deploy.sh validate
sh scripts/deploy.sh build
```

`validate` runs the parser tests, regenerates `generated/projects.json`, builds
`dist/`, validates its JSON, and rejects external URLs in the static output.

To test only the HTTP content-hash verifier against a local or already-running
static server, set `DASHBOARD_URL` and run:

```sh
DASHBOARD_URL='http://127.0.0.1:8765/' sh scripts/deploy.sh verify-http
```

After a live deployment, the same command uses the `DASHBOARD_URL` loaded from
`.env` and checks every generated static file served by the router. Look for one
`HTTP hash verified:` line for each file, followed by `HTTP verification
COMPLETE`. A failed request or mismatch exits nonzero and does not change the
router.

## Dry run

The default deployment mode is a dry run. It requires configuration values but
does not use SSH, SCP, or HTTP:

```sh
export SERVER_HOST='server-lan-address'
export SERVER_USER='confirmed-ssh-user'
export SERVER_SSH_PORT='confirmed-ssh-port'
export SERVER_IDENTITY_FILE='/path/to/server-deploy-key'
export SERVER_WEB_ROOT='confirmed-nginx-root'
export SERVER_RELEASE_ROOT='confirmed-release-directory'
export SERVER_ACTIVE_LINK='confirmed-active-link'
export SERVER_ACTIVATION_MODE='symlink'
export DASHBOARD_URL='http://server-lan-address:port/'
sh scripts/deploy.sh dry-run
```

Running `sh scripts/deploy.sh` with no argument is equivalent to `dry-run`.
That is intentional: setting `.env` values alone never uploads anything.

Do not put these values, passwords, private keys, or tokens in tracked files.
The identity file is passed explicitly to both `ssh` and `scp`; it is never
copied into the deployment image or uploaded to the server. When running in
Docker, mount the key read-only at the same path used by
`SERVER_IDENTITY_FILE`, or use a container-only path such as
`/run/secrets/server-deploy-key`.
The human must replace every placeholder with values verified on the actual
server. With the current symlink activation mode, `SERVER_WEB_ROOT` and
`SERVER_ACTIVE_LINK` must be the same path: that is the path configured as the
Nginx document root. `SERVER_RELEASE_ROOT` is a separate directory containing
versioned releases. All three paths must be confirmed compatible with the
installed Nginx configuration.

## Live deployment boundary

Live deployment is intentionally opt-in:

```sh
DEPLOY_APPROVED=YES sh scripts/deploy.sh deploy
```

The `deploy` argument is required. `DEPLOY_APPROVED=YES` is an additional
explicit confirmation and is normally placed in `.env` only for the one
authorized run, or supplied inline as above.

For embedded SSH servers whose SFTP subsystem is unavailable, set:

```sh
SERVER_SCP_MODE=legacy
```

This makes the OpenSSH client use the legacy SCP protocol (`scp -O`) instead
of its modern SFTP-based default. The default in this script is `legacy`, but
the setting is shown explicitly so the transfer protocol is visible in the
configuration. Use `SERVER_SCP_MODE=sftp` only after the server's SFTP
subsystem has been verified.

For additional local troubleshooting output, set `DEPLOY_DEBUG=1`. This emits
verbose SSH/SCP diagnostics and labels the four deployment stages; it may
include connection metadata, usernames, and paths, so do not publish the log.

The script refuses all other activation modes. It uploads to a versioned
temporary directory, renames the completed upload into its release directory,
then replaces the active symlink by removing the old symlink (without following
it), moving the prepared link into place, and verifying its final target.
HTTP verification fetches each expected
static file (`index.html`, `styles.css`, `app.js`, and files under `data/`),
computes SHA-256 hashes, and compares them with the local release hashes. A
successful HTTP status alone is not considered verification. It does not delete
old releases, so rollback remains possible by restoring a previously verified
active link. The human owns the first live run and must verify the server’s
filesystem, symlink behavior, Nginx reload behavior, credentials, and rollback
before authorizing it.

## Manual rollback verification

The deployment keeps older release directories and does not delete them. First
list the releases and record the currently active target; do not guess a path:

```sh
ssh -i "$SERVER_IDENTITY_FILE" -p "$SERVER_SSH_PORT" \
  "$SERVER_USER@$SERVER_HOST" \
  "set -e; readlink '$SERVER_ACTIVE_LINK'; for release in '$SERVER_RELEASE_ROOT'/*; do [ -d \"\$release\" ] || continue; printf '%s\\n' \"\$release\"; done | sort"
```

The listing uses a shell glob instead of GNU `find` options because 
BusyBox `find` does not support `-mindepth` or `-maxdepth`.

Choose a previously verified release from that listing. Set
`ROLLBACK_RELEASE` locally to its exact absolute path, then prepare and verify a
new symlink before replacing the active one:

```sh
ROLLBACK_RELEASE='/confirmed/release/root/previous-release'
ssh -i "$SERVER_IDENTITY_FILE" -p "$SERVER_SSH_PORT" \
  "$SERVER_USER@$SERVER_HOST" \
  "set -e; [ -d '$ROLLBACK_RELEASE' ]; [ -f '$ROLLBACK_RELEASE/index.html' ]; rm -f '$SERVER_ACTIVE_LINK.next'; ln -s '$ROLLBACK_RELEASE' '$SERVER_ACTIVE_LINK.next'; mv -fT '$SERVER_ACTIVE_LINK.next' '$SERVER_ACTIVE_LINK'; [ \"\$(readlink '$SERVER_ACTIVE_LINK')\" = '$ROLLBACK_RELEASE' ]"
```

Then run the standalone `verify-http` command above. Confirm the dashboard is
served and the output contains hash-verification lines for all files. If the
rollback is successful, record the old and new symlink targets and the command
output without recording credentials or private keys. The failed-upload safety
property is tested separately: an upload that fails before activation must leave
the existing active symlink unchanged.

