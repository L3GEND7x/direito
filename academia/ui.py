"""Componentes visuais do Foco Leve (HTML gerado a partir de dados; sem estado)."""
from __future__ import annotations

import html
import json
from pathlib import Path

_CSS = Path(__file__).parent / "assets" / "tema.css"


def tema_css() -> str:
    return f"<style>{_CSS.read_text(encoding='utf-8')}</style>"


# Roda no documento do app (o iframe do componente tem a mesma origem):
# - declara a página em português e sem tradução automática: o tradutor do Chrome reescreve o texto da página
#   e quebra a interface (o Streamlit marca a página como lang="en");
# - libera os ícones só depois que a fonte de ícones carregar, para o nome do ícone nunca aparecer como texto.
AJUSTES_PAGINA = """<script>
(function () {
  var docs = [];
  try { docs.push(window.parent.document); } catch (e) {}
  try { if (window.top !== window.parent) docs.push(window.top.document); } catch (e) {}
  docs.forEach(function (d) {
    d.documentElement.lang = "pt-BR";
    d.documentElement.setAttribute("translate", "no");
    d.documentElement.classList.add("notranslate");
    if (!d.querySelector('meta[name="google"][content="notranslate"]')) {
      var m = d.createElement("meta"); m.name = "google"; m.content = "notranslate"; d.head.appendChild(m);
    }
  });
  var d = docs[0];
  if (!d || !d.fonts) return;
  var fonte = '24px "Material Symbols Rounded"', tentativas = 0;
  (function esperar() {
    d.fonts.load(fonte, "home").then(function (ok) {
      if (ok.length && d.fonts.check(fonte, "home")) d.documentElement.classList.add("fl-icones");
      else if (++tentativas < 15) setTimeout(esperar, 2000);
    }, function () { if (++tentativas < 15) setTimeout(esperar, 2000); });
  })();
})();
</script>"""


def botao_compartilhar(url: str, texto: str) -> str:
    """Botão "Compartilhar": abre a janela de compartilhamento do aparelho (Web Share API); onde ela não existe
    (a maioria dos computadores), copia o link. Só o link público do app é compartilhado, nenhum dado da conta."""
    dados = json.dumps({"title": "Foco Leve", "text": texto, "url": url}, ensure_ascii=False).replace("</", "<\\/")
    return """<style>
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, system-ui, sans-serif; }
  button { width: 100%; min-height: 48px; border: 0; border-radius: 14px; cursor: pointer; color: #fff; font-size: 16px;
    font-weight: 600; background: linear-gradient(180deg, #f5475a 0%, #e02d42 100%); display: flex; gap: 8px;
    align-items: center; justify-content: center; font-family: inherit; }
  button:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
  #msg { color: #a1a1a6; font-size: 13px; text-align: center; min-height: 18px; margin-top: 6px; }
</style>
<button id="b" type="button" aria-label="Compartilhar o Foco Leve">
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
    <path d="M4 12v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7"/><path d="M16 6l-4-4-4 4"/><path d="M12 2v13"/></svg>
  Compartilhar o app</button>
<div id="msg" role="status" aria-live="polite"></div>
<script>
const dados = """ + dados + """;
const msg = t => { document.getElementById("msg").textContent = t; };
function janelas() {  // o app roda num iframe: o compartilhamento precisa da janela de cima
  const ws = [];
  for (const f of [() => window.top, () => window.parent, () => window]) { try { const w = f(); w.navigator; ws.push(w); } catch (e) {} }
  return ws;
}
document.getElementById("b").addEventListener("click", async () => {
  for (const w of janelas()) {
    try {
      if (w.navigator.share && (!w.navigator.canShare || w.navigator.canShare(dados))) {
        await w.navigator.share(dados);
        msg("Obrigado por compartilhar!");
        return;
      }
    } catch (e) {
      if (e && e.name === "AbortError") { msg(""); return; }  // a pessoa fechou a janela de compartilhamento
    }
  }
  for (const w of janelas()) {
    try { await w.navigator.clipboard.writeText(dados.url); msg("Link copiado! Cole numa conversa para enviar."); return; } catch (e) {}
  }
  msg("Use o botão do WhatsApp ou copie o link abaixo.");
});
</script>"""


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
