"""Regras e cálculos do Foco Leve (sem interface).

Todas as funções recebem o estado (dicionário) e datas como texto "AAAA-MM-DD".
"""
from __future__ import annotations

import copy
import math
import re
import time
import uuid
from datetime import date, timedelta

from . import dados as D

VERSAO = 3


# ---------------------------------------------------------------- utilidades
def hoje() -> str:
    return date.today().isoformat()


def pd(s: str) -> date:
    return date.fromisoformat(s)


def add_dias(s: str, n: int) -> str:
    return (pd(s) + timedelta(days=n)).isoformat()


def dia_js(s: str) -> int:
    """Dia da semana na convenção do JavaScript: domingo=0 ... sábado=6."""
    return (pd(s).weekday() + 1) % 7


def inicio_semana(s: str) -> str:
    d = pd(s)
    return (d - timedelta(days=d.weekday())).isoformat()


def dias_da_semana(ws: str) -> list[str]:
    return [add_dias(ws, i) for i in range(7)]


def dias_entre(a: str, b: str) -> int:
    return (pd(b) - pd(a)).days


def fmt_d(s: str) -> str:
    d = pd(s)
    return f"{d.day:02d}/{d.month:02d}"


def fmt_dy(s: str) -> str:
    d = pd(s)
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def num(v) -> float:
    """Converte texto com vírgula ou ponto em número; devolve nan se inválido."""
    if v is None:
        return math.nan
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else math.nan
    s = str(v).strip().replace(",", ".")
    if not s:
        return math.nan
    try:
        n = float(s)
    except ValueError:
        return math.nan
    return n if math.isfinite(n) else math.nan


def ok(n) -> bool:
    return isinstance(n, (int, float)) and math.isfinite(n)


def br(n: float, casas: int = 1) -> str:
    """Formata número no padrão brasileiro."""
    if not ok(n):
        return "—"
    s = f"{n:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def brx(n: float) -> str:
    """Até uma casa decimal, sem zero desnecessário."""
    if not ok(n):
        return "—"
    return br(n, 0) if abs(n - round(n)) < 1e-9 else br(n, 1)


def novo_id() -> str:
    return uuid.uuid4().hex[:10]


# ---------------------------------------------------------------- estado
def padrao() -> dict:
    return {
        "v": VERSAO,
        "profile": {"nome": "", "idade": 23, "pesoInicial": 115, "altura": 175, "pesoMeta": 89,
                    "objetivo": "Emagrecimento e redução de gordura corporal", "local": "Academia",
                    "nivel": "Iniciante", "dias": 5, "tempoMax": 90, "limitacao": ""},
        "assess": {"done": False, "date": "", "joelho": "", "dor": "", "inchaco": "", "caminhar": "",
                   "diag": "", "diagTxt": "", "liberacao": "", "lesao": "", "proibidos": "", "recomendados": "",
                   "red": {"subito": False, "febre": False, "vermelhidao": False, "apoio": False}},
        "plan": {},
        "ajustes": {},
        "schedule": dict(D.AGENDA_PADRAO),
        "dayOverride": {},
        "startDate": "",
        "sessions": [], "active": None, "checkins": {}, "weights": [], "habits": {},
        "reminders": {"hora": "18:00", "dias": [1, 2, 3, 4, 5], "treino": True, "sessao": True,
                      "peso": True, "resumo": True, "recuperacao": True},
    }


def mesclar(o: dict | None) -> dict:
    """Completa um estado salvo com os campos que faltarem (compatível com a versão web)."""
    d = padrao()
    if not isinstance(o, dict):
        return d
    out = {**d, **o}
    for k in ["profile", "assess", "reminders", "schedule"]:
        out[k] = {**d[k], **(o.get(k) if isinstance(o.get(k), dict) else {})}
    out["assess"]["red"] = {**d["assess"]["red"], **((o.get("assess") or {}).get("red") or {})}
    for k in ["sessions", "weights"]:
        if not isinstance(out.get(k), list):
            out[k] = []
    for k in ["plan", "ajustes", "dayOverride", "checkins", "habits"]:
        if not isinstance(out.get(k), dict):
            out[k] = {}
    if not isinstance(out["reminders"].get("dias"), list):
        out["reminders"]["dias"] = list(d["reminders"]["dias"])
    if (out.get("v") or 0) < VERSAO:
        antigas = [{"0": "OFF", "1": "A", "2": "CARDIO", "3": "B", "4": "REC", "5": "C", "6": "OFF"},
                   {"0": "OFF", "1": "A", "2": "LA", "3": "CARDIO", "4": "B", "5": "LB", "6": "OFF"}]
        if any(all(out["schedule"].get(k) == v for k, v in a.items()) for a in antigas):
            out["schedule"] = dict(D.AGENDA_PADRAO)
        if out["profile"].get("tempoMax") == 60:
            out["profile"]["tempoMax"] = 90
        if out["profile"].get("limitacao") == "Joelho e possível derrame ou lesão muscular, ainda a esclarecer.":
            out["profile"]["limitacao"] = ""
        out["v"] = VERSAO
    return out


# ---------------------------------------------------------------- exercícios
def get_ex(S: dict, ex_id: str) -> dict:
    b = D.EXERCICIOS[ex_id]
    o = S["plan"].get(ex_id) or {}
    e = dict(b)
    for k in ["series", "reps", "descanso", "duracao"]:
        if o.get(k) is not None:
            e[k] = o[k]
    e["ativo"] = o.get("ativo", True)
    e["id"] = ex_id
    return e


def nome_ex(ex_id: str) -> str:
    return D.EXERCICIOS.get(ex_id, {}).get("nome", str(ex_id))


def nome_treino(k: str) -> str:
    return D.TREINOS.get(k, {}).get("nome", "Treino")


def reps_alvo(e: dict) -> str:
    m = re.search(r"\d+", str(e.get("reps") or ""))
    return m.group(0) if m else ""


# ---------------------------------------------------------------- segurança
def sintomas(S: dict) -> bool:
    a = S["assess"]
    ci = S["checkins"].get(hoje())
    return (a.get("dor") == "sim" or a.get("inchaco") == "sim" or a.get("caminhar") == "sim"
            or bool(ci and ((ci.get("dor") or 0) >= 3 or ci.get("inchaco"))))


def alerta_vermelho(S: dict) -> bool:
    ci = S["checkins"].get(hoje())
    return any(S["assess"]["red"].values()) or bool(ci and ci.get("red"))


def seguranca(S: dict) -> str:
    """urgent | pending | caution | noclear | ok"""
    if alerta_vermelho(S):
        return "urgent"
    if not S["assess"].get("done"):
        return "pending"
    if sintomas(S):
        return "caution"
    if S["assess"].get("liberacao") != "sim":
        return "noclear"
    return "ok"


def status_ex(S: dict, ex_id: str) -> tuple[bool, str]:
    e = get_ex(S, ex_id)
    if not e["ativo"]:
        return False, "Desativado no plano (Perfil → Plano de exercícios)."
    if e.get("requer") == "pernas" and sintomas(S):
        return False, "Bloqueado hoje: há dor, inchaço ou dificuldade para caminhar registrados. Se não passar, procure avaliação."
    return True, ""


# ---------------------------------------------------------------- agenda
def treino_do_dia(S: dict, d: str) -> str:
    o = S["dayOverride"].get(d)
    if o in D.TREINOS:
        return o
    k = S["schedule"].get(str(dia_js(d)))
    return k if k in D.TREINOS else "OFF"


def feito_em(S: dict, d: str) -> bool:
    return any(s["date"] == d and s.get("status") == "concluida" for s in S["sessions"])


def planejados_semana(S: dict) -> int:
    return sum(1 for v in S["schedule"].values() if v != "OFF")


def semana_programa(S: dict) -> int:
    """Semana atual do plano de 20 semanas (avança só com a semana anterior aprovada)."""
    from . import plano
    return plano.semana_do_programa(S)["semana"]


def minutos_estimados(S: dict, wk: str) -> int:
    from . import plano
    return int(round(plano.plano_do_dia(S, hoje(), wk=wk)["total"] / 5) * 5)


# ---------------------------------------------------------------- peso
def pesos_ordenados(S: dict) -> list[dict]:
    return sorted(S["weights"], key=lambda x: x["date"])


def peso_atual(S: dict) -> float:
    w = pesos_ordenados(S)
    return float(w[-1]["peso"]) if w else float(S["profile"]["pesoInicial"])


def imc(S: dict, p: float) -> float:
    h = float(S["profile"]["altura"]) / 100
    return p / (h * h) if h > 0 else math.nan


def imc_categoria(v: float) -> str:
    if not ok(v):
        return ""
    if v < 18.5:
        return "baixo peso"
    if v < 25:
        return "peso adequado"
    if v < 30:
        return "sobrepeso"
    if v < 35:
        return "obesidade grau I"
    if v < 40:
        return "obesidade grau II"
    return "obesidade grau III"


def media_semana(S: dict, ws: str):
    ds = dias_da_semana(ws)
    w = [x["peso"] for x in S["weights"] if x["date"] in ds]
    return sum(w) / len(w) if len(w) >= 2 else None


def serie_peso(S: dict, modo: str) -> list[tuple[str, float]]:
    w = pesos_ordenados(S)
    if modo == "diario":
        return [(fmt_d(x["date"]), x["peso"]) for x in w]
    g: dict[str, list[float]] = {}
    for x in w:
        k = inicio_semana(x["date"]) if modo == "semanal" else x["date"][:7]
        g.setdefault(k, []).append(x["peso"])
    out = []
    for k in sorted(g):
        lbl = "sem. " + fmt_d(k) if modo == "semanal" else k[5:7] + "/" + k[2:4]
        out.append((lbl, sum(g[k]) / len(g[k])))
    return out


# ---------------------------------------------------------------- histórico
def historico_ex(S: dict, ex_id: str) -> list[dict]:
    out = []
    for s in sorted(S["sessions"], key=lambda x: x.get("startedAt", 0)):
        e = next((x for x in s.get("ex", []) if x["id"] == ex_id), None)
        if not e:
            continue
        feitos = [x for x in e["sets"] if x.get("done")]
        cargas = [num(x.get("load")) for x in feitos]
        cargas = [c for c in cargas if ok(c)]
        out.append({
            "date": s["date"], "max": max(cargas) if cargas else None,
            "lastReps": num(feitos[-1].get("reps")) if feitos else math.nan,
            "setsDone": len(feitos), "setsTotal": len(e["sets"]), "rpe": num(e.get("rpe")),
            "pain": e.get("painLevel") if e.get("painLevel") not in (None, "", "nenhum") else "",
        })
    return out


def ultima_carga(S: dict, ex_id: str) -> str:
    h = [x for x in historico_ex(S, ex_id) if x["max"] is not None]
    return brx(h[-1]["max"]).replace(".", "") if h else ""


def ultimo_checkin(S: dict):
    if not S["checkins"]:
        return None
    k = sorted(S["checkins"])[-1]
    return {"date": k, **S["checkins"][k]}


def recuperacao(S: dict) -> dict:
    ci = ultimo_checkin(S)
    if not ci:
        return {"nivel": "?", "txt": "Sem registro", "detalhe": "Faça o check-in de hoje para acompanhar a recuperação."}
    idade = dias_entre(ci["date"], hoje())
    if ci.get("red") and idade == 0:
        return {"nivel": "urg", "txt": "Procure atendimento", "detalhe": "Sinal de alerta registrado hoje."}
    if idade > 2:
        return {"nivel": "?", "txt": "Registro antigo", "detalhe": "Último check-in em " + fmt_d(ci["date"]) + "."}
    sono = ci.get("sono")
    det = f"Dor {ci.get('dor', 0)}/10 · fadiga {ci.get('fadiga', 2)}/5" + (f" · sono {brx(sono)} h" if ok(sono) else "") + "."
    if ci.get("inchaco") or (ci.get("dor") or 0) >= 5:
        return {"nivel": "bad", "txt": "Avaliação recomendada", "detalhe": det}
    if (ci.get("dor") or 0) >= 3 or (ci.get("fadiga") or 0) >= 4 or (ok(sono) and sono < 6):
        return {"nivel": "mid", "txt": "Atenção", "detalhe": det}
    return {"nivel": "ok", "txt": "Boa", "detalhe": det}


def recomendacao(S: dict, ex_id: str) -> str:
    """Sugestão de carga para a próxima série, pela regra de progressão do ACSM."""
    e = get_ex(S, ex_id)
    h = historico_ex(S, ex_id)
    if not h:
        if e["tipo"] == "tempo":
            return "Primeira vez: comece em ritmo leve e observe a tolerância."
        if e.get("semCarga"):
            return "Primeira vez: movimento lento, só na amplitude sem dor."
        return "Primeira vez: comece com carga leve e aprenda o ajuste do equipamento."
    last = h[-1]
    txt = f"Última carga: {brx(last['max'])} kg ({fmt_d(last['date'])}). " if last["max"] is not None else ""
    rv = recuperacao(S)
    if last["pain"]:
        return txt + f"Houve desconforto ({last['pain']}) na última vez: mantenha ou reduza e converse com o profissional antes de progredir."
    if rv["nivel"] in ("bad", "mid"):
        return txt + "Recuperação abaixo do ideal: mantenha a carga anterior ou reduza."
    if ok(last["rpe"]) and last["rpe"] >= 9:
        return txt + "Esforço muito alto na última vez: mantenha ou reduza a carga."
    if e["tipo"] == "tempo":
        return f"Último registro em {fmt_d(last['date'])}. Mantenha um ritmo em que consiga conversar; aumente a duração antes da intensidade."
    if e.get("semCarga"):
        return f"Último registro em {fmt_d(last['date'])}. Quando completar todas as séries com folga, aumente 5 a 10 segundos por série."
    alvo = int(reps_alvo(e) or 0)
    dois = h[-2:]
    pronto = last["max"] is not None and len(dois) == 2 and all(
        x["setsDone"] == x["setsTotal"] and not x["pain"]
        and ((alvo and ok(x["lastReps"]) and x["lastReps"] >= alvo + 1) or (ok(x["rpe"]) and x["rpe"] <= 6))
        for x in dois)
    if pronto:
        inc = max(1, round(last["max"] * 0.05))
        return txt + f"Critério de progressão atingido em 2 sessões seguidas: suba de 2 a 10% na carga. Sugestão: {brx(last['max'] + inc)} kg (ou o próximo peso disponível na máquina)."
    return txt + f"Repita a carga. Na última série, se conseguir manter a técnica, faça 1 ou 2 repetições além de {alvo}: repetindo isso em 2 treinos seguidos, o app sugere aumentar a carga."


# ---------------------------------------------------------------- sessão
def ex_sessao(S: dict, se: dict) -> dict:
    """Exercício da sessão com a prescrição gravada quando ela foi iniciada."""
    return {**get_ex(S, se["id"]), **(se.get("presc") or {})}


def nova_entrada(S: dict, ex_id: str, presc: dict | None = None) -> dict:
    e = {**get_ex(S, ex_id), **(presc or {})}
    n = 1 if e["tipo"] == "tempo" else max(1, min(10, int(e.get("series") or 1)))
    o = {"id": ex_id, "sets": [{"done": False, "load": "", "reps": "", "min": ""} for _ in range(n)],
         "rpe": "", "painLevel": "nenhum", "pain": "", "done": False}
    if presc:
        o["presc"] = {k: presc[k] for k in ("series", "reps", "descanso", "duracao") if k in presc}
    if e.get("cardio"):
        o["met"] = str(D.MET_PADRAO_CARDIO[e["cardio"]])
    return o


def iniciar_sessao(S: dict, wk: str) -> None:
    from . import plano
    pl = plano.plano_do_dia(S, hoje(), wk=wk)
    S["active"] = {"id": novo_id(), "date": hoje(), "workout": wk, "startedAt": int(time.time() * 1000),
                   "semana": pl["semana"], "planoMin": pl["total"], "etapas": pl["etapas"],
                   "ex": [nova_entrada(S, it["id"], it) for it in pl["itens"]]}
    if not S.get("startDate"):
        S["startDate"] = hoje()


def marcar_serie(S: dict, i: int, j: int, feito: bool) -> int:
    """Marca a série; preenche repetições, carga ou minutos vazios. Devolve o descanso em segundos."""
    a = S["active"]
    se = a["ex"][i]
    e = ex_sessao(S, se)
    st = se["sets"][j]
    st["done"] = feito
    if not feito:
        se["done"] = False
        return 0
    if e["tipo"] == "tempo":
        if not st.get("min"):
            st["min"] = str(e.get("duracao") or "")
    else:
        if not st.get("reps") and not e.get("semCarga"):
            st["reps"] = reps_alvo(e)
        if not e.get("semCarga") and not st.get("load"):
            st["load"] = (se["sets"][j - 1].get("load") if j > 0 else "") or ultima_carga(S, se["id"])
    if all(x.get("done") for x in se["sets"]):
        se["done"] = True
        return 0
    return int(e.get("descanso") or 0)


def volume(sessao: dict) -> float:
    v = 0.0
    for e in sessao.get("ex", []):
        for x in e["sets"]:
            if not x.get("done"):
                continue
            l, r = num(x.get("load")), num(x.get("reps"))
            if ok(l) and ok(r):
                v += l * r
    return v


def energia(S: dict, sessao: dict) -> dict:
    """Gasto calórico ESTIMADO: MET × peso (kg) × horas (Compêndio 2024)."""
    kg = peso_atual(S)
    cmin, ck = 0.0, 0.0
    for e in sessao.get("ex", []):
        b = D.EXERCICIOS.get(e["id"])
        if not b or not b.get("cardio"):
            continue
        for x in e["sets"]:
            m = num(x.get("min"))
            if x.get("done") and ok(m) and m > 0:
                cmin += m
                met = num(e.get("met"))
                ck += (met if ok(met) else D.MET_PADRAO_CARDIO[b["cardio"]]) * kg * m / 60
    outros = max(0.0, float(sessao.get("minutes") or 0) - cmin)
    met = D.MET_LEVE if sessao.get("workout") == "REC" else D.MET_FORCA
    return {"kcal": round(ck + met * kg * outros / 60), "cardioMin": cmin}


def energia_semana(S: dict, ws: str) -> dict:
    ds = dias_da_semana(ws)
    k = c = 0.0
    for s in S["sessions"]:
        if s["date"] in ds:
            en = energia(S, s)
            k += en["kcal"]
            c += en["cardioMin"]
    return {"kcal": k, "cardioMin": c}


def finalizar_sessao(S: dict, sensacao: str, minutos: float, obs: str = "", rpe_sessao=None, fadiga=None,
                     recuperacao: str | None = None) -> dict:
    a = S["active"]
    recordes = []
    for e in a["ex"]:
        cargas = [num(x.get("load")) for x in e["sets"] if x.get("done")]
        cargas = [c for c in cargas if ok(c)]
        if not cargas:
            continue
        mx = max(cargas)
        ant = [x["max"] for x in historico_ex(S, e["id"]) if x["max"] is not None]
        if ant and mx > max(ant):
            recordes.append(f"{nome_ex(e['id'])}: {brx(mx)} kg")
    feitos = sum(1 for e in a["ex"] if e.get("done"))
    rec = {**a, "endedAt": int(time.time() * 1000), "status": "concluida", "volume": round(volume(a)),
           "feeling": sensacao, "minutes": round(minutos), "notes": obs.strip(),
           "rpeSessao": rpe_sessao, "fadiga": fadiga, "recuperacao": recuperacao,
           "pct": feitos / len(a["ex"]) * 100 if a["ex"] else 0}
    rec["kcal"] = energia(S, rec)["kcal"]
    S["sessions"].append(rec)
    S["active"] = None
    rec["_recordes"] = recordes
    return rec


ROTULO_SINTOMA = {"joelho": "dor articular", "inchaco": "inchaço em articulação", "apoio": "dificuldade para apoiar a perna",
                  "peito": "dor ou aperto no peito", "ar": "falta de ar desproporcional", "tontura": "tontura ou mal-estar",
                  "outro": "outro desconforto"}


def interromper_sessao(S: dict, sintomas_marcados: list[str]) -> bool:
    """Interrompe a sessão por sintoma. Devolve True se o caso pede atendimento médico."""
    a = S["active"]
    feitos = sum(1 for e in a["ex"] if e.get("done"))
    mins = max(1, min(90, round((time.time() * 1000 - a["startedAt"]) / 60000)))
    S["sessions"].append({**a, "endedAt": int(time.time() * 1000), "status": "interrompida",
                          "symptom": ", ".join(ROTULO_SINTOMA[k] for k in sintomas_marcados), "feeling": "dor",
                          "minutes": mins, "notes": "", "pct": feitos / len(a["ex"]) * 100 if a["ex"] else 0})
    S["active"] = None
    t = hoje()
    ci = S["checkins"].get(t) or {"dor": 0, "inchaco": False, "fadiga": 3, "sono": None, "red": False, "redItems": []}
    if "inchaco" in sintomas_marcados:
        ci["inchaco"] = True
    if "apoio" in sintomas_marcados:
        ci["red"] = True
        ci["redItems"] = list(ci.get("redItems") or []) + ["apoio"]
    if {"joelho", "inchaco", "apoio"} & set(sintomas_marcados):
        S["checkins"][t] = ci
    return bool({"peito", "ar", "apoio"} & set(sintomas_marcados))


# ---------------------------------------------------------------- relatório
def relatorio_semanal(S: dict, ws: str) -> str:
    ds = dias_da_semana(ws)
    w = [x for x in pesos_ordenados(S) if x["date"] in ds]
    ses = [s for s in S["sessions"] if s["date"] in ds]
    concl = [s for s in ses if s.get("status") == "concluida"]
    ex_tot = sum(len(s.get("ex", [])) for s in ses)
    ex_ok = sum(1 for s in ses for e in s.get("ex", []) if e.get("done"))
    mins = sum(float(s.get("minutes") or 0) for s in ses)
    vol = sum(volume(s) for s in ses)
    en = energia_semana(S, ws)
    ant = dias_da_semana(add_dias(ws, -7))
    cargas = []
    for ex_id in D.EXERCICIOS:
        h = historico_ex(S, ex_id)
        cur = [x["max"] for x in h if x["date"] in ds and x["max"] is not None]
        if not cur:
            continue
        prev = [x["max"] for x in h if x["date"] in ant and x["max"] is not None]
        cargas.append((nome_ex(ex_id), max(cur), max(prev) if prev else None))
    cis = [{"date": d, **S["checkins"][d]} for d in ds if d in S["checkins"]]

    def media(k):
        v = [c[k] for c in cis if ok(c.get(k))]
        return sum(v) / len(v) if v else None

    sint = []
    for s in ses:
        for e in s.get("ex", []):
            if e.get("painLevel") not in (None, "", "nenhum") or e.get("pain"):
                sint.append(f"{fmt_d(s['date'])} — {nome_ex(e['id'])}: {e.get('painLevel', '')}" + (f" ({e['pain']})" if e.get("pain") else ""))
        if s.get("symptom"):
            sint.append(f"{fmt_d(s['date'])} — sessão interrompida: {s['symptom']}")
    for c in cis:
        if c.get("inchaco"):
            sint.append(f"{fmt_d(c['date'])} — inchaço registrado no check-in")
        if c.get("red"):
            sint.append(f"{fmt_d(c['date'])} — sinal de alerta registrado")
    dor = media("dor")
    recs = []
    if any(c.get("red") for c in cis):
        recs.append("Houve sinal de alerta: só retome após atendimento e nova avaliação.")
    elif (dor is not None and dor >= 3) or any(c.get("inchaco") for c in cis) or sint:
        recs.append("Houve dor, inchaço ou desconforto: não progrida e leve esses registros ao profissional.")
    if len(concl) < min(3, planejados_semana(S)):
        recs.append("Retome a rotina na próxima semana sem compensar treinos perdidos.")
    if not w:
        recs.append("Registre o peso ao menos uma vez por semana, nas mesmas condições.")
    if en["cardioMin"] < 150:
        recs.append("Cardio abaixo de 150 min: tente completar os 30 min de cardio ao final de cada treino.")
    if not recs:
        recs.append("Manter a rotina e seguir a regra de progressão de carga.")

    L = ["FOCO LEVE — Relatório semanal", f"Período: {fmt_dy(ws)} a {fmt_dy(ds[6])}", "", "PESO (dados registrados)"]
    if w:
        L += [f"Início do período: {br(w[0]['peso'])} kg ({fmt_d(w[0]['date'])})",
              f"Fim do período: {br(w[-1]['peso'])} kg ({fmt_d(w[-1]['date'])})"]
    else:
        L.append("Nenhuma pesagem registrada no período.")
    L.append("Média semanal: " + (f"{br(sum(x['peso'] for x in w) / len(w))} kg" if len(w) >= 2 else "indisponível (menos de 2 pesagens)"))
    if len(w) >= 2:
        dv = w[-1]["peso"] - w[0]["peso"]
        L.append(f"Variação no período: {'+' if dv > 0 else ''}{br(dv)} kg (oscilações diárias não indicam, isoladamente, perda ou ganho de gordura)")
    cint = [x.get("cintura") for x in w if ok(x.get("cintura"))]
    L.append("Circunferência abdominal: " + (f"{brx(cint[-1])} cm" if cint else "não registrada"))
    L += ["", "TREINOS", f"Sessões concluídas: {len(concl)} de {planejados_semana(S)} planejadas" + (f" ({len(ses) - len(concl)} interrompida(s))" if len(ses) > len(concl) else ""),
          f"Exercícios concluídos: {ex_ok} de {ex_tot}", f"Minutos de atividade registrados: {br(mins, 0)}",
          f"Volume total levantado: {br(vol, 0)} kg (carga × repetições)",
          f"Cardio: {br(en['cardioMin'], 0)} min (recomendação da OMS: 150 a 300 min por semana)",
          f"Gasto calórico ESTIMADO dos treinos: ≈ {br(en['kcal'], 0)} kcal (Compêndio 2024; não é medição)"]
    if cargas:
        L.append("Cargas (máxima da semana):")
        L += [f"• {n}: {brx(c)} kg" + (f" (semana anterior: {brx(p)} kg)" if p is not None else "") for n, c, p in cargas]
    sono, fad = media("sono"), media("fadiga")
    L += ["", f"RECUPERAÇÃO ({len(cis)} check-in{'s' if len(cis) != 1 else ''})",
          "Dor articular média: " + (f"{br(dor)}/10" if dor is not None else "sem dados"),
          "Fadiga média: " + (f"{br(fad)}/5" if fad is not None else "sem dados"),
          "Sono médio: " + (f"{br(sono)} h" if sono is not None else "sem dados"),
          "Sintomas informados: " + ("" if sint else "nenhum")]
    L += ["• " + x for x in sint]
    L += ["", "SUGESTÕES PARA A PRÓXIMA SEMANA (não substituem orientação profissional)"] + ["• " + x for x in recs]
    return "\n".join(L)


def lembretes(S: dict, agora_hm: str) -> list[str]:
    R, t, out = S["reminders"], hoje(), []
    wk = treino_do_dia(S, t)
    if R["treino"] and dia_js(t) in R["dias"] and wk != "OFF" and not feito_em(S, t) and not S["active"] and agora_hm >= R["hora"]:
        out.append("Seu treino de hoje está pronto. Confira os exercícios programados, respeite suas limitações e registre sua evolução ao finalizar.")
    if R["sessao"] and S["active"] and S["active"]["date"] != t:
        out.append(f"Há uma sessão de {fmt_d(S['active']['date'])} aberta. Finalize ou descarte em Treinos.")
    if R["peso"]:
        w = pesos_ordenados(S)
        ult = w[-1]["date"] if w else None
        if not ult or dias_entre(ult, t) >= 7:
            out.append(f"Última pesagem em {fmt_d(ult)}. Registre o peso desta semana." if ult else "Registre sua primeira pesagem em Evolução.")
    if R["resumo"] and dia_js(t) == 1 and S["sessions"]:
        out.append("O resumo da semana passada está disponível em Evolução.")
    if R["recuperacao"]:
        rv = recuperacao(S)
        if rv["nivel"] in ("bad", "mid"):
            out.append(f"Aviso de recuperação: {rv['txt'].lower()}. {rv['detalhe']}")
    return out


def copia(S: dict) -> dict:
    return copy.deepcopy(S)
