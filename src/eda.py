#!/usr/bin/env python3
"""
EDA y chequeo de calidad del dataset de transacciones (detección de fraude).

Lee  ./transacciones_completo.csv  (carpeta raíz) y genera en ./eda_output/:
  - reporte_calidad.txt        (chequeos de calidad, balance, outliers, poder discriminante)
  - 01..10_*.png               (gráficos de distribución)

Uso:
    pip install pandas numpy matplotlib
    python eda.py
    python eda.py --input otra_ruta.csv --out carpeta_salida
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

C_LEGIT, C_FRAUD = "#2a7ab9", "#d62728"
ESCENARIOS = ["ninguno", "toma_cuenta", "vaciado_fraccionado", "ingenieria_social"]

CONTINUAS = ["monto_pyg", "monto_promedio_usuario_30d", "ratio_monto_vs_promedio",
             "amount_sum_1h", "amount_sum_24h", "tx_count_1h", "tx_count_24h",
             "distancia_zona_habitual_km", "antiguedad_cuenta_dias"]
LOG_SCALE = {"monto_pyg", "monto_promedio_usuario_30d", "ratio_monto_vs_promedio",
             "amount_sum_1h", "amount_sum_24h", "tx_count_1h", "tx_count_24h",
             "distancia_zona_habitual_km"}
BINARIAS = ["es_fin_de_semana", "es_horario_nocturno", "hora_atipica",
            "dispositivo_nuevo", "ip_nueva", "is_new_beneficiary"]
FEATURES = ["hora_sin", "hora_cos"] + BINARIAS + CONTINUAS

plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True,
                     "grid.alpha": 0.25, "font.size": 9})


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def guardar(fig, out, nombre):
    ruta = os.path.join(out, nombre)
    fig.tight_layout()
    fig.savefig(ruta, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {ruta}")


def transformar(serie, nombre):
    return np.log1p(serie) if nombre in LOG_SCALE else serie


def auc_univariante(x, y):
    """AUC de una variable sola vs. la etiqueta (vía rangos, sin scipy)."""
    m = x.notna()
    x, y = x[m], y[m]
    n1, n0 = int(y.sum()), int((1 - y).sum())
    if n1 == 0 or n0 == 0:
        return np.nan
    r = x.rank(method="average")
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


# --------------------------------------------------------------------------- #
# Reporte de calidad (texto)
# --------------------------------------------------------------------------- #
def reporte_calidad(df, out):
    lineas = []

    def p(s=""):
        print(s)
        lineas.append(s)

    def chequeo(nombre, n_malos):
        p(f"  [{'OK ' if n_malos == 0 else 'FALLA'}] {nombre}: {n_malos:,} filas")

    n, y = len(df), df["es_fraude"]
    p("=" * 70)
    p("REPORTE DE CALIDAD DEL DATASET")
    p("=" * 70)
    p(f"Filas: {n:,} | Columnas: {df.shape[1]}")
    p(f"Período: {df['fecha_hora'].min()}  ->  {df['fecha_hora'].max()}")
    p(f"Cuentas emisoras únicas: {df['id_cuenta_emisor'].nunique():,} | "
      f"dispositivos: {df['id_dispositivo_emisor'].nunique():,} | "
      f"IPs: {df['direccion_ip_emisor'].nunique():,}")

    p("\n1) BALANCE DE CLASES")
    n_f = int(y.sum())
    p(f"  Legítimas: {n - n_f:,} | Fraudes: {n_f:,} ({y.mean():.4%}) "
      f"| ratio ~ 1:{(n - n_f) / max(n_f, 1):,.0f}")
    if n_f < 100:
        p("  [ADVERTENCIA] Pocos fraudes (<100): las métricas serán muy ruidosas.")
    if "escenario_fraude" in df:
        p("  Fraude por escenario:")
        for esc, cnt in df.loc[y == 1, "escenario_fraude"].value_counts().items():
            p(f"    - {esc}: {cnt:,} ({cnt / max(n_f, 1):.1%})")

    p("\n2) VALORES NULOS")
    nulos = df.isna().sum()
    nulos = nulos[nulos > 0]
    if nulos.empty:
        p("  Sin nulos.")
    for col, cnt in nulos.items():
        p(f"  {col}: {cnt:,} ({cnt / n:.2%})  "
          "(esperable si es historial insuficiente; XGBoost los maneja)")

    p("\n3) DUPLICADOS")
    chequeo("id_transaccion repetido", int(df["id_transaccion"].duplicated().sum()))
    chequeo("filas idénticas (sin contar el id)",
            int(df.drop(columns="id_transaccion").duplicated().sum()))

    p("\n4) CONSISTENCIA Y RANGOS")
    chequeo("monto_pyg <= 0", int((df["monto_pyg"] <= 0).sum()))
    chequeo("coordenadas fuera de Paraguay (aprox.)", int(
        (~df["geo_latitud_emisor"].between(-28, -19)
         | ~df["geo_longitud_emisor"].between(-63, -54)).sum()))
    chequeo("emisor == receptor",
            int((df["id_cuenta_emisor"] == df["id_cuenta_receptor"]).sum()))
    chequeo("tx_count_1h > tx_count_24h", int((df["tx_count_1h"] > df["tx_count_24h"]).sum()))
    chequeo("amount_sum_1h > amount_sum_24h",
            int((df["amount_sum_1h"] > df["amount_sum_24h"] + 1).sum()))
    chequeo("antiguedad_cuenta_dias < 0", int((df["antiguedad_cuenta_dias"] < 0).sum()))
    chequeo("hora_sin^2 + hora_cos^2 != 1", int(
        ((df["hora_sin"] ** 2 + df["hora_cos"] ** 2 - 1).abs() > 1e-3).sum()))
    chequeo("flags binarios fuera de {0,1}", int(
        sum((~df[b].isin([0, 1])).sum() for b in BINARIAS)))
    chequeo("fecha_hora fuera de orden cronológico",
            int((df["fecha_hora"].diff().dt.total_seconds() < 0).sum()))

    p("\n5) COLUMNAS CONSTANTES (no aportan información)")
    ctes = [c for c in FEATURES if df[c].nunique(dropna=True) <= 1]
    p("  " + (", ".join(ctes) if ctes else "Ninguna."))

    p("\n6) OUTLIERS Y ASIMETRÍA (regla IQR x3)")
    p(f"  {'variable':32s} {'%outliers':>10s} {'asimetría':>10s} {'mediana':>14s} {'máximo':>16s}")
    for c in CONTINUAS:
        s = df[c].dropna()
        q1, q3 = s.quantile(.25), s.quantile(.75)
        iqr = q3 - q1
        out_pct = ((s < q1 - 3 * iqr) | (s > q3 + 3 * iqr)).mean() * 100
        p(f"  {c:32s} {out_pct:9.2f}% {s.skew():10.2f} {s.median():14,.2f} {s.max():16,.2f}")

    p("\n7) PODER DISCRIMINANTE UNIVARIANTE (AUC; 0.5 = sin señal)")
    p("   Un AUC > 0.98 con una sola variable sugiere fuga de información (leakage).")
    aucs = {c: auc_univariante(df[c], y) for c in FEATURES}
    for c, a in sorted(aucs.items(), key=lambda kv: -abs(kv[1] - 0.5) if kv[1] == kv[1] else 0):
        marca = "  <-- revisar posible leakage" if a > 0.98 or a < 0.02 else ""
        p(f"  {c:32s} AUC = {a:.3f}{marca}")

    p("\n8) FEATURES: MEDIA LEGÍTIMA vs. FRAUDE")
    p(f"  {'variable':32s} {'legítima':>14s} {'fraude':>14s}")
    for c in FEATURES:
        p(f"  {c:32s} {df.loc[y == 0, c].mean():14,.3f} {df.loc[y == 1, c].mean():14,.3f}")

    with open(os.path.join(out, "reporte_calidad.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    return aucs


# --------------------------------------------------------------------------- #
# Gráficos
# --------------------------------------------------------------------------- #
def g_balance(df, out):
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    conteo = df["es_fraude"].value_counts().sort_index()
    vals = [conteo.get(0, 0), conteo.get(1, 0)]
    barras = ax[0].bar(["Legítima", "Fraude"], vals, color=[C_LEGIT, C_FRAUD])
    ax[0].set_yscale("log")
    ax[0].set_title("Balance de clases (escala log)")
    for b, v in zip(barras, vals):
        ax[0].text(b.get_x() + b.get_width() / 2, v, f"{v:,}\n({v / len(df):.3%})",
                   ha="center", va="bottom")
    if "escenario_fraude" in df:
        esc = df.loc[df.es_fraude == 1, "escenario_fraude"].value_counts()
        ax[1].barh(esc.index[::-1], esc.values[::-1], color=C_FRAUD)
        ax[1].set_title("Transacciones fraudulentas por escenario")
        for i, v in enumerate(esc.values[::-1]):
            ax[1].text(v, i, f" {v:,}", va="center")
    guardar(fig, out, "01_balance_clases.png")


def g_serie_temporal(df, out):
    d = df.set_index("fecha_hora")
    fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    d["es_fraude"].resample("D").count().plot(ax=ax[0], color=C_LEGIT)
    ax[0].set_title("Transacciones por día")
    ax[0].set_xlabel("")
    d["es_fraude"].resample("D").sum().plot(ax=ax[1], color=C_FRAUD)
    ax[1].set_title("Fraudes por día")
    ax[1].set_xlabel("")
    guardar(fig, out, "02_serie_temporal.png")


def g_horaria(df, out):
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    hora = df["fecha_hora"].dt.hour
    dow = df["fecha_hora"].dt.dayofweek
    for a, serie, rango, etiquetas, titulo in (
            (ax[0], hora, range(24), range(24), "Hora del día"),
            (ax[1], dow, range(7), ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
             "Día de la semana")):
        for clase, color, nombre in ((0, C_LEGIT, "Legítima"), (1, C_FRAUD, "Fraude")):
            frec = serie[df.es_fraude == clase].value_counts(normalize=True).reindex(rango, fill_value=0)
            a.plot(list(rango), frec.values, marker="o", ms=3, color=color, label=nombre)
        a.set_xticks(list(rango))
        a.set_xticklabels(list(etiquetas))
        a.set_title(titulo + " (proporción dentro de cada clase)")
        a.legend()
    guardar(fig, out, "03_distribucion_horaria.png")


def g_histogramas(df, out):
    cols = [c for c in CONTINUAS if c in df]
    discretas = {"tx_count_1h", "tx_count_24h"}
    nc = 3
    nr = int(np.ceil(len(cols) / nc))
    fig, axes = plt.subplots(nr, nc, figsize=(13, 3.2 * nr))
    for a, c in zip(axes.ravel(), cols):
        disc = c in discretas
        f = (lambda s: s) if disc else (lambda s, c=c: transformar(s, c))
        x = f(df[c]).dropna()
        fr = f(df.loc[df.es_fraude == 1, c]).dropna()
        lo = x.min()
        hi = x.quantile(0.995)
        if len(fr):
            hi = max(hi, fr.quantile(0.99))   # no recortar la cola donde está el fraude
        hi = hi if hi > lo else lo + 1
        bins = np.arange(lo - 0.5, hi + 1.5) if disc else np.linspace(lo, hi, 40)
        for clase, color, nombre in ((0, C_LEGIT, "Legítima"), (1, C_FRAUD, "Fraude")):
            v = f(df.loc[df.es_fraude == clase, c]).dropna()
            v = v[v <= hi]
            if len(v) > 1:
                a.hist(v, bins=bins, density=True, alpha=0.5, color=color, label=nombre)
        if disc:
            a.set_yscale("log")
        a.set_title(c + (" (log1p)" if (c in LOG_SCALE and not disc) else "")
                    + (" (eje y log)" if disc else ""))
        a.legend(fontsize=7)
    for a in axes.ravel()[len(cols):]:
        a.axis("off")
    fig.suptitle("Distribución de variables continuas por clase (densidad; se omite solo la cola extrema)",
                 y=1.01)
    guardar(fig, out, "04_histogramas_continuas.png")


def g_binarias(df, out):
    cols = [c for c in BINARIAS if c in df]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    x = np.arange(len(cols))
    w = 0.38
    r0 = [df.loc[df[c] == 0, "es_fraude"].mean() * 100 for c in cols]
    r1 = [df.loc[df[c] == 1, "es_fraude"].mean() * 100 for c in cols]
    b0 = ax.bar(x - w / 2, r0, w, color=C_LEGIT, label="valor = 0")
    b1 = ax.bar(x + w / 2, r1, w, color=C_FRAUD, label="valor = 1")
    for barras in (b0, b1):
        for b in barras:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{b.get_height():.2f}%",
                    ha="center", va="bottom", fontsize=7)
    ax.axhline(df.es_fraude.mean() * 100, color="gray", ls="--", lw=1, label="tasa global")
    ax.set_xticks(x)
    ax.set_xticklabels(cols, rotation=20, ha="right")
    ax.set_ylabel("% de fraude")
    ax.set_title("Tasa de fraude según el valor de cada variable binaria")
    ax.legend()
    guardar(fig, out, "05_tasa_fraude_binarias.png")


def g_boxplots(df, out):
    if "escenario_fraude" not in df:
        return
    cols = ["ratio_monto_vs_promedio", "distancia_zona_habitual_km", "tx_count_1h",
            "amount_sum_1h", "monto_pyg", "antiguedad_cuenta_dias"]
    esc = [e for e in ESCENARIOS if e in set(df["escenario_fraude"])]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    for a, c in zip(axes.ravel(), cols):
        datos = [transformar(df.loc[df.escenario_fraude == e, c], c).dropna() for e in esc]
        a.boxplot(datos, showfliers=False)
        a.set_xticklabels([e.replace("_", "\n") for e in esc], fontsize=7)
        a.set_title(c + (" (log1p)" if c in LOG_SCALE else ""))
    fig.suptitle("Variables clave por escenario (sin outliers)", y=1.01)
    guardar(fig, out, "06_boxplots_escenarios.png")


def g_correlaciones(df, out):
    cols = [c for c in FEATURES if c in df] + ["es_fraude"]
    muestra = df[cols].sample(min(len(df), 100_000), random_state=0)
    muestra = pd.concat([muestra, df.loc[df.es_fraude == 1, cols]]).drop_duplicates()
    corr = muestra.corr(method="spearman")
    fig, ax = plt.subplots(figsize=(11, 9))
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=75, ha="right", fontsize=7)
    ax.set_yticklabels(cols, fontsize=7)
    ax.grid(False)
    for i in range(len(cols)):
        for j in range(len(cols)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=6)
    fig.colorbar(im, shrink=0.8)
    ax.set_title("Correlación de Spearman entre variables (alta correlación = redundancia)")
    guardar(fig, out, "07_correlaciones.png")


def g_auc(aucs, out):
    s = pd.Series(aucs).dropna()
    sep = ((s - 0.5).abs() * 2).sort_values()   # 0 = sin señal, 1 = separación perfecta
    fig, ax = plt.subplots(figsize=(8, 6))
    colores = [C_FRAUD if v > 0.96 else C_LEGIT for v in sep.values]
    ax.barh(sep.index, sep.values, color=colores)
    ax.set_xlim(0, 1.1)
    ax.set_xlabel("Poder discriminante = 2 * |AUC - 0.5|")
    ax.set_title("Señal univariante de cada variable (rojo = posible leakage)")
    for i, v in enumerate(sep.values):
        ax.text(v, i, f" {v:.2f}", va="center", fontsize=7)
    guardar(fig, out, "08_poder_discriminante.png")


def g_nulos(df, out):
    nulos = (df.isna().mean() * 100)
    nulos = nulos[nulos > 0].sort_values()
    if nulos.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 3 + 0.3 * len(nulos)))
    ax.barh(nulos.index, nulos.values, color=C_LEGIT)
    for i, v in enumerate(nulos.values):
        ax.text(v, i, f" {v:.2f}%", va="center")
    ax.set_xlabel("% de nulos")
    ax.set_title("Valores nulos por columna")
    guardar(fig, out, "09_nulos.png")


def g_mapa(df, out):
    fig, ax = plt.subplots(figsize=(7, 7))
    leg = df[df.es_fraude == 0]
    legit = leg.sample(min(len(leg), 40_000), random_state=0)
    fr = df[df.es_fraude == 1]
    ax.scatter(legit["geo_longitud_emisor"], legit["geo_latitud_emisor"],
               s=2, alpha=0.2, color=C_LEGIT, label="Legítima (muestra)")
    ax.scatter(fr["geo_longitud_emisor"], fr["geo_latitud_emisor"],
               s=14, alpha=0.8, color=C_FRAUD, label="Fraude")
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    ax.set_title("Ubicación de los emisores")
    ax.legend(markerscale=3)
    ax.set_aspect("equal", adjustable="datalim")
    guardar(fig, out, "10_mapa_geografico.png")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="transacciones_completo.csv")
    ap.add_argument("--out", default="eda_output")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        raise SystemExit(f"No se encontró '{args.input}'. Ejecutá primero generar_datos.py "
                         "o pasá la ruta con --input.")
    os.makedirs(args.out, exist_ok=True)

    print(f"Leyendo {args.input} ...")
    df = pd.read_csv(args.input, parse_dates=["fecha_hora"])

    aucs = reporte_calidad(df, args.out)

    print("\nGenerando gráficos...")
    g_balance(df, args.out)
    g_serie_temporal(df, args.out)
    g_horaria(df, args.out)
    g_histogramas(df, args.out)
    g_binarias(df, args.out)
    g_boxplots(df, args.out)
    g_correlaciones(df, args.out)
    g_auc(aucs, args.out)
    g_nulos(df, args.out)
    g_mapa(df, args.out)
    print(f"\nListo. Resultados en ./{args.out}/")


if __name__ == "__main__":
    main()