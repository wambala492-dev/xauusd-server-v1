# XAUUSD Server V1

Recebe sinais JSON do TradingView, valida, guarda em SQLite e permite registrar o resultado posterior.

## Instalar
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt

## Configurar
export WEBHOOK_TOKEN="SEU_TOKEN_LONGO"
export DATABASE_PATH="data/market.db"

## Executar
uvicorn app.main:app --host 0.0.0.0 --port 8000

## Endpoints
GET /health
GET /docs
POST /webhook/SEU_TOKEN
GET /signals
GET /signals/{id}
PATCH /signals/{id}/outcome
GET /stats

A V1 não executa ordens. Ela cria a memória de sinais para o futuro News Engine, AI Engine e laboratório de aprendizagem.
