"""Modelo de dados.

Convenções de proteção de dados:
- campos ``*_cifrado`` guardam conteúdo criptografado (Fernet) — nunca o valor em claro;
- campos ``*_hash`` guardam HMAC-SHA256 do número (permite busca e auditoria sem expor o dado);
- campos ``*_mascarado`` são a única forma do documento exibida em listas e logs.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def agora() -> datetime:
    return datetime.now(timezone.utc)


def como_utc(momento: datetime | None) -> datetime | None:
    """O SQLite devolve datas sem fuso; todas são gravadas em UTC."""
    if momento is None:
        return None
    return momento.replace(tzinfo=timezone.utc) if momento.tzinfo is None else momento.astimezone(timezone.utc)


class Perfil(str, enum.Enum):
    ADMIN = "admin"
    ADVOGADO = "advogado"
    ASSISTENTE = "assistente"
    AUDITOR = "auditor"


PERFIL_ROTULO = {
    Perfil.ADMIN: "Administrador",
    Perfil.ADVOGADO: "Advogado",
    Perfil.ASSISTENTE: "Assistente jurídico",
    Perfil.AUDITOR: "Auditor",
}


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    oab: Mapped[str | None] = mapped_column(String(40), nullable=True)
    perfil: Mapped[Perfil] = mapped_column(Enum(Perfil, native_enum=False, length=20))
    senha_hash: Mapped[str] = mapped_column(String(255))
    trocar_senha: Mapped[bool] = mapped_column(Boolean, default=True)
    mfa_segredo_cifrado: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_ultimo_passo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    tentativas_falhas: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    termo_aceito_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    desativado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def perfil_rotulo(self) -> str:
        return PERFIL_ROTULO[self.perfil]


class Sessao(Base):
    __tablename__ = "sessoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    # Etapa: "senha" (falta MFA) ou "completa".
    etapa: Mapped[str] = mapped_column(String(20), default="senha")
    csrf: Mapped[str] = mapped_column(String(64))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    ultimo_uso: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    usuario: Mapped[Usuario] = relationship()


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(2))  # PF | PJ
    documento_cifrado: Mapped[str | None] = mapped_column(Text, nullable=True)
    documento_mascarado: Mapped[str | None] = mapped_column(String(32), nullable=True)
    documento_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    contato_cifrado: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_por_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    processos: Mapped[list["Processo"]] = relationship(back_populates="cliente")


class Processo(Base):
    __tablename__ = "processos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    numero_cnj: Mapped[str | None] = mapped_column(String(25), index=True, nullable=True)
    identificacao_demanda: Mapped[str | None] = mapped_column(String(300), nullable=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))
    parte_contraria: Mapped[str | None] = mapped_column(String(300), nullable=True)
    orgao: Mapped[str | None] = mapped_column(String(200), nullable=True)
    classe: Mapped[str | None] = mapped_column(String(120), nullable=True)
    area: Mapped[str] = mapped_column(String(40))
    polo_cliente: Mapped[str | None] = mapped_column(String(40), nullable=True)
    responsavel_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    encerrado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cliente: Mapped[Cliente] = relationship(back_populates="processos")
    responsavel: Mapped[Usuario] = relationship()

    @property
    def rotulo(self) -> str:
        return self.numero_cnj or (self.identificacao_demanda or f"Demanda #{self.id}")


class StatusConsulta(str, enum.Enum):
    PENDENTE = "pendente_aprovacao"
    RECUSADA = "recusada"
    CONCLUIDA = "concluida"
    FALHA = "falha"
    EXPURGADA = "expurgada"


STATUS_ROTULO = {
    StatusConsulta.PENDENTE: "Aguardando aprovação",
    StatusConsulta.RECUSADA: "Recusada",
    StatusConsulta.CONCLUIDA: "Concluída",
    StatusConsulta.FALHA: "Não concluída",
    StatusConsulta.EXPURGADA: "Resultado expurgado (retenção)",
}


class Consulta(Base):
    __tablename__ = "consultas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(30))
    fonte: Mapped[str] = mapped_column(String(40))
    documento_cifrado: Mapped[str | None] = mapped_column(Text, nullable=True)
    documento_mascarado: Mapped[str] = mapped_column(String(32))
    documento_hash: Mapped[str] = mapped_column(String(64), index=True)
    nascimento_cifrado: Mapped[str | None] = mapped_column(Text, nullable=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id"), index=True)
    finalidade: Mapped[str] = mapped_column(Text)
    base_legal: Mapped[str] = mapped_column(String(40))
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    aprovador_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    motivo_recusa: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[StatusConsulta] = mapped_column(Enum(StatusConsulta, native_enum=False, length=30))
    solicitada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)
    executada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ambiente_fonte: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resultado_cifrado: Mapped[str | None] = mapped_column(Text, nullable=True)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    expurgar_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    processo: Mapped[Processo] = relationship()
    solicitante: Mapped[Usuario] = relationship(foreign_keys=[solicitante_id])
    aprovador: Mapped[Usuario | None] = relationship(foreign_keys=[aprovador_id])

    @property
    def status_rotulo(self) -> str:
        return STATUS_ROTULO[self.status]


class Diligencia(Base):
    """Acompanhamento de pedidos de pesquisa patrimonial feitos AO JUÍZO.

    O JurisData não acessa SISBAJUD, RENAJUD, SNIPER etc.: apenas registra o pedido,
    a decisão judicial e o resultado juntado aos autos.
    """

    __tablename__ = "diligencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id"), index=True)
    sistema: Mapped[str] = mapped_column(String(40))
    pesquisado_nome: Mapped[str] = mapped_column(String(200))
    pesquisado_doc_cifrado: Mapped[str | None] = mapped_column(Text, nullable=True)
    pesquisado_doc_mascarado: Mapped[str | None] = mapped_column(String(32), nullable=True)
    objetivo: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="a_requerer")
    data_pedido: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_decisao: Mapped[date | None] = mapped_column(Date, nullable=True)
    referencia_decisao: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resultado: Mapped[str | None] = mapped_column(Text, nullable=True)
    prazo: Mapped[date | None] = mapped_column(Date, nullable=True)
    criado_por_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    processo: Mapped[Processo] = relationship()
    andamentos: Mapped[list["AndamentoDiligencia"]] = relationship(
        back_populates="diligencia", order_by="AndamentoDiligencia.id"
    )


class AndamentoDiligencia(Base):
    __tablename__ = "andamentos_diligencia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    diligencia_id: Mapped[int] = mapped_column(ForeignKey("diligencias.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    descricao: Mapped[str] = mapped_column(Text)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    diligencia: Mapped[Diligencia] = relationship(back_populates="andamentos")
    usuario: Mapped[Usuario] = relationship()


class RegistroAuditoria(Base):
    """Trilha de auditoria encadeada por hash (cada registro inclui o hash do anterior).

    Qualquer alteração ou exclusão de um registro quebra a cadeia e é detectada em
    ``auditoria.verificar_cadeia``. Os detalhes nunca contêm CPF/CNPJ em claro.
    """

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)
    usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    usuario_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    acao: Mapped[str] = mapped_column(String(60), index=True)
    objeto_tipo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    objeto_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detalhes: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hash_anterior: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
