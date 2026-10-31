"""Catálogos de base legal e finalidade (LGPD, Lei nº 13.709/2018).

A base legal é escolhida e registrada ANTES de cada consulta. O catálogo não substitui a
avaliação do advogado responsável: a hipótese deve corresponder ao caso concreto.
Conferir a redação vigente em https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm
"""

from __future__ import annotations

BASES_LEGAIS: dict[str, str] = {
    "art7_vi": "Art. 7º, VI — exercício regular de direitos em processo judicial, administrativo ou arbitral",
    "art7_ii": "Art. 7º, II — cumprimento de obrigação legal ou regulatória pelo controlador",
    "art7_v": "Art. 7º, V — execução de contrato ou procedimentos preliminares, a pedido do titular",
    "art7_x": "Art. 7º, X — proteção do crédito",
    "art7_ix": "Art. 7º, IX — legítimo interesse (exige avaliação documentada; art. 10)",
    "art7_i": "Art. 7º, I — consentimento do titular (somente com consentimento registrado)",
}

# Base legal mais usual para consultas vinculadas a processo; aparece primeiro no formulário.
BASE_LEGAL_PADRAO = "art7_vi"

FINALIDADES: dict[str, str] = {
    "qualificacao_parte": "Qualificação ou confirmação de identidade de parte",
    "localizacao_citacao": "Subsídio para citação ou intimação",
    "pesquisa_patrimonial": "Pesquisa patrimonial em execução ou cumprimento de sentença",
    "situacao_cadastral": "Verificação de situação cadastral",
    "instrucao_defesa": "Instrução de defesa ou de manifestação processual",
    "due_diligence": "Due diligence contratual ou societária",
    "outra": "Outra (descrever na justificativa)",
}

JUSTIFICATIVA_MIN = 30

DECLARACAO = (
    "Declaro que esta consulta é necessária à finalidade indicada, está vinculada à demanda "
    "selecionada e que os dados obtidos não serão usados para finalidade incompatível "
    "(LGPD, art. 6º, I a III)."
)
