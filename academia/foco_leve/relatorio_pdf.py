"""Relatório da evolução em PDF, para levar ao profissional (sem interface).

Só usa o que foi registrado na conta. Fonte padrão do PDF (Helvetica, Latin-1): cobre os acentos do português;
os poucos símbolos fora dela são trocados por equivalentes simples.
"""
from __future__ import annotations

from fpdf import FPDF

from . import biblioteca as B
from . import evolucao as E
from . import monitoramento as M
from . import objetivos as O
from . import regras as R

VERMELHO = (240, 54, 74)
CINZA = (110, 110, 115)
TROCAS = {"—": "-", "–": "-", "×": "x", "≈": "~", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "•": "-",
          "→": "->", "≥": ">=", "≤": "<=", "°": "o"}


def _t(txt) -> str:
    s = str(txt)
    for a, b in TROCAS.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


class _Pdf(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*CINZA)
        self.cell(0, 5, _t(f"Foco Leve - gerado em {R.fmt_dy(R.hoje())} a partir dos registros da conta. "
                           f"Não é avaliação clínica.   Página {self.page_no()}"), align="C")


def _titulo(pdf: _Pdf, txt: str) -> None:
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*VERMELHO)
    pdf.cell(0, 7, _t(txt), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)


def _par(pdf: _Pdf, txt: str, tam: int = 9) -> None:
    pdf.set_font("Helvetica", "", tam)
    pdf.multi_cell(0, 4.6, _t(txt), new_x="LMARGIN", new_y="NEXT")


def _tabela(pdf: _Pdf, cab: list[str], linhas: list[list], larguras: list[float]) -> None:
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(240, 240, 242)
    for c, w in zip(cab, larguras):
        pdf.cell(w, 6, _t(c), border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for ln in linhas:
        for c, w in zip(ln, larguras):
            pdf.cell(w, 5.5, _t(c), border=1)
        pdf.ln()


def _grafico_peso(pdf: _Pdf, pontos: list[tuple[str, float]], meta: float) -> None:
    """Linha das médias semanais de peso, desenhada com primitivas do PDF."""
    if len(pontos) < 2:
        return
    x0, y0, w, h = pdf.l_margin + 10, pdf.get_y() + 2, pdf.epw - 14, 38
    vals = [v for _, v in pontos]
    lo, hi = min(vals + [meta]) - 1, max(vals) + 1
    if hi - lo > 3 * (max(vals) - min(vals) + 2):  # meta muito longe: não achata a curva
        lo = min(vals) - 1.5
    def px(i):
        return x0 + w * i / (len(pontos) - 1)
    def py(v):
        return y0 + h - h * (v - lo) / (hi - lo)
    pdf.set_draw_color(220, 220, 222)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*CINZA)
    for v in (lo, (lo + hi) / 2, hi):
        pdf.line(x0, py(v), x0 + w, py(v))
        pdf.text(pdf.l_margin, py(v) + 1, _t(R.br(v)))
    if lo <= meta <= hi:
        pdf.set_draw_color(*CINZA)
        pdf.set_dash_pattern(dash=1.2, gap=1.2)
        pdf.line(x0, py(meta), x0 + w, py(meta))
        pdf.set_dash_pattern()
        pdf.text(x0 + w - 12, py(meta) - 1, "meta")
    pdf.set_draw_color(*VERMELHO)
    pdf.set_line_width(0.6)
    for i in range(len(pontos) - 1):
        pdf.line(px(i), py(vals[i]), px(i + 1), py(vals[i + 1]))
    pdf.set_line_width(0.2)
    passo = max(1, len(pontos) // 8)
    for i in range(0, len(pontos), passo):
        pdf.text(px(i) - 4, y0 + h + 4, _t(pontos[i][0]))
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + h + 7)


def gerar(S: dict) -> bytes:
    p = S["profile"]
    t = R.hoje()
    pdf = _Pdf(format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(True, 16)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 9, _t("Foco Leve - Relatório de evolução"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*CINZA)
    inicio = S.get("startDate") or ""
    pdf.cell(0, 5, _t((p.get("nome") or "Sem nome") + f" · gerado em {R.fmt_dy(t)}"
                      + (f" · plano iniciado em {R.fmt_dy(inicio)}" if inicio else "")), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)

    _titulo(pdf, "Perfil")
    _par(pdf, f"Idade {p.get('idade')} anos · altura {R.brx(p.get('altura'))} cm · nível {p.get('nivel')} · "
              f"{p.get('dias')} dia(s) de treino por semana · até {p.get('tempoMax')} min por sessão.\n"
              f"Objetivo: {' + '.join(O.OBJETIVOS[o]['nome'] for o in O.objetivos(S))}"
              + (f" · grupos prioritários: {', '.join(O.prioridades(S))}" if O.prioridades(S) else "")
              + (f"\nLimitações informadas: {p['limitacao']}" if p.get("limitacao") else ""))

    _titulo(pdf, "Peso")
    cw, ini, meta = R.peso_atual(S), float(p["pesoInicial"]), float(p["pesoMeta"])
    i = R.imc(S, cw)
    _par(pdf, f"Inicial {R.br(ini)} kg · atual {R.br(cw)} kg ({'+' if cw - ini > 0 else ''}{R.br(cw - ini)} kg) · "
              f"meta {R.br(meta)} kg · IMC atual {R.br(i)} kg/m² ({R.imc_categoria(i)}; triagem, não é diagnóstico). "
              f"{len(S['weights'])} pesagem(ns) registrada(s).")
    _grafico_peso(pdf, R.serie_peso(S, "semanal"), meta)

    med = E.comparacao_medidas(S)
    if med:
        _titulo(pdf, "Medidas corporais (cm)")
        _tabela(pdf, ["Medida", "Primeira", "Última", "Variação", "Registros"],
                [[m["rotulo"], f"{R.brx(m['primeira'])} ({R.fmt_d(m['data_primeira'])})",
                  f"{R.brx(m['ultima'])} ({R.fmt_d(m['data_ultima'])})",
                  f"{'+' if m['variacao'] > 0 else ''}{R.br(m['variacao'])}", m["registros"]] for m in med],
                [50, 38, 38, 26, 28])

    _titulo(pdf, "Treinos - últimas 8 semanas")
    _tabela(pdf, ["Semana de", "Concluídos", "Planejados", "Cardio (min)"],
            [[x["rotulo"], x["feitos"], x["planejados"], x["cardio"]] for x in E.semanas_recentes(S, 8)], [45, 45, 45, 45])
    cons = E.consistencia(S)
    _par(pdf, f"Semanas do plano aprovadas: {cons['aprovadas']} de {cons['avaliadas']} avaliadas.")

    sg = M.series_por_grupo(S, R.add_dias(t, -27), t)
    if sg:
        _titulo(pdf, "Séries de musculação por grupo - últimos 28 dias")
        _par(pdf, " · ".join(f"{g}: {n}" for g, n in sorted(sg.items(), key=lambda x: -x[1])))

    cargas = E.comparacao_cargas(S)[:15]
    if cargas:
        _titulo(pdf, "Cargas: primeiro registro x último")
        _tabela(pdf, ["Exercício", "Primeira (kg)", "Última (kg)", "Variação", "Registros"],
                [[c["nome"][:44], R.brx(c["primeira"]), R.brx(c["ultima"]),
                  ("+" if c["variacao"] > 0 else "") + R.brx(c["variacao"]), c["registros"]] for c in cargas],
                [78, 26, 26, 26, 24])

    dores = [(s["date"], R.nome_ex(e["id"]), e.get("painLevel")) for s in S["sessions"] if R.dias_entre(s["date"], t) <= 28
             for e in s.get("ex", []) if e.get("painLevel") not in (None, "", "nenhum")]
    interrompidas = [s["date"] for s in S["sessions"] if s.get("status") == "interrompida" and R.dias_entre(s["date"], t) <= 28]
    _titulo(pdf, "Desconfortos registrados - últimos 28 dias")
    if dores or interrompidas:
        _par(pdf, "\n".join(f"{R.fmt_d(d)}: {n} (dor {nv})" for d, n, nv in dores)
             + ("\nSessões interrompidas por sintoma: " + ", ".join(R.fmt_d(d) for d in interrompidas) if interrompidas else ""))
    else:
        _par(pdf, "Nenhum desconforto registrado.")

    obs = M.observacoes(S)
    if obs:
        _titulo(pdf, "Observações automáticas")
        _par(pdf, "\n".join("- " + o["texto"] for o in obs))

    pdf.ln(3)
    pdf.set_text_color(*CINZA)
    _par(pdf, "Os números vêm só do que foi registrado no app. Grupo muscular contado pelo grupo principal de cada "
              f"exercício ({len(B.GRUPOS)} grupos). Este relatório não substitui avaliação médica nem a orientação do "
              "profissional de educação física.", 8)
    return bytes(pdf.output())
