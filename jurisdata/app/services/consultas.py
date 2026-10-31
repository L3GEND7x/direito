"""Fluxo de consulta: regras de negócio, aprovação, execução, visualização e retenção."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import audit, lgpd
from ..connectors.base import TIPOS_CONSULTA, ErroConector, tipo_e_cpf
from ..contexto import Contexto
from ..models import Consulta, Perfil, Processo, StatusConsulta, Usuario, agora, como_utc
from ..security import mascarar_cpfs_em_texto, mascarar_documento
from ..validators import ValorInvalido, normalizar_cnpj, normalizar_cpf, validar_nascimento

log = logging.getLogger("jurisdata.consultas")


class ErroRegra(Exception):
    """Violação de regra de negócio ou de permissão; mensagem segura para exibir."""


PODE_SOLICITAR = {Perfil.ADVOGADO, Perfil.ASSISTENTE}


def pode_ver_resultado(usuario: Usuario, consulta: Consulta) -> bool:
    if usuario.perfil == Perfil.ADVOGADO:
        return True
    if usuario.perfil == Perfil.ASSISTENTE:
        return consulta.solicitante_id == usuario.id
    return False  # administrador e auditor veem só metadados


def pode_ver_metadados(usuario: Usuario, consulta: Consulta) -> bool:
    if usuario.perfil in (Perfil.ADVOGADO, Perfil.AUDITOR):
        return True
    return usuario.perfil == Perfil.ASSISTENTE and consulta.solicitante_id == usuario.id


def consultas_nas_ultimas_24h(db: Session, usuario: Usuario) -> int:
    limite = agora() - timedelta(hours=24)
    return db.scalar(
        select(func.count(Consulta.id)).where(Consulta.solicitante_id == usuario.id, Consulta.solicitada_em >= limite)
    ) or 0


def solicitar(
    db: Session,
    ctx: Contexto,
    usuario: Usuario,
    *,
    tipo: str,
    fonte: str,
    documento: str,
    nascimento: str | None,
    processo_id: int | None,
    finalidade_tipo: str,
    justificativa: str,
    base_legal: str,
    declaracao: bool,
    ip: str | None = None,
) -> Consulta:
    if usuario.perfil not in PODE_SOLICITAR:
        raise ErroRegra("Seu perfil não permite realizar consultas.")
    if tipo not in TIPOS_CONSULTA or not ctx.registro.disponivel(tipo, fonte):
        raise ErroRegra("Tipo de consulta ou fonte indisponível neste ambiente.")
    try:
        if tipo_e_cpf(tipo):
            doc = normalizar_cpf(documento)
            nasc: date | None = validar_nascimento(nascimento or "")
        else:
            doc = normalizar_cnpj(documento)
            nasc = None
    except ValorInvalido as exc:
        raise ErroRegra(str(exc)) from exc

    processo = db.get(Processo, processo_id) if processo_id else None
    if processo is None:
        raise ErroRegra("Vincule a consulta a um processo ou demanda cadastrada.")
    if not processo.ativo:
        raise ErroRegra("O processo/demanda selecionado está encerrado.")
    if base_legal not in lgpd.BASES_LEGAIS:
        raise ErroRegra("Selecione a base legal (LGPD) aplicável.")
    if finalidade_tipo not in lgpd.FINALIDADES:
        raise ErroRegra("Selecione a finalidade da consulta.")
    justificativa = (justificativa or "").strip()
    if len(justificativa) < lgpd.JUSTIFICATIVA_MIN:
        raise ErroRegra(f"Descreva a justificativa concreta (mínimo de {lgpd.JUSTIFICATIVA_MIN} caracteres).")
    if not declaracao:
        raise ErroRegra("É necessário confirmar a declaração de finalidade.")

    doc_hash = ctx.cofre.hash_documento(doc)
    if consultas_nas_ultimas_24h(db, usuario) >= ctx.cfg.limite_diario_consultas:
        audit.registrar(
            db, "consulta_bloqueada", usuario, "processo", processo.id,
            {"motivo": "limite_diario", "limite": ctx.cfg.limite_diario_consultas, "documento_hash": doc_hash}, ip,
        )
        db.commit()
        raise ErroRegra(
            f"Limite de {ctx.cfg.limite_diario_consultas} consultas em 24 horas atingido. "
            "Consultas em volume exigem autorização do administrador."
        )

    consulta = Consulta(
        tipo=tipo,
        fonte=fonte,
        documento_cifrado=ctx.cofre.cifrar(doc),
        documento_mascarado=mascarar_documento(doc),
        documento_hash=doc_hash,
        nascimento_cifrado=ctx.cofre.cifrar(nasc.isoformat()) if nasc else None,
        processo_id=processo.id,
        finalidade=f"{lgpd.FINALIDADES[finalidade_tipo]} — {justificativa}",
        base_legal=base_legal,
        solicitante_id=usuario.id,
        status=StatusConsulta.PENDENTE,
        solicitada_em=agora(),
        expurgar_em=agora() + timedelta(days=ctx.cfg.retencao_dias),
    )
    db.add(consulta)
    db.flush()
    audit.registrar(
        db, "consulta_solicitada", usuario, "consulta", consulta.id,
        {
            "tipo": tipo,
            "fonte": fonte,
            "documento": consulta.documento_mascarado,
            "documento_hash": doc_hash,
            "processo_id": processo.id,
            "base_legal": base_legal,
            "finalidade": finalidade_tipo,
        },
        ip,
    )
    if usuario.perfil == Perfil.ASSISTENTE and ctx.cfg.assistente_exige_aprovacao:
        db.commit()
        return consulta
    return executar(db, ctx, consulta, usuario, ip)


def executar(db: Session, ctx: Contexto, consulta: Consulta, usuario: Usuario, ip: str | None = None) -> Consulta:
    doc = ctx.cofre.decifrar(consulta.documento_cifrado)
    nasc_iso = ctx.cofre.decifrar(consulta.nascimento_cifrado)
    nasc = date.fromisoformat(nasc_iso) if nasc_iso else None
    try:
        conector = ctx.registro.por_id(consulta.fonte)
        resultado = conector.consultar(consulta.tipo, doc, nasc)
    except ErroConector as exc:
        _falhou(db, consulta, usuario, ip, exc.codigo, str(exc))
        return consulta
    except Exception:  # noqa: BLE001 - nunca exibir dados antigos nem stack trace ao usuário
        log.exception("Erro inesperado no conector %s (consulta %s)", consulta.fonte, consulta.id)
        _falhou(db, consulta, usuario, ip, "erro_interno", "Erro interno ao consultar a fonte. A consulta não foi concluída.")
        return consulta

    consulta.status = StatusConsulta.CONCLUIDA
    consulta.executada_em = agora()
    consulta.ambiente_fonte = resultado.ambiente
    consulta.resultado_cifrado = ctx.cofre.cifrar_json(resultado.como_dict())
    consulta.erro = None
    audit.registrar(
        db, "consulta_executada", usuario, "consulta", consulta.id,
        {"fonte": consulta.fonte, "ambiente": resultado.ambiente, "documento_hash": consulta.documento_hash}, ip,
    )
    db.commit()
    return consulta


def _falhou(db: Session, consulta: Consulta, usuario: Usuario, ip: str | None, codigo: str, mensagem: str) -> None:
    consulta.status = StatusConsulta.FALHA
    consulta.executada_em = agora()
    consulta.erro = mensagem
    consulta.resultado_cifrado = None
    audit.registrar(
        db, "consulta_falhou", usuario, "consulta", consulta.id,
        {"fonte": consulta.fonte, "codigo": codigo, "documento_hash": consulta.documento_hash}, ip,
    )
    db.commit()


def aprovar(db: Session, ctx: Contexto, consulta: Consulta, advogado: Usuario, ip: str | None = None) -> Consulta:
    if advogado.perfil != Perfil.ADVOGADO:
        raise ErroRegra("Somente advogados aprovam consultas.")
    if consulta.status != StatusConsulta.PENDENTE:
        raise ErroRegra("Esta consulta não está aguardando aprovação.")
    if consulta.solicitante_id == advogado.id:
        raise ErroRegra("Quem solicitou não pode aprovar a própria consulta.")
    if not consulta.processo.ativo:
        raise ErroRegra("O processo/demanda foi encerrado; a consulta não pode ser aprovada.")
    consulta.aprovador_id = advogado.id
    audit.registrar(db, "consulta_aprovada", advogado, "consulta", consulta.id, {"documento_hash": consulta.documento_hash}, ip)
    return executar(db, ctx, consulta, advogado, ip)


def recusar(db: Session, consulta: Consulta, advogado: Usuario, motivo: str, ip: str | None = None) -> Consulta:
    if advogado.perfil != Perfil.ADVOGADO:
        raise ErroRegra("Somente advogados recusam consultas.")
    if consulta.status != StatusConsulta.PENDENTE:
        raise ErroRegra("Esta consulta não está aguardando aprovação.")
    motivo = (motivo or "").strip()
    if len(motivo) < 10:
        raise ErroRegra("Informe o motivo da recusa.")
    consulta.status = StatusConsulta.RECUSADA
    consulta.aprovador_id = advogado.id
    consulta.motivo_recusa = motivo
    consulta.documento_cifrado = None
    consulta.nascimento_cifrado = None
    audit.registrar(db, "consulta_recusada", advogado, "consulta", consulta.id, {}, ip)
    db.commit()
    return consulta


# --- Visualização ------------------------------------------------------------------------------

def mascarar_profundo(valor):
    if isinstance(valor, dict):
        return {k: mascarar_profundo(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [mascarar_profundo(v) for v in valor]
    if isinstance(valor, str):
        return mascarar_cpfs_em_texto(valor)
    return valor


def achatar(dados, prefixo: str = "") -> list[tuple[str, str]]:
    """Transforma o retorno da fonte (qualquer formato JSON) em linhas campo → valor."""
    linhas: list[tuple[str, str]] = []
    if isinstance(dados, dict):
        for k, v in dados.items():
            linhas += achatar(v, f"{prefixo}.{k}" if prefixo else str(k))
    elif isinstance(dados, list):
        if not dados:
            linhas.append((prefixo, "(vazio)"))
        for i, v in enumerate(dados, 1):
            linhas += achatar(v, f"{prefixo}[{i}]")
    else:
        linhas.append((prefixo, "" if dados is None else str(dados)))
    return linhas


def abrir_resultado(
    db: Session, ctx: Contexto, consulta: Consulta, usuario: Usuario, ip: str | None = None, integral: bool = False
) -> dict | None:
    """Decifra o resultado para exibição e registra o acesso. ``integral`` só para advogado."""
    if not pode_ver_resultado(usuario, consulta):
        raise ErroRegra("Seu perfil não permite ver o conteúdo desta consulta.")
    if consulta.status != StatusConsulta.CONCLUIDA or not consulta.resultado_cifrado:
        return None
    if integral and usuario.perfil != Perfil.ADVOGADO:
        raise ErroRegra("Somente advogados exportam o relatório integral.")
    resultado = ctx.cofre.decifrar_json(consulta.resultado_cifrado) or {}
    if not integral:
        resultado["dados"] = mascarar_profundo(resultado.get("dados", {}))
    return resultado


def documento_exibicao(ctx: Contexto, consulta: Consulta, integral: bool) -> str:
    if integral and consulta.documento_cifrado:
        from ..validators import formatar_cnpj, formatar_cpf

        doc = ctx.cofre.decifrar(consulta.documento_cifrado) or ""
        return formatar_cpf(doc) if len(doc) == 11 else formatar_cnpj(doc)
    return consulta.documento_mascarado


# --- Retenção ----------------------------------------------------------------------------------

def expurgar_vencidas(db: Session, usuario: Usuario | None = None, ip: str | None = None) -> int:
    """Apaga dados pessoais de consultas cujo prazo de retenção venceu.

    Mantém apenas metadados (documento mascarado + HMAC) para a trilha de auditoria.
    """
    momento = agora()
    candidatas = db.execute(
        select(Consulta).where(
            Consulta.expurgar_em.is_not(None),
            or_(Consulta.documento_cifrado.is_not(None), Consulta.resultado_cifrado.is_not(None)),
        )
    ).scalars().all()
    total = 0
    for c in candidatas:
        if como_utc(c.expurgar_em) > momento:
            continue
        if c.status == StatusConsulta.PENDENTE:
            c.status = StatusConsulta.RECUSADA
            c.motivo_recusa = "Prazo de retenção vencido sem aprovação."
        elif c.status == StatusConsulta.CONCLUIDA:
            c.status = StatusConsulta.EXPURGADA
        c.resultado_cifrado = None
        c.documento_cifrado = None
        c.nascimento_cifrado = None
        total += 1
    audit.registrar(db, "retencao_executada", usuario, None, None, {"consultas_expurgadas": total}, ip)
    db.commit()
    return total
