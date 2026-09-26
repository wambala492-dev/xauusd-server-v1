from fastapi import FastAPI, Request
from datetime import datetime, timezone
import json
import re
import requests
import xml.etree.ElementTree as ET


# ============================================================
# XAUUSD IA + NOTÍCIAS
# V6.0
# ============================================================

app = FastAPI(
    title="XAUUSD IA + NOTÍCIAS",
    version="6.0"
)

ULTIMO_SINAL = None


# ============================================================
# RSS
# ============================================================

RSS_FEEDS = [
    "https://www.investing.com/rss/news_25.rss",
    "https://www.investing.com/rss/news_14.rss",
    "https://www.investing.com/rss/news_301.rss"
]


# ============================================================
# PALAVRAS-CHAVE
# ============================================================

PALAVRAS_DOLAR = [
    "dollar",
    "usd",
    "us dollar",
    "greenback",
    "dollar index",
    "dxy",
    "buck"
]

PALAVRAS_DOLAR_FORTE = [
    "firm dollar",
    "strong dollar",
    "dollar strengthens",
    "dollar strengthened",
    "dollar gains",
    "dollar rises",
    "dollar rose",
    "dollar climbs",
    "dollar climbed",
    "dollar advances",
    "dollar advanced",
    "dollar rally",
    "dollar gains ground",
    "dollar hits",
    "dollar high",
    "dollar two-month high",
    "dollar 2-month high",
    "fresh high for dollar",
    "higher dollar"
]

PALAVRAS_DOLAR_FRACO = [
    "weak dollar",
    "weaker dollar",
    "dollar weakens",
    "dollar weakened",
    "dollar falls",
    "dollar fell",
    "dollar drops",
    "dollar dropped",
    "dollar declines",
    "dollar declined",
    "dollar slips",
    "dollar slipped",
    "dollar loses ground",
    "dollar retreat",
    "dollar retreats",
    "dollar selloff"
]


# ============================================================
# FED / POLÍTICA MONETÁRIA
# ============================================================

PALAVRAS_FED = [
    "federal reserve",
    "fed",
    "fomc",
    "powell",
    "fed officials",
    "fed policymakers"
]

PALAVRAS_FED_MONETARIO = [
    "interest rate",
    "interest rates",
    "rate decision",
    "rate hike",
    "rate hikes",
    "rate cut",
    "rate cuts",
    "policy rate",
    "monetary policy",
    "monetary",
    "tightening",
    "easing",
    "quantitative tightening",
    "quantitative easing",
    "hawkish",
    "dovish",
    "higher for longer",
    "rate expectations",
    "rate outlook"
]

PALAVRAS_ALTA_JUROS = [
    "rate hike",
    "rate hikes",
    "higher rates",
    "higher interest rates",
    "rates rise",
    "rates rising",
    "rates increase",
    "rates increased",
    "hawkish",
    "tightening",
    "tight monetary policy",
    "rate hike expectations",
    "higher rate expectations",
    "higher for longer"
]

PALAVRAS_BAIXA_JUROS = [
    "rate cut",
    "rate cuts",
    "lower rates",
    "lower interest rates",
    "rates fall",
    "rates falling",
    "rates decrease",
    "rates decreased",
    "dovish",
    "easing",
    "rate cut expectations",
    "lower rate expectations"
]


# ============================================================
# YIELDS / TREASURY
# ============================================================

PALAVRAS_YIELDS_ALTOS = [
    "higher yields",
    "yield rises",
    "yields rise",
    "yield rose",
    "yields rose",
    "yield climbs",
    "yields climb",
    "yield climbed",
    "yields climbed",
    "treasury yields rise",
    "treasury yields higher",
    "us yields rise",
    "us yields higher",
    "bond yields rise",
    "bond yields higher",
    "10-year yield rises",
    "10-year yields rise",
    "10-year yield higher",
    "10-year yields higher"
]

PALAVRAS_YIELDS_BAIXOS = [
    "lower yields",
    "yield falls",
    "yields fall",
    "yield fell",
    "yields fell",
    "yield declines",
    "yields decline",
    "yield dropped",
    "yields dropped",
    "treasury yields fall",
    "treasury yields lower",
    "us yields fall",
    "us yields lower",
    "bond yields fall",
    "bond yields lower"
]


# ============================================================
# INFLAÇÃO EUA
# ============================================================

PALAVRAS_INFLACAO_EUA = [
    "us inflation",
    "u.s. inflation",
    "us cpi",
    "u.s. cpi",
    "consumer price index",
    "core cpi",
    "cpi inflation",
    "inflation rises",
    "inflation rose",
    "inflation remains high",
    "inflation stays high",
    "hot inflation",
    "inflation cools",
    "inflation cooled",
    "inflation falls",
    "inflation fell",
    "inflation eases",
    "inflation eased",
    "pce inflation",
    "core pce"
]


# ============================================================
# EMPREGO EUA
# ============================================================

PALAVRAS_EMPREGO_EUA = [
    "us jobs",
    "u.s. jobs",
    "us employment",
    "u.s. employment",
    "nonfarm payrolls",
    "non-farm payrolls",
    "payrolls",
    "jobless claims",
    "unemployment rate",
    "us unemployment",
    "u.s. unemployment",
    "jobs report",
    "employment report",
    "labor market",
    "labour market",
    "wage growth",
    "average hourly earnings"
]


# ============================================================
# GEOPOLÍTICA
# ============================================================

PALAVRAS_GEOPOLITICA = [
    "war",
    "warfare",
    "military conflict",
    "military tensions",
    "geopolitical",
    "geopolitical tensions",
    "missile",
    "missiles",
    "airstrike",
    "air strikes",
    "strike",
    "strikes",
    "attack",
    "attacks",
    "invasion",
    "conflict",
    "ceasefire",
    "middle east",
    "iran",
    "israel",
    "russia",
    "ukraine"
]

CONTEXTO_GEOPOLITICO = [
    "iran",
    "israel",
    "ukraine",
    "russia",
    "middle east",
    "war",
    "military",
    "missile",
    "attack",
    "conflict",
    "ceasefire",
    "invasion"
]


# ============================================================
# CRIPTO
# ============================================================

PALAVRAS_CRIPTO = [
    "bitcoin",
    "btc",
    "ethereum",
    "crypto",
    "cryptocurrency",
    "stablecoin",
    "usdt",
    "digital asset",
    "digital assets"
]


# ============================================================
# FUNÇÕES BÁSICAS
# ============================================================

def agora():
    return datetime.now(timezone.utc).isoformat()


def texto_limpo(texto):
    if not texto:
        return ""

    texto = texto.replace("&amp;", "&")
    texto = texto.replace("&quot;", '"')
    texto = texto.replace("&#39;", "'")

    return re.sub(r"\s+", " ", texto).strip()


def contem_palavra(texto, palavra):
    texto = texto.lower()
    palavra = palavra.lower()

    if " " in palavra or "-" in palavra:
        return palavra in texto

    return re.search(
        r"\b" + re.escape(palavra) + r"\b",
        texto
    ) is not None


def contem_alguma(texto, palavras):
    return any(
        contem_palavra(texto, palavra)
        for palavra in palavras
    )


def contexto_eua(texto):
    palavras = [
        "us",
        "u.s.",
        "united states",
        "american",
        "america",
        "federal reserve",
        "fed",
        "fomc",
        "treasury",
        "dollar",
        "usd"
    ]

    return contem_alguma(
        texto,
        palavras
    )


def contexto_monetario_eua(texto):
    return (
        contem_alguma(
            texto,
            PALAVRAS_FED
        )
        and
        contem_alguma(
            texto,
            PALAVRAS_FED_MONETARIO
        )
    )


def contexto_yields_eua(texto):
    return (
        contem_alguma(
            texto,
            PALAVRAS_YIELDS_ALTOS
        )
        or
        contem_alguma(
            texto,
            PALAVRAS_YIELDS_BAIXOS
        )
    )


# ============================================================
# DIREÇÃO DO OURO
# ============================================================

def analisar_direcao_ouro(texto):

    positivo = 0
    negativo = 0

    motivos_positivos = []
    motivos_negativos = []

    # --------------------------------------------------------
    # DÓLAR
    # --------------------------------------------------------

    dolar_forte = contem_alguma(
        texto,
        PALAVRAS_DOLAR_FORTE
    )

    dolar_fraco = contem_alguma(
        texto,
        PALAVRAS_DOLAR_FRACO
    )

    if dolar_forte:

        negativo += 3

        motivos_negativos.append(
            "dolar_forte_pressiona_ouro"
        )

    if dolar_fraco:

        positivo += 3

        motivos_positivos.append(
            "dolar_fraco_favorece_ouro"
        )

    # --------------------------------------------------------
    # DÓLAR EM NOVA MÁXIMA
    # --------------------------------------------------------

    if (
        contem_alguma(
            texto,
            PALAVRAS_DOLAR
        )
        and
        (
            "fresh high" in texto.lower()
            or
            "two-month high" in texto.lower()
            or
            "2-month high" in texto.lower()
            or
            "multi-month high" in texto.lower()
            or
            "dollar ascends" in texto.lower()
            or
            "dollar climbs" in texto.lower()
        )
    ):

        if (
            "dolar_forte_pressiona_ouro"
            not in motivos_negativos
        ):

            negativo += 3

            motivos_negativos.append(
                "dolar_em_alta_pressiona_ouro"
            )

    # --------------------------------------------------------
    # JUROS
    # --------------------------------------------------------

    juros_altos = contem_alguma(
        texto,
        PALAVRAS_ALTA_JUROS
    )

    juros_baixos = contem_alguma(
        texto,
        PALAVRAS_BAIXA_JUROS
    )

    if juros_altos:

        negativo += 3

        motivos_negativos.append(
            "expectativa_alta_juros_pressiona_ouro"
        )

    if juros_baixos:

        positivo += 3

        motivos_positivos.append(
            "expectativa_baixa_juros_favorece_ouro"
        )

    # --------------------------------------------------------
    # YIELDS
    # --------------------------------------------------------

    yields_altos = contem_alguma(
        texto,
        PALAVRAS_YIELDS_ALTOS
    )

    yields_baixos = contem_alguma(
        texto,
        PALAVRAS_YIELDS_BAIXOS
    )

    if (
        yields_altos
        and
        contexto_eua(texto)
    ):

        negativo += 2

        motivos_negativos.append(
            "yields_eua_altos_pressionam_ouro"
        )

    if (
        yields_baixos
        and
        contexto_eua(texto)
    ):

        positivo += 2

        motivos_positivos.append(
            "yields_eua_baixos_favorecem_ouro"
        )

    # --------------------------------------------------------
    # FED
    # --------------------------------------------------------

    if contexto_monetario_eua(texto):

        if contem_palavra(
            texto,
            "hawkish"
        ):

            negativo += 2

            motivos_negativos.append(
                "fed_hawkish_pressiona_ouro"
            )

        if contem_palavra(
            texto,
            "dovish"
        ):

            positivo += 2

            motivos_positivos.append(
                "fed_dovish_favorece_ouro"
            )

    # --------------------------------------------------------
    # INFLAÇÃO
    # --------------------------------------------------------

    if contem_alguma(
        texto,
        PALAVRAS_INFLACAO_EUA
    ):

        if contem_alguma(
            texto,
            [
                "inflation rises",
                "inflation rose",
                "inflation remains high",
                "inflation stays high",
                "hot inflation",
                "higher inflation"
            ]
        ):

            negativo += 2

            motivos_negativos.append(
                "inflacao_alta_pode_pressionar_ouro"
            )

        if contem_alguma(
            texto,
            [
                "inflation cools",
                "inflation cooled",
                "inflation falls",
                "inflation fell",
                "inflation eases",
                "inflation eased",
                "lower inflation"
            ]
        ):

            positivo += 2

            motivos_positivos.append(
                "inflacao_menor_favorece_ouro"
            )

    # --------------------------------------------------------
    # EMPREGO
    # --------------------------------------------------------

    if contem_alguma(
        texto,
        PALAVRAS_EMPREGO_EUA
    ):

        if contem_alguma(
            texto,
            [
                "strong jobs",
                "strong employment",
                "strong payrolls",
                "jobs beat",
                "payrolls beat",
                "employment rises",
                "wage growth accelerates"
            ]
        ):

            negativo += 2

            motivos_negativos.append(
                "emprego_forte_pode_manter_juros_altos"
            )

        if contem_alguma(
            texto,
            [
                "weak jobs",
                "weak employment",
                "weak payrolls",
                "jobs miss",
                "payrolls miss",
                "employment falls",
                "unemployment rises"
            ]
        ):

            positivo += 2

            motivos_positivos.append(
                "emprego_fraco_pode_favorecer_cortes"
            )

    # --------------------------------------------------------
    # GEOPOLÍTICA
    # --------------------------------------------------------

    if contem_alguma(
        texto,
        CONTEXTO_GEOPOLITICO
    ):

        if contem_alguma(
            texto,
            PALAVRAS_GEOPOLITICA
        ):

            positivo += 4

            motivos_positivos.append(
                "geopolitica_favorece_ouro"
            )

    # --------------------------------------------------------
    # COMBINAÇÃO DÓLAR + JUROS/YIELDS
    # --------------------------------------------------------

    if (
        dolar_forte
        and
        (
            juros_altos
            or
            yields_altos
        )
    ):

        negativo += 2

        motivos_negativos.append(
            "dolar_forte_com_juros_ou_yields_altos"
        )

    saldo = (
        positivo
        -
        negativo
    )

    if saldo >= 2:
        direcao = "POSITIVA"

    elif saldo <= -2:
        direcao = "NEGATIVA"

    else:
        direcao = "NEUTRA"

    return {
        "direcao": direcao,
        "pontos_direcao": saldo,
        "motivos_positivos":
            motivos_positivos,
        "motivos_negativos":
            motivos_negativos
    }


# ============================================================
# PESO DE RELEVÂNCIA
# ============================================================

def calcular_peso_relevancia(
    texto,
    categorias,
    pontos_base
):

    peso = 1

    # --------------------------------------------------------
    # FED / FOMC / POWELL
    # --------------------------------------------------------

    if "FED" in categorias:

        peso = max(
            peso,
            5
        )

    # --------------------------------------------------------
    # INFLAÇÃO / EMPREGO
    # --------------------------------------------------------

    if (
        "INFLAÇÃO_EUA"
        in categorias
    ):

        peso = max(
            peso,
            5
        )

    if (
        "EMPREGO_EUA"
        in categorias
    ):

        peso = max(
            peso,
            5
        )

    # --------------------------------------------------------
    # USD / YIELDS
    # --------------------------------------------------------

    if "USD" in categorias:

        peso = max(
            peso,
            4
        )

    if "JUROS_EUA" in categorias:

        peso = max(
            peso,
            4
        )

    # --------------------------------------------------------
    # GEOPOLÍTICA
    # --------------------------------------------------------

    if "GEOPOLÍTICA" in categorias:

        peso = max(
            peso,
            4
        )

    # --------------------------------------------------------
    # CRIPTO
    # --------------------------------------------------------

    if "CRIPTO" in categorias:

        # Se a notícia é predominantemente cripto,
        # reduzimos o peso macro.
        if len(categorias) == 1:

            peso = 0

        else:

            peso = min(
                peso,
                2
            )

    return peso


# ============================================================
# CLASSIFICAÇÃO
# ============================================================

def classificar_noticia(
    titulo,
    descricao=""
):

    texto = texto_limpo(
        f"{titulo} {descricao}"
    ).lower()

    categorias = []
    pontos = 0

    # --------------------------------------------------------
    # USD
    # --------------------------------------------------------

    if contem_alguma(
        texto,
        PALAVRAS_DOLAR
    ):

        categorias.append(
            "USD"
        )

        pontos += 4

    # --------------------------------------------------------
    # FED
    # --------------------------------------------------------

    if contexto_monetario_eua(
        texto
    ):

        categorias.append(
            "FED"
        )

        pontos += 5

    # --------------------------------------------------------
    # JUROS EUA
    # --------------------------------------------------------

    if (
        contexto_eua(texto)
        and
        (
            contem_alguma(
                texto,
                PALAVRAS_ALTA_JUROS
            )
            or
            contem_alguma(
                texto,
                PALAVRAS_BAIXA_JUROS
            )
            or
            contexto_yields_eua(
                texto
            )
        )
    ):

        categorias.append(
            "JUROS_EUA"
        )

        pontos += 4

    # --------------------------------------------------------
    # INFLAÇÃO
    # --------------------------------------------------------

    if (
        contexto_eua(texto)
        and
        contem_alguma(
            texto,
            PALAVRAS_INFLACAO_EUA
        )
    ):

        categorias.append(
            "INFLAÇÃO_EUA"
        )

        pontos += 4

    # --------------------------------------------------------
    # EMPREGO
    # --------------------------------------------------------

    if (
        contexto_eua(texto)
        and
        contem_alguma(
            texto,
            PALAVRAS_EMPREGO_EUA
        )
    ):

        categorias.append(
            "EMPREGO_EUA"
        )

        pontos += 4

    # --------------------------------------------------------
    # GEOPOLÍTICA
    # --------------------------------------------------------

    if (
        contem_alguma(
            texto,
            CONTEXTO_GEOPOLITICO
        )
        and
        contem_alguma(
            texto,
            PALAVRAS_GEOPOLITICA
        )
    ):

        categorias.append(
            "GEOPOLÍTICA"
        )

        pontos += 3

    # --------------------------------------------------------
    # CRIPTO
    # --------------------------------------------------------

    if contem_alguma(
        texto,
        PALAVRAS_CRIPTO
    ):

        categorias.append(
            "CRIPTO"
        )

    # --------------------------------------------------------
    # RELEVÂNCIA
    # --------------------------------------------------------

    categorias_macro = [
        "USD",
        "FED",
        "JUROS_EUA",
        "INFLAÇÃO_EUA",
        "EMPREGO_EUA",
        "GEOPOLÍTICA"
    ]

    relevante_xauusd = any(
        categoria in categorias
        for categoria in categorias_macro
    )

    # --------------------------------------------------------
    # CRIPTO PURA
    # --------------------------------------------------------

    somente_cripto = (
        "CRIPTO" in categorias
        and
        not any(
            categoria in categorias
            for categoria in categorias_macro
        )
    )

    if somente_cripto:

        relevante_xauusd = False
        pontos = 0

    # --------------------------------------------------------
    # IMPACTO
    # --------------------------------------------------------

    if pontos >= 10:

        impacto = "ALTO"

    elif pontos >= 5:

        impacto = "MEDIO"

    elif pontos >= 3:

        impacto = "BAIXO"

    else:

        impacto = "IGNORAR"

    # --------------------------------------------------------
    # DIREÇÃO
    # --------------------------------------------------------

    direcao = analisar_direcao_ouro(
        texto
    )

    # --------------------------------------------------------
    # PESO
    # --------------------------------------------------------

    peso = calcular_peso_relevancia(
        texto,
        categorias,
        pontos
    )

    # --------------------------------------------------------
    # PONTUAÇÃO DIRECIONAL AJUSTADA
    # --------------------------------------------------------

    pontos_direcao_ajustados = (
        direcao["pontos_direcao"]
        *
        peso
    )

    return {
        "impacto": impacto,
        "pontos": pontos,
        "peso_relevancia": peso,
        "categorias": categorias,
        "direcao_ouro":
            direcao["direcao"],
        "pontos_direcao":
            direcao["pontos_direcao"],
        "pontos_direcao_ajustados":
            pontos_direcao_ajustados,
        "motivos_direcao":
            (
                direcao[
                    "motivos_positivos"
                ]
                +
                direcao[
                    "motivos_negativos"
                ]
            ),
        "relevante_xauusd":
            relevante_xauusd
    }


# ============================================================
# BUSCAR NOTÍCIAS
# ============================================================

def buscar_noticias():

    noticias = []

    for feed_url in RSS_FEEDS:

        try:

            resposta = requests.get(
                feed_url,
                timeout=10,
                headers={
                    "User-Agent":
                        "Mozilla/5.0 XAUUSD-IA-NEWS"
                }
            )

            if resposta.status_code != 200:
                continue

            raiz = ET.fromstring(
                resposta.content
            )

            for item in raiz.findall(
                ".//item"
            ):

                titulo = item.findtext(
                    "title",
                    default=""
                )

                descricao = item.findtext(
                    "description",
                    default=""
                )

                link = item.findtext(
                    "link",
                    default=""
                )

                data = item.findtext(
                    "pubDate",
                    default=""
                )

                titulo = texto_limpo(
                    titulo
                )

                descricao = texto_limpo(
                    descricao
                )

                if not titulo:
                    continue

                analise = classificar_noticia(
                    titulo,
                    descricao
                )

                if not analise[
                    "relevante_xauusd"
                ]:
                    continue

                if analise[
                    "impacto"
                ] == "IGNORAR":
                    continue

                noticias.append({

                    "titulo":
                        titulo,

                    "link":
                        link,

                    "data":
                        data,

                    "impacto":
                        analise[
                            "impacto"
                        ],

                    "pontos":
                        analise[
                            "pontos"
                        ],

                    "peso_relevancia":
                        analise[
                            "peso_relevancia"
                        ],

                    "categorias":
                        analise[
                            "categorias"
                        ],

                    "direcao_ouro":
                        analise[
                            "direcao_ouro"
                        ],

                    "pontos_direcao":
                        analise[
                            "pontos_direcao"
                        ],

                    "pontos_direcao_ajustados":
                        analise[
                            "pontos_direcao_ajustados"
                        ],

                    "motivos_direcao":
                        analise[
                            "motivos_direcao"
                        ],

                    "relevante_xauusd":
                        True
                })

        except Exception:
            continue

    # ========================================================
    # DUPLICADOS
    # ========================================================

    unicas = {}

    for noticia in noticias:

        chave = noticia[
            "titulo"
        ].lower().strip()

        if chave not in unicas:

            unicas[
                chave
            ] = noticia

    noticias = list(
        unicas.values()
    )

    # ========================================================
    # ORDENAR POR PESO + IMPACTO
    # ========================================================

    noticias.sort(
        key=lambda x: (
            abs(
                x[
                    "pontos_direcao_ajustados"
                ]
            ),
            x[
                "pontos"
            ]
        ),
        reverse=True
    )

    return noticias[:20]


# ============================================================
# ANÁLISE GERAL DAS NOTÍCIAS
# ============================================================

def analisar_noticias():

    noticias = buscar_noticias()

    forca_positiva = 0
    forca_negativa = 0

    positivas = 0
    negativas = 0
    neutras = 0

    for noticia in noticias:

        pontos = noticia.get(
            "pontos_direcao_ajustados",
            0
        )

        if pontos > 0:

            forca_positiva += pontos
            positivas += 1

        elif pontos < 0:

            forca_negativa += abs(
                pontos
            )

            negativas += 1

        else:

            neutras += 1

    saldo_noticias = (
        forca_positiva
        -
        forca_negativa
    )

    # ========================================================
    # DIREÇÃO
    # ========================================================

    if saldo_noticias >= 5:

        direcao_ouro = "POSITIVA"

    elif saldo_noticias <= -5:

        direcao_ouro = "NEGATIVA"

    else:

        direcao_ouro = "NEUTRA"

    # ========================================================
    # CONFIANÇA
    # ========================================================

    forca_total = (
        forca_positiva
        +
        forca_negativa
    )

    if forca_total >= 12:

        confianca = "ALTA"

    elif forca_total >= 6:

        confianca = "MEDIA"

    else:

        confianca = "BAIXA"

    # ========================================================
    # IMPACTO
    # ========================================================

    if forca_total >= 12:

        impacto = "ALTO"

    elif forca_total >= 6:

        impacto = "MEDIO"

    else:

        impacto = "BAIXO"

    return {

        "status": "OK",

        "impacto":
            impacto,

        "direcao_ouro":
            direcao_ouro,

        "confianca":
            confianca,

        "forca_positiva":
            forca_positiva,

        "forca_negativa":
            forca_negativa,

        "saldo_noticias":
            saldo_noticias,

        "quantidade":
            len(noticias),

        "positivas":
            positivas,

        "negativas":
            negativas,

        "neutras":
            neutras,

        "noticias":
            noticias
    }


# ============================================================
# VALIDAÇÃO
# ============================================================

def validar_sinal(data):

    campos = [
        "ativo",
        "timeframe_operacao",
        "sinal",
        "score_tecnico",
        "entrada",
        "stop_loss",
        "tp1",
        "tp2",
        "tp3"
    ]

    return [
        campo
        for campo in campos
        if campo not in data
    ]


# ============================================================
# ANÁLISE TÉCNICA
# ============================================================

def analisar_tecnico(data):

    sinal = str(data.get("sinal", "")).upper()
    score = float(data.get("score_tecnico", 0))
    compras = int(data.get("compras_alinhadas", 0))
    vendas = int(data.get("vendas_alinhadas", 0))
    rsi = float(data.get("rsi_m5", 50))

    price_action = analisar_price_action(data)

    resultado = {
        "sinal_tecnico": sinal,
        "score": score,
        "alinhamento": False,
        "rsi_confirmado": False,
        "price_action": price_action,
        "status": "AGUARDAR"
    }

    if sinal == "BUY":
        resultado["alinhamento"] = compras >= 4
        resultado["rsi_confirmado"] = 50 <= rsi < 75
    elif sinal == "SELL":
        resultado["alinhamento"] = vendas >= 4
        resultado["rsi_confirmado"] = 25 < rsi <= 50

    base_ok = score >= 70 and resultado["alinhamento"] and resultado["rsi_confirmado"]

    # Sem candles, mantém compatibilidade com o webhook antigo, mas não inventa price action.
    if price_action["status"] == "SEM_DADOS":
        resultado["status"] = sinal if base_ok else "AGUARDAR"
        resultado["price_action_obrigatorio"] = False
        return resultado

    pa_sinal = price_action["confluencia"]["sinal"]
    resultado["price_action_obrigatorio"] = True

    if base_ok and pa_sinal == sinal:
        resultado["status"] = sinal
    else:
        resultado["status"] = "AGUARDAR"

    return resultado



# ============================================================
# V6.0 — ESTRUTURA DE PREÇO / PRICE ACTION
# ============================================================

def _numero(valor, padrao=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return float(padrao)

def normalizar_candles(data):
    bruto = data.get("candles", data.get("ohlc", []))
    if not isinstance(bruto, list): return []
    candles=[]
    for c in bruto[-100:]:
        if not isinstance(c, dict): continue
        o = _numero(c.get("open", c.get("o")))
        h = _numero(c.get("high", c.get("h")))
        l = _numero(c.get("low", c.get("l")))
        cl = _numero(c.get("close", c.get("c")))
        if h<=0 or l<=0 or h<l or cl<=0: continue
        if o<=0: o=cl
        candles.append({"open":o,"high":h,"low":l,"close":cl})
    return candles

def anatomia_candle(c):
    o,h,l,cl=c["open"],c["high"],c["low"],c["close"]; faixa=max(h-l,1e-9); corpo=abs(cl-o); ps=h-max(o,cl); pi=min(o,cl)-l; pct=corpo/faixa
    forca="INDECISAO" if pct<=.15 else "FORTE" if pct>=.70 else "MODERADA" if pct>=.45 else "FRACA"
    direcao="ALTA" if cl>o else "BAIXA" if cl<o else "NEUTRA"
    rejeicao="COMPRADORA" if pi>=corpo*2 and pi>=faixa*.30 else "VENDEDORA" if ps>=corpo*2 and ps>=faixa*.30 else "NENHUMA"
    return {"direcao":direcao,"forca":forca,"corpo":round(corpo,5),"pavio_superior":round(ps,5),"pavio_inferior":round(pi,5),"corpo_percentual":round(pct*100,2),"rejeicao":rejeicao}

def detectar_padrao_candle(candles):
    if not candles: return {"padrao":"SEM_DADOS","sinal":"NEUTRO"}
    atual=candles[-1]; a=anatomia_candle(atual); p=[]; sinal="NEUTRO"
    if a["corpo_percentual"]<=15: p.append("DOJI_INDECISAO")
    if a["rejeicao"]=="COMPRADORA": p.append("REJEICAO_INFERIOR"); sinal="BUY"
    if a["rejeicao"]=="VENDEDORA": p.append("REJEICAO_SUPERIOR"); sinal="SELL"
    if len(candles)>=2:
        ant=candles[-2]; ca=abs(ant["close"]-ant["open"]); cc=abs(atual["close"]-atual["open"])
        if ant["close"]<ant["open"] and atual["close"]>atual["open"] and atual["open"]<=ant["close"] and atual["close"]>=ant["open"] and cc>=ca*.8: p.append("ENGOLFO_ALTISTA"); sinal="BUY"
        if ant["close"]>ant["open"] and atual["close"]<atual["open"] and atual["open"]>=ant["close"] and atual["close"]<=ant["open"] and cc>=ca*.8: p.append("ENGOLFO_BAIXISTA"); sinal="SELL"
    return {"padrao":",".join(p) if p else "NORMAL","sinal":sinal,"anatomia":a}

def calcular_zonas(candles,tolerancia_pct=.0015):
    if len(candles)<8: return {"suporte":None,"resistencia":None,"testes_suporte":0,"testes_resistencia":0,"forca_suporte":"SEM_DADOS","forca_resistencia":"SEM_DADOS"}
    baixos=[c["low"] for c in candles[:-1]][-10:]; altos=[c["high"] for c in candles[:-1]][-10:]; suporte=sum(baixos)/len(baixos); resistencia=sum(altos)/len(altos); atual=candles[-1]["close"]
    def testes(nivel,campo): return sum(1 for c in candles[:-1] if abs(c[campo]-nivel)/max(nivel,1e-9)<=tolerancia_pct)
    ts,tr=testes(suporte,"low"),testes(resistencia,"high")
    def forca(n): return "FORTE" if n>=4 else "MEDIA" if n>=2 else "FRACA" if n==1 else "SEM_TESTE"
    return {"suporte":round(suporte,5),"resistencia":round(resistencia,5),"distancia_suporte_pct":round(abs(atual-suporte)/max(atual,1e-9)*100,4),"distancia_resistencia_pct":round(abs(resistencia-atual)/max(atual,1e-9)*100,4),"testes_suporte":ts,"testes_resistencia":tr,"forca_suporte":forca(ts),"forca_resistencia":forca(tr)}

def analisar_pullback_reteste(candles,zonas,sinal):
    if len(candles)<8 or not zonas.get("suporte") or not zonas.get("resistencia"): return {"pullback":False,"reteste":False,"rompimento":False,"falso_rompimento":False,"confirmacao":False,"tipo":"SEM_DADOS"}
    fechamento=candles[-1]["close"]; suporte=zonas["suporte"]; resistencia=zonas["resistencia"]; margem=max(fechamento*.0015,(resistencia-suporte)*.10); janela=candles[-6:-1]
    rr=any(c["close"]>resistencia+margem*.15 for c in janela); rs=any(c["close"]<suporte-margem*.15 for c in janela); pr=abs(fechamento-resistencia)<=margem; ps=abs(fechamento-suporte)<=margem
    pull=reteste=confirm=falso=False; tipo="NENHUM"
    if sinal=="BUY":
        reteste=pull=rr and pr; confirm=pull and fechamento>=resistencia; falso=rr and fechamento<resistencia-margem*.20; tipo="PULLBACK_RESISTENCIA_ROMPIDAA" if pull else "TESTE_SUPORTE" if ps else "NENHUM"
        if pull: tipo="PULLBACK_RESISTENCIA_ROMPIDA"
    elif sinal=="SELL":
        reteste=pull=rs and ps; confirm=pull and fechamento<=suporte; falso=rs and fechamento>suporte+margem*.20; tipo="PULLBACK_SUPORTE_ROMPIDO" if pull else "TESTE_RESISTENCIA" if pr else "NENHUM"
    return {"pullback":pull,"reteste":reteste,"rompimento":rr if sinal=="BUY" else rs,"falso_rompimento":falso,"confirmacao":confirm,"tipo":tipo}

def analisar_price_action(data):
    candles=normalizar_candles(data)
    if len(candles)<8:
        return {"status":"SEM_DADOS","dados_candles":len(candles),"mensagem":"A V6 precisa receber candles OHLC no webhook para validar suporte, resistência, pullback e anatomia.","zonas":calcular_zonas(candles),"candle_atual":None,"padrao_candle":{"padrao":"SEM_DADOS","sinal":"NEUTRO"},"estrutura":{"pullback":False,"reteste":False,"rompimento":False,"falso_rompimento":False,"confirmacao":False,"tipo":"SEM_DADOS"},"confluencia":{"buy":0,"sell":0,"sinal":"AGUARDAR"}}
    sinal=str(data.get("sinal","")).upper(); zonas=calcular_zonas(candles); padrao=detectar_padrao_candle(candles); estrutura=analisar_pullback_reteste(candles,zonas,sinal); candle=anatomia_candle(candles[-1]); buy=sell=0
    if zonas["forca_suporte"] in ("FORTE","MEDIA"): buy+=2
    if zonas["forca_resistencia"] in ("FORTE","MEDIA"): sell+=2
    if padrao["sinal"]=="BUY": buy+=2
    if padrao["sinal"]=="SELL": sell+=2
    if estrutura["pullback"] and estrutura["confirmacao"]:
        if sinal=="BUY": buy+=3
        if sinal=="SELL": sell+=3
    if estrutura["falso_rompimento"]:
        if sinal=="BUY": sell+=3
        if sinal=="SELL": buy+=3
    if sinal=="BUY" and candle["rejeicao"]=="COMPRADORA": buy+=2
    if sinal=="SELL" and candle["rejeicao"]=="VENDEDORA": sell+=2
    conf="BUY" if sinal=="BUY" and buy>=5 and sell<buy else "SELL" if sinal=="SELL" and sell>=5 and buy<sell else "AGUARDAR"
    return {"status":"OK","dados_candles":len(candles),"zonas":zonas,"candle_atual":candle,"padrao_candle":padrao,"estrutura":estrutura,"confluencia":{"buy":buy,"sell":sell,"sinal":conf}}


# ============================================================
# DECISÃO PROVISÓRIA
# ============================================================

def decisao_provisoria(
    tecnico,
    noticias
):

    status_tecnico = tecnico.get(
        "status",
        "AGUARDAR"
    )

    direcao_noticias = noticias.get(
        "direcao_ouro",
        "NEUTRA"
    )

    if status_tecnico == "BUY":

        if direcao_noticias == "NEGATIVA":

            return "AGUARDAR"

        elif direcao_noticias == "POSITIVA":

            return "BUY"

        return "AGUARDAR"

    if status_tecnico == "SELL":

        if direcao_noticias == "POSITIVA":

            return "AGUARDAR"

        elif direcao_noticias == "NEGATIVA":

            return "SELL"

        return "AGUARDAR"

    return "AGUARDAR"


# ============================================================
# ROTA PRINCIPAL
# ============================================================

@app.get("/")
def inicio():

    return {

        "sistema":
            "XAUUSD IA + NOTÍCIAS",

        "versao":
            "6.0",

        "status":
            "ONLINE",

        "hora":
            agora()
    }


# ============================================================
# NOTÍCIAS
# ============================================================

@app.get("/noticias")
def noticias():

    resultado = analisar_noticias()

    return {

        "ok":
            True,

        "sistema":
            "XAUUSD IA + NOTÍCIAS",

        "hora":
            agora(),

        "resultado":
            resultado
    }


# ============================================================
# WEBHOOK
# ============================================================

@app.post("/webhook")
async def webhook(
    request: Request
):

    global ULTIMO_SINAL

    try:

        data = await request.json()

        # Compatibilidade com o JSON atual do TradingView
        if "stop_loss" not in data and "sl" in data:
            data["stop_loss"] = data["sl"]
        if "candles" not in data and "candles_m5" in data:
            data["candles"] = data["candles_m5"]

    except Exception:

        return {
            "ok": False,
            "erro": "JSON inválido"
        }

    faltando = validar_sinal(
        data
    )

    if faltando:

        return {

            "ok": False,

            "erro":
                "Campos obrigatórios ausentes",

            "campos":
                faltando
        }

    tecnico = analisar_tecnico(
        data
    )

    noticias = analisar_noticias()

    decisao = decisao_provisoria(
        tecnico,
        noticias
    )

    ULTIMO_SINAL = {

        "recebido_em":
            agora(),

        "dados":
            data,

        "analise_tecnica":
            tecnico,

        "analise_noticias":
            noticias,

        "decisao_provisoria":
            decisao
    }

    resposta = {

        "ok":
            True,

        "sistema":
            "XAUUSD IA + NOTÍCIAS",

        "versao":
            "6.0",

        "recebido_em":
            agora(),

        "ativo":
            data["ativo"],

        "timeframe":
            data[
                "timeframe_operacao"
            ],

        "sinal":
            data["sinal"],

        "score_tecnico":
            data[
                "score_tecnico"
            ],

        "analise_tecnica":
            tecnico,

        "noticias":
            noticias,

        "ia": {

            "status":
                "PENDENTE",

            "decisao":
                "PENDENTE"
        },

        "decisao_final":
            decisao
    }

    print(
        "\n"
        +
        "=" * 70
    )

    print(
        "NOVO SINAL XAUUSD"
    )

    print(
        "=" * 70
    )

    print(
        json.dumps(
            resposta,
            indent=2,
            ensure_ascii=False
        )
    )

    print(
        "=" * 70
    )

    return resposta


# ============================================================
# ÚLTIMO SINAL
# ============================================================

@app.get("/ultimo-sinal")
def ultimo_sinal():

    if ULTIMO_SINAL is None:

        return {

            "ok":
                True,

            "mensagem":
                "Nenhum sinal recebido ainda."
        }

    return {

        "ok":
            True,

        "sinal":
            ULTIMO_SINAL
    }


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
