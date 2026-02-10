#!/usr/bin/env sh
set -e

# This script installs the FileMind CLI tool.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/your-username/filemind/main/install.sh | sh
#
# The script will:
# 1. Detect the user's OS and architecture.
# 2. Download the appropriate pre-built binary from the latest GitHub release.
# 3. Place the binary in /usr/local/bin.
#
# This script is inspired by the installation scripts of many modern CLI tools.

REPO="Karthikeya-Akhandam/filemind" # <<< TODO: CHANGE THIS TO YOUR GITHUB USERNAME/REPO
BIN_NAME="filemind"

get_latest_release() {
  # Fetches the latest tag name from releases.json on GitHub Pages
  # (avoids GitHub API rate limits and includes pre-releases)
  JSON=$(curl --silent "https://karthikeya-akhandam.github.io/filemind/releases.json")
  # Prefer latest stable release; fall back to latest pre-release
  TAG=$(echo "$JSON" | grep -B1 '"prerelease": false' | grep '"tag_name":' | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
  if [ -z "$TAG" ]; then
    TAG=$(echo "$JSON" | grep -m 1 '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
  fi
  echo "$TAG"
}

main() {
  # --- Detect OS and Architecture ---
  OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
  ARCH="$(uname -m)"

  case "$OS" in
    linux) OS_NAME="linux" ;;
    darwin) OS_NAME="macos" ;;
    *)
      echo "Unsupported OS: $OS"
      echo "FileMind can be installed on Linux and macOS via this script."
      echo "For Windows, please download the .exe from the GitHub releases page."
      exit 1
      ;;
  esac

  case "$ARCH" in
    x86_64|amd64) ARCH_NAME="amd64" ;;
    arm64|aarch64)
      echo "ARM64 architecture is not yet supported by this build script."
      exit 1
      ;; # TODO: Add arm64 support later
    *)
      echo "Unsupported architecture: $ARCH"
      exit 1
      ;;
  esac

  # --- Download Binary ---
  LATEST_RELEASE=$(get_latest_release)
  if [ -z "$LATEST_RELEASE" ]; then
    echo "Error: Could not find the latest release for $REPO."
    exit 1
  fi

  BINARY_NAME_VERSIONED="$BIN_NAME-$LATEST_RELEASE-${OS_NAME}-${ARCH_NAME}"
  DOWNLOAD_URL="https://github.com/$REPO/releases/download/$LATEST_RELEASE/$BINARY_NAME_VERSIONED"
  INSTALL_DIR="/usr/local/bin"
  INSTALL_PATH="$INSTALL_DIR/$BIN_NAME"

  echo "Downloading FileMind ($LATEST_RELEASE) for $OS_NAME/$ARCH_NAME..."
  echo "$DOWNLOAD_URL"
  
  # Download to a temporary file
  TMP_FILE=$(mktemp)
  if ! curl --progress-bar -fsSL "$DOWNLOAD_URL" -o "$TMP_FILE"; then
    echo "Error: Failed to download the binary. Please check the URL and your network connection."
    rm -f "$TMP_FILE"
    exit 1
  fi
  
  chmod +x "$TMP_FILE"

  # --- Install Binary ---
  echo "Installing to $INSTALL_DIR (this may require sudo password)..."
  
  # Check if sudo is required
  if [ -w "$INSTALL_DIR" ]; then
    # No sudo needed
    mv "$TMP_FILE" "$INSTALL_PATH"
  else
    # Sudo is required
    if ! sudo mv "$TMP_FILE" "$INSTALL_PATH"; then
      echo "Error: Failed to move the binary to $INSTALL_PATH."
      echo "Please check your permissions or run the script with sudo privileges."
      rm -f "$TMP_FILE"
      exit 1
    fi
  fi
  
  echo ""
  echo "✔ FileMind was installed successfully!"
  echo "  Run 'filemind --help' to get started."
}

# --- Run ---
main
