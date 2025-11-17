#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
mkdir -p "$repo_root/.git/hooks"
cp -f "$repo_root/tools/git-hooks/pre-commit" "$repo_root/.git/hooks/pre-commit"
chmod +x "$repo_root/.git/hooks/pre-commit"
echo "pre-commit hook installed to .git/hooks/pre-commit"
