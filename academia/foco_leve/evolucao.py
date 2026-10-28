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
