"""Relatório PDF de consulta (fonte, data, finalidade, base legal e dados retornados)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from fpdf import FPDF

from .. import lgpd
from ..connectors.base import TIPOS_CONSULTA
from ..models import Consulta, Usuario, como_utc
from .consultas import achatar

FUSO = ZoneInfo("America/Sao_Paulo")

_TROCAS = str.maketrans({"—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "•": "-", "→": "->"})


def _t(texto) -> str:
    """As fontes nativas do PDF usam Latin-1; caracteres fora dele viram '?'."""
    return str(texto).translate(_TROCAS).encode("latin-1", "replace").decode("latin-1")


def data_hora(momento: datetime | None) -> str:
    if momento is None:
        return "-"
    return como_utc(momento).astimezone(FUSO).strftime("%d/%m/%Y %H:%M:%S (horário de Brasília)")


class _PDF(FPDF):
    nome_sistema = "JurisData"
    rodape = ""

    def header(self):
        self.set_fill_color(18, 18, 20)
        self.rect(0, 0, self.w, 18, "F")
        self.set_fill_color(139, 30, 45)
        self.rect(0, 18, self.w, 1.2, "F")
        self.set_xy(12, 5)
        self.set_text_color(255, 255, 255)
        self.set_font("helvetica", "B", 14)
        self.cell(0, 8, _t(self.nome_sistema))
        self.set_xy(-90, 5)
        self.set_font("helvetica", "", 8)
        self.cell(78, 8, _t("USO INTERNO - CONTÉM DADOS PESSOAIS (LGPD)"), align="R")
        self.set_text_color(20, 20, 20)
        self.set_y(26)

    def footer(self):
        self.set_y(-14)
        self.set_font("helvetica", "", 7)
        self.set_text_color(110, 110, 110)
        self.multi_cell(0, 3.5, _t(f"{self.rodape}  ·  Página {self.page_no()}/{{nb}}"), align="C")


def gerar_pdf(
    consulta: Consulta,
    resultado: dict,
    documento: str,
    emissor: Usuario,
    gerado_em: datetime,
    registro_auditoria: int,
    nome_sistema: str = "JurisData",
    integral: bool = False,
) -> bytes:
    pdf = _PDF(format="A4")
    pdf.nome_sistema = nome_sistema
    pdf.rodape = (
        f"Gerado em {data_hora(gerado_em)} por {emissor.nome} ({emissor.email}) · "
        f"registro de auditoria nº {registro_auditoria}"
    )
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(True, margin=18)
    pdf.set_margins(12, 26, 12)
    pdf.add_page()

    pdf.set_font("helvetica", "B", 15)
    pdf.cell(0, 9, _t(f"Relatório de consulta nº {consulta.id}"), new_x="LMARGIN", new_y="NEXT")

    ambiente = resultado.get("ambiente")
    if ambiente == "simulado":
        _faixa(pdf, (139, 30, 45), "DADOS FICTÍCIOS - CONECTOR SIMULADO DE TREINAMENTO. NÃO UTILIZAR EM PROCESSO.")
    if resultado.get("aviso") and ambiente != "simulado":
        _faixa(pdf, (120, 90, 20), resultado["aviso"])
    if integral:
        _faixa(pdf, (60, 60, 60), "Versão integral: documentos sem máscara. Restrinja a circulação ao estritamente necessário.")

    _secao(pdf, "Identificação")
    processo = consulta.processo
    linhas = [
        ("Tipo de consulta", TIPOS_CONSULTA.get(consulta.tipo, consulta.tipo)),
        ("Documento consultado", documento),
        ("Fonte", resultado.get("fonte_rotulo", consulta.fonte)),
        ("Data/hora da resposta da fonte", data_hora(_ler_iso(resultado.get("consultado_em")))),
        ("Processo / demanda", processo.rotulo),
        ("Cliente", processo.cliente.nome),
        ("Finalidade", consulta.finalidade),
        ("Base legal (LGPD)", lgpd.BASES_LEGAIS.get(consulta.base_legal, consulta.base_legal)),
        ("Solicitada por", f"{consulta.solicitante.nome} em {data_hora(consulta.solicitada_em)}"),
        ("Aprovada por", consulta.aprovador.nome if consulta.aprovador else "Dispensada (solicitante advogado)"),
    ]
    _tabela(pdf, linhas)

    _secao(pdf, "Dados retornados pela fonte")
    dados = resultado.get("dados", {})
    _tabela(pdf, achatar(dados) or [("-", "Sem dados")])

    conteudo = json.dumps(dados, sort_keys=True, ensure_ascii=False).encode()
    pdf.ln(3)
    pdf.set_font("helvetica", "", 7.5)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(
        0, 4,
        _t(
            "Os dados acima reproduzem a resposta da fonte no momento indicado e podem ter sido alterados "
            "depois. Não substituem certidão oficial. SHA-256 do conteúdo retornado"
            + (" (com máscara)" if not integral else "")
            + f": {hashlib.sha256(conteudo).hexdigest()}"
        ),
    )
    return bytes(pdf.output())


def _ler_iso(valor: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def _faixa(pdf: FPDF, cor: tuple[int, int, int], texto: str) -> None:
    pdf.set_fill_color(*cor)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 8.5)
    pdf.multi_cell(0, 6, _t(texto), fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 20, 20)
    pdf.set_fill_color(255, 255, 255)
    pdf.ln(2)


def _secao(pdf: FPDF, titulo: str) -> None:
    pdf.ln(2)
    pdf.set_font("helvetica", "B", 10.5)
    pdf.set_text_color(139, 30, 45)
    pdf.cell(0, 7, _t(titulo.upper()), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 20, 20)


def _tabela(pdf: FPDF, linhas: list[tuple[str, str]]) -> None:
    pdf.set_font("helvetica", "", 8.5)
    pdf.set_draw_color(215, 215, 220)
    with pdf.table(col_widths=(35, 65), text_align=("LEFT", "LEFT"), line_height=5, first_row_as_headings=False,
                   borders_layout="HORIZONTAL_LINES", cell_fill_color=(246, 246, 248), cell_fill_mode="ROWS") as tabela:
        for chave, valor in linhas:
            linha = tabela.row()
            linha.cell(_t(chave))
            linha.cell(_t(valor))
