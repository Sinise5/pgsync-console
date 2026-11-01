#!/usr/bin/env bash
# Wrapper: load .env.laporan-dev, bypass bash ! expansion
set -a
source "$(dirname "$0")/../.env.laporan-dev"
set +a
exec ~/.pyenv/versions/3.12.13/bin/python3 "$(dirname "$0")/sync_laporan_batch.py" "$@"
