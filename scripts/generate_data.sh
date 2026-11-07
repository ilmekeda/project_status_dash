#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
INPUT=${1:-projects.md}
OUTPUT=${2:-generated/projects.json}

mkdir -p "$ROOT_DIR/$(dirname -- "$OUTPUT")"
python3 "$ROOT_DIR/parser/parse_projects.py" "$ROOT_DIR/$INPUT" -o "$ROOT_DIR/$OUTPUT"
printf '%s\n' "Generated $OUTPUT from $INPUT"
