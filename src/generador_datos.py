"""
================================================================================
GENERADOR DE DATASET SINTÉTICO - DETECTOR DE ANOMALÍAS SPI (Paraguay)
================================================================================

Proyecto: Detector de Anomalías en Transacciones del Sistema de Pagos (SIPAP/SPI)
Autores conceptuales: Luz Mereles y Sol Nunez
Script: Generación profesional de datos sintéticos con XGBoost ponderado en mente

Descripción:
------------
Este script genera un dataset sintético realista de transferencias instantáneas SPI
en Paraguay, con fuerte desbalance (fraude ≈ 0.08%), features de velocity,
geolocalización y zona habitual por usuario.

Esquema final del dataset:

A. Datos originales de la transacción
   - id_transaccion
   - fecha_hora
   - id_cuenta_emisor
   - id_cuenta_receptor
   - id_entidad_receptor
   - monto_pyg
   - id_dispositivo_emisor
   - direccion_ip_emisor
   - geo_latitud_emisor
   - geo_longitud_emisor

B. Variables calculadas para el modelo
   - hora_del_dia
   - hora_sin
   - hora_cos
   - dia_semana
   - es_fin_de_semana
   - es_horario_nocturno
   - horario_habitual
   - cambio_de_dispositivo
   - ubicacion_inusual
   - distancia_zona_habitual_km
   - ip_nueva_emisor
   - dispositivo_nuevo_emisor
   - antiguedad_cuenta_dias
   - tx_count_1h
   - tx_count_24h
   - amount_sum_1h
   - amount_sum_24h
   - unique_beneficiaries_24h
   - new_beneficiaries_1h
   - is_new_beneficiary
   - monto_promedio_usuario_30d
   - ratio_monto_vs_promedio

C. Etiqueta de entrenamiento y campos de análisis
   - es_fraude
   - escenario_fraude

Escenarios de fraude contemplados:
----------------------------------
1. velocidad_alta
2. ubicacion_lejana
3. dispositivo_nuevo
4. beneficiario_nuevo_alto
5. monto_anomalo_nocturno
6. cuenta_mula
7. combinado

Uso:
----
    python generar_dataset_fraude_spi.py

Salida:
-------
    data/transacciones_spi_sinteticas.parquet
    data/transacciones_spi_sinteticas.csv (opcional)
    data/feature_cols.joblib
    data/resumen_dataset.txt

Requisitos:
-----------
    pip install pandas numpy faker pyarrow joblib

================================================================================
"""

import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
import random
import uuid
import joblib
import os
from collections import defaultdict

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

SEED = 42
np.random.seed(SEED)
random.seed(SEED)
fake = Faker('es_ES')
Faker.seed(SEED)

# Tamaño del dataset
N_CUENTAS_EMISORAS = 8_000          # Número de usuarios/cuentas emisoras
N_TRANSACCIONES_NORMALES = 280_000  # Transacciones legítimas
FRAUD_RATE = 0.00085                # ≈ 0.085% de fraude
N_FRAUDES = int(N_TRANSACCIONES_NORMALES * FRAUD_RATE)

# Periodo de datos
FECHA_INICIO = datetime(2025, 7, 1)
FECHA_FIN = datetime(2025, 10, 20)

# Umbrales de negocio
UMBRAL_DISTANCIA_INUSUAL_KM = 85.0
HORARIO_NOCTURNO = (0, 5)           # 00:00 a 05:59

# ============================================================
# DEPARTAMENTOS DE PARAGUAY (zona habitual)
# ============================================================

DEPARTAMENTOS = {
    "Asunción":          {"lat": -25.2865, "lon": -57.6470, "peso": 0.18},
    "Central":           {"lat": -25.3267, "lon": -57.5486, "peso": 0.22},
    "Alto Paraná":       {"lat": -25.5097, "lon": -54.6111, "peso": 0.12},
    "Itapúa":            {"lat": -27.3306, "lon": -55.8667, "peso": 0.08},
    "Caaguazú":          {"lat": -25.4500, "lon": -56.0167, "peso": 0.06},
    "San Pedro":         {"lat": -24.1000, "lon": -57.0833, "peso": 0.04},
    "Cordillera":        {"lat": -25.3833, "lon": -57.1500, "peso": 0.05},
    "Guairá":            {"lat": -25.7500, "lon": -56.4333, "peso": 0.03},
    "Caazapá":           {"lat": -26.2000, "lon": -56.3667, "peso": 0.02},
    "Paraguarí":         {"lat": -25.6333, "lon": -57.1500, "peso": 0.04},
    "Concepción":        {"lat": -23.4000, "lon": -57.4333, "peso": 0.03},
    "Amambay":           {"lat": -22.5500, "lon": -55.7500, "peso": 0.03},
    "Canindeyú":         {"lat": -24.1500, "lon": -54.6167, "peso": 0.02},
    "Presidente Hayes":  {"lat": -23.8500, "lon": -58.4500, "peso": 0.02},
    "Boquerón":          {"lat": -21.7000, "lon": -60.9500, "peso": 0.015},
    "Alto Paraguay":     {"lat": -21.0500, "lon": -57.9000, "peso": 0.01},
    "Ñeembucú":          {"lat": -26.8667, "lon": -58.3000, "peso": 0.02},
    "Misiones":          {"lat": -26.8667, "lon": -57.0333, "peso": 0.025},
}

NOMBRES_DEPARTAMENTOS = list(DEPARTAMENTOS.keys())
PESOS_DEPARTAMENTOS = [DEPARTAMENTOS[d]["peso"] for d in NOMBRES_DEPARTAMENTOS]

# ============================================================
# ESCENARIOS DE FRAUDE
# ============================================================

ESCENARIOS_FRAUDE = {
    "velocidad_alta":           {"prob": 0.20},
    "ubicacion_lejana":         {"prob": 0.18},
    "dispositivo_nuevo":        {"prob": 0.15},
    "beneficiario_nuevo_alto":  {"prob": 0.15},
    "monto_anomalo_nocturno":   {"prob": 0.12},
    "cuenta_mula":              {"prob": 0.12},
    "combinado":                {"prob": 0.08},
}

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def haversine_km(lat1, lon1, lat2, lon2):
    """Calcula distancia en kilómetros entre dos puntos geográficos."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def generar_coordenadas_cercanas(lat_base, lon_base, radio_km=25):
    """Genera lat/lon cercanas a un punto base (comportamiento normal)."""
    # Aproximación: 1 grado ≈ 111 km
    delta = radio_km / 111.0
    lat = lat_base + np.random.uniform(-delta, delta)
    lon = lon_base + np.random.uniform(-delta, delta)
    return round(lat, 6), round(lon, 6)


def generar_coordenadas_lejanas(lat_home, lon_home, min_km=100):
    """Genera una ubicación lejos de la zona habitual (para fraude)."""
    # Elegimos otro departamento aleatorio
    depto = random.choice(NOMBRES_DEPARTAMENTOS)
    lat2 = DEPARTAMENTOS[depto]["lat"] + np.random.uniform(-0.15, 0.15)
    lon2 = DEPARTAMENTOS[depto]["lon"] + np.random.uniform(-0.15, 0.15)
    
    # Aseguramos distancia mínima
    dist = haversine_km(lat_home, lon_home, lat2, lon2)
    if dist < min_km:
        # Forzamos un punto más lejano
        lat2 = lat_home + np.random.choice([-1, 1]) * np.random.uniform(1.2, 2.5)
        lon2 = lon_home + np.random.choice([-1, 1]) * np.random.uniform(1.2, 2.5)
    return round(lat2, 6), round(lon2, 6)


def generar_ip_paraguaya():
    """Genera una IP con apariencia paraguaya (sintética)."""
    # Rangos comunes usados en Paraguay (simplificado)
    return f"{random.randint(180, 190)}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"


def codificacion_ciclica_hora(hora):
    """Convierte hora (0-23) en componentes seno y coseno."""
    angulo = 2 * np.pi * hora / 24
    return np.sin(angulo), np.cos(angulo)


# ============================================================
# 1. GENERACIÓN DE CUENTAS EMISORAS (perfiles de usuarios)
# ============================================================

def crear_cuentas_emisoras(n_cuentas: int) -> pd.DataFrame:
    """
    Crea perfiles realistas de cuentas emisoras.
    Cada cuenta tiene zona habitual, dispositivos preferidos, horario típico, etc.
    """
    print(f"Creando {n_cuentas:,} perfiles de cuentas emisoras...")
    
    cuentas = []
    for i in range(n_cuentas):
        depto = np.random.choice(NOMBRES_DEPARTAMENTOS, p=PESOS_DEPARTAMENTOS)
        lat_home = DEPARTAMENTOS[depto]["lat"]
        lon_home = DEPARTAMENTOS[depto]["lon"]
        
        # Antigüedad de la cuenta (entre 30 días y 4 años)
        antiguedad_dias = np.random.randint(30, 365 * 4)
        fecha_creacion = FECHA_INICIO - timedelta(days=antiguedad_dias)
        
        # Horario habitual (la mayoría opera de día)
        if random.random() < 0.85:
            hora_inicio_habitual = np.random.randint(7, 10)
            hora_fin_habitual = np.random.randint(18, 23)
        else:
            # Algunos trabajan de noche / madrugada
            hora_inicio_habitual = np.random.randint(0, 5)
            hora_fin_habitual = np.random.randint(6, 12)
        
        # Dispositivos preferidos (1 o 2)
        n_dispositivos = 1 if random.random() < 0.7 else 2
        dispositivos = [str(uuid.uuid4())[:12] for _ in range(n_dispositivos)]
        
        # Monto promedio histórico del usuario
        monto_promedio = float(np.random.lognormal(mean=12.1, sigma=0.7))  # ~ Gs 180k - 1.5M
        
        cuentas.append({
            "id_cuenta_emisor": f"PY{str(i).zfill(8)}",
            "departamento_habitual": depto,
            "lat_habitual": lat_home,
            "lon_habitual": lon_home,
            "fecha_creacion_cuenta": fecha_creacion,
            "antiguedad_cuenta_dias_base": antiguedad_dias,
            "hora_inicio_habitual": hora_inicio_habitual,
            "hora_fin_habitual": hora_fin_habitual,
            "dispositivos_preferidos": dispositivos,
            "monto_promedio_historico": round(monto_promedio, 0),
            "ips_conocidas": set(),          # se irá llenando
            "dispositivos_conocidos": set(dispositivos),
            "beneficiarios_conocidos": set(),
        })
    
    return pd.DataFrame(cuentas)


# ============================================================
# 2. GENERACIÓN DE TRANSACCIONES BASE
# ============================================================

def generar_transacciones_base(cuentas_df: pd.DataFrame, n_normales: int, n_fraudes: int) -> pd.DataFrame:
    """
    Genera transacciones normales + inyección de fraudes según escenarios.
    """
    print(f"Generando {n_normales:,} transacciones normales + {n_fraudes:,} fraudes...")
    
    transacciones = []
    cuentas = cuentas_df.to_dict('records')
    
    # ---------- Transacciones NORMALES ----------
    for i in range(n_normales):
        cuenta = random.choice(cuentas)
        
        # Timestamp aleatorio dentro del periodo
        delta = FECHA_FIN - FECHA_INICIO
        fecha_hora = FECHA_INICIO + timedelta(seconds=random.randint(0, int(delta.total_seconds())))
        
        # Coordenadas cercanas a la zona habitual
        lat, lon = generar_coordenadas_cercanas(
            cuenta["lat_habitual"], cuenta["lon_habitual"], radio_km=np.random.uniform(5, 35)
        )
        
        # Dispositivo (casi siempre uno de los preferidos)
        if random.random() < 0.92:
            dispositivo = random.choice(cuenta["dispositivos_preferidos"])
        else:
            dispositivo = str(uuid.uuid4())[:12]
        
        # Monto realista
        monto = max(25_000, np.random.lognormal(mean=12.0, sigma=0.85))
        monto = round(monto / 1000) * 1000  # redondeo a miles
        
        # Receptor
        id_receptor = f"PYR{random.randint(100000, 9999999)}"
        id_entidad = random.choice(["BNF", "ITAU", "CONTINENTAL", "FAMILIAR", "GNB", "UENO", "SOLAR", "VISION"])
        
        transacciones.append({
            "id_transaccion": str(uuid.uuid4()),
            "fecha_hora": fecha_hora,
            "id_cuenta_emisor": cuenta["id_cuenta_emisor"],
            "id_cuenta_receptor": id_receptor,
            "id_entidad_receptor": id_entidad,
            "monto_pyg": monto,
            "id_dispositivo_emisor": dispositivo,
            "direccion_ip_emisor": generar_ip_paraguaya(),
            "geo_latitud_emisor": lat,
            "geo_longitud_emisor": lon,
            "es_fraude": 0,
            "escenario_fraude": "ninguno",
            # Datos auxiliares para cálculo posterior
            "_lat_habitual": cuenta["lat_habitual"],
            "_lon_habitual": cuenta["lon_habitual"],
            "_hora_inicio_hab": cuenta["hora_inicio_habitual"],
            "_hora_fin_hab": cuenta["hora_fin_habitual"],
            "_monto_promedio_hist": cuenta["monto_promedio_historico"],
            "_fecha_creacion": cuenta["fecha_creacion_cuenta"],
            "_dispositivos_pref": cuenta["dispositivos_preferidos"],
        })
    
    # ---------- Transacciones FRAUDULENTAS ----------
    escenarios = list(ESCENARIOS_FRAUDE.keys())
    probs = [ESCENARIOS_FRAUDE[e]["prob"] for e in escenarios]
    
    for i in range(n_fraudes):
        cuenta = random.choice(cuentas)
        escenario = np.random.choice(escenarios, p=probs)
        
        delta = FECHA_FIN - FECHA_INICIO
        fecha_hora = FECHA_INICIO + timedelta(seconds=random.randint(0, int(delta.total_seconds())))
        hora = fecha_hora.hour
        
        # Valores por defecto (se sobreescriben según escenario)
        lat, lon = generar_coordenadas_cercanas(cuenta["lat_habitual"], cuenta["lon_habitual"], 20)
        dispositivo = random.choice(cuenta["dispositivos_preferidos"])
        monto = max(50_000, np.random.lognormal(mean=12.8, sigma=0.9))
        id_receptor = f"PYR{random.randint(100000, 9999999)}"
        
        # Aplicar lógica del escenario
        if escenario == "velocidad_alta":
            monto = np.random.uniform(180_000, 1_800_000)
            # La velocity se forzará después en features
            
        elif escenario == "ubicacion_lejana":
            lat, lon = generar_coordenadas_lejanas(cuenta["lat_habitual"], cuenta["lon_habitual"], min_km=95)
            monto = np.random.uniform(400_000, 5_000_000)
            
        elif escenario == "dispositivo_nuevo":
            dispositivo = str(uuid.uuid4())[:12]  # completamente nuevo
            monto = np.random.uniform(600_000, 4_500_000)
            
        elif escenario == "beneficiario_nuevo_alto":
            id_receptor = f"PYR{random.randint(9000000, 9999999)}"  # forzar nuevo
            monto = np.random.uniform(1_200_000, 8_000_000)
            
        elif escenario == "monto_anomalo_nocturno":
            # Forzar hora nocturna
            fecha_hora = fecha_hora.replace(hour=random.randint(0, 5), minute=random.randint(0, 59))
            monto = np.random.uniform(2_500_000, 15_000_000)
            lat, lon = generar_coordenadas_cercanas(cuenta["lat_habitual"], cuenta["lon_habitual"], 30)
            
        elif escenario == "cuenta_mula":
            monto = np.random.uniform(350_000, 2_800_000)
            # Se reflejará en unique_beneficiaries alto
            
        elif escenario == "combinado":
            # Mezcla de señales fuertes
            lat, lon = generar_coordenadas_lejanas(cuenta["lat_habitual"], cuenta["lon_habitual"], 110)
            dispositivo = str(uuid.uuid4())[:12]
            monto = np.random.uniform(1_500_000, 9_000_000)
            if random.random() < 0.5:
                fecha_hora = fecha_hora.replace(hour=random.randint(0, 5))
        
        monto = round(monto / 1000) * 1000
        
        transacciones.append({
            "id_transaccion": str(uuid.uuid4()),
            "fecha_hora": fecha_hora,
            "id_cuenta_emisor": cuenta["id_cuenta_emisor"],
            "id_cuenta_receptor": id_receptor,
            "id_entidad_receptor": random.choice(["BNF", "ITAU", "CONTINENTAL", "FAMILIAR", "GNB", "UENO"]),
            "monto_pyg": monto,
            "id_dispositivo_emisor": dispositivo,
            "direccion_ip_emisor": generar_ip_paraguaya(),
            "geo_latitud_emisor": lat,
            "geo_longitud_emisor": lon,
            "es_fraude": 1,
            "escenario_fraude": escenario,
            "_lat_habitual": cuenta["lat_habitual"],
            "_lon_habitual": cuenta["lon_habitual"],
            "_hora_inicio_hab": cuenta["hora_inicio_habitual"],
            "_hora_fin_hab": cuenta["hora_fin_habitual"],
            "_monto_promedio_hist": cuenta["monto_promedio_historico"],
            "_fecha_creacion": cuenta["fecha_creacion_cuenta"],
            "_dispositivos_pref": cuenta["dispositivos_preferidos"],
        })
    
    df = pd.DataFrame(transacciones)
    df = df.sort_values("fecha_hora").reset_index(drop=True)
    print(f"Total transacciones generadas: {len(df):,}")
    print(f"Distribución de fraude:\n{df['es_fraude'].value_counts(normalize=True)}")
    return df


# ============================================================
# 3. CÁLCULO DE FEATURES (Opción A - realista)
# ============================================================

def calcular_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula todas las variables de la sección B de forma correcta
    (orden temporal, sin leakage).
    """
    print("Calculando features de velocity, geolocalización y comportamiento...")
    
    df = df.copy()
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    
    # -------------------------------------------------------
    # Features temporales básicas
    # -------------------------------------------------------
    df["hora_del_dia"] = df["fecha_hora"].dt.hour
    df["dia_semana"] = df["fecha_hora"].dt.dayofweek          # 0=lunes ... 6=domingo
    df["es_fin_de_semana"] = df["dia_semana"].isin([5, 6]).astype(int)
    df["es_horario_nocturno"] = df["hora_del_dia"].between(HORARIO_NOCTURNO[0], HORARIO_NOCTURNO[1]).astype(int)
    
    # Codificación cíclica de la hora
    df["hora_sin"], df["hora_cos"] = zip(*df["hora_del_dia"].map(codificacion_ciclica_hora))
    
    # -------------------------------------------------------
    # Distancia a zona habitual + ubicación inusual
    # -------------------------------------------------------
    df["distancia_zona_habitual_km"] = df.apply(
        lambda r: haversine_km(r["geo_latitud_emisor"], r["geo_longitud_emisor"],
                               r["_lat_habitual"], r["_lon_habitual"]), axis=1
    ).round(2)
    
    df["ubicacion_inusual"] = (df["distancia_zona_habitual_km"] > UMBRAL_DISTANCIA_INUSUAL_KM).astype(int)
    
    # -------------------------------------------------------
    # Horario habitual del usuario
    # -------------------------------------------------------
    def es_horario_habitual(row):
        h = row["hora_del_dia"]
        inicio = row["_hora_inicio_hab"]
        fin = row["_hora_fin_hab"]
        if inicio <= fin:
            return int(inicio <= h <= fin)
        else:  # cruza medianoche
            return int(h >= inicio or h <= fin)
    
    df["horario_habitual"] = df.apply(es_horario_habitual, axis=1)
    
    # -------------------------------------------------------
    # Antigüedad de la cuenta al momento de la transacción
    # -------------------------------------------------------
    df["antiguedad_cuenta_dias"] = (df["fecha_hora"] - df["_fecha_creacion"]).dt.days
    
    # -------------------------------------------------------
    # Features de velocity + beneficiarios + dispositivo/IP
    # Se calculan por cuenta emisora en orden temporal
    # -------------------------------------------------------
    df = df.sort_values(["id_cuenta_emisor", "fecha_hora"]).reset_index(drop=True)
    
    # Inicializamos columnas
    velocity_cols = [
        "tx_count_1h", "tx_count_24h", "amount_sum_1h", "amount_sum_24h",
        "unique_beneficiaries_24h", "new_beneficiaries_1h", "is_new_beneficiary",
        "dispositivo_nuevo_emisor", "ip_nueva_emisor", "cambio_de_dispositivo",
        "monto_promedio_usuario_30d", "ratio_monto_vs_promedio"
    ]
    for col in velocity_cols:
        df[col] = 0
    
    # Procesamos por cuenta
    for cuenta, grupo in df.groupby("id_cuenta_emisor"):
        idx = grupo.index
        grupo = grupo.sort_values("fecha_hora")
        
        # Historial de beneficiarios, dispositivos e IPs
        beneficiarios_vistos = set()
        dispositivos_vistos = set()
        ips_vistas = set()
        dispositivo_anterior = None
        
        # Para velocity usamos índices temporales
        timestamps = grupo["fecha_hora"].values
        montos = grupo["monto_pyg"].values
        receptores = grupo["id_cuenta_receptor"].values
        dispositivos = grupo["id_dispositivo_emisor"].values
        ips = grupo["direccion_ip_emisor"].values
        
        tx_count_1h = np.zeros(len(grupo))
        tx_count_24h = np.zeros(len(grupo))
        amount_sum_1h = np.zeros(len(grupo))
        amount_sum_24h = np.zeros(len(grupo))
        unique_ben_24h = np.zeros(len(grupo))
        new_ben_1h = np.zeros(len(grupo))
        is_new_ben = np.zeros(len(grupo))
        disp_nuevo = np.zeros(len(grupo))
        ip_nueva = np.zeros(len(grupo))
        cambio_disp = np.zeros(len(grupo))
        monto_prom_30d = np.zeros(len(grupo))
        ratio_monto = np.zeros(len(grupo))
        
        # Ventanas deslizantes simples (eficiente para este tamaño)
        for i in range(len(grupo)):
            t_actual = timestamps[i]
            
            # Ventana 1 hora
            mask_1h = (timestamps >= t_actual - np.timedelta64(1, 'h')) & (timestamps < t_actual)
            tx_count_1h[i] = mask_1h.sum()
            amount_sum_1h[i] = montos[mask_1h].sum()
            
            # Ventana 24 horas
            mask_24h = (timestamps >= t_actual - np.timedelta64(24, 'h')) & (timestamps < t_actual)
            tx_count_24h[i] = mask_24h.sum()
            amount_sum_24h[i] = montos[mask_24h].sum()
            
            # Beneficiarios únicos en 24h
            bens_24h = set(receptores[mask_24h])
            unique_ben_24h[i] = len(bens_24h)
            
            # Nuevos beneficiarios en 1h
            bens_1h = set(receptores[mask_1h])
            nuevos_1h = bens_1h - beneficiarios_vistos
            new_ben_1h[i] = len(nuevos_1h)
            
            # ¿Es beneficiario nuevo?
            receptor_actual = receptores[i]
            is_new_ben[i] = 0 if receptor_actual in beneficiarios_vistos else 1
            beneficiarios_vistos.add(receptor_actual)
            
            # Dispositivo nuevo
            disp_actual = dispositivos[i]
            disp_nuevo[i] = 0 if disp_actual in dispositivos_vistos else 1
            dispositivos_vistos.add(disp_actual)
            
            # Cambio de dispositivo
            if dispositivo_anterior is not None and disp_actual != dispositivo_anterior:
                cambio_disp[i] = 1
            dispositivo_anterior = disp_actual
            
            # IP nueva
            ip_actual = ips[i]
            ip_nueva[i] = 0 if ip_actual in ips_vistas else 1
            ips_vistas.add(ip_actual)
            
            # Monto promedio últimos 30 días (aproximación con histórico + recientes)
            mask_30d = (timestamps >= t_actual - np.timedelta64(30, 'D')) & (timestamps < t_actual)
            if mask_30d.sum() > 0:
                prom = montos[mask_30d].mean()
            else:
                prom = grupo.iloc[i]["_monto_promedio_hist"]
            monto_prom_30d[i] = prom
            ratio_monto[i] = montos[i] / (prom + 1)
        
        # Asignamos de vuelta
        df.loc[idx, "tx_count_1h"] = tx_count_1h
        df.loc[idx, "tx_count_24h"] = tx_count_24h
        df.loc[idx, "amount_sum_1h"] = amount_sum_1h
        df.loc[idx, "amount_sum_24h"] = amount_sum_24h
        df.loc[idx, "unique_beneficiaries_24h"] = unique_ben_24h
        df.loc[idx, "new_beneficiaries_1h"] = new_ben_1h
        df.loc[idx, "is_new_beneficiary"] = is_new_ben
        df.loc[idx, "dispositivo_nuevo_emisor"] = disp_nuevo
        df.loc[idx, "ip_nueva_emisor"] = ip_nueva
        df.loc[idx, "cambio_de_dispositivo"] = cambio_disp
        df.loc[idx, "monto_promedio_usuario_30d"] = np.round(monto_prom_30d, 0)
        df.loc[idx, "ratio_monto_vs_promedio"] = np.round(ratio_monto, 4)
    
    # -------------------------------------------------------
    # Limpieza final
    # -------------------------------------------------------
    # Eliminamos columnas auxiliares
    cols_aux = [c for c in df.columns if c.startswith("_")]
    df = df.drop(columns=cols_aux)
    
    # Orden final de columnas
    columnas_finales = [
        # A. Originales
        "id_transaccion", "fecha_hora", "id_cuenta_emisor", "id_cuenta_receptor",
        "id_entidad_receptor", "monto_pyg", "id_dispositivo_emisor",
        "direccion_ip_emisor", "geo_latitud_emisor", "geo_longitud_emisor",
        # B. Calculadas
        "hora_del_dia", "hora_sin", "hora_cos", "dia_semana", "es_fin_de_semana",
        "es_horario_nocturno", "horario_habitual", "cambio_de_dispositivo",
        "ubicacion_inusual", "distancia_zona_habitual_km", "ip_nueva_emisor",
        "dispositivo_nuevo_emisor", "antiguedad_cuenta_dias",
        "tx_count_1h", "tx_count_24h", "amount_sum_1h", "amount_sum_24h",
        "unique_beneficiaries_24h", "new_beneficiaries_1h", "is_new_beneficiary",
        "monto_promedio_usuario_30d", "ratio_monto_vs_promedio",
        # C. Etiquetas
        "es_fraude", "escenario_fraude"
    ]
    
    df = df[columnas_finales]
    return df


# ============================================================
# 4. MAIN
# ============================================================

def main():
    print("=" * 70)
    print(" GENERADOR DE DATASET SINTÉTICO - FRAUDE SPI PARAGUAY")
    print("=" * 70)
    
    # Crear carpeta de salida
    os.makedirs("data", exist_ok=True)
    
    # 1. Perfiles de cuentas
    cuentas_df = crear_cuentas_emisoras(N_CUENTAS_EMISORAS)
    
    # 2. Transacciones base (normales + fraude)
    df_raw = generar_transacciones_base(cuentas_df, N_TRANSACCIONES_NORMALES, N_FRAUDES)
    
    # 3. Calcular todas las features
    df = calcular_features(df_raw)
    
    # 4. Guardar
    path_parquet = "data/transacciones_spi_sinteticas.parquet"
    path_csv = "data/transacciones_spi_sinteticas.csv"
    
    df.to_parquet(path_parquet, index=False)
    df.to_csv(path_csv, index=False)
    
    # Lista de features para el modelo (sin IDs ni etiquetas)
    feature_cols = [
        "hora_del_dia", "hora_sin", "hora_cos", "dia_semana", "es_fin_de_semana",
        "es_horario_nocturno", "horario_habitual", "cambio_de_dispositivo",
        "ubicacion_inusual", "distancia_zona_habitual_km", "ip_nueva_emisor",
        "dispositivo_nuevo_emisor", "antiguedad_cuenta_dias",
        "tx_count_1h", "tx_count_24h", "amount_sum_1h", "amount_sum_24h",
        "unique_beneficiaries_24h", "new_beneficiaries_1h", "is_new_beneficiary",
        "monto_promedio_usuario_30d", "ratio_monto_vs_promedio", "monto_pyg"
    ]
    joblib.dump(feature_cols, "data/feature_cols.joblib")
    
    # Resumen
    resumen = f"""
================================================================================
RESUMEN DEL DATASET GENERADO
================================================================================
Fecha de generación: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Periodo de transacciones: {FECHA_INICIO.date()} → {FECHA_FIN.date()}

Total de transacciones: {len(df):,}
Transacciones normales: {(df.es_fraude == 0).sum():,}
Transacciones fraudulentas: {(df.es_fraude == 1).sum():,}
Tasa de fraude: {df.es_fraude.mean()*100:.4f}%

Distribución de escenarios de fraude:
{df[df.es_fraude == 1]['escenario_fraude'].value_counts().to_string()}

Archivos generados:
- {path_parquet}
- {path_csv}
- data/feature_cols.joblib

Features disponibles para el modelo ({len(feature_cols)}):
{feature_cols}
================================================================================
"""
    print(resumen)
    
    with open("data/resumen_dataset.txt", "w", encoding="utf-8") as f:
        f.write(resumen)
    
    print("Dataset generado exitosamente.")
    return df


if __name__ == "__main__":
    df_final = main()