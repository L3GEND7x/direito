"""Trilha de auditoria encadeada por hash."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import RegistroAuditoria, Usuario, agora

GENESE = "0" * 64
_lock = threading.Lock()

ACOES = {
    "login_ok": "Login concluído",
    "login_falha": "Tentativa de login recusada",
    "login_bloqueado": "Conta bloqueada por tentativas",
    "mfa_falha": "Código MFA recusado",
    "mfa_ativado": "MFA ativado",
    "logout": "Saída do sistema",
    "senha_alterada": "Senha alterada",
    "termo_aceito": "Termo de responsabilidade aceito",
    "usuario_criado": "Usuário criado",
    "usuario_alterado": "Usuário alterado",
    "usuario_desativado": "Usuário desativado (sessões revogadas)",
    "usuario_reativado": "Usuário reativado",
    "mfa_redefinido": "MFA redefinido pelo administrador",
    "senha_redefinida": "Senha redefinida pelo administrador",
    "cliente_criado": "Cliente cadastrado",
    "processo_criado": "Processo/demanda cadastrado",
    "processo_encerrado": "Processo/demanda encerrado",
    "consulta_solicitada": "Consulta solicitada",
    "consulta_aprovada": "Consulta aprovada",
    "consulta_recusada": "Consulta recusada",
    "consulta_executada": "Consulta executada",
    "consulta_falhou": "Consulta não concluída",
    "consulta_bloqueada": "Consulta bloqueada por regra",
    "consulta_visualizada": "Resultado visualizado",
    "relatorio_exportado": "Relatório PDF exportado",
    "relatorio_integral_exportado": "Relatório PDF integral exportado (documentos sem máscara)",
    "auditoria_exportada": "Auditoria exportada (CSV)",
    "diligencia_criada": "Diligência patrimonial registrada",
    "diligencia_andamento": "Andamento de diligência registrado",
    "retencao_executada": "Expurgo por retenção executado",
}


def _momento_canonico(m: datetime) -> str:
    # Gravado sempre em UTC; o PostgreSQL pode devolver em outro fuso, o SQLite devolve sem fuso.
    if m.tzinfo is not None:
        m = m.astimezone(timezone.utc)
    return m.replace(tzinfo=None).isoformat(timespec="microseconds")


def _calcular(reg: RegistroAuditoria) -> str:
    conteudo = json.dumps(
        {
            "id": reg.id,
            "momento": _momento_canonico(reg.momento),
            "usuario_id": reg.usuario_id,
            "usuario_email": reg.usuario_email,
            "acao": reg.acao,
            "objeto_tipo": reg.objeto_tipo,
            "objeto_id": reg.objeto_id,
            "detalhes": reg.detalhes,
            "ip": reg.ip,
            "hash_anterior": reg.hash_anterior,
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(conteudo.encode()).hexdigest()


def registrar(
    db: Session,
    acao: str,
    usuario: Usuario | None = None,
    objeto_tipo: str | None = None,
    objeto_id: int | None = None,
    detalhes: dict | None = None,
    ip: str | None = None,
    email: str | None = None,
) -> RegistroAuditoria:
    """Acrescenta um registro à cadeia. Deve ser chamado dentro da mesma transação do ato auditado.

    Em PostgreSQL com vários processos, a serialização é garantida pelo bloqueio da última linha
    (SELECT ... FOR UPDATE) e pela restrição UNIQUE do hash.
    """
    with _lock:
        ultimo = db.execute(
            select(RegistroAuditoria).order_by(RegistroAuditoria.id.desc()).limit(1).with_for_update()
        ).scalar_one_or_none()
        reg = RegistroAuditoria(
            id=(ultimo.id + 1) if ultimo else 1,
            momento=agora(),
            usuario_id=usuario.id if usuario else None,
            usuario_email=usuario.email if usuario else email,
            acao=acao,
            objeto_tipo=objeto_tipo,
            objeto_id=objeto_id,
            detalhes=detalhes or {},
            ip=ip,
            hash_anterior=ultimo.hash if ultimo else GENESE,
        )
        reg.hash = _calcular(reg)
        db.add(reg)
        db.flush()
        return reg


def verificar_cadeia(db: Session) -> tuple[bool, int | None, int]:
    """Retorna (íntegra, id do primeiro registro com problema, total verificado)."""
    anterior = GENESE
    esperado_id = 1
    total = 0
    for reg in db.execute(select(RegistroAuditoria).order_by(RegistroAuditoria.id)).scalars():
        total += 1
        if reg.id != esperado_id or reg.hash_anterior != anterior or _calcular(reg) != reg.hash:
            return False, reg.id, total
        anterior = reg.hash
        esperado_id += 1
    return True, None, total
