import streamlit as st
import pandas as pd
import random
import json
import os
from itertools import combinations
from io import BytesIO
from math import comb

# ============================
# CONFIGURAÇÕES E META
# ============================
APP_VERSAO = "Alirio v3 (posicional)"
APP_NOME = f"Gerador — {APP_VERSAO}"

# Se quiser usar variável de ambiente no Render, troque pela linha abaixo:
# SENHA_CORRETA = os.getenv("APP_PASSWORD", "2802")
SENHA_CORRETA = "2802"

st.set_page_config(page_title=APP_NOME, page_icon="🎯", layout="centered")

# ============================
# PARÂMETROS DA LÓGICA
# ============================
POS_RANGES = {1: (1, 20), 2: (15, 30), 3: (20, 40), 4: (30, 50), 5: (40, 58), 6: (50, 60)}
EXIGE_ACIMA_31 = True

# ============================
# FUNÇÕES UTILITÁRIAS
# ============================
def ler_ultimo_resultado_caixa():
    """Busca o último resultado na API da CAIXA."""
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
    except:
        return set()

# ---------- Faixas por posição dinâmicas ----------
def pos_ranges_for_m(m: int):
    """Gera faixas por posição quando m > 6 (mais elásticas)."""
    ranges = {}
    for i in range(1, 7):
        target = int(round(i * 60 / (m + 1)))
        lo = max(1, target - 12)
        hi = min(60, target + 12)
        ranges[i] = (lo, hi)
    return ranges

def valida_posicoes_first6(nums, m):
    """Valida as 6 primeiras posições do conjunto ordenado."""
    s = sorted(nums)
    if len(s) < 6:
        return False
    faixas = POS_RANGES if m == 6 else pos_ranges_for_m(m)
    for i, x in enumerate(s[:6], start=1):
        lo, hi = faixas[i]
        if not (lo <= x <= hi):
            return False
    return True

# --- Validação posicional (leve): 1ª ∈ [1,9] e 2ª ∈ [10,19] ---
def valida_primeiras_duas_posicoes(nums):
    s = sorted(nums)
    if len(s) < 2:
        return False
    return (1 <= s[0] <= 9) and (10 <= s[1] <= 19)

# ---------- Paridade, década, dígito ----------
def parity_ok(nums):
    m = len(nums)
    ev = sum(1 for x in nums if x % 2 == 0)
    return abs(ev - (m / 2)) <= 1

def max_seq_for_m(m: int):
    if m <= 12:
        return 2
    elif m <= 16:
        return 3
    else:
        return 4

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

def _limit_por_m(m: int):
    if m <= 8:
        return 2
    elif m <= 12:
        return 3
    elif m <= 16:
        return 4
    else:
        return 5

def decade_ok(nums):
    m = len(nums)
    limit = _limit_por_m(m)
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
    m = len(nums)
    limit = _limit_por_m(m)
    units = {}
    for x in nums:
        u = x % 10
        units[u] = units.get(u, 0) + 1
        if units[u] > limit:
            return False
    return True

def repete_ultimo_ok(nums, intervalo, ult=set()):
    if not ult:
        return True
    q = sum(1 for x in nums if x in ult)
    return intervalo[0] <= q <= intervalo[1]

def anti_crowd_filters(nums, m):
    return (
        parity_ok(nums)
        and no_long_sequences(nums, max_len=max_seq_for_m(m))
        and decade_ok(nums)
        and (exige_acima_31_fn(nums) if EXIGE_ACIMA_31 else True)
        and last_digit_ok(nums)
    )

def inclui_atrasado_se_preciso(nums, ult=set(), intervalo=(0, 2), atrasados=set(), p_inc=0.25, m=6):
    """Com p_inc, tenta substituir 1 dezena por um atrasado, mantendo filtros."""
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
            if valida_posicoes_first6(cand, m) and anti_crowd_filters(cand, m) and repete_ultimo_ok(cand, intervalo, ult):
                return cand
    return nums

# ---------- Scorers ----------
def score_interno(nums):
    s = sorted(nums)
    gaps = sum(s[i + 1] - s[i] for i in range(len(s) - 1))
    decade_cov = len(set((x - 1) // 10 for x in s))
    ev = sum(1 for x in s if x % 2 == 0)
    parity_balance = -abs(ev - (len(s) / 2))
    return gaps + 3 * decade_cov + parity_balance

def ganho_cobertura(selecionados, cand):
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

# ---------- Geração ----------
def gera_candidato(tam_jogo=6, ult=set(), intervalo=(0, 2), atrasados=set(), p_inc=0.25, trava_1e2=False):
    for _ in range(4000):
        nums = sorted(random.sample(range(1, 61), tam_jogo))

        # Travas posicionais (leves)
        if trava_1e2 and not valida_primeiras_duas_posicoes(nums):
            continue

        # Filtros
        if not valida_posicoes_first6(nums, tam_jogo):
            continue
        if not anti_crowd_filters(nums, tam_jogo):
            continue
        if not repete_ultimo_ok(nums, intervalo, ult):
            continue

        # Tentativa de incluir atrasado
        nums = inclui_atrasado_se_preciso(nums, ult, intervalo, atrasados, p_inc, m=tam_jogo)

        # Revalida
        if not repete_ultimo_ok(nums, intervalo, ult):
            continue
        if not anti_crowd_filters(nums, tam_jogo):
            continue
        return tuple(nums)
    return None

def gerar_n_jogos(n, tam_jogo=6, ult=set(), intervalo=(0, 2),
                  atrasados=set(), p_inc=0.25, pool_max=600, tentativas_max=50000,
                  trava_1e2=False):

    if tam_jogo > 15:
        pool_max = max(pool_max, 1000)
        tentativas_max = max(tentativas_max, 120000)

    pool, tentativas = set(), 0
    while len(pool) < pool_max and tentativas < tentativas_max:
        c = gera_candidato(
            tam_jogo=tam_jogo,
            ult=ult,
            intervalo=intervalo,
            atrasados=atrasados,
            p_inc=p_inc,
            trava_1e2=trava_1e2
        )
        tentativas += 1
        if c:
            pool.add(c)

    if not pool:
        raise RuntimeError("Pool vazio. Afrouxe filtros ou aumente tentativas.")

    pool = list(pool)
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

# ---------- Cobertura ----------
def cobertura_metricas(jogos):
    pares, trincas = set(), set()
    for j in jogos:
        pares.update(combinations(j, 2))
        trincas.update(combinations(j, 3))
    return len(pares), len(trincas)

def cobertura_teorica_max(n, tam_jogo):
    max_pairs  = min(n * comb(tam_jogo, 2), comb(60, 2))
    max_trincs = min(n * comb(tam_jogo, 3), comb(60, 3))
    return max_pairs, max_trincs

# ---------- Simulação ----------
def simula_sorteios_multiplos(jogos, n_sims=50000):
    from collections import defaultdict
    m = len(jogos[0])
    acc = defaultdict(float)
    for _ in range(n_sims):
        sorteio = set(random.sample(range(1, 61), 6))
        for js in jogos:
            k = len(set(js) & sorteio)
            acc["senas"]  += comb(k, 6)
            acc["quinas"] += comb(k, 5) * comb(m - k, 1) if m - k >= 1 else 0
            acc["quadras"]+= comb(k, 4) * comb(m - k, 2) if m - k >= 2 else 0
    tot = n_sims * len(jogos)
    return {
        "freq_quadras": acc["quadras"] / tot,
        "freq_quinas":  acc["quinas"]  / tot,
        "freq_senas":   acc["senas"]   / tot,
    }

# ---------- Excel ----------
def excel_bytes_duas_abas(df_jogos: pd.DataFrame, resumo_df: pd.DataFrame):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df_jogos.to_excel(w, index=False, sheet_name="JOGOS")
        resumo_df.to_excel(w, index=False, sheet_name="RESUMO")
    return buf.getvalue()

# ============================
# INTERFACE
# ============================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title(f"🔒 Acesso — {APP_NOME}")
    senha = st.text_input("Digite a senha", type="password")
    if st.button("Entrar"):
        if senha == SENHA_CORRETA:
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.stop()

st.title(f"🎯 {APP_NOME} (Web)")
st.caption(f"© Alirio Rocha — {APP_VERSAO} — uso pessoal.")

with st.expander("⚙️ Parâmetros", expanded=True):
    tam_jogo = st.number_input("Tamanho do jogo (6 a 20 dezenas)", 6, 20, 6, 1)
    qtd_jogos = st.number_input("Quantidade de jogos", 1, 30, 6)

    usar_ultimo = st.checkbox("Usar último resultado da CAIXA", True)

    # Entrada manual do último
    ultimo_manual = ""
    if not usar_ultimo:
        ultimo_manual = st.text_input("Digite o último resultado manualmente (ex: 05 14 20 33 42 56)")

    faixa_min = st.number_input("Repetição mínima", 0, 6, 0)
    faixa_max = st.number_input("Repetição máxima", 0, 6, 2)

    atrasados_str = st.text_input("Atrasados (ex: 7,28,39)")
    prob_atrasado = st.slider("Prob. de incluir atrasado", 0.0, 1.0, 0.25, 0.05)

    seed = st.number_input("Semente (0 = aleatório)", 0, 999999, 0)
    simular = st.checkbox("Rodar simulação Monte Carlo", False)

with st.expander("📊 Regras posicionais (leves)", expanded=False):
    usar_trava_1e2 = st.checkbox(
        "Travar 1ª posição em 1–9 e 2ª posição em 10–19",
        True  # ligado por padrão
    )
    st.caption("Sugestão: manter ligado para guiar o gerador sem travar o pool. Funciona para qualquer tamanho de jogo.")

# ----------------- BOTÕES -----------------
col1, col2 = st.columns(2)

with col1:
    gerar = st.button("🚀 GERAR JOGOS", use_container_width=True)
with col2:
    gerar_excel = st.button("📄 Gerar Excel (.xlsx)", use_container_width=True)

# ----------------- LÓGICA PRINCIPAL -----------------
def obter_ultimo(usar_ultimo, ultimo_manual_str):
    """Retorna set() com 6 dezenas do último resultado (API ou Manual)."""
    if usar_ultimo:
        return ler_ultimo_resultado_caixa()
    # Manual
    if ultimo_manual_str.strip():
        try:
            numeros = (
                ultimo_manual_str.replace(",", " ")
                                 .replace("-", " ")
                                 .split()
            )
            u = {int(x) for x in numeros}
            if len(u) != 6 or not all(1 <= x <= 60 for x in u):
                st.warning("Digite exatamente 6 dezenas válidas (1..60).")
                return set()
            return u
        except:
            st.warning("Não foi possível interpretar o último resultado manual.")
            return set()
    return set()

# Mantém resultados do último clique para permitir gerar Excel depois
if "ultimo_jogos_df" not in st.session_state:
    st.session_state.ultimo_jogos_df = None
if "ultimo_resumo_df" not in st.session_state:
    st.session_state.ultimo_resumo_df = None

if gerar or gerar_excel:
    if seed > 0:
        random.seed(seed)

    # Último: API ou Manual
    ult = obter_ultimo(usar_ultimo, ultimo_manual)

    if usar_ultimo:
        if ult:
            st.success(f"Último resultado (API): {sorted(ult)}")
        else:
            st.warning("Não foi possível obter o último resultado via API.")
    else:
        if ult:
            st.success(f"Último resultado (manual): {sorted(ult)}")
        else:
            st.info("Usando sem referência de último resultado.")

    intervalo = (min(faixa_min, faixa_max), max(faixa_min, faixa_max))

    atrasados = set()
    if atrasados_str.strip():
        try:
            atrasados = {int(x.strip()) for x in atrasados_str.split(",")}
        except:
            st.warning("Não foi possível interpretar atrasados.")

    # Se o clique foi para Gerar Jogos (ou também Gerar Excel, pois precisa dos jogos)
    try:
        jogos = gerar_n_jogos(
            n=qtd_jogos,
            tam_jogo=tam_jogo,
            ult=ult,
            intervalo=intervalo,
            atrasados=atrasados,
            p_inc=prob_atrasado,
            trava_1e2=usar_trava_1e2,
        )
    except RuntimeError as e:
        st.error(str(e))
        st.stop()

    st.subheader("🎟 Jogos Gerados")
    for i, j in enumerate(jogos, 1):
        st.write(f"**Jogo {i}:**", " ".join(f"{x:02d}" for x in j))

    pares_u, trincas_u = cobertura_metricas(jogos)
    max_pairs, max_trincs = cobertura_teorica_max(qtd_jogos, tam_jogo)
    st.write(f"**Cobertura:** {pares_u} pares únicos (máx={max_pairs}) — {trincas_u} trincas únicas (máx={max_trincs})")

    if simular:
        st.info("Simulando, aguarde...")
        sim = simula_sorteios_multiplos(jogos)
        st.json(sim)

    # DataFrames
    df = pd.DataFrame([
        {"Jogo": i + 1, **{f"N{k}": f"{n:02d}" for k, n in enumerate(j, start=1)}}
        for i, j in enumerate(jogos)
    ])
    resumo_df = pd.DataFrame([{
        "Tamanho": tam_jogo,
        "Quantidade": qtd_jogos,
        "Pares_Unicos": pares_u,
        "Trincas_Unicas": trincas_u
    }])

    # Guarda para possível Excel
