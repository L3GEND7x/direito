"""Componentes visuais do Foco Leve (HTML gerado a partir de dados; sem estado)."""
from __future__ import annotations

import html
from pathlib import Path

_CSS = Path(__file__).parent / "assets" / "tema.css"


def tema_css() -> str:
    return f"<style>{_CSS.read_text(encoding='utf-8')}</style>"


def esc(x) -> str:
    return html.escape(str(x))


def cabecalho(titulo: str, sobre: str = "") -> str:
    return ("<div class='fl-cab'><div class='marca'>Foco Leve</div>"
            + (f"<div class='sobre'>{esc(sobre)}</div>" if sobre else "")
            + f"<h1>{esc(titulo)}</h1></div>")


def aneis(itens: list[tuple[str, str, str, float, str]]) -> str:
    """Anéis concêntricos de progresso. Cada item: (rótulo, valor, complemento, fração 0–1, cor CSS)."""
    tam, esp, gap = 124, 12, 4
    svg = [f"<svg width='{tam}' height='{tam}' viewBox='0 0 {tam} {tam}' role='img' aria-label='"
           + esc("; ".join(f"{r}: {v} {c}" for r, v, c, _, _ in itens)) + "'>"]
    leg = []
    for k, (rotulo, valor, compl, frac, cor) in enumerate(itens):
        r = tam / 2 - esp / 2 - k * (esp + gap)
        circ = 2 * 3.14159265 * r
        frac = max(0.0, min(1.0, float(frac or 0)))
        svg.append(f"<circle class='anel-fundo' cx='{tam/2}' cy='{tam/2}' r='{r:.1f}' fill='none' stroke-width='{esp}'/>")
        if frac > 0:
            svg.append(f"<circle class='anel' cx='{tam/2}' cy='{tam/2}' r='{r:.1f}' fill='none' stroke='{cor}' stroke-width='{esp}' "
                       f"stroke-linecap='round' stroke-dasharray='{circ:.1f}' stroke-dashoffset='{circ * (1 - frac):.1f}' "
                       f"transform='rotate(-90 {tam/2} {tam/2})'/>")
        leg.append(f"<div><span><i style='background:{cor}'></i>{esc(rotulo)}</span>"
                   f"<b>{esc(valor)} <small>{esc(compl)}</small></b></div>")
    svg.append("</svg>")
    return f"<div class='fl-aneis'>{''.join(svg)}<div class='fl-legenda'>{''.join(leg)}</div></div>"


def semana(dias: list[dict]) -> str:
    """Pontos dos 7 dias: estado em feito | planejado | perdido | descanso; hoje destacado."""
    out = []
    for d in dias:
        simb = "✓" if d["estado"] == "feito" else ("·" if d["estado"] == "descanso" else "")
        cls = d["estado"] + (" hoje" if d.get("hoje") else "")
        out.append(f"<div class='fl-dia {cls}' title='{esc(d.get('titulo', ''))}'><i>{simb}</i>{esc(d['rotulo'])}</div>")
    return f"<div class='fl-semana' role='list' aria-label='Treinos da semana'>{''.join(out)}</div>"


def linha_do_tempo(estados: list[str], fases: list[tuple[str, int, int]], fase_atual: int) -> str:
    """20 blocos (ok | rep | atual | vazio) e as fases embaixo."""
    blocos = "".join(f"<i class='{e}' title='Semana {n}'></i>" for n, e in enumerate(estados, 1))
    # nomes longos não cabem em 5 colunas no celular: aqui só número e semanas; o nome da fase atual vai embaixo
    nomes = "".join(f"<div class='{'atual' if k == fase_atual else ''}'>Fase {k + 1}<br>"
                    f"<span style='color:var(--text-3)'>sem. {a}–{b}</span></div>" for k, (n, a, b) in enumerate(fases))
    chave = ("<div class='fl-chave'><span><i class='ok'></i>Semana concluída</span><span><i class='rep'></i>Semana repetida</span>"
             "<span><i class='atual'></i>Semana atual</span><span><i></i>A fazer</span></div>")
    atual = f"<p class='fl-sec' style='margin:10px 0 0'>Fase atual: <b style='color:var(--text)'>{esc(fases[fase_atual][0])}</b></p>"
    return f"<div class='fl-linha' aria-hidden='true'>{blocos}</div><div class='fl-fases'>{nomes}</div>{atual}{chave}"


def criterios(itens: list[tuple[bool | None, str, str]]) -> str:
    li = []
    for okk, texto, valor in itens:
        cls, simb = ("ok", "✓") if okk else (("nao", "✕") if okk is False else ("", "…"))
        li.append(f"<li><span class='s {cls}'>{simb}</span>{esc(texto)}<b>{esc(valor)}</b></li>")
    return f"<ul class='fl-lista'>{''.join(li)}</ul>"


def vazio(titulo: str, texto: str) -> str:
    return f"<div class='fl-vazio'><b>{esc(titulo)}</b><p>{esc(texto)}</p></div>"


def grade(itens) -> str:
    """Indicadores: (rótulo, valor, nota opcional, destaque)."""
    blocos = "".join(f"<div class='fl-tile{' destaque' if dest else ''}'><small>{esc(r)}</small><b>{esc(v)}</b>"
                     + (f"<em>{esc(n)}</em>" if n else "") + "</div>" for r, v, n, dest in itens)
    n = len(itens)
    return f"<div class='fl-grade{' tres' if n == 3 else ''}'>{blocos}</div>"


def fim_de_sessao(titulo: str, sub: str) -> str:
    check = ("<svg viewBox='0 0 24 24' fill='none' stroke='#30d158' stroke-width='2.6' stroke-linecap='round' "
             "stroke-linejoin='round' aria-hidden='true'><path d='M5 12.5l4.2 4.2L19 7'/></svg>")
    return f"<div class='fl-fim'><div class='check'>{check}</div><h2>{esc(titulo)}</h2><p class='fl-sec'>{esc(sub)}</p></div>"
