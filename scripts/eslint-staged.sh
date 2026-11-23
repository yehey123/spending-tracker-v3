#!/bin/sh
# Run eslint from frontend/ on repo-relative file paths passed by pre-commit.
cd "$(git rev-parse --show-toplevel)/frontend" || exit 1
for f in "$@"; do shift; set -- "$@" "${f#frontend/}"; done
exec npx --no-install eslint --max-warnings=0 "$@"
