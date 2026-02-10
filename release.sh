#!/usr/bin/env bash
set -e

# Usage: ./release.sh v0.1.3
# Updates pyproject.toml version, commits, tags, and pushes.

TAG="$1"

if [ -z "$TAG" ]; then
  echo "Usage: ./release.sh v<major>.<minor>.<patch>"
  exit 1
fi

# Validate tag format (v followed by semver, with optional pre-release suffix)
if ! echo "$TAG" | grep -qE '^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
  echo "Error: Tag must match format v<major>.<minor>.<patch> (e.g., v0.1.3 or v0.1.3-alpha)"
  exit 1
fi

# Ensure working tree is clean
if [ -n "$(git status --porcelain)" ]; then
  echo "Error: Working tree is not clean. Commit or stash changes first."
  exit 1
fi

# Strip the leading 'v' to get the version number
VERSION="${TAG#v}"

# Update pyproject.toml
sed -i "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml

echo "Updated pyproject.toml to version $VERSION"

# Commit, tag, and push
git add pyproject.toml
git commit -m "chore: bump version to $VERSION"
git tag "$TAG"
git push origin main --follow-tags

echo ""
echo "Released $TAG successfully!"
