"""Objetivos, equipamentos e grupos prioritários: como cada escolha do perfil muda o plano (sem interface).

Contas antigas não têm esses campos: valem os padrões (emagrecimento, todos os equipamentos, sem prioridade),
que reproduzem o plano de antes. Nenhuma regra daqui promete resultado: elas só ajustam volume, frequência,
cardio e escolha de exercícios dentro do que a pesquisa (docs/pesquisa.md) sustenta.
"""
from __future__ import annotations

from . import biblioteca as B
from . import dados as D

OBJETIVOS = {
    "emagrecimento": {
        "nome": "Emagrecimento", "icone": ":material/local_fire_department:",
        "resumo": "Cardio semanal + musculação para preservar massa magra.",
        "como": ("A perda de gordura depende do balanço de energia (alimentação, gasto diário e exercício), não só do "
                 "treino. A musculação durante a perda de peso ajuda a preservar a massa magra e aumenta a perda de "
                 "gordura; o cardio soma minutos semanais. Não existe queima localizada de gordura, e nenhum treino "
                 "garante uma quantidade de quilos.")},
    "hipertrofia": {
        "nome": "Hipertrofia", "icone": ":material/fitness_center:",
        "resumo": "Mais séries por grupo, cada um treinado 2× por semana.",
        "como": ("O ganho de massa muscular responde ao volume semanal (séries por grupo), com retorno cada vez menor, "
                 "e a progressão gradual de carga ou repetições. Faixas de repetições diferentes funcionam quando as "
                 "séries são feitas perto da falha; o app mantém 15 repetições e progride pela regra de cargas.")},
    "gluteos": {
        "nome": "Glúteos", "icone": ":material/directions_run:",
        "resumo": "Um exercício extra de glúteos em cada treino de pernas.",
        "como": ("Hip thrust, agachamento, terra romeno, afundo, extensão de quadril e abdução entram em rodízio. "
                 "Em estudos, hip thrust e agachamento produziram hipertrofia de glúteos semelhante em iniciantes; "
                 "nenhum exercício isolado é o melhor para todos.")},
    "peitoral": {
        "nome": "Peitoral", "icone": ":material/accessibility_new:",
        "resumo": "Um exercício extra de peito, em 2 dias da semana.",
        "como": ("Supino reto, inclinado, chest press, flexões e crucifixo/crossover entram em rodízio. O supino inclinado "
                 "trabalhou mais a parte superior do peitoral num estudo com iniciantes; a flexão com carga equivalente "
                 "teve ganhos semelhantes aos do supino.")},
    "completo": {
        "nome": "Treino completo", "icone": ":material/sports_gymnastics:",
        "resumo": "Corpo inteiro ou superiores/inferiores, sem divisões complexas.",
        "como": ("Todos os grandes grupos musculares pelo menos 2× por semana. Com 2 ou 3 dias, o treino é de corpo "
                 "inteiro; com 4 ou mais, alterna superiores e inferiores.")},
    "condicionamento": {
        "nome": "Condicionamento", "icone": ":material/favorite:",
        "resumo": "Mais minutos de cardio na semana, em ritmo de conversa.",
        "como": ("O alvo de cardio sobe para pelo menos 200 min por semana, dentro da faixa da OMS (150 a 300 min de "
                 "atividade moderada), com musculação para todos os grandes grupos.")},
}
PADRAO = ["emagrecimento"]
# objetivos que pedem foco em massa muscular (mais séries nos compostos depois da adaptação)
FOCO_MUSCULAR = {"hipertrofia", "gluteos", "peitoral"}
MAX_PRIORIDADES = 2  # mais que isso não cabe no tempo de uma sessão

# Grupo priorizado → vaga extra (rótulo, opções em rodízio) e os treinos em que ela entra: sempre 2 dias por semana
# ou mais, para o grupo ser treinado pelo menos 2× (ACSM 2026).
PRIORIDADES = {
    "Glúteos": ("Glúteos (prioridade)", ['hip_thrust', 'extensao_quadril_cabo', 'afundo_reverso', 'ponte_gluteo',
                                          'step_up', 'cadeira_abdutora'], ("LA", "LB", "FULL")),
    "Peitoral": ("Peito (prioridade)", ['supino_inclinado', 'flexao_bracos', 'crossover_polia', 'supino_inclinado_halteres',
                                         'flexao_inclinada', 'supino_maquina'], ("A", "B", "FULL")),
    "Quadríceps": ("Quadríceps (prioridade)", ['cadeira_extensora', 'hack_maquina', 'afundo_reverso', 'agachamento_goblet',
                                                'agachamento_peso_corpo'], ("LA", "LB", "FULL")),
    "Posteriores": ("Posteriores (prioridade)", ['mesa_flexora', 'stiff_halteres', 'terra_romeno', 'cadeira_flexora'],
                    ("LA", "LB", "FULL")),
    "Panturrilhas": ("Panturrilha (prioridade)", ['panturrilha_em_pe', 'panturrilha_sentado'], ("LA", "LB", "FULL")),
    "Costas": ("Costas (prioridade)", ['remada_baixa', 'remada_halter', 'puxada_supinada', 'remada_apoio'], ("A", "B", "FULL")),
    "Ombros": ("Ombros (prioridade)", ['elevacao_lateral', 'crucifixo_inverso', 'desenvolvimento_halteres'], ("A", "B", "FULL")),
    "Bíceps": ("Bíceps (prioridade)", ['rosca_inclinada', 'rosca_martelo', 'rosca_maquina'], ("A", "B", "FULL")),
    "Tríceps": ("Tríceps (prioridade)", ['triceps_corda_acima', 'triceps_frances', 'triceps_maquina'], ("A", "B", "FULL")),
    "Abdômen": ("Abdômen (prioridade)", ['pallof', 'prancha', 'abdominal_polia'], ("LA", "B", "FULL")),
}
PRIORIDADE_DO_OBJETIVO = {"gluteos": "Glúteos", "peitoral": "Peitoral"}

# Sem máquinas ou sem algum equipamento, cada vaga ganha opções que dispensam o que falta.
EXTRAS_POR_VAGA = {
    'Peito (composto)': ['supino_inclinado_halteres', 'flexao_inclinada', 'flexao_bracos'],
    'Peito': ['supino_inclinado_halteres', 'flexao_inclinada', 'flexao_bracos'],
    'Peito (isolado)': ['flexao_inclinada'],
    'Tríceps': ['triceps_frances'],
    'Costas (vertical)': ['remada_halter'], 'Costas (horizontal)': ['remada_halter'], 'Costas': ['remada_halter'],
    'Costas (isolado)': ['remada_halter'], 'Posterior de ombro': ['elevacao_lateral'], 'Postura': ['remada_halter'],
    'Bíceps': ['rosca_martelo'], 'Abdômen': ['prancha'],
    'Quadríceps (composto)': ['agachamento_goblet', 'agachamento_peso_corpo', 'agachamento_livre'],
    'Quadríceps (isolado)': ['afundo_reverso', 'step_up'],
    'Posteriores': ['stiff_halteres', 'terra_romeno', 'ponte_gluteo'],
    'Posteriores (isolado)': ['ponte_gluteo'], 'Abdutores': ['ponte_gluteo'], 'Adutores': ['afundo_reverso'],
    'Agachamento': ['agachamento_peso_corpo', 'agachamento_livre'],
    'Glúteos e quadril': ['afundo_reverso', 'ponte_gluteo', 'hip_thrust'],
    'Pernas (composto)': ['agachamento_peso_corpo', 'agachamento_livre'],
    'Ombros': ['desenvolvimento_halteres'],
}


# ---------------------------------------------------------------- leitura do perfil
def objetivos(S: dict) -> list[str]:
    o = S["profile"].get("objetivos")
    validos = [x for x in o if x in OBJETIVOS] if isinstance(o, list) else []
    return list(dict.fromkeys(validos)) or list(PADRAO)


def equipamentos(S: dict) -> set[str]:
    e = S["profile"].get("equipamentos")
    validos = {x for x in e if x in B.EQUIPAMENTOS} if isinstance(e, list) else set()
    return validos or set(B.EQUIPAMENTOS)


def tem_todos_os_equipamentos(S: dict) -> bool:
    return equipamentos(S) == set(B.EQUIPAMENTOS)


def prioridades(S: dict) -> list[str]:
    """Grupos priorizados: os dos objetivos (glúteos, peitoral) primeiro, depois os escolhidos; no máximo 2."""
    p = S["profile"].get("prioridades")
    escolhidos = [x for x in p if x in PRIORIDADES] if isinstance(p, list) else []
    dos_objetivos = [PRIORIDADE_DO_OBJETIVO[o] for o in objetivos(S) if o in PRIORIDADE_DO_OBJETIVO]
    return list(dict.fromkeys(dos_objetivos + escolhidos))[:MAX_PRIORIDADES]


def foco_muscular(S: dict) -> bool:
    return bool(FOCO_MUSCULAR & set(objetivos(S)))


def foco_cardio(S: dict) -> bool:
    """Emagrecimento ou condicionamento: o cardio segue as faixas das fases; sem eles, fica no mínimo da OMS."""
    return bool({"emagrecimento", "condicionamento"} & set(objetivos(S)))


# ---------------------------------------------------------------- efeitos no plano
def falta_equipamento(S: dict, ex_id: str) -> str:
    if ex_id not in D.EXERCICIOS:
        return ""
    precisa = B.meta(ex_id)["equipamentos"]
    if set(precisa) & equipamentos(S):
        return ""
    return "Precisa de " + " ou ".join(B.EQUIPAMENTOS[x].lower() for x in precisa) + ", marcado como indisponível no perfil."


def dificil_demais(S: dict, ex_id: str, nivel: str) -> str:
    if nivel == "iniciante" and ex_id in D.EXERCICIOS and B.meta(ex_id)["dificuldade"] == "avancado":
        return "Técnica mais exigente: entra no plano a partir do nível intermediário."
    return ""


def vagas_do_treino(S: dict, wk: str) -> list[tuple]:
    """Vagas do modelo do treino, com as opções sem o equipamento que falta e as vagas dos grupos priorizados.

    Para quem tem todos os equipamentos e não priorizou nada, devolve o modelo original (o rodízio não muda)."""
    vagas = list(D.MODELOS.get(wk, []))
    if not tem_todos_os_equipamentos(S):
        vagas = [(r, list(op) + [x for x in EXTRAS_POR_VAGA.get(r, []) if x not in op], f2) for r, op, f2 in vagas]
    extras = [(PRIORIDADES[g][0], list(PRIORIDADES[g][1]), False) for g in prioridades(S) if wk in PRIORIDADES[g][2]]
    # a vaga prioritária entra logo depois do primeiro exercício composto: é a última a sair se faltar tempo
    return vagas[:1] + extras + vagas[1:] if extras else vagas


def cardio_semanal_alvo(S: dict, pelo_peso: int) -> int:
    obj = set(objetivos(S))
    if "emagrecimento" in obj:
        alvo = pelo_peso
    else:
        alvo = 150  # mínimo da OMS para adultos
    if "condicionamento" in obj:
        alvo = max(alvo, 200)
    return alvo


def agenda_para(dias: int, objs: list[str] | None) -> dict | None:
    """Com 3 dias e foco muscular ou treino completo, corpo inteiro 3×: cada grupo treinado 3× na semana.
    Nos outros casos, None (vale a agenda padrão de cada número de dias)."""
    if dias == 3 and objs and ({"completo"} | FOCO_MUSCULAR) & set(objs):
        return {"1": "FULL", "3": "FULL", "5": "FULL"}
    return None


def resumo(S: dict) -> list[str]:
    """Linhas para “Como este treino foi montado para você”."""
    obj = objetivos(S)
    out = ["Objetivo: " + " + ".join(OBJETIVOS[o]["nome"] for o in obj)]
    pr = prioridades(S)
    if pr:
        out.append("Grupos prioritários: " + ", ".join(pr) + " (um exercício a mais nos treinos desses grupos, 2× por semana)")
    if foco_muscular(S):
        out.append("Foco muscular: 4 séries nos exercícios compostos depois da adaptação (exceto iniciantes)")
    if not foco_cardio(S):
        out.append("Sem emagrecimento ou condicionamento entre os objetivos: cardio no mínimo da OMS, sessões mais curtas")
    if not tem_todos_os_equipamentos(S):
        falta = [B.EQUIPAMENTOS[x] for x in B.EQUIPAMENTOS if x not in equipamentos(S)]
        out.append("Sem " + ", ".join(f.lower() for f in falta) + ": o plano usa alternativas com o que você tem")
    return out
