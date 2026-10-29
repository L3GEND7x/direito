"""Pontos, níveis e figurinhas (sem interface).

Tudo é calculado a partir dos registros: não há pontos guardados à parte, então ninguém ganha duas vezes pela mesma
coisa, excluir um treino tira os pontos dele e contas antigas recebem na hora o que já conquistaram.
"""
from __future__ import annotations

from datetime import datetime

from . import biblioteca as B
from . import evolucao as E
from . import regras as R

PONTOS = {"treino": 10, "semana_completa": 100, "pesagem_semanal": 20, "recorde": 30, "checkin": 2}
PONTOS_POR_NIVEL = 500
NIVEIS = ["Começando", "Constante", "Dedicado", "Focado", "Determinado", "Imparável", "Lenda"]


def _concluidas(S: dict) -> list[dict]:
    return sorted((s for s in S["sessions"] if s.get("status") == "concluida"), key=lambda s: (s["date"], s.get("startedAt", 0)))


def _semanas(S: dict) -> list[dict]:
    """Semanas desde o primeiro treino até a atual: treinos concluídos × planejados, cardio e se houve pesagem."""
    ses = _concluidas(S)
    if not ses:
        return []
    out, ws, atual = [], R.inicio_semana(ses[0]["date"]), R.inicio_semana(R.hoje())
    pesos = {R.inicio_semana(w["date"]) for w in S["weights"]}
    while ws <= atual:
        dias = R.dias_da_semana(ws)
        planejados = sum(1 for d in dias if R.treino_do_dia(S, d) not in ("OFF", "REC"))
        feitos = len({s["date"] for s in ses if s["date"] in dias})
        out.append({"ws": ws, "planejados": planejados, "feitos": feitos, "completa": planejados > 0 and feitos >= planejados,
                    "cardio": R.energia_semana(S, ws)["cardioMin"], "pesagem": ws in pesos})
        ws = R.add_dias(ws, 7)
    return out


def _recordes(S: dict) -> int:
    """Vezes em que a carga de um exercício passou a maior já registrada antes (o primeiro registro não conta)."""
    n = 0
    for ex_id in E.exercicios_com_carga(S):
        melhor = None
        for _, v in E.cargas_do_exercicio(S, ex_id):
            if melhor is not None and v > melhor:
                n += 1
            melhor = v if melhor is None else max(melhor, v)
    return n


def pontos(S: dict) -> dict:
    sem = _semanas(S)
    pesagens = len({R.inicio_semana(w["date"]) for w in S["weights"]})
    itens = [("Treinos concluídos", len({s["date"] for s in _concluidas(S)}), PONTOS["treino"]),
             ("Semanas com todos os treinos feitos", sum(1 for x in sem if x["completa"]), PONTOS["semana_completa"]),
             ("Semanas com pesagem registrada", pesagens, PONTOS["pesagem_semanal"]),
             ("Recordes de carga", _recordes(S), PONTOS["recorde"]),
             ("Dias com check-in", len(S.get("checkins") or {}), PONTOS["checkin"])]
    total = sum(q * p for _, q, p in itens)
    n = total // PONTOS_POR_NIVEL
    return {"total": total, "itens": [{"motivo": m, "qtd": q, "pts": p, "subtotal": q * p} for m, q, p in itens],
            "nivel": n + 1, "nome_nivel": NIVEIS[min(n, len(NIVEIS) - 1)],
            "no_nivel": total - n * PONTOS_POR_NIVEL, "falta": PONTOS_POR_NIVEL - (total - n * PONTOS_POR_NIVEL)}


def _seguidas(valores: list[bool]) -> int:
    """Maior sequência de True."""
    m = c = 0
    for v in valores:
        c = c + 1 if v else 0
        m = max(m, c)
    return m


def figurinhas(S: dict) -> list[dict]:
    """Álbum: cada figurinha com emoji, nome, como ganhar e se já foi ganha."""
    ses = _concluidas(S)
    n_treinos = len({s["date"] for s in ses})
    sem = _semanas(S)
    fuso = R.agora().tzinfo
    horas = [datetime.fromtimestamp(s["startedAt"] / 1000, fuso).hour for s in ses
             if isinstance(s.get("startedAt"), (int, float)) and s["startedAt"] > 10 ** 11]
    p = S["profile"]
    ini, meta, atual = float(p["pesoInicial"]), float(p["pesoMeta"]), R.peso_atual(S)
    rumo = (ini - atual) if meta < ini else (atual - ini)  # quanto andou na direção da meta
    metas_carga = E.metas_de_carga(S)
    grupos = {B.grupo(e["id"]) for s in ses for e in s.get("ex", []) if any(x.get("done") for x in e.get("sets", []))}
    regras = [
        ("primeiro", "🏁", "Primeiro passo", "Concluir o primeiro treino", n_treinos >= 1),
        ("t10", "💪", "Pegando o ritmo", "10 treinos concluídos", n_treinos >= 10),
        ("t25", "🔥", "Embalado", "25 treinos concluídos", n_treinos >= 25),
        ("t50", "⚡", "Meio centenário", "50 treinos concluídos", n_treinos >= 50),
        ("t100", "🏆", "Centenário", "100 treinos concluídos", n_treinos >= 100),
        ("semana", "⭐", "Semana perfeita", "Fazer todos os treinos planejados de uma semana", any(x["completa"] for x in sem)),
        ("mes", "🌟", "Mês perfeito", "4 semanas perfeitas seguidas", _seguidas([x["completa"] for x in sem]) >= 4),
        ("cardio", "❤️", "Coração em dia", "150 min de cardio numa semana (mínimo da OMS)", any(x["cardio"] >= 150 for x in sem)),
        ("balanca", "⚖️", "Na balança", "Pesagem registrada 4 semanas seguidas", _seguidas([x["pesagem"] for x in sem]) >= 4),
        ("recorde", "📈", "Superação", "Bater um recorde de carga", _recordes(S) >= 1),
        ("recordes10", "🚀", "Em ascensão", "10 recordes de carga", _recordes(S) >= 10),
        ("cedo", "🌅", "Madrugador", "Treinar antes das 7h", any(h < 7 for h in horas)),
        ("noite", "🌙", "Coruja", "Treinar depois das 21h", any(h >= 21 for h in horas)),
        ("completo", "🧩", "Corpo inteiro", "Treinar 8 grupos musculares diferentes", len(grupos - {"", "Cardio", "Mobilidade"}) >= 8),
        ("kg1", "🎈", "Primeiro quilo", "1 kg na direção da sua meta de peso", rumo >= 1),
        ("kg5", "🎯", "Cinco quilos", "5 kg na direção da sua meta de peso", rumo >= 5),
        ("metapeso", "🥇", "Meta de peso", "Chegar à meta de peso", abs(meta - ini) >= 0.5 and rumo >= abs(meta - ini)),
        ("metacarga", "🏋️", "Meta de carga", "Atingir uma meta de carga", any(m["atingida"] for m in metas_carga)),
    ]
    return [{"id": i, "emoji": em, "nome": nome, "como": como, "ganha": bool(ok)} for i, em, nome, como, ok in regras]


def novas(S: dict) -> list[dict]:
    """Figurinhas ganhas que a pessoa ainda não viu (para comemorar uma vez)."""
    vistas = set(S.get("figurinhasVistas") or [])
    return [f for f in figurinhas(S) if f["ganha"] and f["id"] not in vistas]


def marcar_vistas(S: dict) -> None:
    S["figurinhasVistas"] = sorted({f["id"] for f in figurinhas(S) if f["ganha"]} | set(S.get("figurinhasVistas") or []))
