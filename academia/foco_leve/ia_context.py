"""Contexto individual que acompanha cada pergunta ao Personal IA (sem interface).

Só entra o necessário para a pergunta, a partir do estado da conta autenticada: nada de nome, e-mail ou
identificadores. Cada dado vem marcado com a origem — [declarado] pela pessoa ou [calculado] pelo app — para a IA
distinguir os dois e não inventar o que falta.
"""
from __future__ import annotations

import unicodedata

from . import dados as D
from . import evolucao as E
from . import plano as P
from . import regras as R

INTENCOES = {
    "evolucao": ("evolu", "peso", "pesag", "emagrec", "perder", "perdi", "engord", "balanca", "resultado", "progresso",
                 "medida", "cintura", "meta", "estagn", "plato", "semana"),
    "historico": ("ontem", "nao consegui", "conclu", "termin", "faltei", "rotina", "constan", "frequen", "treinei",
                  "historico", "sessao", "sessoes", "semana", "resultado", "carga", "progress", "planejado", "realizado"),
    "treino": ("treino", "exercic", "trocar", "substitu", "montar", "monte", "plano", "series", "repet", "descanso",
               "aparelho", "maquina", "equipamento", "tempo", "minutos", "cansad", "hoje", "amanha", "adapt"),
    "habitos": ("sono", "dormi", "agua", "aliment", "comida", "refeic", "fome", "energia", "habito", "dieta"),
}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def intencoes(texto: str) -> set[str]:
    t = _norm(texto)
    return {k for k, palavras in INTENCOES.items() if any(p in t for p in palavras)}


def perfil_incompleto(S: dict) -> list[str]:
    """O que falta para personalizar com segurança (para a IA pedir aos poucos)."""
    falta = []
    if not S["profile"].get("confirmado"):
        falta.append("dados físicos e objetivo (o perfil ainda tem valores de exemplo)")
    if not S["assess"].get("done"):
        falta.append("avaliação de segurança (dor, inchaço, diagnóstico, liberação)")
    if not S["weights"]:
        falta.append("nenhuma pesagem registrada")
    return falta


def _sim_nao(v) -> str:
    return {"sim": "sim", "nao": "não", "nao_sei": "não sabe"}.get(v, "não informado")


def montar(S: dict, texto: str, hoje: str) -> str:
    """Texto do contexto da conta para esta pergunta."""
    p, a = S["profile"], S["assess"]
    quer = intencoes(texto) or {"treino"}
    linhas = [f"Data de hoje: {R.fmt_dy(hoje)} ({D.DIAS_SEMANA[R.dia_js(hoje)]})."]

    falta = perfil_incompleto(S)
    if falta:
        linhas.append("AINDA NÃO INFORMADO: " + "; ".join(falta) + ". Não suponha esses dados: peça-os aos poucos, "
                      "uma ou duas perguntas por vez, sem bloquear a ajuda que já é possível dar.")

    linhas.append("## Perfil")
    if p.get("confirmado"):
        linhas.append(f"- [declarado] idade {p['idade']} anos; altura {R.brx(p['altura'])} cm; peso inicial "
                      f"{R.brx(p['pesoInicial'])} kg; peso desejado {R.brx(p['pesoMeta'])} kg")
    linhas.append(f"- [declarado] nível: {p.get('nivel') or 'não informado'}; {p.get('dias')} dia(s) de treino por semana; "
                  f"até {p.get('tempoMax')} min por sessão; local: {p.get('local') or 'não informado'}; "
                  f"objetivo: {p.get('objetivo') or 'não informado'}")
    linhas.append(f"- [declarado] limitações: {p.get('limitacao') or 'nenhuma informada'}")
    w = R.pesos_ordenados(S)
    if w:
        imc = R.imc(S, w[-1]["peso"])
        linhas.append(f"- [calculado] peso atual = última pesagem: {R.brx(w[-1]['peso'])} kg em {R.fmt_dy(w[-1]['date'])}; "
                      f"IMC {R.br(imc)} ({R.imc_categoria(imc)}, só triagem)")

    linhas.append("## Segurança")
    if a.get("done"):
        linhas.append(f"- [declarado] dor articular: {_sim_nao(a.get('dor'))}; inchaço: {_sim_nao(a.get('inchaco'))}; "
                      f"dificuldade para caminhar: {_sim_nao(a.get('caminhar'))}; diagnóstico: {_sim_nao(a.get('diag'))}"
                      + (f" ({a['diagTxt']})" if a.get("diagTxt") else "")
                      + f"; liberação para musculação: {_sim_nao(a.get('liberacao'))}; lesão em recuperação: "
                      f"{_sim_nao(a.get('lesao'))}")
        if a.get("proibidos"):
            linhas.append(f"- [declarado] exercícios proibidos pelo profissional: {a['proibidos']}")
        if a.get("joelho"):
            linhas.append(f"- [declarado] observações: {a['joelho']}")
    ci = S["checkins"].get(hoje)
    if ci:
        linhas.append(f"- [declarado] check-in de hoje: dor {ci.get('dor', 0)}/10, inchaço "
                      f"{'sim' if ci.get('inchaco') else 'não'}, fadiga {ci.get('fadiga', '?')}/5"
                      + (f", sono {R.brx(ci['sono'])} h" if R.ok(ci.get("sono")) else "")
                      + (", sinais de alerta marcados" if ci.get("red") else ""))
    else:
        linhas.append("- check-in de hoje: não feito")
    linhas.append(f"- [calculado] situação para treinar: {R.seguranca(S)} (ok, caution ou urgent)")

    sp = P.semana_do_programa(S)
    sem = sp["semana"]
    fi, fase = P.fase_da_semana(sem)
    linhas.append("## Plano do app")
    linhas.append(f"- [calculado] semana {sem} de {D.SEMANAS_PLANO}, fase {fi + 1} ({fase['n']}); esforço da fase {fase['rpe']}; "
                  f"cardio semanal alvo {P.cardio_semanal_alvo(S)} min")
    pl = P.plano_do_dia(S, hoje, sem)
    if pl["wk"] == "OFF":
        linhas.append("- [calculado] hoje: descanso na agenda")
    else:
        itens = "; ".join(f"{R.nome_ex(it['id'])} ({it['id']}) " + (f"{it['duracao']} min" if "duracao" in it
                          else f"{it['series']}x{it['reps']}, descanso {it['descanso']} s") for it in pl["itens"])
        linhas.append(f"- [calculado] hoje: {pl['nome']} (treino {pl['wk']}), ≈ {pl['total']} min: {itens}")
    bloqueados = sorted({x for x in D.EXERCICIOS if P.motivo_bloqueio(S, x, sem)})
    if bloqueados:
        linhas.append("- [calculado] exercícios FORA do plano por segurança (não proponha): " + ", ".join(bloqueados))
    if "treino" in quer:
        dias = R.dias_da_semana(R.inicio_semana(hoje))
        linhas.append("- [calculado] agenda desta semana: " + "; ".join(
            f"{D.DIAS_SEMANA[R.dia_js(d)][:3]} {R.nome_treino(R.treino_do_dia(S, d))}" for d in dias))

    if "historico" in quer or "evolucao" in quer or "treino" in quer:
        ses = sorted(S["sessions"], key=lambda s: s.get("startedAt", 0))[-6:]
        linhas.append("## Treinos registrados (mais recentes)")
        if not ses:
            linhas.append("- nenhum treino registrado ainda")
        for s in ses:
            nao = [R.nome_ex(e["id"]) for e in s.get("ex", []) if not e.get("done")]
            linhas.append(f"- [registrado] {R.fmt_dy(s['date'])}: {R.nome_treino(s.get('workout', ''))}, "
                          f"{s.get('status')}, {R.br(s.get('pct', 0), 0)}% concluído, {s.get('minutes', '?')} min"
                          + (f", sensação {s['feeling']}" if s.get("feeling") else "")
                          + (f", sintoma: {s['symptom']}" if s.get("symptom") else "")
                          + (f"; não feitos: {', '.join(nao[:6])}" if nao else ""))
        if S.get("active"):
            linhas.append("- há um treino em andamento agora")
        c = E.consistencia(S)
        if c["avaliadas"]:
            linhas.append(f"- [calculado] semanas aprovadas: {c['aprovadas']} de {c['avaliadas']}; sequência atual {c['sequencia']}")

    if "evolucao" in quer:
        linhas.append("## Peso (pesagens registradas)")
        if not w:
            linhas.append("- nenhuma pesagem registrada")
        for x in w[-10:]:
            linhas.append(f"- [registrado] {R.fmt_dy(x['date'])}: {R.brx(x['peso'])} kg"
                          + (f", cintura {R.brx(x['cintura'])} cm" if R.ok(x.get("cintura")) else ""))
        cp = E.comparacao_peso(S)
        if cp and cp["registros"] >= 2:
            linhas.append(f"- [calculado] variação entre a primeira e a última pesagem: {R.br(cp['variacao'])} kg "
                          f"em {R.dias_entre(cp['data_primeira'], cp['data_ultima'])} dias; faltam {R.br(cp['falta'])} kg "
                          "para a meta. Oscilações de 1 a 2 kg entre dias são comuns (água, sal, intestino): "
                          "compare médias semanais, não pesagens isoladas.")
        cargas = E.comparacao_cargas(S)[:6]
        if cargas:
            linhas.append("- [calculado] cargas (primeira → última): " + "; ".join(
                f"{x['nome']} {R.brx(x['primeira'])} → {R.brx(x['ultima'])} kg" for x in cargas))

    if "habitos" in quer:
        dias = [R.add_dias(hoje, -i) for i in range(6, -1, -1)]
        hs = [(d, S["habits"].get(d)) for d in dias if S["habits"].get(d)]
        linhas.append("## Hábitos dos últimos 7 dias")
        if not hs:
            linhas.append("- nada registrado")
        for d, h in hs:
            linhas.append(f"- [declarado] {R.fmt_d(d)}: água {h.get('agua') or 0} copos"
                          + (f", sono {R.brx(h['sono'])} h" if R.ok(h.get("sono")) else "")
                          + (f", energia {h['energia']}/5" if h.get("energia") else ""))
    return "\n".join(linhas)
