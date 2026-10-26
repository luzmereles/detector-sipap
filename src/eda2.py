#!/usr/bin/env python3
"""EDA de transferencias sintéticas. No modifica ni limpia el archivo original."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

NUMERICAS = [
    "monto_pyg", "hora", "es_fin_de_semana", "es_fin_de_mes",
    "es_horario_nocturno", "hora_atipica", "dispositivo_nuevo",
    "ubicacion_inusual", "antiguedad_cuenta_dias", "tx_count_5min",
    "tx_count_1h", "tx_count_24h", "amount_sum_1h", "amount_sum_24h",
    "monto_promedio_usuario_30d", "ratio_monto_vs_promedio",
    "destinatario_nuevo", "unique_beneficiaries_24h", "es_fraude",
]
BINARIAS = ["es_fin_de_semana", "es_fin_de_mes", "es_horario_nocturno",
            "hora_atipica", "dispositivo_nuevo", "ubicacion_inusual",
            "destinatario_nuevo", "es_fraude"]
ENTERAS = [c for c in NUMERICAS if c != "ratio_monto_vs_promedio"]
COLORES = {"Normal": "#2878B5", "Fraude": "#E45756"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/dataset_completo.csv"))
    parser.add_argument("--output", type=Path, default=Path("eda"))
    parser.add_argument("--max-normales", type=int, default=20000,
                        help="Máximo de normales SOLO para los diagramas de dispersión")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.max_normales < 1:
        parser.error("--max-normales debe ser positivo")
    if not args.input.is_file():
        parser.error(f"No existe el archivo: {args.input.resolve()}")
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(args.input, low_memory=False)
    if raw.empty:
        parser.error("El CSV no contiene registros")
    requeridas = ["timestamp", "escenario_fraude"] + NUMERICAS
    faltantes = sorted(set(requeridas) - set(raw.columns))
    if faltantes:
        parser.error(f"Faltan columnas esperadas: {', '.join(faltantes)}")
    df = raw.copy()
    checks = []

    def registrar(regla, mascara, detalle=""):
        mascara = pd.Series(mascara, index=df.index).fillna(False)
        checks.append({"regla": regla, "filas_afectadas": int(mascara.sum()),
                       "porcentaje": round(float(mascara.mean() * 100), 6),
                       "detalle": detalle})

    calidad = pd.DataFrame(index=raw.columns)
    calidad["tipo_original"] = raw.dtypes.astype(str)
    calidad["nulos_originales"] = raw.isna().sum()
    calidad["porcentaje_nulos"] = raw.isna().mean() * 100
    calidad["valores_distintos"] = raw.nunique(dropna=True)
    calidad["fallos_conversion"] = 0
    for c in NUMERICAS:
        df[c] = pd.to_numeric(raw[c], errors="coerce")
        fallo = raw[c].notna() & df[c].isna()
        calidad.loc[c, "fallos_conversion"] = int(fallo.sum())
        registrar(f"{c}: no numérico", fallo)
        registrar(f"{c}: infinito", np.isinf(df[c]))
        df[c] = df[c].replace([np.inf, -np.inf], np.nan)
    df["timestamp"] = pd.to_datetime(raw["timestamp"], errors="coerce")
    fallo_fecha = raw["timestamp"].notna() & df["timestamp"].isna()
    calidad.loc["timestamp", "fallos_conversion"] = int(fallo_fecha.sum())
    registrar("Timestamp no interpretable", fallo_fecha)
    registrar("Fila con al menos un nulo original", raw.isna().any(axis=1))
    registrar("Duplicados exactos adicionales", raw.duplicated(),
              "Se cuenta cada repetición después de la primera; no se elimina ninguna fila.")
    for c in BINARIAS:
        registrar(f"{c}: fuera de 0/1", df[c].notna() & ~df[c].isin([0, 1]))
    for c in ENTERAS:
        registrar(f"{c}: valor no entero", df[c].notna() & df[c].mod(1).ne(0))
    for c in NUMERICAS:
        registrar(f"{c}: negativo", df[c].lt(0))
    registrar("Monto fuera de [1000, 10000000]", df.monto_pyg.notna() &
              ~df.monto_pyg.between(1000, 10000000), "Rango configurado en el generador; no validación normativa.")
    registrar("Hora fuera de [0, 23]", df.hora.notna() & ~df.hora.between(0, 23))
    for menor, mayor in [("tx_count_5min", "tx_count_1h"),
                         ("tx_count_1h", "tx_count_24h"),
                         ("amount_sum_1h", "amount_sum_24h")]:
        registrar(f"{menor} > {mayor}", df[menor].gt(df[mayor]),
                  "Revisar semántica de ventanas; los conteos del generador son parcialmente independientes.")
    valido = df.monto_promedio_usuario_30d.gt(0) & df.monto_pyg.notna() & df.ratio_monto_vs_promedio.notna()
    esperado = df.monto_pyg / df.monto_promedio_usuario_30d.where(df.monto_promedio_usuario_30d.gt(0))
    registrar("Promedio histórico no positivo", df.monto_promedio_usuario_30d.le(0))
    registrar("Ratio inconsistente", valido & ~np.isclose(df.ratio_monto_vs_promedio, esperado,
                                                        rtol=1e-5, atol=1e-8, equal_nan=False))
    fecha_ok = df.timestamp.notna()
    for c, esperado in [("hora", df.timestamp.dt.hour),
                        ("es_fin_de_semana", (df.timestamp.dt.dayofweek >= 5).astype(int)),
                        ("es_fin_de_mes", (df.timestamp.dt.day >= 25).astype(int)),
                        ("es_horario_nocturno", ((df.timestamp.dt.hour < 6) |
                                                 (df.timestamp.dt.hour >= 22)).astype(int))]:
        registrar(f"{c}: inconsistente con timestamp", fecha_ok & df[c].notna() & df[c].ne(esperado))
    escenarios = ["F1_toma_cuenta", "F2_rafaga_salidas", "F3_engano", "F4_pruebas_pequenas"]
    registrar("Escenario desconocido", df.escenario_fraude.notna() &
              ~df.escenario_fraude.isin(["normal"] + escenarios))
    registrar("Etiqueta y escenario incompatibles",
              (df.es_fraude.eq(0) & df.escenario_fraude.ne("normal")) |
              (df.es_fraude.eq(1) & ~df.escenario_fraude.isin(escenarios)))
    calidad["nulos_para_analisis"] = df[raw.columns].isna().sum()
    calidad.to_csv(out / "calidad_columnas.csv", index_label="columna")
    reglas = pd.DataFrame(checks)
    reglas.to_csv(out / "reglas_calidad.csv", index=False)
    df[NUMERICAS].describe(percentiles=[.01, .25, .5, .75, .95, .99]).T.to_csv(out / "estadisticas_globales.csv")
    base = df[df.es_fraude.isin([0, 1])].copy()
    base["clase"] = base.es_fraude.map({0: "Normal", 1: "Fraude"})
    base.groupby("clase")[NUMERICAS].describe().to_csv(out / "estadisticas_por_clase.csv")
    base.groupby(["clase", "escenario_fraude"], dropna=False).size().rename("filas").to_csv(out / "escenarios.csv")
    sns.set_theme(style="whitegrid", context="notebook")

    def guardar(fig, nombre, titulo):
        fig.suptitle(titulo, fontsize=15)
        fig.tight_layout(rect=(0, 0, 1, .95))
        fig.savefig(out / nombre, dpi=160, bbox_inches="tight")
        plt.close(fig)

    def vacio(ax, texto="Sin datos válidos"):
        ax.text(.5, .5, texto, ha="center", va="center", transform=ax.transAxes)

    # 1: balance real de clases y calidad, sin muestreo.
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    counts = base.clase.value_counts().reindex(["Normal", "Fraude"], fill_value=0)
    axes[0].bar(counts.index, counts.values, color=list(COLORES.values()))
    axes[0].set_yscale("symlog", linthresh=1)
    axes[0].set_ylabel("Transacciones (escala symlog)")
    axes[0].set_title("Balance de clases: población completa")
    for i, n in enumerate(counts):
        axes[0].annotate(f"{n:,}\n{n / max(len(base), 1):.3%}", (i, n),
                         xytext=(0, 6), textcoords="offset points", ha="center")
    problemas = reglas[reglas.filas_afectadas.gt(0)].nlargest(10, "filas_afectadas").sort_values("filas_afectadas")
    if problemas.empty:
        vacio(axes[1], "Sin incidencias en las reglas evaluadas")
    else:
        axes[1].barh(problemas.regla, problemas.filas_afectadas, color="#F2A541")
    axes[1].set_title("Hasta 10 reglas con más incidencias")
    axes[1].set_xlabel("Filas afectadas (una fila puede incumplir varias reglas)")
    guardar(fig, "01_balance_y_calidad.png", "Balance y calidad de datos")

    # 2: densidades por clase: cada clase se normaliza por separado.
    features = ["monto_pyg", "ratio_monto_vs_promedio", "tx_count_5min", "antiguedad_cuenta_dias"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    for ax, c in zip(axes.flat, features):
        log = c in ["monto_pyg", "ratio_monto_vs_promedio"]
        valores = base[c].dropna()
        valores = valores[valores.gt(0)] if log else valores
        if valores.empty:
            vacio(ax)
            continue
        low, high = valores.min(), valores.max()
        if low == high:
            bins = [low * .9, high * 1.1] if log else [low - .5, high + .5]
        else:
            bins = np.geomspace(low, high, 45) if log else np.linspace(low, high, 45)
        for clase, color in COLORES.items():
            serie = base.loc[base.clase.eq(clase), c].dropna()
            if log:
                serie = serie[serie.gt(0)]
            if len(serie):
                ax.hist(serie, bins=bins, density=True, histtype="step", linewidth=1.8,
                        label=f"{clase} (n={len(serie):,})", color=color)
        if log:
            ax.set_xscale("log")
        ax.set(xlabel=c, ylabel="Densidad", title=c + (" · eje X log" if log else ""))
        ax.legend(fontsize=8)
    guardar(fig, "02_distribuciones.png", "Distribuciones por clase · sin muestreo")

    # 3: normales muestreadas, todos los fraudes; no representa prevalencia.
    normales = base[base.es_fraude.eq(0)]
    normales = normales.sample(n=min(len(normales), args.max_normales), random_state=args.seed)
    fraudes = base[base.es_fraude.eq(1)]
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    pares = [("monto_pyg", "ratio_monto_vs_promedio"), ("tx_count_5min", "tx_count_1h")]
    palette = dict(zip(escenarios, sns.color_palette("Set1", 4)))
    for ax, (x, y) in zip(axes, pares):
        ax.scatter(normales[x], normales[y], s=8, alpha=.12, color=COLORES["Normal"],
                   label=f"Normal: muestra n={len(normales):,}", rasterized=True)
        for esc, color in palette.items():
            sub = fraudes[fraudes.escenario_fraude.eq(esc)]
            if len(sub):
                ax.scatter(sub[x], sub[y], s=23, alpha=.7, color=color, label=f"{esc}: n={len(sub):,}", rasterized=True)
        desconocidos = fraudes[~fraudes.escenario_fraude.isin(escenarios)]
        if len(desconocidos):
            ax.scatter(desconocidos[x], desconocidos[y], s=23, color="black", label="Fraude: otro escenario")
        ax.set(xlabel=x, ylabel=y)
        if x == "monto_pyg":
            ax.set_xscale("symlog", linthresh=1000)
            ax.set_yscale("symlog", linthresh=1)
        ax.legend(fontsize=7)
    guardar(fig, "03_dispersion_fraudes.png", "Dispersión · normales muestreadas y todos los fraudes (no muestra prevalencia)")

    # 4: correlaciones sin usar escenario_fraude como predictor.
    columnas = ["monto_pyg", "ratio_monto_vs_promedio", "tx_count_5min", "tx_count_1h",
                "tx_count_24h", "amount_sum_1h", "antiguedad_cuenta_dias",
                "dispositivo_nuevo", "ubicacion_inusual", "destinatario_nuevo", "es_fraude"]
    corr = base[columnas].corr(method="spearman")
    corr.to_csv(out / "correlaciones_spearman.csv")
    fig, ax = plt.subplots(figsize=(13, 10))
    sns.heatmap(corr, mask=np.triu(np.ones_like(corr, dtype=bool), k=1),
                cmap="vlag", vmin=-1, vmax=1, center=0, annot=True, fmt=".2f",
                annot_kws={"size": 8}, square=True, ax=ax)
    guardar(fig, "04_correlaciones.png", "Correlación de Spearman · todas las filas con etiqueta válida")

    # 5: tasas con denominadores explícitos; días sin registros quedan como NaN.
    temporal = base.dropna(subset=["timestamp"]).copy()
    temporal["dia"] = temporal.timestamp.dt.floor("D")
    diario = temporal.groupby("dia").es_fraude.agg(transacciones="size", fraudes="sum")
    if not diario.empty:
        diario = diario.reindex(pd.date_range(diario.index.min(), diario.index.max(), freq="D"))
    diario["tasa_fraude_pct"] = diario.fraudes.div(diario.transacciones) * 100
    diario.to_csv(out / "resumen_diario.csv", index_label="dia")
    temporal["hora_real"] = temporal.timestamp.dt.hour
    horario = temporal.groupby("hora_real").es_fraude.agg(transacciones="size", fraudes="sum").reindex(range(24))
    horario["tasa_fraude_pct"] = horario.fraudes.div(horario.transacciones) * 100
    horario.to_csv(out / "resumen_horario.csv", index_label="hora")
    fig, axes = plt.subplots(2, 1, figsize=(14, 9))
    if diario.empty:
        vacio(axes[0])
    else:
        axes[0].plot(diario.index, diario.tasa_fraude_pct, color=COLORES["Fraude"], linewidth=1.5)
    axes[0].set(title="Tasa diaria: fraudes / transacciones del día", ylabel="Fraude (%)", xlabel="Fecha")
    axes[1].bar(horario.index, horario.tasa_fraude_pct, color=COLORES["Fraude"])
    axes[1].set(title="Tasa por hora: fraudes / transacciones de esa hora", xlabel="Hora del timestamp", ylabel="Fraude (%)")
    axes[1].set_xticks(range(24))
    guardar(fig, "05_comportamiento_temporal.png", "Comportamiento temporal · población completa con fecha y etiqueta válidas")

    resumen = {
        "archivo": str(args.input), "filas": len(df), "columnas": len(raw.columns),
        "etiquetas_validas": len(base), "etiquetas_invalidas_o_nulas": len(df) - len(base),
        "fraudes": int(base.es_fraude.sum()),
        "tasa_fraude_pct": float(base.es_fraude.mean() * 100) if len(base) else None,
        "fecha_min": str(df.timestamp.min()), "fecha_max": str(df.timestamp.max()),
        "timestamps_validos_ordenados": bool(df.timestamp.dropna().is_monotonic_increasing),
        "normales_en_dispersion": len(normales), "fraudes_en_dispersion": len(fraudes),
        "reglas_con_incidencias": int(reglas.filas_afectadas.gt(0).sum()),
    }
    (out / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    notas = [
        "EDA de datos sintéticos; no constituye evidencia de comportamiento real de fraude.",
        "No se modifica el CSV ni se eliminan duplicados o registros originales.",
        "Valores no interpretables e infinitos se excluyen de cálculos numéricos, y se reportan.",
        "Las tasas usan todas las etiquetas válidas; revisar exclusiones en resumen.json.",
        "Solo la dispersión muestrea normales; incluye todos los fraudes. No inferir prevalencia de sus puntos.",
        "Los histogramas normalizan cada clase por separado; densidad no equivale a cantidad de casos.",
        "Los puntos con coordenadas idénticas pueden superponerse en la dispersión.",
        "escenario_fraude revela la etiqueta en este generador: no usar como predictor de fraude.",
        "Correlación no prueba causalidad ni mide por sí sola capacidad predictiva.",
        "Las señales de separación reflejan reglas del generador; no garantizan desempeño en datos reales.",
        "Los conteos de ventanas se generan parcialmente de forma independiente: revisar inconsistencias temporales.",
        "Sin identificadores de usuario/beneficiario no se pueden reconstruir ni verificar agregados históricos.",
        "No exigir acumulados >= monto actual sin definir si las ventanas incluyen la transacción actual.",
        "El análisis usa dataset completo para descripción, no para seleccionar variables o umbrales con test.",
        "El umbral de monto se toma del código suministrado y no se certifica como normativa vigente.",
    ]
    (out / "notas_interpretacion.txt").write_text("\n".join(notas) + "\n", encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"\nListo: 5 gráficos PNG y reportes guardados en {out.resolve()}")


if __name__ == "__main__":
    main()
