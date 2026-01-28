import streamlit as st
import pandas as pd
import random
import json
import os
from itertools import combinations
from datetime import datetime
from io import BytesIO
from math import comb

# ============================
# CONFIGURAÇÕES E META
# ============================
APP_VERSAO = "Alirio v3 (Revisado)"
APP_NOME = f"Gerador Mega-Sena — {APP_VERSAO}"
SENHA_CORRETA = "Alirio2026!"  # troque aqui se quiser alterar diretamente

st.set_page_config(page_title=APP_NOME, page_icon="🎯", layout="centered")

# ============================
# PARÂMETROS DA LÓGICA
# ============================
POS_RANGES = {1: (1, 20), 2: (15, 30), 3: (20, 40), 4: (30, 50), 5: (40, 58), 6: (50, 60)}
MAX_SEQ = 2          # máximo de consecutivos
EXIGE_ACIMA_31 = True

# ============================
# FUNÇÕES UTILITÁRIAS
# ============================

def ler_ultimo_resultado_caixa():
    """
    Lê o último resultado da Mega-Sena do endpoint público da CAIXA.
    Se não conseguir (timeout/bloqueio), retorna set() e o app segue normalmente.
    """
    import urllib.request
    url = "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://loterias.caixa.gov.br/",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
            obj = json.loads(data)
            dezenas = obj.get("listaDezenas") or obj.get("listaDezenasOrdemSorteio")
            nums = {int(x) for x in dezenas} if dezenas else set()
            return nums if len(nums) == 6 else set()
    except Exception:
        return set()


def valida_posicoes_first6(nums):
    """
    Mantém sua heurística de faixas por posição (ordem estatística) para as 6 primeiras posições.
    Para bilhetes com 7..15 dezenas, validamos apenas as 6 menores (ordem estatística 1..6).
    """
    s = sorted(nums)
    if len(s) < 6:
        return False
    for i, x in enumerate(s[:6], start=1):
        lo, hi = POS_RANGES[i]
        if not (lo <= x <= hi):
            return False
    return True


def parity_ok(nums):
    """Paridade equilibrada para tamanho variável: diferença entre pares e ímpares ≤ 1."""
    m = len(nums)
    ev = sum(1 for x in nums if x % 2 == 0)
    return abs(ev - (m / 2)) <= 1


def no_long_sequences(nums, max_len=2):
    s = sorted(nums)
    run = 1
    for i in range(1, len(s)):
        if s[i] == s[i - 1] + 1:
            run += 1
            if run > max_len:
                return False
        else:
            run = 1
    return True


def decade_ok(nums):
    """
    Limite dinâmico por “dezena” (01–10, 11–20, ...).
    Para m<=8 -> 2; m<=12 -> 3; m<=15 -> 4.
    """
    m = len(nums)
    if m <= 8:
        limit = 2
    elif m <= 12:
        limit = 3
    else:
        limit = 4
    counts = {}
    for x in nums:
        d = (x - 1) // 10
        counts[d] = counts.get(d, 0) + 1
        if counts[d] > limit:
            return False
    return True


def exige_acima_31_fn(nums):
    return any(x > 31 for x in nums)


def last_digit_ok(nums):
    """
    Mesma unidade (0..9) limitada dinamicamente:
    m<=8 -> 2; m<=12 -> 3; m<=15 -> 4.
    """
    m = len(nums)
    if m <= 8:
        limit = 2
    elif m <= 12:
        limit = 3
    else:
        limit = 4
    units = {}
    for x in nums:
        u = x % 10
        units[u] = units.get(u, 0) + 1
        if units[u] > limit:
            return False
    return True


def repete_ultimo_ok(nums, intervalo, ult=set()):
    """Quantidade que repete do último: entre intervalo[0] e intervalo[1]."""
    if not ult:
        return True
    q = sum(1 for x in nums if x in ult)
    return intervalo[0] <= q <= intervalo[1]


def anti_crowd_filters(nums):
    return (
        parity_ok(nums)
        and no_long_sequences(nums, MAX_SEQ)
        and decade_ok(nums)
        and (exige_acima_31_fn(nums) if EXIGE_ACIMA_31 else True)
        and last_digit_ok(nums)
    )


def inclui_atrasado_se_preciso(nums, ult=set(), intervalo=(0, 2), atrasados=set(), p_inc=0.25):
    """Tenta incluir 1 atrasado substituindo algum número, mantendo restrições."""
    if not atrasados or p_inc <= 0:
        return nums
    if random.random() <= p_inc:
        candidatos = list(atrasados - set(nums))
        random.shuffle(candidatos)
        for a in candidatos:
            cand = set(nums)
            rem = random.choice(list(cand))
            cand.remove(rem)
            cand.add(a)
            cand = tuple(sorted(cand))
            if valida_posicoes_first6(cand) and anti_crowd_filters(cand) and repete_ultimo_ok(cand, intervalo, ult):
                return cand
    return nums


def gera_candidato(tam_jogo=6, ult=set(), intervalo=(0, 2), atrasados=set(), p_inc=0.25):
    """Gera um bilhete com tam_jogo (6..15) respeitando filtros."""
    for _ in range(4000):
        nums = sorted(random.sample(range(1, 61), tam_jogo))
        if not valida_posicoes_first6(nums):
            continue
        if not anti_crowd_filters(nums):
            continue
        if not repete_ultimo_ok(nums, intervalo, ult):
            continue
        nums = inclui_atrasado_se_preciso(nums, ult, intervalo, atrasados, p_inc)
        if not repete_ultimo_ok(nums, intervalo, ult):
            continue
        if not anti_crowd_filters(nums):
            continue
        return tuple(nums)
    return None


def score_interno(nums):
    """Critérios suaves internos: gaps + cobertura de décadas + balanço de paridade."""
    s = sorted(nums)
    gaps = sum(s[i + 1] - s[i] for i in range(len(s) - 1))
    decade_cov = len(set((x - 1) // 10 for x in s))
    ev = sum(1 for x in s if x % 2 == 0)
    parity_balance = -abs(ev - (len(s) / 2))
    return gaps + 3 * decade_cov + parity_balance


def ganho_cobertura(selecionados, cand):
    """Greedy: maximiza novas trincas e pares únicos frente ao conjunto já selecionado."""
    pares_sel, trincas_sel = set(), set()
    for t in selecionados:
        pares_sel.update(combinations(t, 2))
        trincas_sel.update(combinations(t, 3))
    novos_pares = set(combinations(cand, 2)) - pares_sel
    novas_trincas = set(combinations(cand, 3)) - trincas_sel
    overlap_pairs = comb(len(cand), 2) - len(novos_pares)
    overlap_trinc = comb(len(cand), 3) - len(novas_trincas)
    score = 3 * len(novas_trincas) + 1.2 * len(novos_pares) - 0.5 * (overlap_pairs + 0.2 * overlap_trinc)
    score += 0.01 * score_interno(cand)
    return score


def gerar_n_jogos(n, tam_jogo=6, ult=set(), intervalo=(0, 2), atrasados=set(), p_inc=0.25, pool_max=600, tentativas_max=50000):
    """Gera N bilhetes de tamanho tam_jogo (6..15) usando seleção por cobertura."""
    pool, tentativas = set(), 0
    while len(pool) < pool_max and tentativas < tentativas_max:
        c = gera_candidato(tam_jogo=tam_jogo, ult=ult, intervalo=intervalo, atrasados=atrasados, p_inc=p_inc)
        tentativas += 1
        if c:
            pool.add(c)
    pool = list(pool)
    if not pool:
        raise RuntimeError("Pool vazio. Afrouxe filtros ou aumente tentativas.")

    pool.sort(key=score_interno, reverse=True)
    selec = [pool.pop(0)]
    while len(selec) < n and pool:
        melhor, melhor_sc = None, -1e9
        amostra = pool if len(pool) < 250 else random.sample(pool, 250)
        for cand in amostra:
            sc = ganho_cobertura(selec, cand)
            if sc > melhor_sc:
                melhor_sc, melhor = sc, cand
        selec.append(melhor)
        pool.remove(melhor)
    return selec


def cobertura_metricas(jogos):
    pares, trincas = set(), set()
    for j in jogos:
        pares.update(combinations(j, 2))
        trincas.update(combinations(j, 3))
    return len(pares), len(trincas)


def cobertura_teorica_max(n, tam_jogo):
    """Máximo teórico de pares/trincas sem overlap: min(n*C(m,k), C(60,k))."""
    max_pairs = min(n * comb(tam_jogo, 2), comb(60, 2))
    max_trincs = min(n * comb(tam_jogo, 3), comb(60, 3))
    return max_pairs, max_trincs


def simula_sorteios_multiplos(jogos, n_sims=100_000):
    """
    Simulação Monte Carlo correta para apostas múltiplas:
    Para um bilhete de m dezenas e um sorteio S (6 dezenas), se k=|bilhete ∩ S|:
      - Senas:  C(k,6)
      - Quinas: C(k,5) * C(m-k,1)
      - Quadras: C(k,4) * C(m-k,2)
    Retorna médias por bilhete/por sorteio.
    """
    from collections import defaultdict
    m = len(jogos[0]) if jogos else 6
    acc = defaultdict(float)
    for _ in range(n_sims):
        sorteio = set(random.sample(range(1, 61), 6))
        for js in jogos:
            k = len(set(js) & sorteio)
            acc["senas"] += comb(k, 6)
            acc["quinas"] += comb(k, 5) * comb(m - k, 1) if m - k >= 1 else 0
            acc["quadras"] += comb(k, 4) * comb(m - k, 2) if m - k >= 2 else 0
    total_bilhetes = n_sims * len(jogos) if jogos else 1
    return {
        "freq_quadras": acc["quadras"] / total_bilhetes,
        "freq_quinas": acc["quinas"] / total_bilhetes,
        "freq_senas": acc["senas"] / total_bilhetes,
    }


def montar_resumo_df(jogos, ult, intervalo, atrasados, prob_atrasado, pares_u, trincas_u, sim_result=None, seed=None, tam_jogo=6, status_ultimo=""):
    """Monta um DataFrame de 1 linha com o resumo do lote gerado."""
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sim_quadras = sim_result.get("freq_quadras") if sim_result else None
    sim_quinas = sim_result.get("freq_quinas") if sim_result else None
    sim_senas = sim_result.get("freq_senas") if sim_result else None
    return pd.DataFrame([
        {
            "DataHora": data_hora,
            "App": APP_VERSAO,
            "Tam_Jogo": tam_jogo,
            "Qtde_Jogos": len(jogos),
            "Pares_Unicos": pares_u,
            "Trincas_Unicas": trincas_u,
            "Usou_Ultimo": bool(ult),
            "Status_Ultimo": status_ultimo,
            "Ultimo_Resultado": ",".join(f"{x:02d}" for x in sorted(ult)) if ult else "",
            "Restricao_Repeticao": f"{intervalo[0]}–{intervalo[1]}",
            "Atrasados": ",".join(str(x) for x in sorted(atrasados)) if atrasados else "",
            "Prob_Incluir_Atrasado": prob_atrasado,
            "Seed": seed,
            "Sim_Quadras_freq": sim_quadras,
            "Sim_Quinas_freq": sim_quinas,
            "Sim_Senas_freq": sim_senas,
        }
    ])


def excel_bytes_duas_abas(df_jogos: pd.DataFrame, resumo_df: pd.DataFrame) -> bytes:
    """Gera bytes .xlsx com duas abas: JOGOS e RESUMO."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df_jogos.to_excel(w, index=False, sheet_name="JOGOS")
        resumo_df.to_excel(w, index=False, sheet_name="RESUMO")
    return buf.getvalue()

# ============================
# LOGIN (SIMPLES)
# ============================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title(f"🔒 Acesso — {APP_NOME}")
    senha = st.text_input("Digite a senha", type="password")
    col1, _ = st.columns([1, 6])
    with col1:
        if st.button("Entrar"):
            if senha == SENHA_CORRETA:
                st.session_state.autenticado = True
                st.success("Autenticado com sucesso!")
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()

# ============================
# INTERFACE PRINCIPAL
# ============================
st.title(f"🎯 {APP_NOME} (Web)")
st.caption(f"© Alirio Rocha — {APP_VERSAO} — uso pessoal. Lógica privada no seu PC.")

# Botão Sair (logout)
col_logout, _ = st.columns([1, 6])
with col_logout:
    if st.button("Sair"):
        st.session_state.autenticado = False
        st.rerun()

with st.expander("⚙️ Parâmetros", expanded=True):
    tam_jogo = st.number_input("Tamanho do jogo (6 a 15 dezenas)", min_value=6, max_value=15, value=6, step=1)
    qtd_jogos = st.number_input("Quantidade de jogos", 1, 30, 6, step=1)

    usar_ultimo = st.checkbox("Usar último resultado da CAIXA", value=True)
    c1, c2 = st.columns(2)
    with c1:
        faixa_min = st.number_input("Repetição mínima do último concurso", 0, 6, 0, step=1)
    with c2:
        faixa_max = st.number_input("Repetição máxima do último concurso", 0, 6, 2, step=1)

    atrasados_str = st.text_input("Atrasados (ex: 7,28,39)", "")
    prob_atrasado = st.slider("Probabilidade de incluir 1 atrasado", 0.0, 1.0, 0.25, 0.05)

    seed = st.number_input("Semente (0 = aleatório)", min_value=0, max_value=999_999, value=0, step=1)
    salvar_historico = st.checkbox("Salvar também no histórico local (CSV)", value=False)

    simular = st.checkbox("Rodar simulação Monte Carlo (pode demorar)", value=False)
    n_sims = st.number_input("Nº de sorteios na simulação", 1_000, 200_000, 50_000, step=5_000)

if st.button("🚀 GERAR JOGOS", use_container_width=True):
    # Seed (reprodutibilidade)
    if seed and int(seed) > 0:
        random.seed(int(seed))

    # Último resultado
    ult = ler_ultimo_resultado_caixa() if usar_ultimo else set()
    status_ultimo = "Não usado"
    if usar_ultimo:
        if ult:
            status_ultimo = "OK — último resultado obtido"
            st.success(f"Último resultado lido: {', '.join(f'{x:02d}' for x in sorted(ult))}")
        else:
            status_ultimo = "Falhou — seguindo sem restrição"
            st.warning("Não foi possível obter o último resultado agora. Seguindo sem essa restrição.")

    # Mostrar badge fixo de status
    st.info(f"📌 Status (último resultado): {status_ultimo}")

    intervalo = (min(faixa_min, faixa_max), max(faixa_min, faixa_max))

    atrasados = set()
    if atrasados_str.strip():
        try:
            atrasados = {int(x.strip()) for x in atrasados_str.split(",") if x.strip()}
        except Exception:
            st.warning("Não foi possível interpretar os atrasados. Use formato 7,28,39.")

    # Geração
    try:
        jogos = gerar_n_jogos(
            n=int(qtd_jogos),
            tam_jogo=int(tam_jogo),
            ult=ult,
            intervalo=intervalo,
            atrasados=atrasados,
            p_inc=float(prob_atrasado),
        )
    except RuntimeError as e:
        st.error(str(e))
        st.stop()

    st.subheader("🎟 Jogos Gerados")
    for i, j in enumerate(jogos, 1):
        st.write(f"**Jogo {i}:**", " ".join(f"{x:02d}" for x in sorted(j)))

    # Cobertura
    pares_u, trincas_u = cobertura_metricas(jogos)
    max_pairs, max_trincs = cobertura_teorica_max(int(qtd_jogos), int(tam_jogo))
    perc_pairs = (pares_u / max_pairs * 100) if max_pairs else 0
    perc_trincs = (trincas_u / max_trincs * 100) if max_trincs else 0
    st.write(
        f"**Cobertura:** {pares_u} pares únicos (máx teórico ~ {int(max_pairs)}; {perc_pairs:.1f}%) — "
        f"{trincas_u} trincas únicas (máx teórico ~ {int(max_trincs)}; {perc_trincs:.1f}%)"
    )

    # Simulação (para apostas múltiplas com contagem correta)
    sim_result = None
    if simular:
        with st.spinner("Rodando simulação..."):
            sim_result = simula_sorteios_multiplos(jogos, int(n_sims))
        st.write("**Simulação (média de prêmios por bilhete por sorteio):**")
        st.json(sim_result)

    # DataFrame de jogos
    df = pd.DataFrame([
        {"Jogo": i + 1, **{f"N{k}": f"{n:02d}" for k, n in enumerate(sorted(j), start=1)}}
        for i, j in enumerate(jogos)
    ])

    # RESUMO
    resumo_df = montar_resumo_df(
        jogos=jogos,
        ult=ult,
        intervalo=intervalo,
        atrasados=atrasados,
        prob_atrasado=prob_atrasado,
        pares_u=pares_u,
        trincas_u=trincas_u,
        sim_result=sim_result,
        seed=seed if seed else None,
        tam_jogo=int(tam_jogo),
        status_ultimo=status_ultimo,
    )

    # 📋 Bloco de texto para copiar
    texto_jogos = "\n".join(
        [f"Jogo {i}: " + " ".join(f'{x:02d}' for x in sorted(j)) for i, j in enumerate(jogos, 1)]
    )
    st.text_area("📋 Copiar jogos", value=texto_jogos, height=180)

    # 📥 Downloads
    st.download_button(
        "📥 Baixar CSV (JOGOS)",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"alirio_mega_{datetime.now().strftime('%Y-%m-%d')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    excel_bytes_out = excel_bytes_duas_abas(df, resumo_df)
    st.download_button(
        "📥 Baixar Excel (.xlsx) — JOGOS + RESUMO",
        data=excel_bytes_out,
        file_name=f"alirio_mega_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    # 🗂️ Histórico local (CSV)
    if salvar_historico:
        # 1) JOGOS
        jogos_csv = "historico_jogos.csv"
        df_out = df.copy()
        df_out.insert(0, "DataHora", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        df_out.insert(1, "Seed", seed if seed else None)
        df_out.insert(2, "Tam_Jogo", int(tam_jogo))
        if not os.path.exists(jogos_csv):
            df_out.to_csv(jogos_csv, index=False, encoding="utf-8")
        else:
            df_out.to_csv(jogos_csv, index=False, encoding="utf-8", mode="a", header=False)

        # 2) RESUMO
        resumo_csv = "historico_resumo.csv"
        if not os.path.exists(resumo_csv):
            resumo_df.to_csv(resumo_csv, index=False, encoding="utf-8")
        else:
            resumo_df.to_csv(resumo_csv, index=False, encoding="utf-8", mode="a", header=False)

        st.success("Histórico atualizado: 'historico_jogos.csv' e 'historico_resumo.csv'.")

# Sidebar com status
with st.sidebar:
    st.markdown("### Status")
    # Nota: 'ult' só existe após clicar GERAR; mostramos mensagem informativa
    st.write("Use o botão 'GERAR JOGOS' para atualizar o status.")
