"""Regras de segurança do Personal IA (sem interface), aplicadas pelo app e não pelo modelo.

- Sinais de alerta no texto: urgência (dor no peito, falta de ar, desmaio...) tem resposta fixa, sem chamar a IA;
  dor forte, inchaço, perda de força ou lesão viram instrução obrigatória para a resposta e um aviso na tela.
- Mensagens vazias ou longas demais são recusadas antes de qualquer custo.
- Toda proposta de mudança no plano é validada aqui: só campos e valores permitidos, só exercícios do catálogo e
  liberados para a pessoa (as mesmas regras de bloqueio do plano). Nada é gravado sem o clique de confirmação.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from . import dados as D
from . import plano as P
from . import regras as R

TEXTO_MAXIMO = 4000
TREINOS_EDITAVEIS = ("A", "B", "LA", "LB", "FULL", "CARDIO")
NIVEIS = ("Iniciante", "Intermediário", "Avançado")

_URGENTE = ("dor no peito", "aperto no peito", "pressao no peito", "falta de ar", "nao consigo respirar",
            "dificuldade para respirar", "desmai", "apaguei", "palpitac", "coracao disparado", "visao turva",
            "formigamento no braco", "boca torta", "fala enrolada", "confusao mental")
_LESAO = ("dor aguda", "dor forte", "dor intensa", "dor muito forte", "inchac", "inchad", "perda de forca",
          "perdi a forca", "perdi forca", "sem forca na", "estalo", "estalou", "lesao", "lesion", "torci", "torcao",
          "machuquei", "nao consigo apoiar", "nao consigo pisar", "sangr", "desloc", "fratur", "rompi", "ruptura",
          "distensao", "estirei", "estiramento", "hernia", "travou", "travei", "dormencia", "formigamento")
_DESCONFORTO = ("dor", "doendo", "doi ", "doi.", "doi,", "dolorid", "incomod", "fisgada", "pontada", "desconforto")

RESPOSTA_URGENTE = (
    "### Isso pode ser urgente\n"
    "Você descreveu um sinal que precisa de avaliação médica **agora**, não de ajuste de treino.\n\n"
    "- **Pare qualquer exercício** e fique em repouso, sentado ou deitado.\n"
    "- Se for **dor ou aperto no peito, falta de ar, desmaio, fraqueza de um lado do corpo, fala enrolada ou "
    "palpitação forte**, ligue para o **SAMU (192)** ou vá a um pronto-socorro.\n"
    "- Não volte a treinar antes de ser avaliado por um profissional de saúde.\n\n"
    "_Esta orientação é automática do Foco Leve e não passa pela IA. Ela não substitui atendimento médico._")


def _normalizar(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return " " + "".join(c for c in t if unicodedata.category(c) != "Mn") + " "


@dataclass
class Alerta:
    nivel: str | None = None  # "urgente", "lesao", "desconforto" ou None
    termos: list[str] = field(default_factory=list)


def classificar(texto: str) -> Alerta:
    t = _normalizar(texto)
    for nivel, lista in (("urgente", _URGENTE), ("lesao", _LESAO), ("desconforto", _DESCONFORTO)):
        achados = [x.strip(" .,") for x in lista if x in t]
        if achados:
            return Alerta(nivel, achados)
    return Alerta()


def instrucao_de_seguranca(alerta: Alerta, S: dict) -> str:
    """Instrução do app para a resposta da IA, quando há sintoma no texto ou registrado no Foco Leve."""
    partes = []
    if alerta.nivel == "lesao":
        partes.append("A pessoa relatou possível lesão ou sintoma importante (" + ", ".join(alerta.termos) + "). "
                      "Não sugira exercícios que carreguem a região afetada nem 'treinar com dor'; suspenda a progressão; "
                      "oriente avaliação por profissional de saúde antes de retomar; ofereça só alternativas que não "
                      "envolvam a região e diga que devem ser interrompidas se a dor aumentar. Não diagnostique.")
    elif alerta.nivel == "desconforto":
        partes.append("A pessoa relatou dor ou desconforto (" + ", ".join(alerta.termos) + "). Pergunte onde, desde "
                      "quando, a intensidade (0 a 10) e se há inchaço ou perda de força antes de propor exercícios "
                      "para a região; enquanto isso, prefira alternativas que não doam e não diagnostique.")
    if R.alerta_vermelho(S):
        partes.append("O Foco Leve tem sinais de alerta registrados na avaliação ou no check-in de hoje: recomende "
                      "não treinar e procurar avaliação médica.")
    elif R.sintomas(S) or R.lesao_em_recuperacao(S):
        partes.append("O Foco Leve tem dor, inchaço, lesão em recuperação ou liberação pendente registrados: "
                      "mantenha só exercícios liberados pelo plano e intensidade leve.")
    return " ".join(partes)


class MensagemInvalida(ValueError):
    """Mensagem que não pode ser enviada (pronta para mostrar)."""


def validar_texto(texto: str, tem_foto: bool = False) -> str:
    t = (texto or "").strip()
    if not t and not tem_foto:
        raise MensagemInvalida("Escreva uma mensagem ou anexe uma foto.")
    if len(t) > TEXTO_MAXIMO:
        raise MensagemInvalida(f"A mensagem tem {len(t)} caracteres; o limite é {TEXTO_MAXIMO}. Resuma ou divida em partes.")
    return t


# ---------------------------------------------------------------- propostas de alteração (ferramenta da IA)
FERRAMENTA_PROPOSTA = {
    "name": "propor_alteracao",
    "description": (
        "Registra uma proposta concreta de mudança no plano do Foco Leve para a pessoa revisar. NÃO altera nada: o app "
        "mostra um cartão com botões Aplicar/Descartar, e só o clique da pessoa grava. Use quando a pessoa pedir ou "
        "aceitar um ajuste concreto: montar ou trocar os exercícios de musculação de um treino desta semana, mudar "
        "tempo por sessão, dias por semana ou nível, registrar uma limitação nova, ou trocar o treino de hoje por "
        "descanso ou recuperação. Use só ids de exercícios do catálogo do sistema. Explique a proposta no texto."),
    "eager_input_streaming": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["tipo", "resumo"],
        "properties": {
            "tipo": {"type": "string", "enum": ["treino_da_semana", "perfil", "hoje"]},
            "resumo": {"type": "string", "description": "Uma frase dizendo o que muda, para o cartão de confirmação."},
            "treino": {"type": "string", "enum": list(TREINOS_EDITAVEIS),
                       "description": "tipo=treino_da_semana: qual treino da agenda desta semana muda."},
            "exercicios": {"type": "array", "items": {"type": "string"}, "maxItems": 10,
                           "description": "tipo=treino_da_semana: ids de musculação, na ordem."},
            "cardio": {"type": "string", "description": "tipo=treino_da_semana: id da modalidade de cardio (opcional)."},
            "tempo_max": {"type": "integer", "minimum": 30, "maximum": 180, "description": "tipo=perfil: minutos por sessão."},
            "dias": {"type": "integer", "minimum": 1, "maximum": 7, "description": "tipo=perfil: dias de treino por semana."},
            "nivel": {"type": "string", "enum": list(NIVEIS), "description": "tipo=perfil."},
            "limitacao": {"type": "string", "maxLength": 300,
                          "description": "tipo=perfil: limitação nova a ACRESCENTAR (nunca remove as existentes)."},
            "hoje": {"type": "string", "enum": ["descanso", "recuperacao"],
                     "description": "tipo=hoje: trocar o treino de hoje por descanso ou recuperação leve."},
        },
    },
}


def validar_proposta(entrada, S: dict, semana: int) -> tuple[dict | None, list[str]]:
    """Confere a proposta da IA contra o esquema e contra a segurança do plano. Devolve (proposta limpa, avisos)."""
    if not isinstance(entrada, dict):
        return None, ["Proposta em formato inválido."]
    tipo = entrada.get("tipo")
    resumo = str(entrada.get("resumo") or "").strip()[:300]
    if tipo not in ("treino_da_semana", "perfil", "hoje") or not resumo:
        return None, ["Proposta sem tipo ou sem resumo."]
    avisos: list[str] = []
    out: dict = {"tipo": tipo, "resumo": resumo, "semana": semana}
    if tipo == "treino_da_semana":
        wk = entrada.get("treino")
        if wk not in TREINOS_EDITAVEIS:
            return None, ["Treino da proposta não existe."]
        ex = []
        for x in entrada.get("exercicios") or []:
            e = D.EXERCICIOS.get(x)
            if not e or e["tipo"] != "carga" or e.get("cardio") or e["grupo"] == "Recuperação":
                avisos.append(f"“{x}” não é um exercício de musculação do catálogo e foi ignorado.")
                continue
            m = P.motivo_bloqueio(S, x, semana)
            if m:
                avisos.append(f"{R.nome_ex(x)} ficou de fora: {m}")
                continue
            if x not in ex:
                ex.append(x)
        if not ex:
            return None, avisos + ["Nenhum exercício liberado sobrou na proposta."]
        out.update({"treino": wk, "exercicios": ex[:10]})
        c = entrada.get("cardio")
        if c:
            if c in D.CARDIO_TODOS and not P.motivo_bloqueio(S, c, semana):
                out["cardio"] = c
            else:
                avisos.append(f"Cardio “{c}” não liberado; fica o do plano.")
    elif tipo == "perfil":
        mud = {}
        if isinstance(entrada.get("tempo_max"), int) and 30 <= entrada["tempo_max"] <= 180:
            mud["tempoMax"] = entrada["tempo_max"]
        if isinstance(entrada.get("dias"), int) and 1 <= entrada["dias"] <= 7:
            mud["dias"] = entrada["dias"]
        if entrada.get("nivel") in NIVEIS:
            mud["nivel"] = entrada["nivel"]
        lim = re.sub(r"\s+", " ", str(entrada.get("limitacao") or "")).strip()[:300]
        if lim:
            mud["limitacao_nova"] = lim
        if not mud:
            return None, ["A proposta de perfil não tem nenhuma mudança válida."]
        out["mudancas"] = mud
    else:
        if entrada.get("hoje") not in ("descanso", "recuperacao"):
            return None, ["A proposta para hoje precisa ser descanso ou recuperação."]
        out["hoje"] = entrada["hoje"]
    return out, avisos


def descrever(prop: dict) -> list[str]:
    """Linhas legíveis do que a proposta muda (para o cartão de confirmação)."""
    if prop["tipo"] == "treino_da_semana":
        linhas = [f"{D.TREINOS[prop['treino']]['nome']} — semana {prop['semana']}:"]
        linhas += [f"• {R.nome_ex(x)}" for x in prop["exercicios"]]
        if prop.get("cardio"):
            linhas.append(f"• Cardio: {R.nome_ex(prop['cardio'])}")
        return linhas
    if prop["tipo"] == "perfil":
        m, rot = prop["mudancas"], []
        if "tempoMax" in m:
            rot.append(f"Tempo máximo por sessão: {m['tempoMax']} min")
        if "dias" in m:
            rot.append(f"Dias de treino por semana: {m['dias']} (a agenda é refeita)")
        if "nivel" in m:
            rot.append(f"Nível: {m['nivel']}")
        if "limitacao_nova" in m:
            rot.append(f"Acrescentar às limitações: “{m['limitacao_nova']}”")
        return rot
    return ["Hoje: " + ("dia de descanso" if prop["hoje"] == "descanso" else "recuperação leve (mobilidade e alongamento)")]


def aplicar_proposta(prop: dict, S: dict, semana: int, hoje: str) -> list[str]:
    """Aplica uma proposta JÁ CONFIRMADA pela pessoa. Valida de novo (o estado pode ter mudado). Devolve avisos."""
    entrada = {"tipo": prop["tipo"], "resumo": prop["resumo"], "treino": prop.get("treino"),
               "exercicios": prop.get("exercicios"), "cardio": prop.get("cardio"), "hoje": prop.get("hoje")}
    if prop["tipo"] == "perfil":
        m = prop.get("mudancas") or {}
        entrada.update({"tempo_max": m.get("tempoMax"), "dias": m.get("dias"), "nivel": m.get("nivel"),
                        "limitacao": m.get("limitacao_nova")})
    limpa, avisos = validar_proposta(entrada, S, semana)
    if not limpa:
        raise ValueError(" ".join(avisos) or "A proposta não é mais válida.")
    if limpa["tipo"] == "treino_da_semana":
        S.setdefault("ajustes", {})[f"{semana}|{limpa['treino']}"] = {
            "ex": limpa["exercicios"], "cardio": limpa.get("cardio"), "presc": {}}
    elif limpa["tipo"] == "perfil":
        m = dict(limpa["mudancas"])
        nova = m.pop("limitacao_nova", None)
        if nova:
            atual = str(S["profile"].get("limitacao") or "").strip()
            m["limitacao"] = (atual + "; " if atual else "") + nova
        P.atualizar_perfil(S, m)
    else:
        S["dayOverride"][hoje] = "OFF" if limpa["hoje"] == "descanso" else "REC"
    return avisos
