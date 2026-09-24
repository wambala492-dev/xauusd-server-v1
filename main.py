import json, os, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent.parent
DB = Path(os.getenv("DATABASE_PATH", BASE/"data/market.db"))
TOKEN = os.getenv("WEBHOOK_TOKEN", "CHANGE_ME")
DB.parent.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="XAUUSD Learning Engine V1", version="1.0.0")

class SignalIn(BaseModel):
    source: str = "TradingView"
    system: Optional[str] = None
    symbol: str
    exchange: Optional[str] = None
    timeframe: str
    timestamp: Optional[str] = None
    direction: str
    technical_score: Optional[float] = None
    price: Optional[float] = None
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    tp3: Optional[float] = None
    model_config = {"extra": "allow"}

class OutcomeIn(BaseModel):
    status: str = Field(..., description="OPEN, TP1, TP2, TP3, SL, CANCELLED ou EXPIRED")
    result_r: Optional[float] = None
    exit_price: Optional[float] = None
    notes: Optional[str] = None

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = conn()
    c.execute("""CREATE TABLE IF NOT EXISTS signals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        received_at TEXT NOT NULL, source TEXT, system TEXT,
        symbol TEXT NOT NULL, exchange TEXT, timeframe TEXT NOT NULL,
        signal_timestamp TEXT, direction TEXT NOT NULL,
        technical_score REAL, price REAL, entry REAL, stop_loss REAL,
        tp1 REAL, tp2 REAL, tp3 REAL,
        outcome_status TEXT NOT NULL DEFAULT 'OPEN',
        result_r REAL, exit_price REAL, outcome_notes TEXT,
        raw_json TEXT NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_signal_time ON signals(symbol,timeframe,received_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_outcome ON signals(outcome_status)")
    c.commit(); c.close()

@app.on_event("startup")
def startup(): init_db()

@app.get("/")
def root(): return {"service":"XAUUSD Learning Engine","version":"V1","status":"online","docs":"/docs"}

@app.get("/health")
def health(): return {"status":"ok","database":str(DB),"time_utc":datetime.now(timezone.utc).isoformat()}

@app.post("/webhook/{token}")
def webhook(token: str, payload: SignalIn):
    if token != TOKEN: raise HTTPException(401, "Invalid webhook token")
    direction = payload.direction.upper().strip()
    if direction not in {"BUY","SELL","WAIT"}: raise HTTPException(422, "direction must be BUY, SELL or WAIT")
    raw = payload.model_dump(mode="json")
    c = conn()
    cur = c.execute("""INSERT INTO signals(
        received_at,source,system,symbol,exchange,timeframe,signal_timestamp,
        direction,technical_score,price,entry,stop_loss,tp1,tp2,tp3,raw_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
        datetime.now(timezone.utc).isoformat(),payload.source,payload.system,
        payload.symbol,payload.exchange,payload.timeframe,payload.timestamp,
        direction,payload.technical_score,payload.price,payload.entry,
        payload.stop_loss,payload.tp1,payload.tp2,payload.tp3,
        json.dumps(raw,ensure_ascii=False)))
    sid=cur.lastrowid; c.commit(); c.close()
    return {"ok":True,"signal_id":sid,"message":"Signal received and stored"}

@app.get("/signals")
def signals(limit:int=50, symbol:Optional[str]=None):
    limit=max(1,min(limit,500)); c=conn()
    if symbol:
        rows=c.execute("SELECT * FROM signals WHERE symbol=? ORDER BY id DESC LIMIT ?",(symbol,limit)).fetchall()
    else:
        rows=c.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    c.close()
    return {"count":len(rows),"signals":[dict(r) for r in rows]}

@app.get("/signals/{signal_id}")
def signal(signal_id:int):
    c=conn(); row=c.execute("SELECT * FROM signals WHERE id=?",(signal_id,)).fetchone(); c.close()
    if not row: raise HTTPException(404,"Signal not found")
    d=dict(row); d["raw_json"]=json.loads(d["raw_json"]); return d

@app.patch("/signals/{signal_id}/outcome")
def outcome(signal_id:int, data:OutcomeIn):
    status=data.status.upper().strip()
    allowed={"OPEN","TP1","TP2","TP3","SL","CANCELLED","EXPIRED"}
    if status not in allowed: raise HTTPException(422,f"status must be one of {sorted(allowed)}")
    c=conn()
    cur=c.execute("""UPDATE signals SET outcome_status=?,result_r=?,exit_price=?,outcome_notes=? WHERE id=?""",
                  (status,data.result_r,data.exit_price,data.notes,signal_id))
    c.commit(); c.close()
    if cur.rowcount==0: raise HTTPException(404,"Signal not found")
    return {"ok":True,"signal_id":signal_id,"outcome_status":status,"result_r":data.result_r}

@app.get("/stats")
def stats(symbol:Optional[str]=None):
    c=conn(); where="WHERE symbol=?" if symbol else ""; p=(symbol,) if symbol else ()
    total=c.execute(f"SELECT COUNT(*) n FROM signals {where}",p).fetchone()["n"]
    closed=c.execute(f"""SELECT COUNT(*) n FROM signals {where} {"AND" if where else "WHERE"}
        outcome_status IN ('TP1','TP2','TP3','SL','CANCELLED','EXPIRED')""",p).fetchone()["n"]
    wins=c.execute(f"""SELECT COUNT(*) n FROM signals {where} {"AND" if where else "WHERE"}
        result_r IS NOT NULL AND result_r>0""",p).fetchone()["n"]
    avg=c.execute(f"""SELECT AVG(result_r) avg_r FROM signals {where} {"AND" if where else "WHERE"}
        result_r IS NOT NULL""",p).fetchone()["avg_r"]
    c.close()
    return {"symbol":symbol or "ALL","total_signals":total,"closed_signals":closed,
            "positive_results":wins,"win_rate_percent":(wins/closed*100 if closed else None),
            "average_result_r":avg}
