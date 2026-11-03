#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DIST_DIR=${DIST_DIR:-"$ROOT_DIR/dist"}
RELEASE_ID=${RELEASE_ID:-"$(date -u +%Y%m%dT%H%M%SZ)"}
MODE=${1:-dry-run}
ENV_FILE=${ENV_FILE:-"$ROOT_DIR/.env"}

die() {
  printf '%s\n' "deploy: $*" >&2
  exit 1
}

log() {
  printf '%s\n' "deploy: $*"
}

load_env_file() {
  [ -f "$ENV_FILE" ] || return 0

  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|'#'*) continue ;;
    esac
    case "$line" in
      *=*) name=${line%%=*}; value=${line#*=} ;;
      *) die "$ENV_FILE: expected KEY=value" ;;
    esac
    case "$name" in
      [A-Za-z_][A-Za-z0-9_]*) ;;
      *) die "$ENV_FILE: invalid variable name '$name'" ;;
    esac

    # Explicitly exported shell variables take precedence over .env values.
    eval "already_set=\${$name+x}"
    if [ -z "$already_set" ]; then
      export "$name=$value"
    fi
  done < "$ENV_FILE"
}

load_env_file
SERVER_SCP_MODE=${SERVER_SCP_MODE:-legacy}
DEPLOY_DEBUG=${DEPLOY_DEBUG:-}
HTTP_FILE_TIMEOUT=${HTTP_FILE_TIMEOUT:-15}
SSH_TIMEOUT=${SSH_TIMEOUT:-30}
SCP_TIMEOUT=${SCP_TIMEOUT:-120}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required"
}

require_value() {
  name=$1
  eval "value=\${$name:-}"
  [ -n "$value" ] || die "$name is required"
}

require_positive_integer() {
  name=$1
  eval "value=\${$name:-}"
  case "$value" in
    ''|*[!0-9]*) die "$name must be a positive integer" ;;
    0) die "$name must be a positive integer" ;;
  esac
}

validate_remote_path() {
  name=$1
  eval "value=\${$name:-}"
  case "$value" in
    *[!A-Za-z0-9_./:-]*) die "$name contains unsupported path characters" ;;
  esac
}

validate_scp_mode() {
  case "$SERVER_SCP_MODE" in
    legacy|sftp) ;;
    *) die "SERVER_SCP_MODE must be legacy or sftp" ;;
  esac
}

validate_configuration() {
  require_value SERVER_HOST
  require_value SERVER_USER
  require_value SERVER_SSH_PORT
  require_value SERVER_IDENTITY_FILE
  require_value SERVER_WEB_ROOT
  require_value DASHBOARD_URL
  require_value SERVER_RELEASE_ROOT
  require_value SERVER_ACTIVE_LINK
  require_value SERVER_ACTIVATION_MODE
  validate_scp_mode
  validate_remote_path SERVER_WEB_ROOT
  validate_remote_path SERVER_RELEASE_ROOT
  validate_remote_path SERVER_ACTIVE_LINK
  [ "$SERVER_WEB_ROOT" = "$SERVER_ACTIVE_LINK" ] ||
    die "SERVER_WEB_ROOT must equal SERVER_ACTIVE_LINK for symlink activation"
  [ "$SERVER_ACTIVATION_MODE" = symlink ] ||
    die "only SERVER_ACTIVATION_MODE=symlink is implemented"
}

ssh_remote() {
  remote=$1
  command=$2
  if [ "$DEPLOY_DEBUG" = 1 ]; then
    timeout "$SSH_TIMEOUT" ssh -vvv -i "$SERVER_IDENTITY_FILE" \
      -p "$SERVER_SSH_PORT" "$remote" "$command"
  else
    timeout "$SSH_TIMEOUT" ssh -i "$SERVER_IDENTITY_FILE" \
      -p "$SERVER_SSH_PORT" "$remote" "$command"
  fi
}

scp_release() {
  source_dir=$1
  destination=$2
  if [ "$DEPLOY_DEBUG" = 1 ]; then
    if [ "$SERVER_SCP_MODE" = legacy ]; then
      timeout "$SCP_TIMEOUT" scp -vvv -O -i "$SERVER_IDENTITY_FILE" \
        -P "$SERVER_SSH_PORT" -r "$source_dir/index.html" \
        "$source_dir/styles.css" "$source_dir/app.js" "$source_dir/data" \
        "$destination"
    else
      timeout "$SCP_TIMEOUT" scp -vvv -i "$SERVER_IDENTITY_FILE" \
        -P "$SERVER_SSH_PORT" -r "$source_dir/index.html" \
        "$source_dir/styles.css" "$source_dir/app.js" "$source_dir/data" \
        "$destination"
    fi
  elif [ "$SERVER_SCP_MODE" = legacy ]; then
    timeout "$SCP_TIMEOUT" scp -O -i "$SERVER_IDENTITY_FILE" \
      -P "$SERVER_SSH_PORT" -r "$source_dir/index.html" \
      "$source_dir/styles.css" "$source_dir/app.js" "$source_dir/data" \
      "$destination"
  else
    timeout "$SCP_TIMEOUT" scp -i "$SERVER_IDENTITY_FILE" \
      -P "$SERVER_SSH_PORT" -r "$source_dir/index.html" \
      "$source_dir/styles.css" "$source_dir/app.js" "$source_dir/data" \
      "$destination"
  fi
}

validate_and_build() {
  require_command python3
  require_command sha256sum
  require_command grep
  python3 -m unittest discover -s "$ROOT_DIR/parser/tests" -v
  sh "$ROOT_DIR/scripts/generate_data.sh"
  sh "$ROOT_DIR/scripts/build_static.sh" "$DIST_DIR"
  for path in index.html styles.css app.js data/projects.json; do
    [ -s "$DIST_DIR/$path" ] || die "missing or empty build output: $path"
  done
  python3 -m json.tool "$DIST_DIR/data/projects.json" >/dev/null

  set +e
  grep -R -n -E 'https?://' "$DIST_DIR" >/dev/null 2>&1
  grep_status=$?
  set -e
  case "$grep_status" in
    0) die 'static output contains an external URL' ;;
    1) ;;
    *) die 'could not scan static output for external URLs' ;;
  esac
}

verify_http_hashes() (
  set -eu
  require_command sha256sum
  require_command curl
  require_command mktemp
  require_command find
  require_command sort

  http_base=$DASHBOARD_URL
  case "$http_base" in
    */) ;;
    *) http_base="$http_base/" ;;
  esac
  http_tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/project-dashboard-http.XXXXXX")
  trap 'rm -rf "$http_tmp_dir"' 0
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM

  (cd "$DIST_DIR" && find index.html styles.css app.js data -type f -print | sort) > "$http_tmp_dir/manifest"
  [ -s "$http_tmp_dir/manifest" ] || die 'no HTTP files to verify'
  while IFS= read -r relative_path; do
    local_hash=$(sha256sum "$DIST_DIR/$relative_path" | awk '{print $1}')
    response_file="$http_tmp_dir/response"
    curl --fail --silent --show-error --location --max-time "$HTTP_FILE_TIMEOUT" \
      --header 'Cache-Control: no-cache' --output "$response_file" \
      "$http_base$relative_path" || die "HTTP GET failed for $relative_path"
    remote_hash=$(sha256sum "$response_file" | awk '{print $1}')
    [ "$local_hash" = "$remote_hash" ] ||
      die "HTTP hash mismatch for $relative_path (local=$local_hash http=$remote_hash)"
    log "HTTP hash verified: $relative_path sha256=$local_hash"
  done < "$http_tmp_dir/manifest"
)

run_stage() {
  label=$1
  shift
  log "$label START"
  if "$@"; then
    log "$label COMPLETE"
  else
    status=$?
    die "$label failed (exit=$status)"
  fi
}

case "$MODE" in
  validate|build)
    validate_and_build
    log "Local $MODE passed"
    ;;
  verify-http)
    validate_and_build
    require_value DASHBOARD_URL
    require_positive_integer HTTP_FILE_TIMEOUT
    run_stage 'HTTP verification' verify_http_hashes
    ;;
  dry-run)
    validate_configuration
    validate_and_build
    log 'DRY RUN: no SSH, SCP, upload, or activation performed'
    printf 'To deploy: DEPLOY_APPROVED=YES sh scripts/deploy.sh deploy\n'
    printf 'release=%s\ntarget=%s@%s:%s\nweb_root=%s\nrelease_root=%s\nactive_link=%s\nactivation_mode=%s\nscp_mode=%s\ndebug=%s\ndashboard_url=%s\n' \
      "$RELEASE_ID" "$SERVER_USER" "$SERVER_HOST" "$SERVER_SSH_PORT" \
      "$SERVER_WEB_ROOT" "$SERVER_RELEASE_ROOT" "$SERVER_ACTIVE_LINK" \
      "$SERVER_ACTIVATION_MODE" "$SERVER_SCP_MODE" "$DEPLOY_DEBUG" "$DASHBOARD_URL"
    ;;
  deploy)
    [ "${DEPLOY_APPROVED:-}" = YES ] || die 'set DEPLOY_APPROVED=YES for live deployment'
    validate_configuration
    require_command ssh
    require_command scp
    require_command timeout
    [ -f "$SERVER_IDENTITY_FILE" ] || die 'SERVER_IDENTITY_FILE is not a readable file'
    require_positive_integer SSH_TIMEOUT
    require_positive_integer SCP_TIMEOUT
    require_positive_integer HTTP_FILE_TIMEOUT
    validate_and_build

    remote_base="$SERVER_USER@$SERVER_HOST"
    remote_release="$SERVER_RELEASE_ROOT/$RELEASE_ID"
    remote_staging="$remote_release.tmp"
    active_next="$SERVER_ACTIVE_LINK.next"

    prepare_command="set -e; mkdir -p '$SERVER_RELEASE_ROOT'; \
[ ! -e '$remote_release' ] && [ ! -L '$remote_release' ] || exit 41; \
[ ! -e '$remote_staging' ] && [ ! -L '$remote_staging' ] || exit 42; \
[ ! -e '$active_next' ] && [ ! -L '$active_next' ] || exit 43; \
[ ! -e '$SERVER_ACTIVE_LINK' ] || [ -L '$SERVER_ACTIVE_LINK' ] || exit 44; \
case \"\$(mv --help 2>&1)\" in *'-T'*) ;; *) echo 'BusyBox mv lacks -T; refusing unsafe activation' >&2; exit 45 ;; esac; \
mkdir '$remote_staging'"

    log "Release: $RELEASE_ID"
    run_stage 'Stage 1/4: prepare staging' ssh_remote "$remote_base" "$prepare_command"
    run_stage 'Stage 2/4: upload files' scp_release "$DIST_DIR" "$remote_base:$remote_staging/"

    activate_command="set -e; \
[ -d '$remote_staging' ] && [ ! -e '$remote_release' ] && [ ! -L '$remote_release' ]; \
mv '$remote_staging' '$remote_release'; \
ln -s '$remote_release' '$active_next'; \
mv -fT '$active_next' '$SERVER_ACTIVE_LINK'; \
[ \"\$(readlink '$SERVER_ACTIVE_LINK')\" = '$remote_release' ]"
    run_stage 'Stage 3/4: activate release' ssh_remote "$remote_base" "$activate_command"
    run_stage 'Stage 4/4: HTTP hash verification' verify_http_hashes
    log "Deployed and HTTP-verified release $RELEASE_ID"
    ;;
  *)
    die 'usage: scripts/deploy.sh {validate|build|verify-http|dry-run|deploy}'
    ;;
esac
