#!/bin/sh
set -eu

# The downloads directory is usually a host bind mount. Docker creates a
# missing mount point as root, so the unprivileged app user cannot write to it.
# Fix ownership/modes best-effort: odd or read-only mounts must not block boot.
if [ -d /app/downloads ]; then
    chown -R appuser:appuser /app/downloads 2>/dev/null || true
    chmod -R ug+rwX /app/downloads 2>/dev/null || true
fi

# Drop privileges for the actual server process.
exec gosu appuser "$@"
