#!/bin/bash
set -euo pipefail

OLD_OWNER_NAME="isaac-cf-wong"

OLD_REPO_NAME="python-package-template"
OLD_REPO_NAME_NORMALIZED="${OLD_REPO_NAME//-/_}"

url=$(git config --get remote.origin.url)

if [[ "$url" =~ [:/]([^/]+)/([^/]+)(\.git)?$ ]]; then
    NEW_OWNER_NAME="${BASH_REMATCH[1]}"
    NEW_REPO_NAME="${BASH_REMATCH[2]%.git}"
else
    echo "Unable to parse owner/repo from remote.origin.url: $url" >&2
    exit 1
fi

NEW_REPO_NAME_NORMALIZED="${NEW_REPO_NAME//-/_}"

# Preflight checks
[[ -f "cliff.toml" ]] || {
    echo "Missing cliff.toml" >&2
    exit 1
}
[[ -d "src/$OLD_REPO_NAME_NORMALIZED" ]] || {
    echo "Missing source package dir: src/$OLD_REPO_NAME_NORMALIZED" >&2
    exit 1
}
[[ ! -e "src/$NEW_REPO_NAME_NORMALIZED" ]] || {
    echo "Target package dir already exists: src/$NEW_REPO_NAME_NORMALIZED" >&2
    exit 1
}

if sed --version >/dev/null 2>&1; then
    # GNU sed (Linux)
    SED_INPLACE=(-i)
else
    # BSD sed (macOS)
    SED_INPLACE=(-i '')
fi

# Replace old owner name with new owner name in cliff.toml
OLD_REPO_URL="https://github.com/$OLD_OWNER_NAME/$OLD_REPO_NAME"
NEW_REPO_URL="https://github.com/$NEW_OWNER_NAME/$NEW_REPO_NAME"
sed "${SED_INPLACE[@]}" "s#${OLD_REPO_URL}#${NEW_REPO_URL}#g" cliff.toml

find . -type d \( -name ".git" -o -name "__pycache__" -o -name ".venv" -o -name "node_modules" -o -name ".pytest_cache" \) -prune \
    -o -type f \( -name "*.py" -o -name "*.md" -o -name "*.toml" -o -name "LICENSE" \) \
    -exec sed "${SED_INPLACE[@]}" -e "s/$OLD_REPO_NAME/$NEW_REPO_NAME/g" -e "s/$OLD_REPO_NAME_NORMALIZED/$NEW_REPO_NAME_NORMALIZED/g" {} +

mv "src/$OLD_REPO_NAME_NORMALIZED" "src/$NEW_REPO_NAME_NORMALIZED"
