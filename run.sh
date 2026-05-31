#!/bin/bash
set -e

# Ensure agent-comm is available to agent-comm-platform
# The platform Dockerfile expects ../agent-comm relative to itself,
# but when built via submodule, we need to symlink it.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_DIR="$SCRIPT_DIR/agent-comm-platform"

# Create symlink if needed
if [ ! -e "$PLATFORM_DIR/agent-comm" ] && [ ! -L "$PLATFORM_DIR/agent-comm" ]; then
    ln -sf "$SCRIPT_DIR/agent-comm" "$PLATFORM_DIR/agent-comm"
    echo "Linked agent-comm into agent-comm-platform"
fi

exec docker compose "$@"