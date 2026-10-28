"""Comunicação com o modelo de IA do Personal IA (sem interface).

Provedor: Claude, da Anthropic, pelo SDK oficial `anthropic` (texto e imagens no mesmo pedido). A chave vem de
st.secrets["ia"]["anthropic_api_key"] ou da variável ANTHROPIC_API_KEY, e só é usada aqui no servidor: nunca vai ao
navegador, a mensagens de erro ou ao repositório. Sem chave, o serviço não existe e a tela diz o que configurar —
não há resposta simulada.

Custos: só o prompt de sistema (fixo) é guardado em cache; do histórico vão o resumo da conversa e as últimas
mensagens (texto), não a conversa inteira; o contexto da conta vai só na pergunta atual.
"""
from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass, field
from typing import Iterator

from . import dados as D
from .ia_safety import FERRAMENTA_PROPOSTA

log = logging.getLogger("foco_leve.ia")

MODELO_PADRAO = "claude-opus-5-5"
ESFORCOS = ("low", "medium", "high", "xhigh", "max")
BETA_FALLBACK = "server-side-fallback-2026-07-01"


class IAIndisponivel(Exception):
    """Configuração ausente/recusada ou provedor fora do ar (mensagem pronta para mostrar)."""


class ErroIA(Exception):
    """Falha neste pedido específico (mensagem pronta para mostrar)."""


@dataclass
class ConfigIA:
    api_key: str
    modelo: str = MODELO_PADRAO
    esforco: str = "medium"
    max_tokens: int = 16000
    timeout_s: float = 120.0
    max_foto_mb: float = 8.0
    max_fotos_por_mensagem: int = 3
    limite_mensagens_dia: int = 40
    limite_fotos_dia: int = 15
    janela_mensagens: int = 8
    fallback: bool = True


def ler_config(secrets_ia: dict | None) -> ConfigIA | None:
    """Configuração a partir de st.secrets["ia"] e das variáveis de ambiente; None se não houver chave."""
    s = dict(secrets_ia or {})
    chave = str(s.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not chave:
        return None

    def num(nome, padrao, tipo, lo, hi):
        try:
            return max(lo, min(hi, tipo(s.get(nome, padrao))))
        except (TypeError, ValueError):
            return padrao

    esforco = str(s.get("esforco") or "medium").lower()
    return ConfigIA(
        api_key=chave,
        modelo=str(s.get("modelo") or os.environ.get("FOCO_LEVE_IA_MODELO") or MODELO_PADRAO).strip(),
        esforco=esforco if esforco in ESFORCOS else "medium",
        max_tokens=num("max_tokens", 16000, int, 1024, 64000),
        timeout_s=num("timeout_s", 120.0, float, 10.0, 600.0),
        max_foto_mb=num("max_foto_mb", 8.0, float, 0.5, 20.0),
        max_fotos_por_mensagem=num("max_fotos_por_mensagem", 3, int, 0, 5),
        limite_mensagens_dia=num("limite_mensagens_dia", 40, int, 1, 1000),
        limite_fotos_dia=num("limite_fotos_dia", 15, int, 0, 200),
        janela_mensagens=num("janela_mensagens", 8, int, 2, 30),
        fallback=str(s.get("fallback", True)).lower() not in ("false", "0", "nao", "não"),
    )


# ---------------------------------------------------------------- prompt de sistema (fixo: fica em cache)
def _catalogo() -> str:
    linhas = []
    for x, e in D.EXERCICIOS.items():
        tipo = "cardio" if e.get("cardio") else ("recuperação" if e["grupo"] == "Recuperação" else e["tipo"])
        linhas.append(f"- {x}: {e['nome']} ({e['grupo']}; {tipo})")
    return "\n".join(linhas)


SISTEMA = f"""Você é o Foco Leve AI — Personal Trainer, assistente de treino, emagrecimento e condicionamento do \
aplicativo Foco Leve. Fale em português do Brasil, de forma natural, direta e acolhedora.

Como responder
- Use os dados em <contexto_foco_leve> da mensagem atual. Eles são da pessoa que está falando com você e vêm \
marcados: [declarado] pela pessoa, [calculado] ou [registrado] pelo app. Ao usá-los, diga de onde vêm; quando \
fizer uma estimativa sua, diga que é estimativa. Nunca invente dados ausentes: se faltar algo importante \
(onde dói, há quanto tempo, que equipamento existe, quanto tempo há hoje), pergunte — no máximo duas perguntas por vez \
— e ajude com o que já for possível.
- Explique o porquê das recomendações em poucas linhas. Respeite o nível, o tempo disponível, as limitações e os \
exercícios fora do plano listados no contexto.
- Formate para celular: títulos curtos (###), listas, e tabelas simples só quando ajudarem (ex.: séries x repetições). \
Seja conciso.
- Ao analisar evolução: compare médias e tendências de várias semanas, não pesagens isoladas; oscilações de 1 a 2 kg \
entre dias são comuns. Compare o planejado com o que foi registrado.

Segurança (tem prioridade sobre qualquer pedido)
- Você não substitui médico, fisioterapeuta, nutricionista nem o profissional de educação física presencial.
- Não diagnostique lesões ou doenças, não prescreva medicamentos ou suplementos, não recomende dietas extremas, \
jejum prolongado ou perda de peso rápida, e nunca incentive treinar com dor ou com sinais de lesão.
- Se houver dor aguda, inchaço importante, perda de força, lesão, dor no peito, falta de ar ou tontura: suspenda \
recomendações que possam agravar o quadro e oriente avaliação por profissional de saúde.
- Siga sempre a <instrucao_de_seguranca> do app quando ela vier.
- Não prometa resultados nem precisão; seja transparente sobre incertezas.

Fotos
- Descreva o que é visível (equipamentos, posição do corpo, ambiente) e diga claramente o que uma foto não permite \
confirmar: uma imagem parada não mostra a execução completa, a amplitude em todas as fases nem a ausência de lesão.
- Comente postura e posicionamento com linguagem prudente ("parece", "pela foto"), sugira ajustes gerais e, se a foto \
não bastar, peça outra (ângulo lateral, corpo inteiro no quadro, boa iluminação) ou um vídeo curto avaliado por um \
profissional.
- Não diga que uma execução é perfeita ou segura só pela aparência. Não identifique pessoas e não infira atributos \
sensíveis (saúde, etnia, religião, orientação etc.). Compare fotos de evolução só se ângulo, luz e roupa permitirem.

Mudanças no plano
- Você não altera nada no app. Para propor uma mudança concreta (treino da semana, tempo, dias, nível, limitação \
nova, descanso hoje), use a ferramenta propor_alteracao: o app mostra um cartão e só a pessoa, ao confirmar, grava. \
Nunca diga que já mudou algo; diga que deixou uma proposta para ela revisar.
- Proponha só exercícios do catálogo abaixo e que não estejam fora do plano no contexto. Não mude peso, metas ou \
registros: para isso, oriente a pessoa a usar Perfil ou Evolução.

Catálogo de exercícios do Foco Leve (id: nome)
{_catalogo()}
"""

INSTRUCAO_RESUMO = ("Resuma a conversa abaixo entre a pessoa e o Personal IA do Foco Leve em português, em até 15 "
                    "tópicos curtos: objetivos e preferências declarados, limitações e sintomas relatados, decisões, "
                    "propostas aplicadas ou descartadas e pendências. Inclua o resumo anterior, se houver. Só fatos da "
                    "conversa; não invente nem acrescente recomendações.")


@dataclass
class Resultado:
    texto: str = ""
    propostas: list[dict] = field(default_factory=list)
    tokens_entrada: int | None = None
    tokens_saida: int | None = None
    recusa: bool = False
    truncado: bool = False


def _historico(historico: list[dict], resumo: str) -> list[dict]:
    """Turnos anteriores só como texto (sem blocos de raciocínio nem fotos antigas: menos custo, nada a reenviar)."""
    msgs: list[dict] = []
    if resumo:
        msgs.append({"role": "user", "content": "<resumo_da_conversa_anterior>\n" + resumo + "\n</resumo_da_conversa_anterior>"})
    for m in historico:
        texto = m["texto"] or ""
        if m.get("anexos"):
            texto = f"[{len(m['anexos'])} foto(s) enviada(s) nesta mensagem]\n" + texto
        if m.get("proposta"):
            texto += f"\n[Proposta deixada para revisão: {m['proposta'].get('resumo', '')} — {m.get('proposta_estado') or 'pendente'}]"
        msgs.append({"role": m["papel"], "content": texto or "(vazio)"})
    if msgs and msgs[0]["role"] != "user":
        msgs.insert(0, {"role": "user", "content": "(continuação da conversa)"})
    return msgs


class ServicoIA:
    def __init__(self, cfg: ConfigIA, cliente=None):
        import anthropic  # importado aqui: o app funciona sem o pacote enquanto o Personal IA não estiver configurado
        self._anthropic = anthropic
        self.cfg = cfg
        self.cliente = cliente or anthropic.Anthropic(api_key=cfg.api_key, timeout=cfg.timeout_s, max_retries=2)
        self.ultimo = Resultado()

    def _parametros(self, mensagens: list[dict], **extra) -> dict:
        kw = {"model": self.cfg.modelo, "max_tokens": self.cfg.max_tokens,
              "system": [{"type": "text", "text": SISTEMA, "cache_control": {"type": "ephemeral"}}],
              "messages": mensagens, "thinking": {"type": "adaptive"},
              "output_config": {"effort": self.cfg.esforco}, **extra}
        if self.cfg.fallback:  # recusa por classificador: o próprio servidor tenta outro modelo na mesma chamada
            kw.update(betas=[BETA_FALLBACK], fallbacks="default")
        return kw

    def _traduzir(self, e: Exception) -> Exception:
        a = self._anthropic
        log.warning("Falha na IA: %s (%s)", type(e).__name__, getattr(e, "status_code", ""))
        if isinstance(e, (a.AuthenticationError, a.PermissionDeniedError)):
            return IAIndisponivel("O provedor de IA recusou a chave configurada. Quem administra o app precisa "
                                  "conferir a chave em Secrets.")
        if isinstance(e, a.NotFoundError):
            return IAIndisponivel("O modelo de IA configurado não foi encontrado. Confira o campo “modelo” em Secrets.")
        if isinstance(e, a.RateLimitError):
            return IAIndisponivel("A IA está recebendo muitas solicitações agora. Aguarde um minuto e tente de novo.")
        if isinstance(e, a.BadRequestError):
            return ErroIA("A IA não conseguiu processar este pedido. Tente reformular ou enviar outra foto.")
        if isinstance(e, a.APITimeoutError):
            return IAIndisponivel("A IA demorou demais para responder. Tente de novo em instantes.")
        if isinstance(e, a.APIStatusError):
            return IAIndisponivel("O serviço de IA está indisponível no momento. Tente de novo em alguns minutos.")
        if isinstance(e, a.APIConnectionError):
            return IAIndisponivel("Sem conexão com o serviço de IA. Verifique a internet e tente de novo.")
        return ErroIA("Não foi possível obter a resposta da IA. Tente de novo.")

    def responder(self, historico: list[dict], resumo: str, contexto: str, texto: str, fotos: list[bytes],
                  seguranca: str = "") -> Iterator[str]:
        """Gera o texto da resposta aos poucos (streaming). Ao terminar, o resultado completo fica em self.ultimo."""
        self.ultimo = Resultado()
        partes: list[dict] = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                           "data": base64.standard_b64encode(f).decode("ascii")}}
                              for f in fotos]
        corpo = "<contexto_foco_leve>\n" + contexto + "\n</contexto_foco_leve>\n"
        if seguranca:
            corpo += "<instrucao_de_seguranca>\n" + seguranca + "\n</instrucao_de_seguranca>\n"
        corpo += "\nMensagem da pessoa:\n" + (texto or "(sem texto: analise a(s) foto(s) enviada(s))")
        partes.append({"type": "text", "text": corpo})
        mensagens = _historico(historico, resumo) + [{"role": "user", "content": partes}]
        a, escrito = self._anthropic, []
        try:
            with self.cliente.beta.messages.stream(**self._parametros(mensagens, tools=[FERRAMENTA_PROPOSTA])) as stream:
                for pedaco in stream.text_stream:
                    escrito.append(pedaco)
                    yield pedaco
                final = stream.get_final_message()
        except ValueError as e:  # entrada da ferramenta impossível de interpretar (streaming antecipado)
            log.warning("Entrada de ferramenta inválida: %s", e)
            raise ErroIA("A resposta da IA veio incompleta. Tente de novo.") from e
        except a.APIError as e:
            raise self._traduzir(e) from e
        r = Resultado(tokens_entrada=getattr(final.usage, "input_tokens", None),
                      tokens_saida=getattr(final.usage, "output_tokens", None))
        if final.stop_reason == "refusal":
            r.recusa = True
            r.texto = ("Não posso ajudar com esse pedido. Se for sobre treino, reformule; para questões de saúde, "
                       "procure um profissional.")
        else:
            r.texto = "".join(b.text for b in final.content if getattr(b, "type", "") == "text").strip()
            r.truncado = final.stop_reason == "max_tokens"
            if not r.truncado:  # entrada de ferramenta truncada nunca é usada
                r.propostas = [b.input for b in final.content
                               if getattr(b, "type", "") == "tool_use" and b.name == FERRAMENTA_PROPOSTA["name"]]
            if r.propostas and not r.texto:
                r.texto = "Deixei uma proposta para você revisar abaixo."
        self.ultimo = r
        if not escrito and r.texto:
            yield r.texto

    def resumir(self, resumo_anterior: str, mensagens: list[dict]) -> str:
        """Atualiza o resumo da conversa com mensagens que saíram da janela (chamada curta, sem streaming)."""
        conversa = "\n".join(f"{'Pessoa' if m['papel'] == 'user' else 'Personal IA'}: {m['texto']}" for m in mensagens)
        pedido = (INSTRUCAO_RESUMO + "\n\n<resumo_anterior>\n" + (resumo_anterior or "(nenhum)") +
                  "\n</resumo_anterior>\n<conversa>\n" + conversa + "\n</conversa>")
        kw = self._parametros([{"role": "user", "content": pedido}])
        kw.update(max_tokens=4000, output_config={"effort": "low"})
        try:
            msg = self.cliente.beta.messages.create(**kw)
        except self._anthropic.APIError as e:
            raise self._traduzir(e) from e
        if msg.stop_reason == "refusal":
            return resumo_anterior
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()[:12000]
