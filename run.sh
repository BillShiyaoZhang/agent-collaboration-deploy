#!/bin/bash
set -e
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec docker compose "$@"
