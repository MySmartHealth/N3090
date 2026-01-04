#!/usr/bin/env bash
set -euo pipefail

# Build and run llama.cpp HTTP server with CUDA (RTX 3090/3060)
# Usage:
#   LLAMA_CPP_PORT=8080 MODEL=./models/foo.gguf ./bin/llama_cpp_server.sh run
# Subcommands: deps|install, build, run|serve, clean

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
APP_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
LLAMA_DIR=${LLAMA_DIR:-"${APP_DIR}/.cache/llama.cpp"}
MODEL=${MODEL:-"${APP_DIR}/models/BiMediX2-8B-hf.i1-Q6_K.gguf"}
PORT=${LLAMA_CPP_PORT:-8080}
HOST=${LLAMA_CPP_HOST:-0.0.0.0}
CTX=${LLAMA_CTX:-8192}
GPU_LAYERS=${LLAMA_GPU_LAYERS:-9999}
THREADS=${LLAMA_THREADS:-$(nproc)}
FLASH=${LLAMA_FLASH:-true}
BUILD_DIR="${LLAMA_DIR}/build"
CMD=${1:-run}

install_deps() {
  sudo apt update
  sudo apt install -y git build-essential cmake ninja-build pkg-config
}

clone_repo() {
  mkdir -p "${LLAMA_DIR%/*}"
  if [[ ! -d "$LLAMA_DIR/.git" ]]; then
    git clone --depth 1 https://github.com/ggerganov/llama.cpp.git "$LLAMA_DIR"
  else
    (cd "$LLAMA_DIR" && git pull --ff-only)
  fi
}

build_server() {
  clone_repo
  cmake -S "$LLAMA_DIR" -B "$BUILD_DIR" \
    -DLLAMA_CUBLAS=ON \
    -DLLAMA_BUILD_SERVER=ON \
    -DLLAMA_CUDA_F16=ON \
    -DLLAMA_NATIVE=OFF
  cmake --build "$BUILD_DIR" --config Release -- -j"${THREADS}"
}

run_server() {
  if [[ ! -x "$BUILD_DIR/bin/server" ]]; then
    echo "[INFO] llama.cpp server binary missing; building first."
    build_server
  fi

  if [[ ! -f "$MODEL" ]]; then
    echo "[ERROR] MODEL not found: $MODEL" >&2
    exit 1
  fi

  export GGML_CUDA=1
  export GGML_CUDA_FORCE_MMQ=1

  ARGS=(
    "-m" "$MODEL"
    "-c" "$CTX"
    "-ngl" "$GPU_LAYERS"
    "-t" "$THREADS"
    "--host" "$HOST"
    "--port" "$PORT"
    "--api-key" ""
  )

  if [[ "$FLASH" == "true" ]]; then
    ARGS+=("--flash-attn")
  fi

  echo "[INFO] Starting llama.cpp server on $HOST:$PORT with model $MODEL"
  echo "[INFO] Context $CTX, GPU layers $GPU_LAYERS, threads $THREADS"
  exec "$BUILD_DIR/bin/server" "${ARGS[@]}"
}

clean_build() {
  rm -rf "$BUILD_DIR"
}

case "$CMD" in
  deps|install)
    install_deps
    ;;
  build)
    install_deps
    build_server
    ;;
  run|serve)
    run_server
    ;;
  clean)
    clean_build
    ;;
  *)
    echo "Usage: $0 [deps|build|run|serve|clean]" >&2
    exit 1
    ;;
fi
