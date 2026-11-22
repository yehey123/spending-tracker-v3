#!/bin/sh
# Point git at the versioned hooks in .githooks/.
cd "$(git rev-parse --show-toplevel)" || exit 1
git config core.hooksPath .githooks
chmod +x .githooks/* scripts/install-hooks.sh
echo "core.hooksPath set to .githooks; made these hooks executable:"
ls .githooks
