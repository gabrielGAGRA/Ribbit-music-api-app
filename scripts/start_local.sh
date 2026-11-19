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
    echo "Erro: ambiente virtual .venv não encontrado. Execute as etapas de instalação do README.md primeiro." >&2
    exit 1
  fi
fi

if [ ! -d "${ROOT_DIR}/node_modules" ]; then
  echo "Dependências do frontend não encontradas. Executando npm install..."
  npm install
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

echo "Iniciando frontend Angular em http://localhost:4200 (proxy para :8000) ..."
npm run dev:web
