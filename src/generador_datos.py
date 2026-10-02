"""
Generador de datos sintéticos para un detector de anomalías
en transferencias SPI desde la perspectiva del banco emisor. (primera verision) 

Prueba rápida:
- 230 cuentas emisoras ficticias.
- 5.000 transferencias simuladas durante 30 días.
- 25 fraudes exactos: 0,5 %.
- Sin historial individual ni variables de ventanas temporales.
- metodo_iniciacion queda solo para trazabilidad:
  no se modifica para inyectar fraude y no se usa en XGBoost.

"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# 1. CONFIGURACIÓN GENERAL
# ============================================================

SEMILLA = 42

random.seed(SEMILLA)
np.random.seed(SEMILLA)

CONFIG = {
    "cantidad_usuarios": 230,
    "cantidad_transferencias": 5_000,
    "cantidad_fraudes": 25,
    "fecha_inicio": datetime(2026, 1, 1, 0, 0, 0),
    "dias_simulacion": 30,
    "monto_minimo_pyg": 1,
    "monto_maximo_spi_pyg": 10_000_000,
}


# ============================================================
# 2. CENTROS GEOGRÁFICOS SIMULADOS
# ============================================================

CENTROS_CIUDADES = {
    "ASUNCION": (-25.2867, -57.6470),
    "SAN_LORENZO": (-25.3400, -57.5100),
    "LUQUE": (-25.2667, -57.4917),
    "CAPIATA": (-25.3550, -57.4450),
    "FERNANDO_DE_LA_MORA": (-25.3397, -57.5214),
    "LIMPIO": (-25.1667, -57.4833),

    "CIUDAD_DEL_ESTE": (-25.5097, -54.6111),
    "ENCARNACION": (-27.3306, -55.8667),
    "CORONEL_OVIEDO": (-25.4444, -56.4403),
    "CAAGUAZU": (-25.4500, -56.0200),
    "VILLARRICA": (-25.7800, -56.4400),
    "PARAGUARI": (-25.6200, -57.1500),
    "CAAZAPA": (-26.2000, -56.3700),

    "CONCEPCION": (-23.3990, -57.4320),
    "HORQUETA": (-23.3400, -57.0600),
    "SAN_PEDRO_DEL_YCUAMANDYYU": (-24.0800, -57.0800),
    "PEDRO_JUAN_CABALLERO": (-22.5470, -55.7330),
    "SALTO_DEL_GUAIRA": (-24.0600, -54.3100),

    "PILAR": (-26.8600, -58.3000),
    "SAN_JUAN_BAUTISTA": (-26.6800, -57.1500),
    "AYOLAS": (-27.4000, -56.9000),

    "FILADELFIA": (-22.3500, -60.0300),
    "MARISCAL_ESTIGARRIBIA": (-22.0300, -60.6200),
    "FUERTE_OLIMPO": (-21.0500, -57.8700),
}


# ============================================================
# 3. SEGMENTOS DE COMPORTAMIENTO
# ============================================================

SEGMENTOS = {
    "S1_PERSONAL_COTIDIANO": {
        "peso_usuarios": 0.55,

        "frecuencia_mensual_transferencias": (3, 14),

        "monto_media_pyg": 180_000,
        "monto_desviacion_pyg": 100_000,
        "monto_normal_min_pyg": 10_000,
        "monto_normal_max_pyg": 700_000,

        "horas_activas": (7, 22),

        "pesos_metodo_iniciacion": {
            "MANUAL": 0.10,
            "ALIAS": 0.50,
            "QR": 0.40,
        },

        "probabilidad_cambio_dispositivo": 0.02,

        "zonas_habituales": [
            "ASUNCION",
            "SAN_LORENZO",
            "LUQUE",
            "CAPIATA",
            "FERNANDO_DE_LA_MORA",
        ],

        "radio_normal_km": 25,
    },

    "S2_PERSONAL_MAYOR_MOVIMIENTO": {
        "peso_usuarios": 0.20,

        "frecuencia_mensual_transferencias": (8, 28),

        "monto_media_pyg": 900_000,
        "monto_desviacion_pyg": 650_000,
        "monto_normal_min_pyg": 50_000,
        "monto_normal_max_pyg": 4_500_000,

        "horas_activas": (6, 23),

        "pesos_metodo_iniciacion": {
            "MANUAL": 0.35,
            "ALIAS": 0.40,
            "QR": 0.25,
        },

        "probabilidad_cambio_dispositivo": 0.03,

        "zonas_habituales": [
            "ASUNCION",
            "SAN_LORENZO",
            "LUQUE",
            "CIUDAD_DEL_ESTE",
            "ENCARNACION",
        ],

        "radio_normal_km": 80,
    },

    "S3_MICROEMPRENDEDOR": {
        "peso_usuarios": 0.18,

        "frecuencia_mensual_transferencias": (18, 65),

        "monto_media_pyg": 1_300_000,
        "monto_desviacion_pyg": 1_100_000,
        "monto_normal_min_pyg": 50_000,
        "monto_normal_max_pyg": 6_000_000,

        "horas_activas": (7, 21),

        "pesos_metodo_iniciacion": {
            "MANUAL": 0.45,
            "ALIAS": 0.45,
            "QR": 0.10,
        },

        "probabilidad_cambio_dispositivo": 0.04,

        "zonas_habituales": [
            "ASUNCION",
            "SAN_LORENZO",
            "LUQUE",
            "CAPIATA",
            "CIUDAD_DEL_ESTE",
            "ENCARNACION",
            "CORONEL_OVIEDO",
        ],

        "radio_normal_km": 60,
    },

    "S4_PYME_PAGADORA": {
        "peso_usuarios": 0.07,

        "frecuencia_mensual_transferencias": (45, 130),

        "monto_media_pyg": 3_800_000,
        "monto_desviacion_pyg": 2_000_000,
        "monto_normal_min_pyg": 150_000,
        "monto_normal_max_pyg": 9_500_000,

        "horas_activas": (8, 18),

        "pesos_metodo_iniciacion": {
            "MANUAL": 0.65,
            "ALIAS": 0.30,
            "QR": 0.05,
        },

        "probabilidad_cambio_dispositivo": 0.05,

        "zonas_habituales": [
            "ASUNCION",
            "CIUDAD_DEL_ESTE",
            "ENCARNACION",
            "CORONEL_OVIEDO",
        ],

        "radio_normal_km": 40,
    },
}


# ============================================================
# 4. VARIABILIDAD LEGÍTIMA
# ============================================================

VARIABILIDAD = {
    "probabilidad_monto_alto_legitimo": {
        "S1_PERSONAL_COTIDIANO": 0.015,
        "S2_PERSONAL_MAYOR_MOVIMIENTO": 0.050,
        "S3_MICROEMPRENDEDOR": 0.080,
        "S4_PYME_PAGADORA": 0.100,
    },

    "factor_monto_alto_legitimo": {
        "S1_PERSONAL_COTIDIANO": (1.5, 3.5),
        "S2_PERSONAL_MAYOR_MOVIMIENTO": (1.5, 3.0),
        "S3_MICROEMPRENDEDOR": (1.3, 2.5),
        "S4_PYME_PAGADORA": (1.1, 1.5),
    },

    "probabilidad_hora_fuera_rango_legitima": 0.02,
    "probabilidad_geo_fuera_perfil_legitima": 0.015,
}


# ============================================================
# 5. ESCENARIOS DE FRAUDE
# ============================================================

ESCENARIOS_FRAUDE = {
    "F01_TOMA_CUENTA": {
        "peso": 0.35,

        "segmentos_aplicables": [
            "S1_PERSONAL_COTIDIANO",
            "S2_PERSONAL_MAYOR_MOVIMIENTO",
            "S3_MICROEMPRENDEDOR",
            "S4_PYME_PAGADORA",
        ],

        "rango_zscore_documentado": (3.0, 7.0),

        "requiere_fuera_rango_monto": True,
    },

    "F02_INGENIERIA_SOCIAL": {
        "peso": 0.30,

        "segmentos_aplicables": [
            "S1_PERSONAL_COTIDIANO",
            "S2_PERSONAL_MAYOR_MOVIMIENTO",
            "S3_MICROEMPRENDEDOR",
        ],

        "rango_zscore_documentado": (2.5, 6.0),

        "requiere_fuera_rango_monto": True,
    },

    "F03_OPERACION_NOCTURNA": {
        "peso": 0.20,

        "segmentos_aplicables": [
            "S1_PERSONAL_COTIDIANO",
            "S2_PERSONAL_MAYOR_MOVIMIENTO",
            "S3_MICROEMPRENDEDOR",
            "S4_PYME_PAGADORA",
        ],

        "rango_zscore_documentado": (1.0, 3.5),

        "requiere_fuera_rango_monto": False,
    },

    "F04_ANOMALIA_COMBINADA": {
        "peso": 0.15,

        "segmentos_aplicables": [
            "S1_PERSONAL_COTIDIANO",
            "S2_PERSONAL_MAYOR_MOVIMIENTO",
            "S3_MICROEMPRENDEDOR",
            "S4_PYME_PAGADORA",
        ],

        "rango_zscore_documentado": (1.5, 3.0),

        "requiere_fuera_rango_monto": False,
    },
}


# ============================================================
# 6. FUNCIONES AUXILIARES
# ============================================================

def elegir_ponderado(valores, pesos):
    return random.choices(
        population=valores,
        weights=pesos,
        k=1,
    )[0]


def hora_normal(segmento):
    inicio, fin = segmento["horas_activas"]
    return random.randint(inicio, fin)


def hora_fuera_rango(segmento):
    inicio, fin = segmento["horas_activas"]

    horas_fuera = [
        hora
        for hora in range(24)
        if hora < inicio or hora > fin
    ]

    return random.choice(horas_fuera)


def distancia_haversine_km(lat1, lon1, lat2, lon2):
    radio_tierra_km = 6371.0

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )

    return 2 * radio_tierra_km * math.asin(
        math.sqrt(a)
    )


def distancia_minima_zona_segmento(latitud, longitud, segmento):
    return min(
        distancia_haversine_km(
            latitud,
            longitud,
            CENTROS_CIUDADES[ciudad][0],
            CENTROS_CIUDADES[ciudad][1],
        )
        for ciudad in segmento["zonas_habituales"]
    )


def generar_coordenada_normal(segmento):
    ciudad = random.choice(
        segmento["zonas_habituales"]
    )

    latitud_centro, longitud_centro = (
        CENTROS_CIUDADES[ciudad]
    )

    latitud = latitud_centro + float(
        np.random.normal(0, 0.008)
    )

    longitud = longitud_centro + float(
        np.random.normal(0, 0.008)
    )

    return latitud, longitud


def generar_coordenada_fuera_zona(segmento):
    ciudades_candidatas = [
        ciudad
        for ciudad in CENTROS_CIUDADES
        if ciudad not in segmento["zonas_habituales"]
    ]

    for _ in range(500):
        ciudad = random.choice(
            ciudades_candidatas
        )

        latitud_centro, longitud_centro = (
            CENTROS_CIUDADES[ciudad]
        )

        latitud = latitud_centro + float(
            np.random.normal(0, 0.008)
        )

        longitud = longitud_centro + float(
            np.random.normal(0, 0.008)
        )

        distancia = distancia_minima_zona_segmento(
            latitud,
            longitud,
            segmento,
        )

        if distancia > segmento["radio_normal_km"]:
            return latitud, longitud

    raise RuntimeError(
        "No se encontró una coordenada fuera de zona "
        "después de 500 intentos."
    )


def generar_monto_normal(codigo_segmento, segmento):
    monto = float(
        np.random.normal(
            segmento["monto_media_pyg"],
            segmento["monto_desviacion_pyg"],
        )
    )

    monto = max(
        segmento["monto_normal_min_pyg"],
        monto,
    )

    monto = min(
        segmento["monto_normal_max_pyg"],
        monto,
    )

    if random.random() < VARIABILIDAD[
        "probabilidad_monto_alto_legitimo"
    ][codigo_segmento]:

        minimo, maximo = VARIABILIDAD[
            "factor_monto_alto_legitimo"
        ][codigo_segmento]

        monto = min(
            segmento["monto_normal_max_pyg"],
            monto * random.uniform(minimo, maximo),
        )

    monto = max(
        CONFIG["monto_minimo_pyg"],
        monto,
    )

    return int(round(monto))


def generar_monto_fraude(
    segmento,
    rango_zscore_documentado,
    requiere_fuera_rango,
):
    """
    Genera un monto que respeta simultáneamente:

    - El intervalo documentado de z-score del escenario.
    - El límite máximo SPI de Gs. 10.000.000.
    - El requisito de estar fuera del rango normal, cuando corresponda.
    """

    zscore_minimo_escenario, zscore_maximo_escenario = (
        rango_zscore_documentado
    )

    zscore_maximo_spi = (
        (
            CONFIG["monto_maximo_spi_pyg"]
            - segmento["monto_media_pyg"]
        )
        / segmento["monto_desviacion_pyg"]
    )

    zscore_minimo_valido = (
        zscore_minimo_escenario
    )

    zscore_maximo_valido = min(
        zscore_maximo_escenario,
        zscore_maximo_spi,
    )

    if requiere_fuera_rango:
        zscore_minimo_fuera_rango = (
            (
                segmento["monto_normal_max_pyg"]
                - segmento["monto_media_pyg"]
            )
            / segmento["monto_desviacion_pyg"]
        ) + 0.05

        zscore_minimo_valido = max(
            zscore_minimo_valido,
            zscore_minimo_fuera_rango,
        )

    if zscore_minimo_valido > zscore_maximo_valido:
        raise ValueError(
            "No existe un monto válido para este escenario "
            "que respete al mismo tiempo el rango de z-score, "
            "el rango normal y el límite SPI."
        )

    zscore = random.uniform(
        zscore_minimo_valido,
        zscore_maximo_valido,
    )

    monto = int(
        round(
            segmento["monto_media_pyg"]
            + zscore
            * segmento["monto_desviacion_pyg"]
        )
    )

    assert (
        CONFIG["monto_minimo_pyg"]
        <= monto
        <= CONFIG["monto_maximo_spi_pyg"]
    )

    return monto


def generar_metodo_iniciacion(segmento):
    metodos = list(
        segmento["pesos_metodo_iniciacion"].keys()
    )

    pesos = list(
        segmento["pesos_metodo_iniciacion"].values()
    )

    return elegir_ponderado(
        metodos,
        pesos,
    )


# ============================================================
# 7. USUARIOS Y FRECUENCIAS
# ============================================================

def crear_usuarios():
    codigos_segmento = list(SEGMENTOS.keys())

    pesos_segmento = [
        SEGMENTOS[codigo]["peso_usuarios"]
        for codigo in codigos_segmento
    ]

    usuarios = []

    for numero_usuario in range(
        1,
        CONFIG["cantidad_usuarios"] + 1,
    ):
        codigo_segmento = elegir_ponderado(
            codigos_segmento,
            pesos_segmento,
        )

        segmento = SEGMENTOS[codigo_segmento]

        frecuencia_minima, frecuencia_maxima = (
            segmento[
                "frecuencia_mensual_transferencias"
            ]
        )

        frecuencia_mensual = random.randint(
            frecuencia_minima,
            frecuencia_maxima,
        )

        usuarios.append(
            {
                "id_cuenta_emisor": (
                    f"CTA-EMI-{numero_usuario:06d}"
                ),
                "segmento_generador": codigo_segmento,
                "frecuencia_mensual": frecuencia_mensual,
            }
        )

    return usuarios


def ajustar_frecuencias_al_objetivo(usuarios):
    objetivo = CONFIG["cantidad_transferencias"]

    total_actual = sum(
        usuario["frecuencia_mensual"]
        for usuario in usuarios
    )

    while total_actual < objetivo:
        candidatos = [
            usuario
            for usuario in usuarios
            if usuario["frecuencia_mensual"]
            < SEGMENTOS[
                usuario["segmento_generador"]
            ]["frecuencia_mensual_transferencias"][1]
        ]

        if not candidatos:
            raise RuntimeError(
                "No se puede aumentar la frecuencia "
                "sin superar máximos de segmento."
            )

        usuario = random.choice(candidatos)

        usuario["frecuencia_mensual"] += 1

        total_actual += 1

    while total_actual > objetivo:
        candidatos = [
            usuario
            for usuario in usuarios
            if usuario["frecuencia_mensual"]
            > SEGMENTOS[
                usuario["segmento_generador"]
            ]["frecuencia_mensual_transferencias"][0]
        ]

        if not candidatos:
            raise RuntimeError(
                "No se puede reducir la frecuencia "
                "sin bajar de mínimos de segmento."
            )

        usuario = random.choice(candidatos)

        usuario["frecuencia_mensual"] -= 1

        total_actual -= 1

    assert sum(
        usuario["frecuencia_mensual"]
        for usuario in usuarios
    ) == objetivo

    return usuarios


# ============================================================
# 8. GENERACIÓN DE TRANSACCIÓN NORMAL
# ============================================================

def generar_transaccion_normal(usuario, consecutivo):
    codigo_segmento = usuario[
        "segmento_generador"
    ]

    segmento = SEGMENTOS[codigo_segmento]

    segundos_periodo = (
        CONFIG["dias_simulacion"]
        * 24
        * 60
        * 60
    )

    fecha_hora = CONFIG["fecha_inicio"] + timedelta(
        seconds=random.randint(
            0,
            segundos_periodo - 1,
        )
    )

    if random.random() < VARIABILIDAD[
        "probabilidad_hora_fuera_rango_legitima"
    ]:
        hora = hora_fuera_rango(segmento)
    else:
        hora = hora_normal(segmento)

    fecha_hora = fecha_hora.replace(
        hour=hora,
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
    )

    if random.random() < VARIABILIDAD[
        "probabilidad_geo_fuera_perfil_legitima"
    ]:
        latitud, longitud = generar_coordenada_fuera_zona(
            segmento
        )
    else:
        latitud, longitud = generar_coordenada_normal(
            segmento
        )

    return {
        "id_transaccion": f"TX{consecutivo:06d}",
        "fecha_hora": fecha_hora,

        "id_cuenta_emisor": usuario[
            "id_cuenta_emisor"
        ],

        "id_cuenta_receptor": (
            f"CTA-REC-{random.randint(1, 920):06d}"
        ),

        "id_entidad_receptor": (
            f"ENTIDAD_{random.randint(1, 6):02d}"
        ),

        "monto_pyg": generar_monto_normal(
            codigo_segmento,
            segmento,
        ),

        "metodo_iniciacion": generar_metodo_iniciacion(
            segmento
        ),

        "id_dispositivo_emisor": (
            f"DISP-"
            f"{random.randint(1, CONFIG['cantidad_usuarios'] * 3):06d}"
        ),

        "cambio_de_dispositivo": int(
            random.random()
            < segmento[
                "probabilidad_cambio_dispositivo"
            ]
        ),

        "direccion_ip_emisor": (
            f"181."
            f"{random.randint(0, 255)}."
            f"{random.randint(0, 255)}."
            f"{random.randint(1, 254)}"
        ),

        "geo_latitud_emisor": round(
            latitud,
            6,
        ),

        "geo_longitud_emisor": round(
            longitud,
            6,
        ),

        "es_fraude": 0,
        "segmento_generador": codigo_segmento,
        "escenario_fraude": "NINGUNO",
    }


# ============================================================
# 9. INYECCIÓN DE FRAUDE
# ============================================================

def elegir_escenario_compatible(codigo_segmento):
    escenarios_compatibles = [
        codigo_escenario
        for codigo_escenario, configuracion in (
            ESCENARIOS_FRAUDE.items()
        )
        if codigo_segmento
        in configuracion["segmentos_aplicables"]
    ]

    pesos = [
        ESCENARIOS_FRAUDE[codigo]["peso"]
        for codigo in escenarios_compatibles
    ]

    return elegir_ponderado(
        escenarios_compatibles,
        pesos,
    )


def inyectar_fraude(transaccion, escenario):
    """
    Modifica solamente:

    - monto_pyg
    - fecha_hora
    - geo_latitud_emisor
    - geo_longitud_emisor
    - cambio_de_dispositivo

    metodo_iniciacion no se modifica ni participa
    en la generación del fraude.
    """

    codigo_segmento = transaccion[
        "segmento_generador"
    ]

    segmento = SEGMENTOS[codigo_segmento]

    configuracion = ESCENARIOS_FRAUDE[escenario]

    transaccion["monto_pyg"] = generar_monto_fraude(
        segmento=segmento,
        rango_zscore_documentado=configuracion[
            "rango_zscore_documentado"
        ],
        requiere_fuera_rango=configuracion[
            "requiere_fuera_rango_monto"
        ],
    )

    if escenario == "F01_TOMA_CUENTA":
        transaccion["fecha_hora"] = (
            transaccion["fecha_hora"].replace(
                hour=hora_fuera_rango(segmento),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )
        )

        latitud, longitud = generar_coordenada_fuera_zona(
            segmento
        )

        transaccion["geo_latitud_emisor"] = round(
            latitud,
            6,
        )

        transaccion["geo_longitud_emisor"] = round(
            longitud,
            6,
        )

        transaccion["cambio_de_dispositivo"] = 1

    elif escenario == "F02_INGENIERIA_SOCIAL":
        transaccion["fecha_hora"] = (
            transaccion["fecha_hora"].replace(
                hour=hora_normal(segmento),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )
        )

        latitud, longitud = generar_coordenada_normal(
            segmento
        )

        transaccion["geo_latitud_emisor"] = round(
            latitud,
            6,
        )

        transaccion["geo_longitud_emisor"] = round(
            longitud,
            6,
        )

        transaccion["cambio_de_dispositivo"] = 0

    elif escenario == "F03_OPERACION_NOCTURNA":
        transaccion["fecha_hora"] = (
            transaccion["fecha_hora"].replace(
                hour=random.randint(0, 5),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )
        )

        senales_adicionales = random.sample(
            ["geo", "dispositivo"],
            k=random.choice([1, 2]),
        )

        if "geo" in senales_adicionales:
            latitud, longitud = (
                generar_coordenada_fuera_zona(
                    segmento
                )
            )

            transaccion["geo_latitud_emisor"] = round(
                latitud,
                6,
            )

            transaccion["geo_longitud_emisor"] = round(
                longitud,
                6,
            )

        if "dispositivo" in senales_adicionales:
            transaccion["cambio_de_dispositivo"] = 1

    elif escenario == "F04_ANOMALIA_COMBINADA":
        senales_adicionales = random.sample(
            ["hora", "geo", "dispositivo"],
            k=random.choice([2, 3]),
        )

        if "hora" in senales_adicionales:
            transaccion["fecha_hora"] = (
                transaccion["fecha_hora"].replace(
                    hour=hora_fuera_rango(segmento),
                    minute=random.randint(0, 59),
                    second=random.randint(0, 59),
                )
            )

        if "geo" in senales_adicionales:
            latitud, longitud = (
                generar_coordenada_fuera_zona(
                    segmento
                )
            )

            transaccion["geo_latitud_emisor"] = round(
                latitud,
                6,
            )

            transaccion["geo_longitud_emisor"] = round(
                longitud,
                6,
            )

        if "dispositivo" in senales_adicionales:
            transaccion["cambio_de_dispositivo"] = 1

    else:
        raise ValueError(
            f"Escenario desconocido: {escenario}"
        )

    transaccion["es_fraude"] = 1

    transaccion["escenario_fraude"] = escenario

    return transaccion


# ============================================================
# 10. CÁLCULO DE FEATURES DERIVADAS
# ============================================================

def calcular_features(df):
    resultado = df.copy()

    zscores = []
    fuera_rango_monto = []
    fuera_rango_hora = []
    fuera_zona_geo = []

    for fila in resultado.itertuples(index=False):
        segmento = SEGMENTOS[
            fila.segmento_generador
        ]

        zscore = (
            fila.monto_pyg
            - segmento["monto_media_pyg"]
        ) / segmento["monto_desviacion_pyg"]

        zscores.append(
            round(
                float(zscore),
                6,
            )
        )

        fuera_rango_monto.append(
            int(
                fila.monto_pyg
                < segmento["monto_normal_min_pyg"]
                or fila.monto_pyg
                > segmento["monto_normal_max_pyg"]
            )
        )

        hora = pd.Timestamp(
            fila.fecha_hora
        ).hour

        inicio, fin = segmento["horas_activas"]

        fuera_rango_hora.append(
            int(
                hora < inicio
                or hora > fin
            )
        )

        distancia_minima = (
            distancia_minima_zona_segmento(
                fila.geo_latitud_emisor,
                fila.geo_longitud_emisor,
                segmento,
            )
        )

        fuera_zona_geo.append(
            int(
                distancia_minima
                > segmento["radio_normal_km"]
            )
        )

    horas = pd.to_datetime(
        resultado["fecha_hora"]
    ).dt.hour

    resultado["zscore_monto_segmento"] = zscores

    resultado[
        "monto_fuera_rango_segmento"
    ] = fuera_rango_monto

    resultado["hora_sin"] = np.sin(
        2
        * np.pi
        * horas
        / 24
    ).round(6)

    resultado["hora_cos"] = np.cos(
        2
        * np.pi
        * horas
        / 24
    ).round(6)

    resultado[
        "hora_fuera_rango_segmento"
    ] = fuera_rango_hora

    resultado[
        "geo_fuera_zona_segmento"
    ] = fuera_zona_geo

    return resultado


# ============================================================
# 11. VALIDACIÓN DE CONSISTENCIA
# ============================================================

def validar_datos(
    transferencias_crudas,
    transferencias_modelo,
    usuarios,
):
    assert len(usuarios) == CONFIG[
        "cantidad_usuarios"
    ]

    assert sum(
        usuario["frecuencia_mensual"]
        for usuario in usuarios
    ) == CONFIG["cantidad_transferencias"]

    assert len(transferencias_crudas) == CONFIG[
        "cantidad_transferencias"
    ]

    assert int(
        transferencias_crudas["es_fraude"].sum()
    ) == CONFIG["cantidad_fraudes"]

    assert transferencias_crudas[
        "monto_pyg"
    ].between(
        CONFIG["monto_minimo_pyg"],
        CONFIG["monto_maximo_spi_pyg"],
    ).all()

    assert transferencias_crudas[
        "metodo_iniciacion"
    ].isin(
        ["MANUAL", "ALIAS", "QR"]
    ).all()

    assert transferencias_crudas[
        "cambio_de_dispositivo"
    ].isin(
        [0, 1]
    ).all()

    assert transferencias_crudas[
        "es_fraude"
    ].isin(
        [0, 1]
    ).all()

    assert transferencias_crudas[
        "geo_latitud_emisor"
    ].notna().all()

    assert transferencias_crudas[
        "geo_longitud_emisor"
    ].notna().all()

    assert (
        transferencias_crudas.loc[
            transferencias_crudas["es_fraude"] == 0,
            "escenario_fraude",
        ]
        == "NINGUNO"
    ).all()

    assert (
        transferencias_crudas.loc[
            transferencias_crudas["es_fraude"] == 1,
            "escenario_fraude",
        ]
        != "NINGUNO"
    ).all()

    assert (
        "metodo_inusual_segmento"
        not in transferencias_modelo.columns
    )

    assert transferencias_modelo[
        "hora_sin"
    ].between(
        -1 - 1e-6,
        1 + 1e-6,
    ).all()

    assert transferencias_modelo[
        "hora_cos"
    ].between(
        -1 - 1e-6,
        1 + 1e-6,
    ).all()

    fraudes = transferencias_modelo[
        transferencias_modelo["es_fraude"] == 1
    ]

    for fila in fraudes.itertuples(index=False):
        if fila.escenario_fraude == "F01_TOMA_CUENTA":
            assert fila.monto_fuera_rango_segmento == 1
            assert fila.hora_fuera_rango_segmento == 1
            assert fila.geo_fuera_zona_segmento == 1
            assert fila.cambio_de_dispositivo == 1

        elif (
            fila.escenario_fraude
            == "F02_INGENIERIA_SOCIAL"
        ):
            assert fila.monto_fuera_rango_segmento == 1
            assert fila.hora_fuera_rango_segmento == 0
            assert fila.geo_fuera_zona_segmento == 0
            assert fila.cambio_de_dispositivo == 0

        elif (
            fila.escenario_fraude
            == "F03_OPERACION_NOCTURNA"
        ):
            hora = pd.Timestamp(
                fila.fecha_hora
            ).hour

            assert hora in [0, 1, 2, 3, 4, 5]

            assert fila.hora_fuera_rango_segmento == 1

            assert (
                fila.geo_fuera_zona_segmento == 1
                or fila.cambio_de_dispositivo == 1
            )

        elif (
            fila.escenario_fraude
            == "F04_ANOMALIA_COMBINADA"
        ):
            assert (
                1.5
                <= fila.zscore_monto_segmento
                <= 3.0
            )

            total_senales = (
                fila.hora_fuera_rango_segmento
                + fila.geo_fuera_zona_segmento
                + fila.cambio_de_dispositivo
            )

            assert total_senales >= 2

        else:
            raise AssertionError(
                f"Escenario desconocido: "
                f"{fila.escenario_fraude}"
            )


# ============================================================
# 12. EJECUCIÓN PRINCIPAL
# ============================================================

def main():
    usuarios = crear_usuarios()

    usuarios = ajustar_frecuencias_al_objetivo(
        usuarios
    )

    transferencias = []

    consecutivo = 1

    for usuario in usuarios:
        for _ in range(
            usuario["frecuencia_mensual"]
        ):
            transaccion = generar_transaccion_normal(
                usuario,
                consecutivo,
            )

            transferencias.append(transaccion)

            consecutivo += 1

    assert len(transferencias) == CONFIG[
        "cantidad_transferencias"
    ]

    indices_fraude = random.sample(
        range(len(transferencias)),
        CONFIG["cantidad_fraudes"],
    )

    for indice in indices_fraude:
        transaccion = transferencias[indice]

        escenario = elegir_escenario_compatible(
            transaccion["segmento_generador"]
        )

        transferencias[indice] = inyectar_fraude(
            transaccion,
            escenario,
        )

    columnas_crudas = [
        "id_transaccion",
        "fecha_hora",
        "id_cuenta_emisor",
        "id_cuenta_receptor",
        "id_entidad_receptor",
        "monto_pyg",
        "metodo_iniciacion",
        "id_dispositivo_emisor",
        "cambio_de_dispositivo",
        "direccion_ip_emisor",
        "geo_latitud_emisor",
        "geo_longitud_emisor",
        "es_fraude",
        "segmento_generador",
        "escenario_fraude",
    ]

    transferencias_crudas = (
        pd.DataFrame(transferencias)
        [columnas_crudas]
        .sort_values("fecha_hora")
        .reset_index(drop=True)
    )

    transferencias_modelo = calcular_features(
        transferencias_crudas
    )

    columnas_modelo = columnas_crudas + [
        "zscore_monto_segmento",
        "monto_fuera_rango_segmento",
        "hora_sin",
        "hora_cos",
        "hora_fuera_rango_segmento",
        "geo_fuera_zona_segmento",
    ]

    transferencias_modelo = (
        transferencias_modelo[columnas_modelo]
    )

    validar_datos(
        transferencias_crudas,
        transferencias_modelo,
        usuarios,
    )

    carpeta_salida = Path("data")

    carpeta_salida.mkdir(exist_ok=True)

    transferencias_crudas.to_csv(
        carpeta_salida
        / "transferencias_crudas.csv",
        index=False,
    )

    transferencias_modelo.to_csv(
        carpeta_salida
        / "transferencias_modelo.csv",
        index=False,
    )

    print("Generación completada y validada.")
    print()

    print(
        f"Usuarios: {len(usuarios)}"
    )

    print(
        f"Transferencias: "
        f"{len(transferencias_crudas)}"
    )

    print(
        f"Fraudes: "
        f"{int(transferencias_crudas['es_fraude'].sum())}"
    )

    print(
        f"Tasa de fraude: "
        f"{transferencias_crudas['es_fraude'].mean():.2%}"
    )

    print()
    print("Fraudes por escenario:")

    print(
        transferencias_crudas.loc[
            transferencias_crudas["es_fraude"] == 1,
            "escenario_fraude",
        ].value_counts()
    )

    print()
    print("Transferencias por segmento:")

    print(
        transferencias_crudas[
            "segmento_generador"
        ].value_counts()
    )


if __name__ == "__main__":
    main()