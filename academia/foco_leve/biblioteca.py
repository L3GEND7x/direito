"""Biblioteca de exercícios: grupo muscular, equipamento, dificuldade e fontes de cada exercício do catálogo.

Os dados de execução (instruções, cuidados, séries, repetições e descanso) ficam em dados.EXERCICIOS; aqui fica
o que serve para filtrar e explicar. As fontes citadas são as da pesquisa em docs/pesquisa.md: nenhuma afirma que
um exercício é "o melhor", só o que cada estudo comparou.
"""
from __future__ import annotations

from . import dados as D

GRUPOS = ["Glúteos", "Quadríceps", "Posteriores", "Panturrilhas", "Peitoral", "Costas", "Ombros", "Bíceps", "Tríceps",
          "Abdômen", "Adutores", "Cardio", "Mobilidade"]
GRUPOS_PRIORIZAVEIS = GRUPOS[:10]

EQUIPAMENTOS = {
    "maquinas": "Máquinas e polias",
    "halteres": "Halteres e banco",
    "barra": "Barra, anilhas e rack",
    "corpo": "Peso do corpo e colchonete",
    "cardio": "Esteira, bicicleta ou elíptico",
}
DIFICULDADES = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado"}

# Referências científicas (detalhes, limitações e endereços conferidos em docs/pesquisa.md).
REFERENCIAS = {
    "acsm2026": ("ACSM (2026). Position stand: prescrição de treinamento resistido para função muscular, hipertrofia e "
                 "desempenho em adultos saudáveis (revisão de 137 revisões sistemáticas). Med Sci Sports Exerc 58(3):512–545.",
                 "https://acsm.org/wp-content/uploads/2026/03/Resistance-Training-Position-Stand-infographic.pdf"),
    "currier2023": ("Currier BS et al. (2023). Prescrição de treino resistido para força e hipertrofia: revisão sistemática "
                    "e meta-análise em rede bayesiana. Br J Sports Med 57:1211–1220.",
                    "https://doi.org/10.1136/bjsports-2023-106807"),
    "schoenfeld2017": ("Schoenfeld BJ, Ogborn D, Krieger JW (2017). Relação dose-resposta entre volume semanal de treino "
                       "resistido e aumento de massa muscular: revisão sistemática e meta-análise. J Sports Sci 35:1073–1082.",
                       "https://doi.org/10.1080/02640414.2016.1210197"),
    "bmjsem2025": ("BMJ Open Sport & Exercise Medicine (2025). Exercício resistido durante a perda de peso por dieta em "
                   "pessoas com sobrepeso ou obesidade: revisão sistemática e meta-análise de 25 ensaios. 11(3):e002363.",
                   "https://doi.org/10.1136/bmjsem-2024-002363"),
    "oms2020": ("Bull FC et al. (2020). Diretrizes da OMS sobre atividade física e comportamento sedentário. "
                "Br J Sports Med 54:1451–1462.", "https://doi.org/10.1136/bjsports-2020-102955"),
    "plotkin2023": ("Plotkin DL et al. (2023). Hip thrust e agachamento produziram hipertrofia de glúteos semelhante em "
                    "9 semanas (pessoas sem treino prévio); o agachamento aumentou mais coxa e adutores. Front Physiol 14:1279170.",
                    "https://doi.org/10.3389/fphys.2023.1279170"),
    "barbalho2020": ("Barbalho M et al. (2020). Em mulheres treinadas, 12 semanas de agachamento aumentaram mais a espessura "
                     "de glúteos e quadríceps que o hip thrust (amostra pequena). Int J Sports Med 41(5):306–310.",
                     "https://doi.org/10.1055/a-1082-1126"),
    "kikuchi2017": ("Kikuchi N, Nakazato K (2017). Flexão de braços com carga equivalente e supino produziram ganhos "
                    "semelhantes de peitoral em 8 semanas (18 homens jovens). J Exerc Sci Fit.",
                    "https://doi.org/10.1016/j.jesf.2017.06.003"),
    "chaves2020": ("Chaves SFN et al. (2020). Supino inclinado aumentou mais a porção superior do peitoral que o reto; força "
                   "geral semelhante (47 homens sem treino). Int J Exerc Sci 13(6):859–872.",
                   "https://pmc.ncbi.nlm.nih.gov/articles/PMC7449336/"),
}

# id: (grupo principal, grupos secundários, equipamento (um ou vários, qualquer um serve), dificuldade, fontes)
_M = {
    'supino_maquina': ("Peitoral", ["Ombros", "Tríceps"], "maquinas", "iniciante", ["currier2023"]),
    'supino_inclinado': ("Peitoral", ["Ombros", "Tríceps"], "maquinas", "iniciante", ["chaves2020"]),
    'crucifixo_maquina': ("Peitoral", ["Ombros"], "maquinas", "iniciante", []),
    'crossover_polia': ("Peitoral", ["Ombros"], "maquinas", "intermediario", []),
    'supino_halteres': ("Peitoral", ["Ombros", "Tríceps"], "halteres", "intermediario", ["kikuchi2017"]),
    'supino_inclinado_halteres': ("Peitoral", ["Ombros", "Tríceps"], "halteres", "intermediario", ["chaves2020"]),
    'flexao_inclinada': ("Peitoral", ["Ombros", "Tríceps", "Abdômen"], "corpo", "iniciante", ["kikuchi2017"]),
    'flexao_bracos': ("Peitoral", ["Ombros", "Tríceps", "Abdômen"], "corpo", "intermediario", ["kikuchi2017"]),
    'remada_apoio': ("Costas", ["Bíceps", "Ombros"], "maquinas", "iniciante", []),
    'puxada_polia': ("Costas", ["Bíceps"], "maquinas", "iniciante", []),
    'remada_baixa': ("Costas", ["Bíceps", "Ombros"], "maquinas", "iniciante", []),
    'puxada_supinada': ("Costas", ["Bíceps"], "maquinas", "iniciante", []),
    'puxada_bracos_estendidos': ("Costas", [], "maquinas", "intermediario", []),
    'remada_alta_maquina': ("Costas", ["Bíceps"], "maquinas", "iniciante", []),
    'remada_halter': ("Costas", ["Bíceps", "Ombros"], "halteres", "iniciante", []),
    'desenvolvimento_maquina': ("Ombros", ["Tríceps"], "maquinas", "iniciante", []),
    'desenvolvimento_halteres': ("Ombros", ["Tríceps"], "halteres", "intermediario", []),
    'elevacao_lateral': ("Ombros", [], "halteres", "iniciante", []),
    'face_pull': ("Ombros", ["Costas"], "maquinas", "iniciante", []),
    'crucifixo_inverso': ("Ombros", ["Costas"], "maquinas", "iniciante", []),
    'rosca_sentado': ("Bíceps", [], "halteres", "iniciante", []),
    'rosca_scott': ("Bíceps", [], "maquinas", "iniciante", []),
    'rosca_martelo': ("Bíceps", [], "halteres", "iniciante", []),
    'rosca_maquina': ("Bíceps", [], "maquinas", "iniciante", []),
    'rosca_inclinada': ("Bíceps", [], "halteres", "intermediario", []),
    'triceps_polia': ("Tríceps", [], "maquinas", "iniciante", []),
    'triceps_frances': ("Tríceps", [], "halteres", "intermediario", []),
    'triceps_maquina': ("Tríceps", [], "maquinas", "iniciante", []),
    'triceps_corda_acima': ("Tríceps", [], "maquinas", "intermediario", []),
    'leg_press': ("Quadríceps", ["Glúteos", "Posteriores"], "maquinas", "iniciante", []),
    'hack_maquina': ("Quadríceps", ["Glúteos", "Adutores"], "maquinas", "intermediario", []),
    'cadeira_extensora': ("Quadríceps", [], "maquinas", "iniciante", []),
    'agachamento_goblet': ("Quadríceps", ["Glúteos", "Adutores"], "halteres", "iniciante", []),
    'agachamento_peso_corpo': ("Quadríceps", ["Glúteos", "Adutores"], "corpo", "iniciante", []),
    'agachamento_livre': ("Quadríceps", ["Glúteos", "Adutores", "Posteriores"], "barra", "avancado",
                          ["plotkin2023", "barbalho2020"]),
    'avanco_estatico': ("Quadríceps", ["Glúteos"], ("corpo", "halteres"), "iniciante", []),
    'afundo_reverso': ("Glúteos", ["Quadríceps", "Adutores"], ("halteres", "corpo"), "intermediario", []),
    'step_up': ("Glúteos", ["Quadríceps"], ("halteres", "corpo"), "intermediario", []),
    'hip_thrust': ("Glúteos", ["Posteriores", "Quadríceps"], ("barra", "maquinas"), "intermediario",
                   ["plotkin2023", "barbalho2020"]),
    'ponte_gluteo': ("Glúteos", ["Posteriores"], "corpo", "iniciante", []),
    'extensao_quadril_cabo': ("Glúteos", ["Posteriores"], "maquinas", "iniciante", []),
    'cadeira_abdutora': ("Glúteos", [], "maquinas", "iniciante", []),
    'cadeira_adutora': ("Adutores", [], "maquinas", "iniciante", []),
    'stiff_halteres': ("Posteriores", ["Glúteos"], "halteres", "intermediario", []),
    'terra_romeno': ("Posteriores", ["Glúteos"], "barra", "avancado", []),
    'cadeira_flexora': ("Posteriores", [], "maquinas", "iniciante", []),
    'mesa_flexora': ("Posteriores", ["Panturrilhas"], "maquinas", "iniciante", []),
    'panturrilha_sentado': ("Panturrilhas", [], "maquinas", "iniciante", []),
    'panturrilha_em_pe': ("Panturrilhas", [], "maquinas", "iniciante", []),
    'abdominal_maquina': ("Abdômen", [], "maquinas", "iniciante", []),
    'abdominal_polia': ("Abdômen", [], "maquinas", "intermediario", []),
    'pallof': ("Abdômen", [], "maquinas", "iniciante", []),
    'prancha': ("Abdômen", ["Ombros"], "corpo", "iniciante", []),
    'esteira_caminhada': ("Cardio", [], "cardio", "iniciante", ["oms2020"]),
    'esteira_inclinada': ("Cardio", ["Glúteos"], "cardio", "iniciante", ["oms2020"]),
    'cardio_longo': ("Cardio", [], "cardio", "iniciante", ["oms2020"]),
    'bicicleta': ("Cardio", ["Quadríceps"], "cardio", "iniciante", ["oms2020"]),
    'bike_reclinada': ("Cardio", ["Quadríceps"], "cardio", "iniciante", ["oms2020"]),
    'eliptico': ("Cardio", [], "cardio", "iniciante", ["oms2020"]),
    'ergometro_bracos': ("Cardio", ["Ombros"], "cardio", "iniciante", ["oms2020"]),
    'caminhada_livre': ("Cardio", [], tuple(EQUIPAMENTOS), "iniciante", ["oms2020"]),  # não precisa de nada
    'respiracao': ("Mobilidade", [], "corpo", "iniciante", []),
    'mobilidade_ombros': ("Mobilidade", ["Ombros"], "corpo", "iniciante", []),
}


def meta(ex_id: str) -> dict:
    g, sec, eq, dif, fontes = _M[ex_id]
    return {"grupo": g, "secundarios": list(sec), "equipamentos": [eq] if isinstance(eq, str) else list(eq),
            "dificuldade": dif, "fontes": list(fontes)}


def grupo(ex_id: str) -> str:
    return _M[ex_id][0] if ex_id in _M else ""


def objetivos_do_exercicio(ex_id: str) -> list[str]:
    """Objetivos para os quais o exercício costuma entrar no plano (derivado do grupo, não de uma lista à mão)."""
    m = meta(ex_id)
    if m["grupo"] == "Mobilidade":
        return []
    if m["grupo"] == "Cardio":
        return ["emagrecimento", "condicionamento", "completo"]
    out = ["hipertrofia", "completo", "emagrecimento"]  # treino resistido preserva massa magra durante a perda de peso
    if "Glúteos" in [m["grupo"]] + m["secundarios"]:
        out.append("gluteos")
    if m["grupo"] == "Peitoral":
        out.append("peitoral")
    return out


def por_grupo(g: str) -> list[str]:
    """Exercícios cujo grupo principal é g, na ordem do catálogo."""
    return [x for x in D.EXERCICIOS if grupo(x) == g]
