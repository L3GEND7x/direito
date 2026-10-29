"""Acompanhamento automático a partir do que foi registrado (sem interface, sem IA).

Cada observação é uma frase curta calculada dos registros: treinos planejados × concluídos, frequência, séries,
cargas, peso, sessões interrompidas e desconfortos. Nada é inventado: sem dados, não há observação. Nada muda o
plano sozinho: quando faz sentido ajustar algo, a frase só indica onde a pessoa pode fazer isso. Dor não vira
diagnóstico: a observação repete a orientação de segurança e indica procurar um profissional.
"""
from __future__ import annotations

from . import biblioteca as B
from . import dados as D
from . import objetivos as O
from . import regras as R

DOR = ("moderado", "forte")


def _concluidas(S: dict) -> list[dict]:
    return sorted((s for s in S["sessions"] if s.get("status") == "concluida"), key=lambda s: (s["date"], s.get("startedAt", 0)))


def _series_feitas(e: dict) -> int:
    return sum(1 for x in e.get("sets", []) if x.get("done"))


def series_por_grupo(S: dict, ini: str, fim: str) -> dict[str, int]:
    """Séries de força concluídas entre ini e fim (inclusive), pelo grupo principal de cada exercício."""
    out: dict[str, int] = {}
    for s in S["sessions"]:
        if not ini <= s["date"] <= fim:
            continue
        for e in s.get("ex", []):
            g = B.grupo(e["id"])
            if g and g not in ("Cardio", "Mobilidade"):
                out[g] = out.get(g, 0) + _series_feitas(e)
    return {g: n for g, n in out.items() if n}


def series_semanais(S: dict, grupo: str, n: int = 8) -> list[dict]:
    """Séries concluídas de um grupo em cada uma das últimas n semanas (a atual inclusive)."""
    atual = R.inicio_semana(R.hoje())
    out = []
    for k in range(n - 1, -1, -1):
        ws = R.add_dias(atual, -7 * k)
        out.append({"Semana": R.fmt_d(ws), "Séries": series_por_grupo(S, ws, R.add_dias(ws, 6)).get(grupo, 0)})
    return out


def _feitos_na_semana(S: dict, ws: str) -> tuple[int, int]:
    """(concluídos, planejados) de uma semana inteira."""
    dias = R.dias_da_semana(ws)
    planejados = sum(1 for d in dias if R.treino_do_dia(S, d) not in ("OFF", "REC"))
    feitos = len({s["date"] for s in S["sessions"] if s["date"] in dias and s.get("status") == "concluida"})
    return feitos, planejados


def _comparar_cargas(S: dict, sessao: dict) -> tuple[list[str], list[str]]:
    """Exercícios da sessão com carga maior / menor que o registro anterior do mesmo exercício."""
    subiu, desceu = [], []
    for e in sessao.get("ex", []):
        h = [x for x in R.historico_ex(S, e["id"]) if x["max"] is not None]
        datas = [x["date"] for x in h]
        if sessao["date"] not in datas:
            continue
        i = max(k for k, d in enumerate(datas) if d == sessao["date"])
        if i == 0:
            continue
        atual, antes = h[i]["max"], h[i - 1]["max"]
        if atual > antes:
            subiu.append(R.nome_ex(e["id"]))
        elif atual < antes:
            desceu.append(R.nome_ex(e["id"]))
    return subiu, desceu


def _parados(S: dict) -> list[str]:
    """Exercícios com a mesma carga nas 4 últimas sessões com carga registrada."""
    out = []
    for ex_id in D.EXERCICIOS:
        h = [x["max"] for x in R.historico_ex(S, ex_id) if x["max"] is not None]
        if len(h) >= 4 and len(set(h[-4:])) == 1:
            out.append(R.nome_ex(ex_id))
    return out


def observacoes(S: dict) -> list[dict]:
    """Observações em ordem de importância: {"tipo": "alerta"|"info"|"ok", "texto", "telas": {"inicio", "treinos", "evolucao"}}."""
    t = R.hoje()
    obs: list[dict] = []

    def add(tipo, texto, *telas):
        obs.append({"tipo": tipo, "texto": texto, "telas": set(telas)})

    # desconforto registrado: sempre primeiro (segurança)
    recentes = [s for s in S["sessions"] if R.dias_entre(s["date"], t) <= 14]
    com_dor = list(dict.fromkeys(R.nome_ex(e["id"]) for s in recentes for e in s.get("ex", []) if e.get("painLevel") in DOR))
    if com_dor:
        add("alerta", "Você registrou dor moderada ou forte em: " + ", ".join(com_dor[:3]) + " (últimos 14 dias). "
            "Não aumente a carga nesses exercícios; se a dor continuar, piorar ou vier com inchaço, suspenda o "
            "exercício e procure um profissional de saúde.", "inicio", "treinos", "evolucao")
    interrompidas = sum(1 for s in recentes if s.get("status") == "interrompida")
    if interrompidas:
        add("alerta", f"{interrompidas} sessão(ões) interrompida(s) por sintoma nos últimos 14 dias. "
            "Antes do próximo treino, confira o check-in de hoje.", "inicio", "evolucao")

    ses = _concluidas(S)
    if not ses:
        if S["sessions"]:
            return obs
        add("info", "Ainda não há treinos concluídos: as observações sobre frequência, séries e cargas aparecem "
            "depois do primeiro treino salvo.", "inicio", "evolucao")
        return obs

    # semana atual: planejado × concluído até hoje
    ws = R.inicio_semana(t)
    dias_ate_hoje = [d for d in R.dias_da_semana(ws) if d <= t]
    planejados = [d for d in dias_ate_hoje if R.treino_do_dia(S, d) not in ("OFF", "REC")]
    feitos = len({s["date"] for s in ses if s["date"] in dias_ate_hoje})
    _, plan_semana = _feitos_na_semana(S, ws)
    if planejados:
        tipo = "ok" if feitos >= len(planejados) else "info"
        add(tipo, f"Nesta semana: {feitos} de {len(planejados)} treino(s) planejado(s) até hoje concluído(s) "
            f"({plan_semana} na semana).", "inicio", "treinos")

    # dias sem treinar (só quando havia treino planejado no intervalo)
    ultimo = ses[-1]["date"]
    parado = R.dias_entre(ultimo, t)
    perdidos = [d for d in (R.add_dias(ultimo, k) for k in range(1, parado)) if R.treino_do_dia(S, d) not in ("OFF", "REC")]
    if parado >= 5 and perdidos:
        add("info", f"Você está há {parado} dias sem concluir um treino. Para retomar, faça o treino do dia, "
            "sem tentar compensar os que ficaram para trás.", "inicio", "treinos")

    # frequência: 2 semanas fechadas mais recentes × as 2 anteriores
    sem = [_feitos_na_semana(S, R.add_dias(ws, -7 * k)) for k in (1, 2, 3, 4)]
    recente, anterior = sem[0][0] + sem[1][0], sem[2][0] + sem[3][0]
    if anterior >= 4 and recente <= 0.7 * anterior:
        add("info", f"Sua frequência caiu nas últimas 2 semanas: {recente} treino(s), contra {anterior} nas 2 anteriores. "
            "Se a agenda ficou difícil de cumprir, você pode reduzir os dias de treino em Meu plano — o plano só muda "
            "se você confirmar.", "inicio", "evolucao")
    elif anterior and recente > anterior:
        add("ok", f"Sua frequência subiu: {recente} treino(s) nas últimas 2 semanas, contra {anterior} nas 2 anteriores.",
            "evolucao")

    # última sessão: séries e cargas
    u = ses[-1]
    forca = [e for e in u.get("ex", []) if D.EXERCICIOS.get(e["id"], {}).get("tipo") == "carga"]
    total = sum(len(e.get("sets", [])) for e in forca)
    if total:
        add("info", f"Última sessão ({R.fmt_d(u['date'])}): {sum(_series_feitas(e) for e in forca)} de {total} séries "
            "de musculação concluídas.", "treinos", "evolucao")
    subiu, desceu = _comparar_cargas(S, u)
    if subiu:
        add("ok", f"Você aumentou a carga em {len(subiu)} exercício(s) em relação ao registro anterior "
            f"({', '.join(subiu[:3])}). Confira a técnica antes de aumentar de novo.", "inicio", "treinos", "evolucao")
    if desceu:
        add("info", f"Carga menor que a do registro anterior em: {', '.join(desceu[:3])}. Se foi por cansaço ou "
            "desconforto, tudo bem manter assim até a recuperação melhorar.", "treinos", "evolucao")
    parados = _parados(S)
    if parados:
        add("info", f"Mesma carga nas últimas 4 sessões em: {', '.join(parados[:3])}. A sugestão de aumento aparece "
            "quando você passa das repetições-alvo com boa técnica em 2 treinos seguidos.", "evolucao")

    # grupos prioritários: séries nos últimos 7 dias
    pr = O.prioridades(S)
    if pr:
        sg = series_por_grupo(S, R.add_dias(t, -6), t)
        add("info", "Grupos prioritários, últimos 7 dias: " + ", ".join(f"{g} {sg.get(g, 0)} série(s)" for g in pr) + ".",
            "treinos", "evolucao")

    # peso: médias de 2 semanas (só com pesagens suficientes)
    pesos = R.pesos_ordenados(S)
    rec = [w["peso"] for w in pesos if R.dias_entre(w["date"], t) <= 13]
    ant = [w["peso"] for w in pesos if 14 <= R.dias_entre(w["date"], t) <= 27]
    if len(rec) >= 2 and len(ant) >= 2:
        dif = sum(rec) / len(rec) - sum(ant) / len(ant)
        sinal = "+" if dif > 0 else ""
        add("info", f"Média de peso das últimas 2 semanas: {R.br(sum(rec) / len(rec))} kg ({sinal}{R.br(dif)} kg em "
            "relação às 2 anteriores). Oscilações de um dia para o outro são normais; vale a tendência.", "evolucao")
    # medidas: só com 2 ou mais registros da mesma medida
    from . import evolucao as E
    med = E.comparacao_medidas(S)
    if med:
        add("info", "Medidas desde o primeiro registro: " + ", ".join(
            f"{m['rotulo'].split(' (')[0].lower()} {'+' if m['variacao'] > 0 else ''}{R.br(m['variacao'])} cm" for m in med)
            + ". Medidas mostram mudanças que o peso sozinho pode esconder.", "evolucao")
    return obs


def para_tela(S: dict, tela: str, limite: int = 3) -> list[dict]:
    return [o for o in observacoes(S) if tela in o["telas"]][:limite]


# ---------------------------------------------------------------- sugestões com confirmação
DISPENSA_DIAS = 14  # "Agora não" esconde a mesma sugestão por 2 semanas


def sugestoes(S: dict) -> list[dict]:
    """Ajustes que a pessoa pode aplicar com um toque. Nenhum é aplicado sem confirmação.

    {"id", "texto", "acao": ("dias", n) | ("desativar", ex_id)}"""
    t = R.hoje()
    out = []
    dispensadas = S.get("dispensadas") or {}

    def add(sid, texto, acao):
        quando = dispensadas.get(sid)
        if quando and R.dias_entre(quando, t) < DISPENSA_DIAS:
            return
        out.append({"id": sid, "texto": texto, "acao": acao})

    # frequência abaixo da agenda em 3 semanas seguidas → menos dias
    ws = R.inicio_semana(t)
    sem = [_feitos_na_semana(S, R.add_dias(ws, -7 * k)) for k in (1, 2, 3)]
    dias = int(S["profile"].get("dias") or 0)
    if all(p for _, p in sem) and all(f < p for f, p in sem):
        alvo = max(1, round(sum(f for f, _ in sem) / 3 + 0.49))
        if alvo < dias:
            add(f"dias-{alvo}", f"Nas últimas 3 semanas você fez em média {R.br(sum(f for f, _ in sem) / 3)} treino(s) por "
                f"semana, com {dias} planejados. Quer passar a agenda para {alvo} dia(s)? Os treinos já feitos não mudam.",
                ("dias", alvo))
    # dor moderada ou forte no mesmo exercício em 2 sessões dos últimos 21 dias → tirar do plano
    contagem: dict[str, int] = {}
    for s in S["sessions"]:
        if R.dias_entre(s["date"], t) <= 21:
            for e in s.get("ex", []):
                if e.get("painLevel") in DOR:
                    contagem[e["id"]] = contagem.get(e["id"], 0) + 1
    for ex_id, n in contagem.items():
        if n >= 2 and ex_id in D.EXERCICIOS and (S["plan"].get(ex_id) or {}).get("ativo", True):
            add(f"tirar-{ex_id}", f"Você registrou dor em {R.nome_ex(ex_id)} em {n} treinos recentes. Quer tirar esse exercício "
                "do plano? Outro da mesma vaga entra no lugar; dá para voltar em Meu plano → Ajustes por exercício. "
                "Se a dor continuar, procure um profissional de saúde.", ("desativar", ex_id))
    return out


def aplicar(S: dict, sug: dict) -> str:
    """Aplica uma sugestão confirmada pela pessoa e devolve a frase do que mudou."""
    from . import plano as P
    tipo, valor = sug["acao"]
    if tipo == "dias":
        P.atualizar_perfil(S, {"dias": int(valor)})
        return f"Agenda refeita para {valor} dia(s) por semana."
    if tipo == "desativar":
        S["plan"].setdefault(valor, {})["ativo"] = False
        return f"{R.nome_ex(valor)} saiu do plano."
    return ""


def dispensar(S: dict, sug: dict) -> None:
    S.setdefault("dispensadas", {})[sug["id"]] = R.hoje()
