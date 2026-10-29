"""Números da evolução calculados só a partir do que foi registrado (sem interface)."""
from __future__ import annotations

from . import dados as D
from . import plano as P
from . import regras as R


def estado_dos_dias(S: dict, ws: str) -> list[dict]:
    """Os 7 dias de uma semana: feito, planejado (ainda a fazer), perdido (passou sem treino) ou descanso."""
    t = R.hoje()
    out = []
    for d in R.dias_da_semana(ws):
        wk = R.treino_do_dia(S, d)
        if R.feito_em(S, d):
            estado = "feito"
        elif wk in ("OFF", "REC"):
            estado = "descanso"
        elif d < t:
            estado = "perdido"
        else:
            estado = "planejado"
        out.append({"data": d, "rotulo": D.DIAS_CURTOS[R.dia_js(d)][0], "estado": estado, "hoje": d == t,
                    "titulo": f"{D.DIAS_SEMANA[R.dia_js(d)]}: {D.TREINOS[wk]['nome']}"})
    return out


def semanas_recentes(S: dict, n: int = 8) -> list[dict]:
    """Treinos concluídos, planejados e minutos de cardio das últimas n semanas (a atual inclusive)."""
    atual = R.inicio_semana(R.hoje())
    out = []
    for k in range(n - 1, -1, -1):
        ws = R.add_dias(atual, -7 * k)
        dias = R.dias_da_semana(ws)
        planejados = sum(1 for d in dias if R.treino_do_dia(S, d) not in ("OFF", "REC"))
        feitos = len({s["date"] for s in S["sessions"] if s["date"] in dias and s.get("status") == "concluida"})
        en = R.energia_semana(S, ws)
        out.append({"ws": ws, "rotulo": R.fmt_d(ws), "planejados": planejados, "feitos": feitos,
                    "cardio": round(en["cardioMin"]), "kcal": round(en["kcal"])})
    return out


def estados_20(S: dict) -> tuple[list[str], int]:
    """Estado de cada uma das 20 semanas do plano e a semana atual."""
    sp = P.semana_do_programa(S)
    estados = [""] * D.SEMANAS_PLANO
    for h in sp["historico"]:
        i = h["semana"] - 1
        if h["aprovada"]:
            estados[i] = "ok"
        elif estados[i] != "ok":
            estados[i] = "rep"
    atual = sp["semana"]
    if not sp["concluido"]:
        estados[atual - 1] = "atual"
    return estados, atual


def consistencia(S: dict) -> dict:
    """Semanas avaliadas e aprovadas, e a sequência atual de semanas aprovadas seguidas."""
    hist = P.semana_do_programa(S)["historico"]
    aprovadas = sum(1 for h in hist if h["aprovada"])
    seq = 0
    for h in reversed(hist):
        if not h["aprovada"]:
            break
        seq += 1
    return {"avaliadas": len(hist), "aprovadas": aprovadas, "sequencia": seq,
            "taxa": aprovadas / len(hist) if hist else None}


def criterios_semana_atual(S: dict) -> list[tuple[bool | None, str, str]]:
    """Como está a semana em andamento frente às regras de avanço do plano."""
    ws = R.inicio_semana(R.hoje())
    r = P.avaliar_semana(S, ws)
    dias = R.dias_da_semana(ws)
    ses = [s for s in S["sessions"] if s["date"] in dias]
    dor = any(e.get("painLevel") in ("moderado", "forte") for s in ses for e in s.get("ex", []))
    interrompida = any(s.get("status") == "interrompida" for s in ses)
    alerta = any((S["checkins"].get(d) or {}).get("red") or (S["checkins"].get(d) or {}).get("inchaco") for d in dias)
    ruim = any(s.get("recuperacao") == "ruim" for s in ses)
    feitos_ok = r["feitos"] >= r["minimo"] if r["conta"] else None
    return [
        # a semana ainda está em andamento: abaixo do mínimo fica "em aberto", não reprovado
        (True if feitos_ok else None, "Treinos concluídos (mínimo 60%)",
         f"{r['feitos']} de {r['minimo']}" if r["conta"] else "sem treinos"),
        (not dor, "Sem dor moderada ou forte", "ok" if not dor else "registrada"),
        (not interrompida, "Nenhuma sessão interrompida", "ok" if not interrompida else "houve"),
        (not alerta, "Sem sinal de alerta ou inchaço no check-in", "ok" if not alerta else "registrado"),
        (not ruim, "Recuperação boa ou regular", "ok" if not ruim else "ruim"),
    ]


def ultima_sessao(S: dict) -> dict | None:
    ses = sorted(S["sessions"], key=lambda s: s.get("startedAt", 0))
    if not ses:
        return None
    s = ses[-1]
    feitos = sum(1 for e in s.get("ex", []) if e.get("done"))
    cardio = R.energia(S, s)["cardioMin"]
    return {"data": s["date"], "nome": R.nome_treino(s.get("workout", "")), "status": s.get("status"),
            "minutos": s.get("minutes"), "feitos": feitos, "total": len(s.get("ex", [])),
            "volume": s.get("volume") or round(R.volume(s)), "cardio": round(cardio), "kcal": s.get("kcal")}


def comparacao_cargas(S: dict) -> list[dict]:
    """Primeira e última carga registrada de cada exercício (só exercícios com pelo menos um registro)."""
    out = []
    for ex_id in D.EXERCICIOS:
        h = [x for x in R.historico_ex(S, ex_id) if x["max"] is not None]
        if not h:
            continue
        out.append({"id": ex_id, "nome": R.nome_ex(ex_id), "primeira": h[0]["max"], "data_primeira": h[0]["date"],
                    "ultima": h[-1]["max"], "data_ultima": h[-1]["date"], "registros": len(h),
                    "variacao": h[-1]["max"] - h[0]["max"]})
    return sorted(out, key=lambda x: x["data_ultima"], reverse=True)


def comparacao_peso(S: dict) -> dict | None:
    w = R.pesos_ordenados(S)
    if not w:
        return None
    p = S["profile"]
    return {"primeira": w[0]["peso"], "data_primeira": w[0]["date"], "ultima": w[-1]["peso"], "data_ultima": w[-1]["date"],
            "variacao": w[-1]["peso"] - w[0]["peso"], "desde_inicial": w[-1]["peso"] - float(p["pesoInicial"]),
            "falta": max(0.0, w[-1]["peso"] - float(p["pesoMeta"])), "registros": len(w)}


# Medidas corporais registradas junto com a pesagem: chave → (rótulo, mínimo, máximo) em cm
MEDIDAS = {"cintura": ("Cintura (abdominal)", 40, 250), "quadril": ("Quadril", 50, 250),
           "braco": ("Braço contraído", 15, 80), "coxa": ("Coxa", 25, 120)}


def serie_medida(S: dict, chave: str) -> list[tuple[str, float]]:
    """(data, cm) de cada registro da medida, em ordem de data."""
    return [(w["date"], float(w[chave])) for w in R.pesos_ordenados(S) if R.ok(R.num(w.get(chave)))]


def comparacao_medidas(S: dict) -> list[dict]:
    """Primeiro e último registro de cada medida com pelo menos 2 registros."""
    out = []
    for k, (rotulo, _, _) in MEDIDAS.items():
        sm = serie_medida(S, k)
        if len(sm) >= 2:
            out.append({"chave": k, "rotulo": rotulo, "primeira": sm[0][1], "data_primeira": sm[0][0],
                        "ultima": sm[-1][1], "data_ultima": sm[-1][0], "variacao": sm[-1][1] - sm[0][1], "registros": len(sm)})
    return out


# ---------------------------------------------------------------- por exercício, recordes, metas e semanas
def cargas_do_exercicio(S: dict, ex_id: str) -> list[tuple[str, float]]:
    """(data, maior carga da sessão) de cada sessão com carga registrada nesse exercício."""
    return [(x["date"], x["max"]) for x in R.historico_ex(S, ex_id) if x["max"] is not None]


def exercicios_com_carga(S: dict) -> list[str]:
    """Exercícios com pelo menos uma carga registrada, do mais treinado ao menos."""
    n = {x: len(cargas_do_exercicio(S, x)) for x in D.EXERCICIOS if not D.EXERCICIOS[x].get("semCarga")}
    return sorted((x for x, k in n.items() if k), key=lambda x: (-n[x], R.nome_ex(x)))


def recordes(S: dict, n: int = 10) -> list[dict]:
    """Maior carga já registrada em cada exercício (a primeira vez que ela apareceu), mais recentes primeiro."""
    out = []
    for ex_id in exercicios_com_carga(S):
        h = cargas_do_exercicio(S, ex_id)
        topo = max(v for _, v in h)
        data = next(d for d, v in h if v == topo)
        out.append({"id": ex_id, "nome": R.nome_ex(ex_id), "carga": topo, "data": data, "registros": len(h),
                    "novo": R.dias_entre(data, R.hoje()) <= 7 and len(h) > 1 and h[0][1] < topo})
    return sorted(out, key=lambda x: x["data"], reverse=True)[:n]


def metas_de_carga(S: dict) -> list[dict]:
    """Progresso de cada meta de carga: última carga registrada ÷ meta."""
    out = []
    for ex_id, alvo in (S.get("metasCarga") or {}).items():
        if ex_id not in D.EXERCICIOS or not R.ok(R.num(alvo)) or float(alvo) <= 0:
            continue
        h = cargas_do_exercicio(S, ex_id)
        atual = h[-1][1] if h else None
        melhor = max((v for _, v in h), default=None)
        out.append({"id": ex_id, "nome": R.nome_ex(ex_id), "meta": float(alvo), "atual": atual, "melhor": melhor,
                    "progresso": min(1.0, (melhor or 0) / float(alvo)), "atingida": melhor is not None and melhor >= float(alvo)})
    return sorted(out, key=lambda x: (x["atingida"], -x["progresso"]))


def _resumo_semana(S: dict, ws: str) -> dict:
    dias = R.dias_da_semana(ws)
    ses = [s for s in S["sessions"] if s["date"] in dias and s.get("status") == "concluida"]
    series = sum(1 for s in ses for e in s.get("ex", []) if D.EXERCICIOS.get(e["id"], {}).get("tipo") == "carga"
                 for x in e.get("sets", []) if x.get("done"))
    return {"treinos": len({s["date"] for s in ses}), "series": series, "volume": round(sum(R.volume(s) for s in ses)),
            "cardio": round(R.energia_semana(S, ws)["cardioMin"])}


def comparar_semanas(S: dict) -> dict:
    """Semana atual (até hoje) e a anterior inteira: treinos, séries, volume (kg) e minutos de cardio."""
    ws = R.inicio_semana(R.hoje())
    return {"atual": _resumo_semana(S, ws), "anterior": _resumo_semana(S, R.add_dias(ws, -7))}


# ---------------------------------------------------------------- peso semanal
PESAGEM_SEMANAL = "Pesagem semanal"


def pesos_semanais(S: dict) -> list[dict]:
    """Média de peso de cada semana com pesagem e a variação em relação à semana com pesagem anterior.

    "Evolução" = andou na direção da meta de peso; "regressão" = se afastou dela; variação menor que 0,1 kg = estável."""
    meta = float(S["profile"]["pesoMeta"])
    g: dict[str, list[float]] = {}
    for w in R.pesos_ordenados(S):
        g.setdefault(R.inicio_semana(w["date"]), []).append(float(w["peso"]))
    out, anterior = [], None
    for ws in sorted(g):
        media = sum(g[ws]) / len(g[ws])
        item = {"ws": ws, "rotulo": R.fmt_d(ws), "media": media, "variacao": None, "direcao": "inicio"}
        if anterior is not None:
            v = media - anterior
            item["variacao"] = v
            if abs(v) < 0.1:
                item["direcao"] = "estavel"
            else:
                item["direcao"] = "evolucao" if abs(media - meta) < abs(anterior - meta) else "regressao"
        out.append(item)
        anterior = media
    return out


def pesagem_desta_semana(S: dict) -> dict | None:
    ws = R.inicio_semana(R.hoje())
    ds = R.dias_da_semana(ws)
    w = [x for x in R.pesos_ordenados(S) if x["date"] in ds]
    return w[-1] if w else None
