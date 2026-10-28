"""Plano personalizado de 20 semanas (sem interface).

O plano é calculado a cada vez a partir do perfil, da avaliação, das limitações e do histórico.
Mudar peso, altura, dias, tempo ou limitações recalcula só o que vem pela frente: as sessões
já registradas guardam os exercícios e as prescrições que foram feitos.
"""
from __future__ import annotations

import math

import re

from . import dados as D
from . import regras as R

PESAGEM_INICIAL = "Informado no primeiro acesso"
AQUECIMENTO_MIN = 10
VOLTA_CALMA_MIN = 5
CARDIO_MINIMO = 30
CARDIO_MAXIMO = 60
MIN_EXERCICIOS_FORCA = 3


# ---------------------------------------------------------------- perfil
def nivel(S: dict) -> str:
    n = str(S["profile"].get("nivel") or "").lower()
    if n.startswith("avan"):
        return "avancado"
    if n.startswith("inter"):
        return "intermediario"
    return "iniciante"


def semente(S: dict) -> int:
    """Deslocamento próprio de cada conta na rotação dos exercícios (0 em estados antigos ou de teste)."""
    try:
        return max(0, int(S.get("semente") or 0))
    except (TypeError, ValueError):
        return 0


def resumo_personalizacao(S: dict, semana: int) -> list[str]:
    """Em linguagem simples, o que do perfil desta pessoa está moldando o plano."""
    p = S["profile"]
    n = {"iniciante": "Iniciante: 2 séries nas 2 primeiras semanas e exercícios complementares só a partir da fase 2",
         "intermediario": "Intermediário: exercícios complementares desde a 1ª semana",
         "avancado": "Avançado: exercícios complementares desde a 1ª semana e 4 séries nos compostos a partir da fase 2"}[nivel(S)]
    out = [n, f"{int(p.get('dias') or 0)} dia(s) de treino por semana, até {int(p.get('tempoMax') or 90)} min por sessão"]
    i = imc_atual(S)
    if R.ok(i):
        out.append(f"IMC {R.br(i)}: " + ("cardio e exercícios de baixo impacto nesta fase" if baixo_impacto(S, semana)
                                          else "sem restrição de impacto por IMC nesta fase"))
    falta = R.peso_atual(S) - float(p["pesoMeta"])
    out.append(f"Faltam {R.br(max(0.0, falta))} kg para a meta: alvo de {cardio_semanal_alvo(S)} min de cardio na semana")
    lim = regioes_limitadas(S)
    if lim:
        out.append("Limitações consideradas: " + ", ".join(sorted(set(lim.values()))) + " (exercícios dessas regiões ficam fora)")
    if str(S["assess"].get("proibidos") or "").strip():
        out.append("Exercícios proibidos na avaliação ficam fora do plano")
    return out


def fase_da_semana(semana: int) -> tuple[int, dict]:
    semana = max(1, min(D.SEMANAS_PLANO, semana))
    for i, f in enumerate(D.FASES_20):
        ini, fim = f["semanas"]
        if ini <= semana <= fim:
            return i, f
    return len(D.FASES_20) - 1, D.FASES_20[-1]


def objetivo_da_semana(semana: int) -> str:
    i, f = fase_da_semana(semana)
    return f["objetivos"][(semana - f["semanas"][0]) % len(f["objetivos"])]


def imc_atual(S: dict) -> float:
    return R.imc(S, R.peso_atual(S))


def baixo_impacto(S: dict, semana: int) -> bool:
    """IMC alto combinado com a fase e o nível: o IMC nunca decide sozinho."""
    i = imc_atual(S)
    if not R.ok(i):
        return False
    fase_idx = fase_da_semana(semana)[0]
    if i >= 35 and fase_idx <= 1:
        return True
    return i >= 30 and fase_idx == 0 and nivel(S) == "iniciante"


def regioes_limitadas(S: dict) -> dict[str, str]:
    """Regiões citadas nas limitações do perfil e da avaliação → palavra encontrada."""
    a = S["assess"]
    texto = " ".join(str(x or "") for x in (S["profile"].get("limitacao"), a.get("joelho"), a.get("diagTxt"),
                                            a.get("proibidos"))).lower() + " "
    achadas = {}
    for regiao, palavras in D.PALAVRAS_ARTICULACAO.items():
        for p in palavras:
            if p in texto:
                achadas[regiao] = p.strip()
                break
    return achadas


def cardio_semanal_alvo(S: dict) -> int:
    """Quanto mais longe da meta, mais perto do topo da faixa da OMS (150 a 300 min)."""
    falta = R.peso_atual(S) - float(S["profile"]["pesoMeta"])
    if falta > 10:
        return 250
    if falta > 3:
        return 200
    return 150


# ---------------------------------------------------------------- exercícios permitidos
def _normalizar(txt: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", str(txt or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " " + re.sub(r"[^a-z0-9]+", " ", t).strip() + " "


def nomes_do_exercicio(ex_id: str) -> list[str]:
    """Formas como alguém escreveria o exercício: nome sem o parêntese, a primeira palavra (se longa) e apelidos."""
    nome = re.sub(r"\(.*?\)|\d+\s*°?", "", D.EXERCICIOS[ex_id]["nome"])  # sem parêntese e sem “45°”
    formas = [_normalizar(nome)]
    primeira = _normalizar(nome).split()[0] if _normalizar(nome).split() else ""
    if len(primeira) >= 5:
        formas.append(f" {primeira} ")
    formas += [_normalizar(x) for x in D.APELIDOS.get(ex_id, [])]
    return [f for f in formas if f.strip()]


def proibido_por_nome(S: dict, ex_id: str) -> str:
    """O nome (ou apelido) do exercício aparece em “Exercícios proibidos” da avaliação.

    O nome completo bloqueia só aquele exercício. A primeira palavra sozinha (ex.: “rosca”, “cadeira”) bloqueia
    a família inteira, a não ser que o texto já cite o nome completo de algum exercício dessa família: assim
    “rosca martelo” tira só a rosca martelo e “rosca” tira todas."""
    texto = _normalizar(S["assess"].get("proibidos"))
    if not texto.strip():
        return ""
    formas = nomes_do_exercicio(ex_id)
    if formas[0] in texto:
        return formas[0].strip()
    primeira = formas[0].split()[0]
    familia_citada = any(nomes_do_exercicio(x)[0] in texto for x in D.EXERCICIOS
                         if x != ex_id and nomes_do_exercicio(x)[0].split()[0] == primeira)
    for f in formas[1:]:
        if f in texto and not (f.strip() == primeira and familia_citada):
            return f.strip()
    return ""


def motivo_bloqueio(S: dict, ex_id: str, semana: int) -> str:
    """Texto do motivo quando o exercício não deve entrar no plano; vazio se pode."""
    livre, msg = R.status_ex(S, ex_id)
    if not livre:
        return msg
    termo = proibido_por_nome(S, ex_id)
    if termo:
        return f"Listado como proibido na avaliação (“{termo}”). Só volte a fazer com liberação do profissional."
    for regiao, palavra in regioes_limitadas(S).items():
        if ex_id in D.ARTICULACOES.get(regiao, []):
            return f"Fora do plano por causa de “{palavra}” nas limitações. Inclua só com liberação do profissional."
    if baixo_impacto(S, semana) and ex_id in D.EXIGE_CHAO_OU_EQUILIBRIO:
        return "Deixado para depois: exige chão ou equilíbrio em uma perna, o que é mais difícil nesta fase."
    if ex_id in D.EXERCICIOS and D.EXERCICIOS[ex_id].get("cardio") and baixo_impacto(S, semana) \
            and ex_id not in D.CARDIO_BAIXO_IMPACTO:
        return "Deixado para depois: nesta fase o cardio é de baixo impacto."
    return ""


def digitos_da_semana(semana: int, bases: list[int]) -> list[int]:
    """Numeração mista: semanas seguidas geram combinações diferentes de opções.

    O primeiro dígito muda toda semana e os seguintes mudam quando o anterior dá a volta,
    como um hodômetro. Assim as 20 semanas não repetem a mesma combinação de exercícios."""
    n, out = semana - 1, []
    for b in bases:
        out.append(n % b if b else 0)
        n //= max(1, b)
    return out


def escolher_na_vaga(S: dict, opcoes: list[str], semana: int, inicio: int, usados: set) -> str | None:
    n = len(opcoes)
    for k in range(n):
        ex_id = opcoes[(inicio + k) % n]
        if ex_id not in usados and not motivo_bloqueio(S, ex_id, semana):
            return ex_id
    return None


def lista_cardio(S: dict, semana: int) -> list[str]:
    return D.CARDIO_BAIXO_IMPACTO if baixo_impacto(S, semana) else D.CARDIO_TODOS


def escolher_cardio(S: dict, semana: int, inicio: int, preferido: str | None = None) -> str | None:
    lista = lista_cardio(S, semana)
    if preferido and preferido in D.CARDIO_TODOS and not motivo_bloqueio(S, preferido, semana):
        return preferido
    n = len(lista)
    for k in range(n):
        ex_id = lista[(inicio + k) % n]
        if not motivo_bloqueio(S, ex_id, semana):
            return ex_id
    return "ergometro_bracos" if not motivo_bloqueio(S, "ergometro_bracos", semana) else None


def prescricao(S: dict, ex_id: str, semana: int) -> dict:
    """Séries, repetições e descanso da fase; o que o usuário editou no plano tem prioridade."""
    b = D.EXERCICIOS[ex_id]
    _, fase = fase_da_semana(semana)
    p = {"series": 3, "reps": b.get("reps", "15"), "descanso": int(b.get("descanso") or 0)}
    if b["tipo"] == "carga":
        if nivel(S) == "iniciante" and semana <= 2:
            p["series"] = 2
        elif nivel(S) == "avancado" and fase_da_semana(semana)[0] >= 1 and ex_id not in D.ISOLADOS:
            p["series"] = 4  # compostos com uma série a mais depois da adaptação
        if p["descanso"] >= 60:
            p["descanso"] = fase["descanso"]
    else:
        p = {"series": 1, "duracao": int(b.get("duracao") or 0), "descanso": 0}
        o = S["plan"].get(ex_id) or {}
        if o.get("duracao") and not b.get("cardio"):  # o cardio é calculado pelo plano
            p["duracao"] = int(o["duracao"])
        return p
    o = S["plan"].get(ex_id) or {}
    for k in ("series", "reps", "descanso"):
        if o.get(k) not in (None, "") and k in p:
            p[k] = o[k]
    return p


def minutos_forca(itens: list[dict]) -> float:
    t = 0.0
    for it in itens:
        if "duracao" in it:
            continue
        t += float(it["series"]) * (45 + float(it["descanso"])) / 60 + 1
    return t


# ---------------------------------------------------------------- plano do dia
def plano_do_dia(S: dict, data: str, semana: int | None = None, wk: str | None = None) -> dict:
    semana = semana or semana_do_programa(S)["semana"]
    wk = wk or R.treino_do_dia(S, data)
    W = D.TREINOS[wk]
    fase_idx, fase = fase_da_semana(semana)
    dia = R.dia_js(data)
    out = {"wk": wk, "nome": W["nome"], "curto": W["curto"], "obj": W["obj"], "data": data, "semana": semana,
           "fase_idx": fase_idx, "fase": fase, "objetivo_semana": objetivo_da_semana(semana),
           "itens": [], "etapas": {}, "total": 0, "avisos": [], "bloqueados": [], "personalizado": False}
    if wk == "OFF":
        return out
    if wk == "REC":
        out["itens"] = [{"id": x, **prescricao(S, x, semana)} for x in W["ex"] if not motivo_bloqueio(S, x, semana)]
        out["etapas"] = {"Recuperação": 15}
        out["total"] = 15
        return out

    ajuste = (S.get("ajustes") or {}).get(f"{semana}|{wk}") or {}
    forca: list[str] = []
    cardio_inicio = semana - 1
    if ajuste.get("ex"):
        out["personalizado"] = True
        for x in ajuste["ex"]:
            if x in D.EXERCICIOS and not D.EXERCICIOS[x].get("cardio") and D.EXERCICIOS[x]["tipo"] == "carga":
                m = motivo_bloqueio(S, x, semana)
                if m:
                    out["bloqueados"].append((x, m))
                elif x not in forca:
                    forca.append(x)
    elif wk in D.MODELOS:
        vagas = D.MODELOS[wk]
        # o cardio é o dígito que muda toda semana; depois as vagas fixas e, por último, as da fase 2.
        # Mesmo com exercícios bloqueados, duas semanas seguidas nunca ficam iguais.
        ordem = [i for i, v in enumerate(vagas) if not v[2]] + [i for i, v in enumerate(vagas) if v[2]]
        # a semente da conta desloca a rotação: duas pessoas com o mesmo perfil não recebem o mesmo treino
        dig = digitos_da_semana(semana + semente(S), [len(lista_cardio(S, semana))] + [len(vagas[i][1]) for i in ordem])
        cardio_inicio = dig[0]
        inicio_vaga = {i: dig[k + 1] for k, i in enumerate(ordem)}
        for vaga, (_, opcoes, so_fase2) in enumerate(vagas):
            if so_fase2 and fase_idx == 0 and nivel(S) == "iniciante":
                continue  # quem já treina recebe os exercícios complementares desde a primeira semana
            ex_id = escolher_na_vaga(S, opcoes, semana, inicio_vaga[vaga], set(forca))
            if ex_id:
                forca.append(ex_id)
            else:
                out["bloqueados"].append((opcoes[0], motivo_bloqueio(S, opcoes[0], semana) or "Sem opção liberada."))
    else:
        for x in W["ex"]:
            if D.EXERCICIOS[x]["tipo"] == "carga":
                m = motivo_bloqueio(S, x, semana)
                (out["bloqueados"].append((x, m)) if m else forca.append(x))

    itens = [{"id": x, **prescricao(S, x, semana), **((ajuste.get("presc") or {}).get(x) or {})} for x in forca]
    # o dia da semana desloca a modalidade: dois treinos da mesma semana não repetem o cardio
    cardio_id = escolher_cardio(S, semana, cardio_inicio + dia, ajuste.get("cardio")) \
        if wk in D.TREINOS_COM_CARDIO else None

    alvo = float(S["profile"].get("tempoMax") or 90)
    lo, hi = fase["cardio"]
    teto = (50 if fase_idx == 0 else 65) if wk == "CARDIO" else CARDIO_MAXIMO
    if wk == "CARDIO":
        cardio = teto
    else:
        n_dias = sum(1 for v in S["schedule"].values() if v in D.TREINOS_COM_CARDIO) or 1
        cardio = max(CARDIO_MINIMO, lo, min(hi, round(cardio_semanal_alvo(S) / n_dias)))
    if wk in ("LA", "LB") and not forca and R.sintomas(S):
        out["avisos"].append("Exercícios de pernas bloqueados hoje: troque para um treino de superiores em "
                             "“Trocar o treino de hoje”, ou descanse.")
    if cardio_id == "ergometro_bracos":
        cardio = 15
        out["avisos"].append("Cardio de pernas bloqueado hoje: use o ergômetro de braços por até 15 min, se não houver dor.")

    def total():
        return AQUECIMENTO_MIN + minutos_forca(itens) + (cardio if cardio_id else 0) + VOLTA_CALMA_MIN

    # Cabe no tempo: o cardio desce até o piso da fase, depois saem isolados do fim,
    # depois o cardio desce até 30 min e, por último, os exercícios ficam com 2 séries.
    if cardio_id and cardio_id != "ergometro_bracos" and total() > alvo:
        cardio = max(CARDIO_MINIMO, lo, cardio - math.ceil(total() - alvo))
    cortes = []
    while total() > alvo and len(itens) > MIN_EXERCICIOS_FORCA:
        iso = [k for k, it in enumerate(itens) if it["id"] in D.ISOLADOS]
        if not iso:
            break
        cortes.append(R.nome_ex(itens.pop(iso[-1])["id"]))
    if cardio_id and cardio_id != "ergometro_bracos" and total() > alvo:
        cardio = max(CARDIO_MINIMO, cardio - math.ceil(total() - alvo))
    if total() > alvo:
        for it in itens:
            if D.EXERCICIOS[it["id"]]["tipo"] == "carga" and int(it["series"]) > 2:
                it["series"] = 2
    if cortes:
        out["avisos"].append(f"Para caber em {R.brx(alvo)} min, saíram: {', '.join(cortes)}.")
    # Sobrou tempo: o cardio cresce, sem acrescentar exercícios desnecessários. Quanto mais longe da meta,
    # mais ele pode crescer acima do teto da fase (+15 min longe da meta, +5 no meio do caminho, 0 perto).
    folga = {250: 15, 200: 5}.get(cardio_semanal_alvo(S), 0)
    if cardio_id and cardio_id != "ergometro_bracos" and total() < alvo:
        limite = teto if wk == "CARDIO" else min(teto, hi + folga)
        cardio = max(cardio, min(limite, cardio + math.floor(alvo - total())))

    if cardio_id:
        itens.append({"id": cardio_id, "series": 1, "duracao": int(cardio), "descanso": 0})
    out["itens"] = itens
    out["etapas"] = {"Aquecimento": AQUECIMENTO_MIN, "Musculação": int(round(minutos_forca(itens))),
                     "Cardio": int(cardio) if cardio_id else 0, "Volta à calma": VOLTA_CALMA_MIN}
    out["total"] = int(round(total()))
    if out["total"] < 85 and alvo >= 90:
        out["avisos"].append("Sessão abaixo de 90 min nesta fase: o volume cresce aos poucos, conforme a recuperação.")
    if alvo < 90:
        out["avisos"].append(f"Tempo máximo definido em {R.brx(alvo)} min, abaixo da meta de 90 min do plano.")
    return out


def plano_da_semana(S: dict, semana: int, ws: str | None = None) -> list[dict]:
    """Os 7 dias de uma semana do plano, usando a agenda atual."""
    ws = ws or R.inicio_semana(R.hoje())
    return [plano_do_dia(S, d, semana) for d in R.dias_da_semana(ws)]


# ---------------------------------------------------------------- progressão condicionada
def avaliar_semana(S: dict, ws: str) -> dict:
    """Resultado de uma semana encerrada. A fase só avança com execução e recuperação adequadas."""
    inicio = S.get("startDate") or ""
    dias = [d for d in R.dias_da_semana(ws) if not inicio or d >= inicio]
    planejados = [d for d in dias if R.treino_do_dia(S, d) not in ("OFF", "REC")]
    feitos = {s["date"] for s in S["sessions"] if s["date"] in dias and s.get("status") == "concluida"}
    minimo = max(1, math.ceil(0.6 * len(planejados))) if planejados else 0
    sinais = []
    for s in S["sessions"]:
        if s["date"] not in dias:
            continue
        if s.get("status") == "interrompida":
            sinais.append("sessão interrompida por sintoma")
        if any(e.get("painLevel") in ("moderado", "forte") for e in s.get("ex", [])):
            sinais.append("dor moderada ou forte em exercício")
        if s.get("recuperacao") == "ruim":
            sinais.append("recuperação ruim registrada")
    for d in dias:
        ci = S["checkins"].get(d)
        if ci and (ci.get("red") or ci.get("inchaco") or (ci.get("dor") or 0) >= 5):
            sinais.append("sinal de alerta, inchaço ou dor forte no check-in")
    sinais = list(dict.fromkeys(sinais))
    if not planejados:
        return {"conta": False, "aprovada": False, "motivo": "Semana sem treinos planejados.", "feitos": 0, "minimo": 0}
    if len(feitos) < minimo:
        motivo = f"{len(feitos)} de {len(planejados)} treinos concluídos (mínimo {minimo}): a semana se repete."
        return {"conta": True, "aprovada": False, "motivo": motivo, "feitos": len(feitos), "minimo": minimo}
    if sinais:
        return {"conta": True, "aprovada": False, "feitos": len(feitos), "minimo": minimo,
                "motivo": "A semana se repete por causa de: " + "; ".join(sinais) + "."}
    return {"conta": True, "aprovada": True, "feitos": len(feitos), "minimo": minimo,
            "motivo": f"{len(feitos)} de {len(planejados)} treinos concluídos, sem sinais de alerta."}


def semana_do_programa(S: dict) -> dict:
    """Semana atual do plano: avança só quando a semana anterior foi aprovada."""
    inicio = S.get("startDate") or ""
    semana, historico = 1, []
    if inicio:
        ws, atual = R.inicio_semana(inicio), R.inicio_semana(R.hoje())
        while ws < atual:
            r = avaliar_semana(S, ws)
            if r["conta"]:
                historico.append({"ws": ws, "semana": semana, **r})
                if r["aprovada"] and semana < D.SEMANAS_PLANO:
                    semana += 1
            ws = R.add_dias(ws, 7)
    concluido = bool(historico) and historico[-1]["semana"] == D.SEMANAS_PLANO and historico[-1]["aprovada"]
    return {"semana": semana, "historico": historico, "concluido": concluido}


# ---------------------------------------------------------------- perfil e agenda
def agenda_para(dias: int) -> dict:
    dias = max(1, min(7, int(dias)))
    return {str(d): D.AGENDAS_POR_DIAS[dias].get(str(d), "OFF") for d in range(7)}


def sincronizar_pesagem_inicial(S: dict) -> bool:
    """Contas que mudaram o peso inicial antes desta correção ficaram com a pesagem do primeiro acesso diferente
    do perfil. O peso inicial do perfil é o declarado por último: a pesagem do primeiro acesso passa a segui-lo."""
    if not S["profile"].get("confirmado"):
        return False
    ini, mudou = float(S["profile"]["pesoInicial"]), False
    for w in S["weights"]:
        if w.get("cond") == PESAGEM_INICIAL and float(w["peso"]) != ini:
            w["peso"], mudou = ini, True
    return mudou


def atualizar_perfil(S: dict, novos: dict) -> list[str]:
    """Aplica os dados novos; se os dias mudarem, a agenda é refeita. O histórico não é tocado."""
    p = S["profile"]
    mudou = [k for k, v in novos.items() if p.get(k) != v]
    dias_antes = p.get("dias")
    p.update(novos)
    if "pesoInicial" in mudou:
        # a pesagem criada no primeiro acesso é o próprio peso inicial: corrigir um corrige o outro
        # (as pesagens registradas depois, na Evolução, não mudam)
        for w in S["weights"]:
            if w.get("cond") == PESAGEM_INICIAL:
                w["peso"] = novos["pesoInicial"]
    if "dias" in novos and int(novos["dias"]) != int(dias_antes or 0):
        S["schedule"] = agenda_para(novos["dias"])
    return mudou
