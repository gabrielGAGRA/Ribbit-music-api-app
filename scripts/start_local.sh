#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [ ! -x "${PYTHON_BIN}" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "Erro: ambiente virtual .venv não encontrado. Execute: uv venv --python 3.15 .venv && uv sync --frozen" >&2
    exit 1
  fi
fi

if ! "${PYTHON_BIN}" -c "import sys; sys.exit(0 if sys.version_info >= (3, 15) else 1)" >/dev/null 2>&1; then
  PY_VER="$("${PYTHON_BIN}" --version 2>&1 || echo "desconhecida")"
  echo "Erro: Python >= 3.15 é obrigatório (encontrado: ${PY_VER} em ${PYTHON_BIN})." >&2
  echo "Crie o ambiente virtual com: uv venv --python 3.15 .venv && uv sync --frozen" >&2
  exit 1
fi

if [ ! -d "${ROOT_DIR}/node_modules" ]; then
  echo "Dependências do frontend não encontradas. Executando npm ci..."
  npm ci
fi

echo "Inicializando banco de dados SQLite..."
"${PYTHON_BIN}" -m scripts.init_db

BACKEND_PID=""
cleanup() {
  if [ -n "${BACKEND_PID}" ] && kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
    echo ""
    echo "Encerrando backend (PID ${BACKEND_PID})..."
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

echo "Iniciando backend FastAPI em http://127.0.0.1:8000 ..."
"${PYTHON_BIN}" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "Aguardando backend ficar saudável em http://127.0.0.1:8000/health ..."
BACKEND_READY=0
for _ in $(seq 1 30); do
  if ! kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
    echo "Erro: processo do backend encerrou inesperadamente." >&2
    exit 1
  fi
  if "${PYTHON_BIN}" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=1)" >/dev/null 2>&1; then
    BACKEND_READY=1
    break
  fi
  sleep 1
done

if [ "${BACKEND_READY}" -ne 1 ]; then
  echo "Erro: backend não respondeu em http://127.0.0.1:8000/health dentro de 30s." >&2
  exit 1
fi

echo "Iniciando frontend Angular em http://localhost:4200 (proxy para :8000) ..."
npm run dev:web
