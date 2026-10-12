from __future__ import annotations

import json
import sqlite3
import os
from contextlib import contextmanager
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

DB_PATH = Path(__file__).with_name("learning_engine.db")


def agora() -> str:
    return datetime.now(timezone.utc).isoformat()


class _PGConnection:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=()):
        return self.conn.execute(sql.replace("?", "%s"), params)

    def executescript(self, script):
        for statement in script.split(";"):
            if statement.strip():
                self.conn.execute(statement)


@contextmanager
def _db():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, row_factory=dict_row, connect_timeout=10) as conn:
            yield _PGConnection(conn)
    else:
        conn = sqlite3.connect(DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()


def init_learning_db() -> None:
    with _db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id TEXT PRIMARY KEY,
            titulo TEXT NOT NULL,
            fonte TEXT,
            tipo TEXT NOT NULL DEFAULT 'hipotese',
            regra TEXT NOT NULL,
            condicoes TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'TESTANDO',
            amostras INTEGER NOT NULL DEFAULT 0,
            respeitou INTEGER NOT NULL DEFAULT 0,
            falhou INTEGER NOT NULL DEFAULT 0,
            inconclusivo INTEGER NOT NULL DEFAULT 0,
            confianca REAL NOT NULL DEFAULT 0.0,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS observations (
            id TEXT PRIMARY KEY,
            knowledge_id TEXT NOT NULL,
            ativo TEXT NOT NULL,
            timeframe TEXT,
            detectado_em TEXT NOT NULL,
            contexto TEXT NOT NULL DEFAULT '{}',
            resultado TEXT NOT NULL DEFAULT 'EM_OBSERVACAO',
            detalhe TEXT,
            FOREIGN KEY(knowledge_id) REFERENCES knowledge(id)
        );
        """)


def _consolidar_conhecimentos_duplicados() -> None:
    """Consolida hipóteses duplicadas pela mesma regra e condições.

    Mantém o conhecimento mais antigo, move as observações dos duplicados
    para ele e recalcula as estatísticas apenas a partir dos resultados reais.
    Observações EM_OBSERVACAO continuam pendentes e não contam como amostras.
    """
    with _db() as db:
        grupos = db.execute(
            """SELECT regra, condicoes, COUNT(*) AS qtd
               FROM knowledge
               GROUP BY regra, condicoes
               HAVING COUNT(*) > 1"""
        ).fetchall()

        for grupo in grupos:
            rows = db.execute(
                """SELECT * FROM knowledge
                   WHERE regra=? AND condicoes=?
                   ORDER BY criado_em ASC, id ASC""",
                (grupo["regra"], grupo["condicoes"]),
            ).fetchall()
            if len(rows) < 2:
                continue

            principal = rows[0]
            principal_id = principal["id"]
            duplicados = [r["id"] for r in rows[1:]]

            for dup_id in duplicados:
                db.execute(
                    "UPDATE observations SET knowledge_id=? WHERE knowledge_id=?",
                    (principal_id, dup_id),
                )
                db.execute("DELETE FROM knowledge WHERE id=?", (dup_id,))

            resultados = db.execute(
                """SELECT resultado, COUNT(*) AS qtd
                   FROM observations
                   WHERE knowledge_id=?
                   GROUP BY resultado""",
                (principal_id,),
            ).fetchall()
            contagem = {str(r["resultado"]).upper(): int(r["qtd"]) for r in resultados}
            respeitou = contagem.get("RESPEITOU", 0)
            falhou = contagem.get("FALHOU", 0)
            inconclusivo = contagem.get("INCONCLUSIVO", 0)
            amostras = respeitou + falhou
            status, confianca = _status(amostras, respeitou, falhou)

            db.execute(
                """UPDATE knowledge
                   SET amostras=?, respeitou=?, falhou=?, inconclusivo=?,
                       status=?, confianca=?, atualizado_em=?
                   WHERE id=?""",
                (amostras, respeitou, falhou, inconclusivo, status, confianca, agora(), principal_id),
            )


def _status(amostras: int, respeitou: int, falhou: int) -> tuple[str, float]:
    avaliadas = respeitou + falhou
    if avaliadas == 0:
        return "TESTANDO", 0.0
    confianca = round((respeitou / avaliadas) * 100, 2)
    if avaliadas < 30:
        return "TESTANDO", confianca
    if confianca >= 70:
        return "VALIDADA", confianca
    if confianca >= 55:
        return "CONTEXTUAL", confianca
    if confianca >= 45:
        return "EM_OBSERVACAO", confianca
    return "REJEITADA", confianca


def criar_conhecimento(titulo: str, regra: str, fonte: str = "", condicoes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    init_learning_db()
    now = agora()
    kid = str(uuid.uuid4())
    with _db() as db:
        db.execute(
            "INSERT INTO knowledge (id,titulo,fonte,regra,condicoes,criado_em,atualizado_em) VALUES (?,?,?,?,?,?,?)",
            (kid, titulo, fonte, regra, json.dumps(condicoes or {}, ensure_ascii=False), now, now),
        )
    return obter_conhecimento(kid)


def obter_conhecimento(kid: str) -> Optional[Dict[str, Any]]:
    init_learning_db()
    with _db() as db:
        row = db.execute("SELECT * FROM knowledge WHERE id=?", (kid,)).fetchone()
    return dict(row) if row else None


def listar_conhecimentos() -> list[Dict[str, Any]]:
    init_learning_db()
    with _db() as db:
        rows = db.execute("SELECT * FROM knowledge ORDER BY atualizado_em DESC").fetchall()
    return [dict(r) for r in rows]


def listar_observacoes_pendentes(knowledge_id: Optional[str] = None) -> list[Dict[str, Any]]:
    """Lista observações que foram detectadas mas ainda não receberam resultado real."""
    init_learning_db()
    with _db() as db:
        if knowledge_id:
            rows = db.execute(
                "SELECT * FROM observations WHERE knowledge_id=? AND resultado='EM_OBSERVACAO' ORDER BY detectado_em ASC",
                (knowledge_id,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM observations WHERE resultado='EM_OBSERVACAO' ORDER BY detectado_em ASC"
            ).fetchall()
    return [dict(r) for r in rows]


def _id_observacao(knowledge_id: str, ativo: str, timeframe: str, contexto: Dict[str, Any]) -> str:
    """Identificador permanente para uma ocorrência com ID explícito do sinal."""
    identificador = contexto.get("identificador_sinal")
    if identificador is None or isinstance(identificador, bool) or not str(identificador).strip():
        raise ValueError("identificador_sinal obrigatório para evitar duplicações")
    chave = json.dumps([str(knowledge_id), str(ativo).upper(), str(timeframe).upper(), str(identificador)], ensure_ascii=False, separators=(",", ":"))
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "xauusd:v7.3.1:" + chave))


def registrar_observacao(
    knowledge_id: str,
    ativo: str,
    timeframe: str,
    contexto: Dict[str, Any],
    resultado: str = "EM_OBSERVACAO",
    detalhe: str = "",
) -> Dict[str, Any]:
    """Registra uma detecção ou um resultado.

    EM_OBSERVACAO cria apenas uma ocorrência pendente e NÃO altera as
    estatísticas de amostras/confiança. Resultados finais são resolvidos
    posteriormente pela função resolver_observacao().
    """
    init_learning_db()
    resultado = resultado.upper()
    if resultado not in {"RESPEITOU", "FALHOU", "INCONCLUSIVO", "EM_OBSERVACAO"}:
        raise ValueError("resultado deve ser RESPEITOU, FALHOU, INCONCLUSIVO ou EM_OBSERVACAO")

    with _db() as db:
        k = db.execute("SELECT * FROM knowledge WHERE id=?", (knowledge_id,)).fetchone()
        if not k:
            raise ValueError("knowledge_id inexistente")

        # Identidade determinística, com conflito tratado atomicamente pela chave primária.
        # O mesmo sinal não volta a ser contado mesmo após a resolução.
        obs_id = _id_observacao(knowledge_id, ativo, timeframe, contexto)
        if resultado == "EM_OBSERVACAO":
            db.execute(
                "INSERT INTO observations (id,knowledge_id,ativo,timeframe,detectado_em,contexto,resultado,detalhe) "
                "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT (id) DO NOTHING",
                (obs_id, knowledge_id, ativo, timeframe, agora(), json.dumps(contexto, ensure_ascii=False), resultado, detalhe),
            )
            saida = dict(db.execute("SELECT * FROM knowledge WHERE id=?", (knowledge_id,)).fetchone())
            saida["observation_id"] = obs_id
            saida["observacao_duplicada"] = str(db.execute("SELECT resultado FROM observations WHERE id=?", (obs_id,)).fetchone()["resultado"]).upper() != "EM_OBSERVACAO"
            return saida

        # Resultados manuais com o mesmo identificador não podem duplicar amostras.
        inserido = db.execute(
            "INSERT INTO observations (id,knowledge_id,ativo,timeframe,detectado_em,contexto,resultado,detalhe) "
            "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT (id) DO NOTHING",
            (obs_id, knowledge_id, ativo, timeframe, agora(), json.dumps(contexto, ensure_ascii=False), resultado, detalhe),
        )
        if inserido.rowcount == 0:
            raise ValueError("sinal já registado; use resolver_observacao para uma observação pendente")

        amostras = int(k["amostras"]) + (0 if resultado == "INCONCLUSIVO" else 1)
        respeitou = int(k["respeitou"]) + (1 if resultado == "RESPEITOU" else 0)
        falhou = int(k["falhou"]) + (1 if resultado == "FALHOU" else 0)
        inconclusivo = int(k["inconclusivo"]) + (1 if resultado == "INCONCLUSIVO" else 0)
        status, confianca = _status(amostras, respeitou, falhou)

        db.execute(
            "UPDATE knowledge SET amostras=?,respeitou=?,falhou=?,inconclusivo=?,status=?,confianca=?,atualizado_em=? WHERE id=?",
            (amostras, respeitou, falhou, inconclusivo, status, confianca, agora(), knowledge_id),
        )

    return obter_conhecimento(knowledge_id)


def resolver_observacao(observation_id: str, resultado: str, detalhe: str = "") -> Dict[str, Any]:
    """Fecha uma observação pendente e conta o resultado uma única vez."""
    init_learning_db()
    resultado = resultado.upper()
    if resultado not in {"RESPEITOU", "FALHOU", "INCONCLUSIVO"}:
        raise ValueError("resultado deve ser RESPEITOU, FALHOU ou INCONCLUSIVO")

    with _db() as db:
        obs = db.execute("SELECT * FROM observations WHERE id=?" + (" FOR UPDATE" if os.environ.get("DATABASE_URL", "").strip() else ""), (observation_id,)).fetchone()
        if not obs:
            raise ValueError("observation_id inexistente")
        if str(obs["resultado"]).upper() != "EM_OBSERVACAO":
            raise ValueError("observação já foi resolvida")

        k = db.execute("SELECT * FROM knowledge WHERE id=?", (obs["knowledge_id"],)).fetchone()
        if not k:
            raise ValueError("knowledge_id inexistente")

        db.execute(
            "UPDATE observations SET resultado=?, detalhe=? WHERE id=? AND resultado='EM_OBSERVACAO'",
            (resultado, detalhe, observation_id),
        )

        # INCONCLUSIVO fica registrado, mas não entra no denominador da confiança.
        amostras = int(k["amostras"]) + (0 if resultado == "INCONCLUSIVO" else 1)
        respeitou = int(k["respeitou"]) + (1 if resultado == "RESPEITOU" else 0)
        falhou = int(k["falhou"]) + (1 if resultado == "FALHOU" else 0)
        inconclusivo = int(k["inconclusivo"]) + (1 if resultado == "INCONCLUSIVO" else 0)
        status, confianca = _status(amostras, respeitou, falhou)

        db.execute(
            "UPDATE knowledge SET amostras=?,respeitou=?,falhou=?,inconclusivo=?,status=?,confianca=?,atualizado_em=? WHERE id=?",
            (amostras, respeitou, falhou, inconclusivo, status, confianca, agora(), obs["knowledge_id"]),
        )

    return obter_conhecimento(str(obs["knowledge_id"]))


def resumo() -> Dict[str, Any]:
    conhecimentos = listar_conhecimentos()
    return {
        "total_conhecimentos": len(conhecimentos),
        "testando": sum(x["status"] == "TESTANDO" for x in conhecimentos),
        "validadas": sum(x["status"] == "VALIDADA" for x in conhecimentos),
        "contextuais": sum(x["status"] == "CONTEXTUAL" for x in conhecimentos),
        "em_observacao": sum(x["status"] == "EM_OBSERVACAO" for x in conhecimentos),
        "rejeitadas": sum(x["status"] == "REJEITADA" for x in conhecimentos),
    }



def obter_ou_criar_conhecimento(titulo: str, regra: str, fonte: str, condicoes: Dict[str, Any]) -> Dict[str, Any]:
    """Obtém hipótese idêntica ou cria uma; serialização estável evita duplicados."""
    init_learning_db()
    cond = json.dumps(condicoes, ensure_ascii=False, sort_keys=True)
    with _db() as db:
        row = db.execute("SELECT * FROM knowledge WHERE regra=? AND condicoes=? ORDER BY criado_em LIMIT 1", (regra, cond)).fetchone()
        if row:
            return dict(row)
        kid = str(uuid.uuid4())
        now = agora()
        db.execute("INSERT INTO knowledge (id,titulo,fonte,regra,condicoes,criado_em,atualizado_em) VALUES (?,?,?,?,?,?,?)", (kid, titulo, fonte, regra, cond, now, now))
        return dict(db.execute("SELECT * FROM knowledge WHERE id=?", (kid,)).fetchone())

init_learning_db()

_consolidar_conhecimentos_duplicados()
