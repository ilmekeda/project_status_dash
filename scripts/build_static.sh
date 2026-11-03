#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DIST_DIR=${1:-"$ROOT_DIR/dist"}

mkdir -p "$DIST_DIR/data"
cp "$ROOT_DIR/manual-preview/styles.css" "$DIST_DIR/styles.css"
cp "$ROOT_DIR/manual-preview/app.js" "$DIST_DIR/app.js"
sed -e 's#../generated/projects.json#data/projects.json#' \
  -e 's#Data: generated/projects.json#Data: data/projects.json#' \
  "$ROOT_DIR/manual-preview/index.html" > "$DIST_DIR/index.html"
cp "$ROOT_DIR/generated/projects.json" "$DIST_DIR/data/projects.json"

python3 -m json.tool "$DIST_DIR/data/projects.json" >/dev/null
printf '%s\n' "Built static dashboard in $DIST_DIR"
