#!/usr/bin/env bash
set -euo pipefail

# Install local prerequisites for development on Debian/Ubuntu
# Optional CUDA toolkit install when INSTALL_CUDA=true (defaults to off to avoid driver surprises)

if ! command -v sudo >/dev/null 2>&1; then
  echo "[ERROR] sudo not available; run as root or install sudo." >&2
  exit 1
fi

sudo apt update
# Python tooling
sudo apt install -y python3-pip python3-venv
# Node.js & npm (use distro or your preferred NodeSource if needed)
sudo apt install -y nodejs npm
# PM2 globally
sudo npm install -g pm2

# Install Python dependencies for inference-node (scraper and backend)
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
python3 -m pip install --upgrade pip
python3 -m pip install -r "$REPO_ROOT/services/inference-node/requirements.txt"

INSTALL_CUDA=${INSTALL_CUDA:-false}
CUDA_TOOLKIT_VERSION=${CUDA_TOOLKIT_VERSION:-12-4}

if [[ "$INSTALL_CUDA" == "true" ]]; then
  echo "[INFO] Installing NVIDIA CUDA toolkit ${CUDA_TOOLKIT_VERSION} (drivers must already be installed or managed separately)."
  sudo apt install -y curl gnupg ca-certificates lsb-release
  UBUNTU_CODENAME=$(lsb_release -cs)
  # Map Ubuntu codenames to NVIDIA repo directories (e.g., noble -> ubuntu2404)
  case "$UBUNTU_CODENAME" in
    noble) CUDA_REPO_CODENAME="ubuntu2404" ;;
    jammy) CUDA_REPO_CODENAME="ubuntu2204" ;;
    focal) CUDA_REPO_CODENAME="ubuntu2004" ;;
    *) CUDA_REPO_CODENAME="$UBUNTU_CODENAME" ;;
  esac
  CUDA_PIN_PATH=/etc/apt/preferences.d/cuda-repository-pin-600
  CUDA_REPO_URL="https://developer.download.nvidia.com/compute/cuda/repos/${CUDA_REPO_CODENAME}/x86_64"
  # Add NVIDIA CUDA repo keyring
  TMP_DEB=/tmp/cuda-keyring.deb
  curl -fsSL "${CUDA_REPO_URL}/cuda-keyring_1.1-1_all.deb" -o "$TMP_DEB"
  sudo dpkg -i "$TMP_DEB"
  sudo apt-get update

  CUDA_TOOLKIT_PKG="cuda-toolkit-${CUDA_TOOLKIT_VERSION}"
  if ! apt-cache show "$CUDA_TOOLKIT_PKG" >/dev/null 2>&1; then
    echo "[WARN] Package $CUDA_TOOLKIT_PKG not found in CUDA repo; falling back to cuda-toolkit-12-6." >&2
    CUDA_TOOLKIT_PKG="cuda-toolkit-12-6"
  fi

  sudo apt-get install -y "$CUDA_TOOLKIT_PKG"
  echo "[INFO] CUDA toolkit installed. Ensure /usr/local/cuda/bin is on your PATH."
  if [[ -f "$CUDA_PIN_PATH" ]]; then
    echo "[INFO] CUDA repo pin present at $CUDA_PIN_PATH"
  fi
fi

echo "[OK] Installed python3-pip, python3-venv, nodejs, npm, and pm2." \
     "$( [[ "$INSTALL_CUDA" == "true" ]] && echo "plus CUDA toolkit ${CUDA_TOOLKIT_VERSION}" )"