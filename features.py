"""
Esquema del dataset, partición temporal e ingeniería de variables. ESTE MÓDULO LO USAN
generar_datos.py, LOS NOTEBOOKS (EDA y entrenamiento en Google Colab) Y LA API, así el modelo recibe
exactamente las mismas variables al entrenar y al predecir (evita el "training-serving skew").

Reglas de derivación de las 14 features (todas se calculan con datos de UNA transferencia y su
contexto histórico, ya conocido al momento de autorizarla; ninguna usa estadísticas aprendidas,
por eso no hay nada que "ajustar" con el conjunto de entrenamiento):

    log_monto                 = ln(1 + monto_gs)
    sin_historial             = 1 si monto_promedio_30d_gs es 0 (o vacío): sin transferencias en 30 días
    log_ratio_monto_promedio  = ln(monto_gs / monto_promedio_30d_gs)   (0 si sin_historial = 1,
                                es decir, se asume ratio = 1; el ratio se acota abajo en 0,001)
    hora                      = hora local (0-23) del timestamp
    es_nocturna               = 1 si hora < 6 (00:00 a 05:59)
    dia_semana                = 0 = lunes ... 6 = domingo
    es_fin_de_semana          = 1 si dia_semana >= 5 (sábado o domingo)
    es_fin_de_mes             = 1 si el día está entre los últimos 5 días del mes
                                (día > días_del_mes - 5; ej.: 27 a 31 en meses de 31 días)
    log_antiguedad_origen     = ln(1 + antiguedad_cuenta_origen_dias)
    n_tx_1h, n_tx_24h         = conteos de transferencias previas del emisor (sin transformar)
    destinatario_nuevo        = 1/0 (calculado con el historial previo del emisor)
    dispositivo_nuevo         = 1/0 (calculado con el historial previo del emisor)
    ciudad_distinta           = 1 si ciudad != ciudad_habitual

El escalado que necesita la regresión logística (StandardScaler) NO está aquí: vive dentro del
pipeline del modelo y se ajusta solo con el conjunto de entrenamiento (notebooks/02_entrenamiento.ipynb).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Partición temporal (no aleatoria): se entrena con el pasado y se evalúa con el futuro
INICIO_DATOS = pd.Timestamp("2025-07-01")
INICIO_VALIDACION = pd.Timestamp("2026-03-01")   # entrenamiento: jul 2025 - feb 2026
INICIO_PRUEBA = pd.Timestamp("2026-05-01")       # validación: mar - abr 2026 · prueba: may - jun 2026
FIN_DATOS = pd.Timestamp("2026-07-01")


def particion(timestamps: pd.Series) -> pd.Series:
    """'entrenamiento', 'validacion' o 'prueba' según la fecha de la transferencia."""
    t = pd.to_datetime(timestamps)
    return pd.Series(np.select([t < INICIO_VALIDACION, t < INICIO_PRUEBA], ["entrenamiento", "validacion"],
                               "prueba"), index=timestamps.index)


# Esquema del dataset (orden de columnas del CSV)
COLUMNAS_DATASET = [
    "transaction_id", "timestamp", "cuenta_emisor_id", "banco_origen", "banco_destino",
    "cuenta_destino_id", "ciudad", "ciudad_habitual", "dispositivo_id", "monto_gs",
    "n_tx_1h", "n_tx_24h", "monto_promedio_30d_gs", "destinatario_nuevo", "dispositivo_nuevo",
    "antiguedad_cuenta_origen_dias", "es_fraude", "tipo_fraude",
]

# Columnas que necesita construir_features (las mismas que exige la API)
COLUMNAS_ENTRADA = [
    "timestamp", "monto_gs", "ciudad", "ciudad_habitual", "antiguedad_cuenta_origen_dias",
    "monto_promedio_30d_gs", "n_tx_1h", "n_tx_24h", "destinatario_nuevo", "dispositivo_nuevo",
]

# Variables que ve el modelo (orden fijo)
FEATURES = [
    "log_monto",
    "log_ratio_monto_promedio",
    "sin_historial",
    "hora",
    "es_nocturna",
    "dia_semana",
    "es_fin_de_semana",
    "es_fin_de_mes",
    "log_antiguedad_origen",
    "n_tx_1h",
    "n_tx_24h",
    "destinatario_nuevo",
    "dispositivo_nuevo",
    "ciudad_distinta",
]

# Descripción legible de cada variable (para explicar decisiones en la API / UI)
DESCRIPCION = {
    "log_monto": "monto de la transferencia",
    "log_ratio_monto_promedio": "monto comparado con su promedio de 30 días",
    "sin_historial": "cliente sin historial reciente",
    "hora": "hora de la transferencia",
    "es_nocturna": "horario nocturno (00-06 hs)",
    "dia_semana": "día de la semana",
    "es_fin_de_semana": "fin de semana",
    "es_fin_de_mes": "fin de mes (últimos 5 días)",
    "log_antiguedad_origen": "antigüedad de la cuenta origen",
    "n_tx_1h": "cantidad de transferencias en la última hora",
    "n_tx_24h": "cantidad de transferencias en las últimas 24 h",
    "destinatario_nuevo": "primera vez que le transfiere a este destinatario",
    "dispositivo_nuevo": "dispositivo registrado hace menos de 24 h",
    "ciudad_distinta": "operación desde una ciudad distinta a la habitual",
}

DATASET = Path(__file__).resolve().parent / "data" / "transacciones_spi.csv.gz"


def leer_dataset(ruta: Path | str = DATASET) -> pd.DataFrame:
    """Lee el CSV del dataset con los tipos de datos correctos."""
    return pd.read_csv(ruta, parse_dates=["timestamp"],
                       dtype={"destinatario_nuevo": bool, "dispositivo_nuevo": bool, "monto_gs": "int64",
                              "monto_promedio_30d_gs": "int64", "es_fraude": "int64"})


def construir_features(df: pd.DataFrame) -> pd.DataFrame:
    """Recibe transferencias con COLUMNAS_ENTRADA y devuelve la matriz de FEATURES."""
    ts = pd.to_datetime(df["timestamp"])
    monto = df["monto_gs"].astype(float)
    promedio = pd.to_numeric(df["monto_promedio_30d_gs"], errors="coerce").astype(float)
    sin_hist = promedio.isna() | (promedio <= 0)
    ratio = np.where(sin_hist, 1.0, monto / promedio.where(~sin_hist, 1.0))

    X = pd.DataFrame({
        "log_monto": np.log1p(monto),
        "log_ratio_monto_promedio": np.log(np.clip(ratio, 1e-3, None)),
        "sin_historial": sin_hist.astype(int),
        "hora": ts.dt.hour,
        "es_nocturna": (ts.dt.hour < 6).astype(int),
        "dia_semana": ts.dt.dayofweek,
        "es_fin_de_semana": (ts.dt.dayofweek >= 5).astype(int),
        "es_fin_de_mes": (ts.dt.day > ts.dt.days_in_month - 5).astype(int),
        "log_antiguedad_origen": np.log1p(df["antiguedad_cuenta_origen_dias"].astype(float).clip(lower=0)),
        "n_tx_1h": df["n_tx_1h"].astype(int),
        "n_tx_24h": df["n_tx_24h"].astype(int),
        "destinatario_nuevo": df["destinatario_nuevo"].astype(int),
        "dispositivo_nuevo": df["dispositivo_nuevo"].astype(int),
        "ciudad_distinta": (df["ciudad"].astype(str) != df["ciudad_habitual"].astype(str)).astype(int),
    }, index=df.index)
    return X[FEATURES]
