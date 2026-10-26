"""
================================================================================
GENERADOR DE DATOS SINTÉTICOS DE FRAUDE - TRANSFERENCIAS SPI (SIPAP/QR)  v2
================================================================================
Alcance: Transferencias instantáneas SPI del lado emisor.
Límite regulatorio: ₲ 10.000.000 por transacción (BCP, marzo 2026).
Monto mínimo: ₲ 1.000.

Archivos que genera (en ./data):
  - dataset_completo.csv : todo + timestamp + escenario_fraude (SOLO ANÁLISIS,
                           NO usar como features).
  - train.csv / valid.csv / test.csv : split cronológico 60/20/20, solo
                           features + es_fraude (listos para XGBoost).

Cambios respecto a v1:
  * escenario_fraude y timestamp ya NO están en train/valid/test (fuga de etiqueta).
  * Crea la carpeta data/ si no existe.
  * Generación vectorizada (segundos en vez de minutos).
  * Conteos consistentes: tx_5min <= tx_1h <= tx_24h (incluyen la tx actual,
    por lo que el mínimo es 1) y unique_beneficiaries_24h <= tx_24h.
  * Montos acumulados consistentes: monto <= amount_sum_1h <= amount_sum_24h.
  * El promedio histórico del usuario se genera PRIMERO y el monto después
    (antes el promedio dependía del monto actual).
  * Solapamiento entre clases: normales con ráfagas y con montos grandes
    legítimos; fraudes "sigilosos" idénticos a una tx normal; ruido en flags.
  * Mismas distribuciones de antigüedad para ambas clases (sin artefactos).
  * Sin acumulación artificial de montos en el tope de ₲ 10.000.000.
  * Orden cronológico estable (reproducible con timestamps repetidos).
================================================================================
"""

import os
import numpy as np
import pandas as pd

# ==============================================================================
# CONFIGURACIÓN GLOBAL
# ==============================================================================
SEED = 42
N_TOTAL = 1_000_000            # Total de transacciones
FRAUD_RATE = 0.003             # 0.3% de fraude (3.000 fraudes ~ 600/200/200 por split... ver verificación)
RUIDO_FRAUDE = 0.08            # prob. de invertir cada flag binario en fraudes
FRAUDE_SIGILOSO = 0.10         # % de fraudes indistinguibles de una tx normal
LIMITE_SPI = 10_000_000        # ₲ 10 millones (BCP, marzo 2026)
MONTO_MINIMO = 1_000           # ₲ 1.000
DIAS_SIMULACION = 90           # 3 meses de datos
FECHA_INICIO = pd.Timestamp("2026-01-01")
OUT_DIR = "data"

rng = np.random.default_rng(SEED)

COLS_EXCLUIR_DE_FEATURES = ["timestamp", "escenario_fraude"]

# Distribución de la hora del día
_h = np.arange(24)
_p = np.exp(-0.5 * ((_h - 14) / 4.5) ** 2) + 0.02
PROB_HORA_NORMAL = _p / _p.sum()
_n = ((_h < 6) | (_h >= 22)).astype(float)
PROB_HORA_NOCHE = _n / _n.sum()

# Escenarios de fraude (parámetros: lognormal = (mu, sigma))
ESCENARIOS = {
    "F1_toma_cuenta": dict(
        peso=0.30, p_noche=0.50, monto=(np.log(2_500_000), 0.7), ratio=(np.log(10), 0.6),
        redondo=0.60, disp=0.85, ubic=0.70, hatip=0.60, dest=0.90, velocidad="normal"),
    "F2_rafaga_salidas": dict(
        peso=0.30, p_noche=0.40, monto=(np.log(600_000), 0.7), ratio=(np.log(4), 0.5),
        redondo=0.50, disp=0.50, ubic=0.60, hatip=0.50, dest=0.70, velocidad="rafaga"),
    "F3_engano": dict(
        peso=0.25, p_noche=0.00, monto=(np.log(1_800_000), 0.7), ratio=(np.log(6), 0.5),
        redondo=0.30, disp=0.05, ubic=0.03, hatip=0.15, dest=0.95, velocidad="normal"),
    "F4_pruebas_pequenas": dict(
        peso=0.15, p_noche=0.40, monto=(np.log(60_000), 0.8), ratio=(np.log(1.3), 0.4),
        redondo=0.40, disp=0.60, ubic=0.40, hatip=0.50, dest=0.80, velocidad="pruebas"),
}


# ==============================================================================
# FUNCIONES AUXILIARES (todas vectorizadas)
# ==============================================================================
def gen_timestamps(n, p_noche=0.0):
    """Timestamps enteros (sin microsegundos). p_noche = prob. de forzar franja nocturna."""
    dia = rng.integers(0, DIAS_SIMULACION, n)
    hora = rng.choice(24, size=n, p=PROB_HORA_NORMAL)
    if p_noche > 0:
        m = rng.random(n) < p_noche
        hora[m] = rng.choice(24, size=int(m.sum()), p=PROB_HORA_NOCHE)
    segs = dia * 86400 + hora * 3600 + rng.integers(0, 60, n) * 60 + rng.integers(0, 60, n)
    return FECHA_INICIO + pd.to_timedelta(segs, unit="s")


def finalizar_monto(monto, prob_redondo):
    """Entero en [MONTO_MINIMO, LIMITE_SPI]; parte redondeado a miles.
    Lo que excede el límite se re-sortea (evita un pico artificial en el tope)."""
    monto = np.asarray(monto, dtype=float).copy()
    exceso = monto > LIMITE_SPI
    monto[exceso] = rng.uniform(0.3, 1.0, int(exceso.sum())) * LIMITE_SPI
    redondo = rng.random(len(monto)) < prob_redondo
    monto = np.where(redondo, np.round(monto / 1000) * 1000, np.floor(monto))
    return np.clip(monto, MONTO_MINIMO, LIMITE_SPI).astype(np.int64)


def velocidad_base(n, prob_rafaga=0.03):
    """Conteos de velocidad (incluyen la tx actual) con 5min <= 1h <= 24h.
    Un % de normales son 'ráfagas' legítimas (pagos múltiples el mismo día)."""
    lam = rng.gamma(2.0, 3.0, n)                       # actividad del usuario
    tx24 = 1 + rng.poisson(lam)
    tx1h = 1 + rng.binomial(tx24 - 1, 0.15)
    rafaga = rng.random(n) < prob_rafaga
    extra = rng.integers(2, 7, n) * rafaga
    tx24 = tx24 + extra
    tx1h = tx1h + extra
    tx5 = 1 + rng.binomial(tx1h - 1, np.where(rafaga, 0.5, 0.2))
    uniq = np.maximum(1, rng.binomial(tx24, 0.6))
    return tx5, tx1h, tx24, uniq


def acumulados(monto, tx1h, tx24, escala_prev):
    """amount_sum_1h y amount_sum_24h consistentes: monto <= sum_1h <= sum_24h."""
    n = len(monto)
    s1 = monto + (tx1h - 1) * escala_prev * rng.uniform(0.5, 1.5, n)
    s24 = s1 + (tx24 - tx1h) * escala_prev * rng.uniform(0.5, 1.5, n)
    return np.floor(s1).astype(np.int64), np.floor(s24).astype(np.int64)


def bern(n, p):
    return (rng.random(n) < p).astype(int)


def ruido(x, prob=RUIDO_FRAUDE):
    flip = rng.random(len(x)) < prob
    return np.where(flip, 1 - x, x)


def armar_df(ts, monto, promedio, tx5, tx1h, tx24, s1, s24, uniq,
             disp, ubic, hatip, dest, antig, es_fraude, escenario):
    hora = np.asarray(ts.hour)
    dow = np.asarray(ts.dayofweek)
    dmes = np.asarray(ts.day)
    return pd.DataFrame({
        "timestamp": ts,
        "monto_pyg": monto,
        "hora": hora,
        "es_fin_de_semana": (dow >= 5).astype(int),
        "es_fin_de_mes": (dmes >= 25).astype(int),
        "es_horario_nocturno": ((hora < 6) | (hora >= 22)).astype(int),
        "hora_atipica": hatip,
        "dispositivo_nuevo": disp,
        "ubicacion_inusual": ubic,
        "antiguedad_cuenta_dias": antig,
        "tx_count_5min": tx5,
        "tx_count_1h": tx1h,
        "tx_count_24h": tx24,
        "amount_sum_1h": s1,
        "amount_sum_24h": s24,
        "monto_promedio_usuario_30d": promedio,
        "ratio_monto_vs_promedio": np.round(monto / promedio, 4),
        "destinatario_nuevo": dest,
        "unique_beneficiaries_24h": uniq,
        "es_fraude": es_fraude,
        "escenario_fraude": escenario,
    })


# ==============================================================================
# 1. TRANSACCIONES NORMALES
# ==============================================================================
def generar_normales(n, etiqueta=0, escenario="normal"):
    ts = gen_timestamps(n)
    hora = np.asarray(ts.hour)
    nocturno = ((hora < 6) | (hora >= 22)).astype(int)

    # Promedio histórico del usuario PRIMERO; el monto se genera alrededor de él
    promedio = np.maximum(rng.lognormal(12.0, 1.1, n).astype(np.int64), MONTO_MINIMO)
    cola = rng.random(n) < 0.04                       # compras grandes legítimas
    ratio_obj = np.where(cola, rng.lognormal(np.log(3.5), 0.5, n), rng.lognormal(0.0, 0.45, n))
    monto = finalizar_monto(promedio * ratio_obj, 0.30)
    ratio = monto / promedio

    tx5, tx1h, tx24, uniq = velocidad_base(n)
    s1, s24 = acumulados(monto, tx1h, tx24, promedio.astype(float))

    # Flags con dependencias realistas (cambiar de celular -> ubicación nueva, etc.)
    grande = (ratio > 2.5).astype(float)
    disp = bern(n, 0.04 + 0.06 * grande)
    ubic = bern(n, 0.02 + 0.15 * disp)
    dest = bern(n, 0.08 + 0.12 * grande)
    hatip = bern(n, 0.03 + 0.12 * nocturno)
    antig = rng.integers(30, 3650, n)

    return armar_df(ts, monto, promedio, tx5, tx1h, tx24, s1, s24, uniq,
                    disp, ubic, hatip, dest, antig,
                    np.full(n, etiqueta), np.full(n, escenario, dtype=object))


# ==============================================================================
# 2. FRAUDES POR ESCENARIO
# ==============================================================================
def generar_fraude(esc, cfg, n):
    ts = gen_timestamps(n, cfg["p_noche"])

    monto = finalizar_monto(rng.lognormal(*cfg["monto"], n), cfg["redondo"])
    ratio_obj = rng.lognormal(*cfg["ratio"], n)
    promedio = np.maximum((monto / ratio_obj).astype(np.int64), MONTO_MINIMO)

    if cfg["velocidad"] == "normal":
        tx5, tx1h, tx24, uniq = velocidad_base(n)
        escala_prev = promedio.astype(float)
    elif cfg["velocidad"] == "rafaga":
        tx24 = 1 + rng.integers(10, 26, n)
        tx1h = np.minimum(rng.integers(6, 16, n), tx24)
        tx5 = np.minimum(rng.integers(3, 8, n), tx1h)
        uniq = np.maximum(1, np.minimum(rng.integers(4, 13, n), tx24))
        escala_prev = monto.astype(float)        # las salidas previas son similares
    else:  # pruebas
        tx24 = 1 + rng.integers(8, 21, n)
        tx1h = np.minimum(rng.integers(4, 11, n), tx24)
        tx5 = np.minimum(rng.integers(2, 7, n), tx1h)
        uniq = np.maximum(1, np.minimum(rng.integers(1, 5, n), tx24))
        escala_prev = monto.astype(float)

    s1, s24 = acumulados(monto, tx1h, tx24, escala_prev)

    disp = ruido(bern(n, cfg["disp"]))
    ubic = ruido(bern(n, cfg["ubic"]))
    hatip = ruido(bern(n, cfg["hatip"]))
    dest = ruido(bern(n, cfg["dest"]))
    antig = rng.integers(30, 3650, n)

    return armar_df(ts, monto, promedio, tx5, tx1h, tx24, s1, s24, uniq,
                    disp, ubic, hatip, dest, antig,
                    np.ones(n, dtype=int), np.full(n, esc, dtype=object))


# ==============================================================================
# 3. ENSAMBLAR, ORDENAR CRONOLÓGICAMENTE Y SEPARAR 60/20/20
# ==============================================================================
n_fraudes = int(N_TOTAL * FRAUD_RATE)
n_normales = N_TOTAL - n_fraudes

print(f"Generando {n_normales:,} transacciones normales...")
df_normal = generar_normales(n_normales)

print(f"Generando {n_fraudes:,} transacciones fraudulentas...")
pesos = np.array([c["peso"] for c in ESCENARIOS.values()])
conteos = rng.multinomial(n_fraudes, pesos / pesos.sum())

partes = []
for (esc, cfg), n_esc in zip(ESCENARIOS.items(), conteos):
    n_sig = int((rng.random(n_esc) < FRAUDE_SIGILOSO).sum())   # fraudes que parecen normales
    partes.append(generar_fraude(esc, cfg, n_esc - n_sig))
    if n_sig > 0:
        partes.append(generar_normales(n_sig, etiqueta=1, escenario=esc))
df_fraude = pd.concat(partes, ignore_index=True)

df = pd.concat([df_normal, df_fraude], ignore_index=True)
df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)

df_features = df.drop(columns=COLS_EXCLUIR_DE_FEATURES)

n = len(df_features)
train_end = int(n * 0.60)
valid_end = int(n * 0.80)
train_df = df_features.iloc[:train_end].copy()
valid_df = df_features.iloc[train_end:valid_end].copy()
test_df = df_features.iloc[valid_end:].copy()

# ==============================================================================
# 4. VERIFICACIONES DE CALIDAD
# ==============================================================================
print("\n" + "=" * 65)
print("VERIFICACIÓN DE DISTRIBUCIÓN")
print("=" * 65)
for name, subset in [("Train (60%)", train_df), ("Valid (20%)", valid_df), ("Test (20%)", test_df)]:
    nf = int(subset["es_fraude"].sum())
    print(f"{name:12} | {len(subset):>9,} filas | {nf:>5} fraudes ({subset['es_fraude'].mean()*100:.3f}%)")
    if nf == 0:
        raise ValueError(f"ERROR CRÍTICO: {name} no tiene fraudes.")

print("\n" + "=" * 65)
print("VERIFICACIÓN DE CONSISTENCIA")
print("=" * 65)
checks = {
    "sin fuga: escenario_fraude/timestamp fuera de train/valid/test":
        not any(c in d.columns for d in (train_df, valid_df, test_df) for c in COLS_EXCLUIR_DE_FEATURES),
    "tx_5min <= tx_1h <= tx_24h":
        bool(((df.tx_count_5min <= df.tx_count_1h) & (df.tx_count_1h <= df.tx_count_24h)).all()),
    "tx_5min >= 1": bool((df.tx_count_5min >= 1).all()),
    "unique_beneficiaries_24h <= tx_24h":
        bool((df.unique_beneficiaries_24h <= df.tx_count_24h).all()),
    "monto <= sum_1h <= sum_24h":
        bool(((df.monto_pyg <= df.amount_sum_1h) & (df.amount_sum_1h <= df.amount_sum_24h)).all()),
    "monto en [1.000, 10.000.000]":
        bool(df.monto_pyg.between(MONTO_MINIMO, LIMITE_SPI).all()),
    "sin nulos": not bool(df.isna().any().any()),
    "sin microsegundos": not bool((df.timestamp.dt.microsecond != 0).any()),
}
for k, v in checks.items():
    print(f"  [{'OK' if v else 'FALLA'}] {k}")
if not all(checks.values()):
    raise ValueError("Falló al menos una verificación de consistencia.")

print(f"\nMonto mín / medio / máx: ₲ {df.monto_pyg.min():,.0f} / {df.monto_pyg.mean():,.0f} / {df.monto_pyg.max():,.0f}")
print(f"Montos exactamente en el tope: {(df.monto_pyg == LIMITE_SPI).mean()*100:.3f}%")
print("\nRatio monto/promedio (cuantiles 50/90/99):")
for lbl, sub in [("normales", df[df.es_fraude == 0]), ("fraudes", df[df.es_fraude == 1])]:
    q = sub.ratio_monto_vs_promedio.quantile([0.5, 0.9, 0.99]).round(2).tolist()
    print(f"  {lbl:9}: {q}")

print("\n" + "=" * 65)
print("DISTRIBUCIÓN DE ESCENARIOS DE FRAUDE")
print("=" * 65)
print(df[df.es_fraude == 1]["escenario_fraude"].value_counts().to_string())

# ==============================================================================
# 5. GUARDAR ARCHIVOS
# ==============================================================================
os.makedirs(OUT_DIR, exist_ok=True)
df.to_csv(f"{OUT_DIR}/dataset_completo.csv", index=False)
train_df.to_csv(f"{OUT_DIR}/train.csv", index=False)
valid_df.to_csv(f"{OUT_DIR}/valid.csv", index=False)
test_df.to_csv(f"{OUT_DIR}/test.csv", index=False)

print("\n" + "=" * 65)
print("ARCHIVOS GENERADOS en ./" + OUT_DIR)
print("=" * 65)
print(f"  dataset_completo.csv  ({len(df):,} filas, incluye timestamp y escenario)")
print(f"  train.csv             ({len(train_df):,} filas)")
print(f"  valid.csv             ({len(valid_df):,} filas)")
print(f"  test.csv              ({len(test_df):,} filas)")
print("=" * 65)