"""
Generador de transferencias sintéticas del SPI (Sistema de Pagos Instantáneos) con contexto paraguayo,
vistas desde el BANCO EMISOR.

Simula 8.000 clientes de bancos paraguayos durante 13 meses (junio 2025 - junio 2026; junio 2025 se usa
solo como historial previo, el dataset cubre julio 2025 - junio 2026) con comportamientos financieros
realistas (fin de mes, aguinaldo, horarios, ciudades, sesiones de varios pagos seguidos) e inyecta
4 tipologías de fraude con una tasa < 0,1 %.

El dataset se genera LIMPIO desde su creación (no se simulan errores de carga). Su calidad se evalúa
en notebooks/01_eda.ipynb y los modelos se entrenan en notebooks/02_entrenamiento.ipynb (Google Colab).

Salidas (en data/):
    transacciones_spi.csv.gz     dataset completo para el EDA y el entrenamiento
    muestra_transacciones.csv    5.000 filas al azar para inspeccionar en Excel
    demo/flujo_demo.csv          simulador de la demo: todos los fraudes del período de prueba
                                 (may-jun 2026) + 2.500 transferencias legítimas del mismo período

Uso:
    python generar_datos.py                  # configuración por defecto (~2 minutos)
    python generar_datos.py --clientes 1000  # versión chica para pruebas rápidas
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from features import COLUMNAS_DATASET, INICIO_PRUEBA  # noqa: E402  (esquema único del proyecto)

SALIDA = RAIZ / "data" / "transacciones_spi.csv.gz"
MUESTRA = RAIZ / "data" / "muestra_transacciones.csv"
DEMO = RAIZ / "data" / "demo" / "flujo_demo.csv"

# --------------------------------------------------------------------------------------
# Parámetros del contexto paraguayo (pesos aproximados, ver data/DATASET.md)
# --------------------------------------------------------------------------------------
BANCOS = {
    "Banco Itaú": 0.17, "Banco Continental": 0.13, "ueno bank": 0.16, "Banco Familiar": 0.09,
    "Banco Basa": 0.08, "Banco GNB": 0.08, "Banco Atlas": 0.06, "Visión Banco": 0.06,
    "Sudameris Bank": 0.05, "Banco Nacional de Fomento": 0.07, "Interfisa Banco": 0.03,
    "Banco Río": 0.02,
}
CIUDADES = {
    "Asunción": 0.26, "Ciudad del Este": 0.10, "San Lorenzo": 0.07, "Luque": 0.07,
    "Capiatá": 0.05, "Lambaré": 0.05, "Fernando de la Mora": 0.05, "Encarnación": 0.06,
    "Limpio": 0.03, "Ñemby": 0.03, "Pedro Juan Caballero": 0.03, "Coronel Oviedo": 0.03,
    "Concepción": 0.03, "Villarrica": 0.03, "Caaguazú": 0.02, "Hernandarias": 0.02,
    "Itauguá": 0.02, "Mariano Roque Alonso": 0.02,
}

# Perfil horario de uso legítimo (0-23 hs), picos al mediodía y a la salida del trabajo
PERFIL_HORA = np.array([0.4, 0.2, 0.1, 0.1, 0.1, 0.3, 1.0, 2.2, 3.5, 4.5, 5.2, 5.8,
                        6.2, 5.5, 4.8, 4.6, 4.8, 5.4, 6.0, 5.8, 4.8, 3.4, 2.0, 1.0])
PERFIL_HORA = PERFIL_HORA / PERFIL_HORA.sum()
PERFIL_NOCTURNO = np.roll(PERFIL_HORA, 5)  # clientes "noctámbulos" (legítimos)
PERFIL_NOCTURNO = PERFIL_NOCTURNO / PERFIL_NOCTURNO.sum()

INICIO_WARMUP = pd.Timestamp("2025-06-01")  # junio se usa solo para construir historial
INICIO = pd.Timestamp("2025-07-01")
FIN = pd.Timestamp("2026-07-01")            # un año de datos: jul 2025 - jun 2026

SALARIO_MINIMO = 3_044_000   # Gs. mensuales: referencia de capacidad económica, no un límite
MONTO_MAXIMO = 10_000_000    # Gs. por transferencia: límite operativo supuesto del proyecto
MONTO_MINIMO = 1_000         # Gs.

# Tipos de operación legítima (internos: NO se guardan en el dataset)
OPERACIONES = {
    "cotidiana": 0.515,  # pagos chicos: despensa, delivery, servicios, comercios
    "personal": 0.37,    # envíos a familiares y amigos
    "mayor": 0.10,       # alquiler, cuotas, colegio
    "grande": 0.015,     # compras grandes (electrodomésticos, muebles, señas)
}
# Granularidad del importe: cada transferencia se redondea a uno de estos múltiplos.
# El 50 % de los importes NO es múltiplo de 1.000 (ej.: Gs. 5.699, Gs. 128.437).
GRANULARIDAD = np.array([1, 100, 1_000, 10_000, 50_000])
P_GRANULARIDAD = np.array([0.30, 0.20, 0.30, 0.12, 0.08])

# Tipologías de fraude: % de CASOS (eventos de fraude), de mayor a menor peso.
# Un caso puede tener varias transferencias (K_ESPERADO = transferencias promedio por caso).
# Como cada ráfaga tiene 3 a 7 transferencias, en CANTIDAD DE TRANSFERENCIAS la ráfaga queda primera.
TIPOLOGIAS = {
    "toma_de_cuenta": 0.45,
    "rafaga_de_transferencias": 0.25,
    "cuenta_mula": 0.20,
    "camuflado": 0.10,
}
K_ESPERADO = {"toma_de_cuenta": 2.4, "rafaga_de_transferencias": 5.0, "cuenta_mula": 3.15, "camuflado": 1.3}

# Camuflado: imita el comportamiento normal del cliente con 1 o 2 rarezas LEVES (cada una también es
# frecuente en las transferencias legítimas). Probabilidad de que se elija cada rareza:
RAREZAS_CAMUFLADO = {
    "destinatario_nuevo": 0.35,  # una cuenta nueva (si no, la de un contacto habitual comprometido)
    "monto_mayor": 0.25,         # 1,3 a 2,5 veces su promedio (no 4 a 8 veces como la toma de cuenta)
    "segundo_pago": 0.20,        # "falta un pago más": otro pago al mismo destino horas después
    "hora_borde": 0.15,          # temprano (6-7 h) o tarde (22-23 h), nunca de madrugada
    "otra_ciudad": 0.05,         # desde otra ciudad
}
P_CAMUFLADO_DOS_RAREZAS = 0.40   # el resto de los casos tiene una sola rareza

# Población legítima y ruido (casos legítimos que se parecen a fraude). El ruido es intencional:
# ninguna señal por sí sola debe alcanzar para decidir que una transferencia es fraude.
P_CLIENTES_NUEVOS = 0.10       # abren su cuenta durante el año (jul 2025 - may 2026)
P_NUEVOS_ACTIVOS = 0.15        # de ellos, los que hacen varias transferencias en sus primeros días
P_ESPORADICOS = 0.10           # clientes con pocas transferencias al mes (a menudo sin historial)
P_VIAJE = 0.05                 # transferencias hechas desde otra ciudad
EPISODIOS_DISPOSITIVO = 1.2    # media anual de dispositivos nuevos legítimos por cliente
                               # (celular nuevo, reinstalar la app, otra computadora)
P_HABITUAL_COTIDIANA = 0.88    # pagos cotidianos a comercios habituales (el resto, a uno nuevo)
P_HABITUAL_PERSONAL = 0.88     # envíos a contactos habituales (el resto, a alguien nuevo)


def _norm(d: dict) -> tuple[np.ndarray, np.ndarray]:
    k = np.array(list(d.keys()))
    p = np.array(list(d.values()), dtype=float)
    return k, p / p.sum()


def _es_fin_de_mes(dias: pd.DatetimeIndex) -> np.ndarray:
    """Últimos 5 días del mes (misma regla que la feature es_fin_de_mes)."""
    return np.asarray(dias.day > dias.days_in_month - 5)


def _pesos_dia(dias: pd.DatetimeIndex) -> np.ndarray:
    """Más movimiento a fin de mes (cobro de sueldos) y en diciembre (aguinaldo)."""
    w = np.ones(len(dias))
    w[_es_fin_de_mes(dias)] *= 1.4
    w[dias.month == 12] *= 1.3
    w[(dias.month == 12) & (dias.day >= 18) & (dias.day <= 24)] *= 1.5  # compras navideñas
    w[dias.dayofweek == 6] *= 0.75  # domingo
    return w / w.mean()


def otra_ciudad(actuales: np.ndarray, rng) -> np.ndarray:
    """Ciudad de un viaje: de la lista general, ponderada por población, distinta de la actual."""
    ciudades, p = _norm(CIUDADES)
    salida = actuales.copy()
    for i, actual in enumerate(actuales):
        w = np.where(ciudades == actual, 0.0, p)
        salida[i] = rng.choice(ciudades, p=w / w.sum())
    return salida


def redondear(monto: np.ndarray, rng) -> np.ndarray:
    """Aplica el tope operativo y una granularidad realista al importe."""
    monto = np.asarray(monto, dtype=float)
    # por encima del límite: la persona transfiere un importe cercano al máximo permitido
    sobre = monto > MONTO_MAXIMO
    monto = np.where(sobre, MONTO_MAXIMO * rng.uniform(0.55, 1.0, len(monto)), monto)
    g = rng.choice(GRANULARIDAD, len(monto), p=P_GRANULARIDAD).astype(float)
    g = np.where(g * 4 > monto, np.where(monto >= 4_000, 1_000.0, 1.0), g)  # no deformar montos chicos
    m =np.round(monto / g) * g
    return np.clip(m, MONTO_MINIMO, MONTO_MAXIMO).astype(np.int64)


def montos_legitimos(tipo: np.ndarray, ingreso: np.ndarray, es_dic: np.ndarray, rng) -> np.ndarray:
    n = len(tipo)
    cap = ingreso / SALARIO_MINIMO  # capacidad económica relativa al salario mínimo
    m = np.select(
        [tipo == "cotidiana", tipo == "personal", tipo == "mayor"],
        [55_000 * cap ** 0.35 * rng.lognormal(0, 0.85, n),
         0.05 * ingreso * rng.lognormal(0, 0.9, n),
         0.28 * ingreso * rng.lognormal(0, 0.45, n)],
        default=2_500_000 * cap ** 0.6 * rng.lognormal(0, 0.6, n),
    )
    return redondear(m * np.where(es_dic, 1.25, 1.0), rng)


def generar(n_clientes: int, tasa_fraude: float, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    bancos, p_bancos = _norm(BANCOS)
    ciudades, p_ciudades = _norm(CIUDADES)
    tipos_op, p_op = _norm(OPERACIONES)

    # ------------------------------ clientes (emisores) -------------------------------
    ingreso = SALARIO_MINIMO * rng.lognormal(np.log(1.25), 0.6, n_clientes)
    alta_capacidad = rng.random(n_clientes) < 0.05  # clientes de mayor capacidad económica
    ingreso = np.where(alta_capacidad, ingreso * rng.uniform(3, 6, n_clientes), ingreso)
    # perfil del cliente: regular, nuevo (abre la cuenta durante el año) o esporádico
    perfil_cli = rng.choice(["regular", "nuevo", "esporadico"], n_clientes,
                            p=[1 - P_CLIENTES_NUEVOS - P_ESPORADICOS, P_CLIENTES_NUEVOS, P_ESPORADICOS])
    es_nuevo = perfil_cli == "nuevo"
    tasa = rng.gamma(2.0, 0.33, n_clientes)
    tasa = np.where(perfil_cli == "esporadico", rng.uniform(0.02, 0.08, n_clientes), tasa)
    nuevo_activo = es_nuevo & (rng.random(n_clientes) < P_NUEVOS_ACTIVOS)
    tasa = np.where(es_nuevo & ~nuevo_activo, tasa * 0.35, tasa)  # la mayoría de los nuevos opera poco
    # alta: cuentas existentes (7 % con menos de 90 días; antigüedad acotada a 30 años) o abiertas en el año
    alta_existente = INICIO_WARMUP - pd.to_timedelta(
        np.where(rng.random(n_clientes) < 0.07, rng.uniform(0, 90, n_clientes),
                 np.minimum(rng.lognormal(np.log(1300), 0.7, n_clientes), 30 * 365)), unit="D")
    alta_en_el_anio = INICIO + pd.to_timedelta(rng.uniform(0, (FIN - INICIO).days - 30, n_clientes), unit="D")
    cli = pd.DataFrame({
        "emisor": [f"EMI-{i:05d}" for i in range(n_clientes)],
        "banco": rng.choice(bancos, n_clientes, p=p_bancos),
        "ciudad": rng.choice(ciudades, n_clientes, p=p_ciudades),
        "ingreso": ingreso,
        "perfil": perfil_cli,
        "tasa_diaria": tasa,
        "tasa_sesiones": rng.gamma(1.0, 0.006, n_clientes),
        "noctambulo": rng.random(n_clientes) < 0.02,
        "alta_cuenta": np.where(es_nuevo, alta_en_el_anio, alta_existente),
    })
    perfil = lambda c: PERFIL_NOCTURNO if cli.at[c, "noctambulo"] else PERFIL_HORA  # noqa: E731

    # --------------------- transacciones legítimas individuales -----------------------
    dias = pd.date_range(INICIO_WARMUP, FIN - pd.Timedelta(days=1), freq="D")
    w_dia = _pesos_dia(dias)
    # primer día en que cada cliente puede operar (los nuevos, desde que abren la cuenta)
    dia_alta = np.clip((pd.to_datetime(cli["alta_cuenta"]) - INICIO_WARMUP).dt.days.to_numpy(), 0, len(dias) - 1)
    dias_activos = len(dias) - dia_alta
    n_por_cliente = rng.poisson(cli["tasa_diaria"].to_numpy() * dias_activos)
    idx_r = np.repeat(np.arange(n_clientes), n_por_cliente)
    n_r = len(idx_r)
    dia = rng.choice(len(dias), n_r, p=w_dia / w_dia.sum())
    antes = dia < dia_alta[idx_r]  # nadie opera antes de abrir su cuenta
    dia[antes] = rng.integers(dia_alta[idx_r][antes], len(dias))
    noct = cli["noctambulo"].to_numpy()[idx_r]
    hora = np.where(noct, rng.choice(24, n_r, p=PERFIL_NOCTURNO), rng.choice(24, n_r, p=PERFIL_HORA))
    ts_r = dias[dia] + pd.to_timedelta(hora * 3600 + rng.integers(0, 3600, n_r), unit="s")
    tipo_r = rng.choice(tipos_op, n_r, p=p_op)

    # ------------- sesiones legítimas de varios pagos seguidos (ráfagas legítimas) ------
    # pagar servicios, sueldos del personal doméstico, cuotas... más frecuentes a fin de mes,
    # en horario diurno (8 a 20 h) y a destinatarios habituales
    w_ses = _pesos_dia(dias) * np.where(_es_fin_de_mes(dias), 3.0, 1.0)
    n_ses = rng.poisson(cli["tasa_sesiones"].to_numpy() * len(dias))
    cli_ses = np.repeat(np.arange(n_clientes), n_ses)
    filas_s = []
    for c in cli_ses:
        d_i = int(rng.choice(len(dias), p=w_ses / w_ses.sum()))
        if d_i < dia_alta[c]:
            continue
        t = dias[d_i] + pd.Timedelta(hours=int(rng.integers(8, 21)), seconds=int(rng.integers(0, 3600)))
        for _ in range(min(12, 3 + rng.poisson(1.5))):
            filas_s.append((c, t, False))
            t = t + pd.Timedelta(seconds=int(rng.uniform(30, 480)))
    # clientes nuevos activos: en sus primeros días les transfieren a varios contactos y pagan cuentas
    # (dispositivo nuevo, sin historial y destinatarios nuevos: legítimo pero parecido a una mula)
    for c in np.where(nuevo_activo)[0]:
        t = dias[dia_alta[c]] + pd.Timedelta(days=int(rng.integers(0, 3)), hours=int(rng.integers(8, 21)))
        for _ in range(int(rng.integers(2, 6))):
            filas_s.append((c, t, True))
            t = t + pd.Timedelta(minutes=float(rng.uniform(3, 90)))
    idx_s = np.array([f[0] for f in filas_s], dtype=int)
    ts_s = pd.DatetimeIndex([f[1] for f in filas_s])
    inicio_s = np.array([f[2] for f in filas_s], dtype=bool)
    tipo_s = np.where(inicio_s, rng.choice(["personal", "mayor"], len(idx_s), p=[0.7, 0.3]),
                      rng.choice(["personal", "mayor", "cotidiana"], len(idx_s), p=[0.5, 0.25, 0.25]))
    es_sesion = np.concatenate([np.zeros(len(idx_r), bool), ~inicio_s])
    es_inicio = np.concatenate([np.zeros(len(idx_r), bool), inicio_s])

    idx = np.concatenate([idx_r, idx_s])
    ts = pd.DatetimeIndex(np.concatenate([ts_r.to_numpy(), ts_s.to_numpy()]))
    tipo = np.concatenate([tipo_r, tipo_s])
    n = len(idx)
    monto = montos_legitimos(tipo, cli["ingreso"].to_numpy()[idx], np.asarray(ts.month == 12), rng)

    # ----- destinatarios: contactos habituales, comercios/proveedores y cuentas nuevas -----
    n_com = max(600, n_clientes // 2)
    com_ciudad = rng.choice(ciudades, n_com, p=p_ciudades)
    com_banco = rng.choice(bancos, n_com, p=p_bancos)
    com_id = np.array([f"B{i}" for i in range(n_com)], dtype=object)
    com_por_ciudad = {c: np.where(com_ciudad == c)[0] for c in ciudades}

    destino = np.empty(n, dtype=object)
    banco_dest = np.empty(n, dtype=object)
    dispositivo = np.empty(n, dtype=object)
    ciudad_tx = cli["ciudad"].to_numpy()[idx].astype(object)
    ts_np = ts.to_numpy()
    contactos = {}  # por cliente: (ids, bancos) de sus contactos habituales

    orden = np.argsort(idx, kind="stable")
    cortes = np.cumsum(np.bincount(idx, minlength=n_clientes))[:-1]
    contador_unico = 0
    for c, filas in enumerate(np.split(orden, cortes)):
        n_cont = 4 + rng.poisson(5)
        ids_cont = np.array([f"P{c}-{q}" for q in range(n_cont)], dtype=object)
        cont_banco = rng.choice(bancos, n_cont, p=p_bancos).astype(object)
        contactos[c] = (ids_cont, cont_banco)
        if len(filas) == 0:
            continue
        filas = filas[np.argsort(ts_np[filas], kind="stable")]
        k = len(filas)
        pesos_cont = 1 / np.arange(1, n_cont + 1) ** 1.1
        pesos_cont /= pesos_cont.sum()
        pool = com_por_ciudad.get(cli.at[c, "ciudad"])
        if pool is None or len(pool) == 0:
            pool = np.arange(n_com)
        hab_com = rng.choice(pool, min(len(pool), 6 + rng.poisson(8)), replace=False)

        t_c = tipo[filas]
        u = rng.random(k)
        u[es_sesion[filas]] = 0.0    # las sesiones de pagos van siempre a destinatarios habituales
        u[es_inicio[filas]] = 0.999  # los primeros pagos de un cliente nuevo van a cuentas nuevas
        dest = np.empty(k, dtype=object)
        bd = np.empty(k, dtype=object)
        # cotidiana: comercios habituales u otro comercio de su ciudad
        m = t_c == "cotidiana"
        com = np.where(u < P_HABITUAL_COTIDIANA, hab_com[rng.integers(len(hab_com), size=k)], pool[rng.integers(len(pool), size=k)])
        dest[m], bd[m] = com_id[com[m]], com_banco[com[m]]
        # personal / mayor: contactos habituales o alguien nuevo (legítimo)
        p = rng.choice(n_cont, size=k, p=pesos_cont)
        m_hab = np.isin(t_c, ["personal", "mayor"]) & (u < P_HABITUAL_PERSONAL)
        dest[m_hab], bd[m_hab] = ids_cont[p[m_hab]], cont_banco[p[m_hab]]
        # grande: 60 % un comercio cualquiera, 40 % una persona nueva
        com_g = rng.integers(n_com, size=k)
        m_g = (t_c == "grande") & (u < 0.60)
        dest[m_g], bd[m_g] = com_id[com_g[m_g]], com_banco[com_g[m_g]]
        m_nuevo = pd.isna(dest)
        nu = int(m_nuevo.sum())
        dest[m_nuevo] = [f"U{contador_unico + q}" for q in range(nu)]
        bd[m_nuevo] = rng.choice(bancos, nu, p=p_bancos)
        contador_unico += nu
        destino[filas], banco_dest[filas] = dest, bd

        # -- dispositivos: 15 % usa dos (celular + web). Además, episodios de dispositivo nuevo
        #    legítimo: cambio de celular (el nuevo se sigue usando) o uso puntual de otro equipo
        disp = np.full(k, f"D{c}-0", dtype=object)
        if rng.random() < 0.15:
            disp[rng.random(k) < 0.3] = f"D{c}-W"
        n_epi = rng.poisson(EPISODIOS_DISPOSITIVO * len(dias) / 365)
        for j, pos in enumerate(sorted(rng.integers(0, k, n_epi))):
            if rng.random() < 0.6:   # cambio de celular: desde aquí usa el nuevo
                actual = disp[pos]
                disp[pos:] = np.where(disp[pos:] == actual, f"D{c}-N{j}", disp[pos:])
            else:                    # uso puntual de otro equipo (1 o 2 transferencias)
                disp[pos:pos + int(rng.integers(1, 3))] = f"D{c}-N{j}"
        dispositivo[filas] = disp

    # viajes: 5 % de las transferencias se hacen desde otra ciudad (de la lista general,
    # ponderada por población, distinta de la ciudad habitual)
    viaje = np.where(rng.random(n) < P_VIAJE)[0]
    ciudad_tx[viaje] = otra_ciudad(ciudad_tx[viaje], rng)

    df = pd.DataFrame({
        "timestamp": ts,
        "cuenta_emisor_id": cli["emisor"].to_numpy()[idx],
        "banco_origen": cli["banco"].to_numpy()[idx],
        "banco_destino": banco_dest,
        "cuenta_destino_id": destino,
        "ciudad": ciudad_tx,
        "ciudad_habitual": cli["ciudad"].to_numpy()[idx],
        "dispositivo_id": dispositivo,
        "monto_gs": monto,
        "alta_cuenta_origen": cli["alta_cuenta"].to_numpy()[idx],
        "es_fraude": 0,
        "tipo_fraude": "ninguno",
    })

    # ----------------------------- inyección de fraude --------------------------------
    fraude = _inyectar_fraude(df, cli, contactos, tasa_fraude, rng, bancos, p_bancos, perfil)
    df = pd.concat([df, fraude], ignore_index=True)
    df = _calcular_contexto(df)
    return _anonimizar(df, rng)


def _inyectar_fraude(df, cli, contactos, tasa, rng, bancos, p_bancos, perfil) -> pd.DataFrame:
    """Cuatro tipologías (ver data/DATASET.md). Cada caso es una COMBINACIÓN de señales que también
    aparecen por separado en transferencias legítimas: ninguna señal sola alcanza para decidir."""
    tipos, p_tipos = _norm(TIPOLOGIAS)
    n_periodo = int((df["timestamp"] >= INICIO).sum())
    k_medio = sum(TIPOLOGIAS[t] * K_ESPERADO[t] for t in TIPOLOGIAS)
    n_eventos = int(round(tasa * n_periodo / k_medio))
    # reparto exacto de casos según TIPOLOGIAS (no al azar), en orden aleatorio
    eventos = rng.permutation(np.repeat(tipos, np.round(p_tipos * n_eventos).astype(int)))

    leg = df[df["timestamp"] < FIN]
    base_cli = leg.groupby("cuenta_emisor_id")["monto_gs"].median()   # importe típico del cliente
    media_cli = leg.groupby("cuenta_emisor_id")["monto_gs"].mean()    # su promedio (lo que ve el banco)
    # el fraude sigue el mismo calendario de actividad que las transferencias legítimas
    # (más casos a fin de mes y en diciembre), así la tasa de fraude es estable entre meses
    dias_p = pd.date_range(INICIO, FIN - pd.Timedelta(days=1), freq="D")
    w_p = _pesos_dia(dias_p)
    w_p = w_p / w_p.sum()

    # historial legítimo por cliente (para elegir víctimas con cuenta abierta y mulas "dormidas")
    tiempos = {e: g.to_numpy() for e, g in leg.groupby("cuenta_emisor_id")["timestamp"]}
    alta = pd.to_datetime(cli["alta_cuenta"])
    esporadicos = np.where(cli["perfil"].to_numpy() == "esporadico")[0]
    siguiente_emisor = len(cli)  # las cuentas mula nuevas reciben IDs a continuación de los clientes

    def hora_habitual(c):
        return int(rng.choice(24, p=perfil(c)))

    def momento(dia, h):
        return dia.normalize() + pd.Timedelta(hours=h, seconds=int(rng.integers(0, 3600)))

    def victima(dia, dias_minimos=7):
        """Cliente con la cuenta abierta hace al menos `dias_minimos` días y con historial previo."""
        for _ in range(100):
            c = int(rng.integers(len(cli)))
            t_c = tiempos.get(cli.at[c, "emisor"])
            if alta[c] <= dia - pd.Timedelta(days=dias_minimos) and t_c is not None and (t_c < dia.to_datetime64()).any():
                return c
        return c

    def contacto_habitual(c, dia):
        """Un destinatario al que el cliente YA le transfirió antes de `dia` (elegido según la frecuencia)."""
        previas = leg.loc[(leg["cuenta_emisor_id"] == cli.at[c, "emisor"]) & (leg["timestamp"] < dia),
                          ["cuenta_destino_id", "banco_destino"]]
        if previas.empty:
            return None
        frec = previas.value_counts()
        return frec.index[int(rng.choice(len(frec), p=(frec / frec.sum()).to_numpy()))]

    rarezas_cam, p_rarezas_cam = _norm(RAREZAS_CAMUFLADO)

    def dormida(dia):
        """Cliente esporádico sin transferencias en los 30 días previos (cuenta mula 'dormida')."""
        for _ in range(100):
            c = int(rng.choice(esporadicos))
            t_c = tiempos.get(cli.at[c, "emisor"])
            if t_c is None:
                continue
            previas = t_c[t_c < dia.to_datetime64()]
            if len(previas) and previas.max() < (dia - pd.Timedelta(days=30)).to_datetime64():
                return c
        return None

    filas = []
    for e, tipo in enumerate(eventos):
        dia = dias_p[rng.choice(len(dias_p), p=w_p)]
        c = victima(dia, 60 if tipo == "camuflado" else 7)  # el camuflado nunca usa una cuenta reciente
        emisor = {"cuenta_emisor_id": cli.at[c, "emisor"], "banco_origen": cli.at[c, "banco"],
                  "ciudad_habitual": cli.at[c, "ciudad"], "alta_cuenta_origen": cli.at[c, "alta_cuenta"]}
        base = float(base_cli.get(emisor["cuenta_emisor_id"], 0.05 * cli.at[c, "ingreso"]))   # monto típico
        media = float(media_cli.get(emisor["cuenta_emisor_id"], 0.1 * cli.at[c, "ingreso"]))  # su promedio
        ciudad = cli.at[c, "ciudad"]
        if rng.random() < P_VIAJE:
            ciudad = otra_ciudad(np.array([ciudad], dtype=object), rng)[0]
        disp = "PROPIO"  # se reemplaza por el último dispositivo legítimo del cliente
        tx = []  # (timestamp, destino, banco_destino, monto)

        if tipo == "toma_de_cuenta":  # phishing / robo de credenciales
            # combinación anómala: al menos 2 señales; ninguna está siempre presente
            senal = {"dispositivo": rng.random() < 0.80, "madrugada": rng.random() < 0.55,
                     "otra_ciudad": rng.random() < 0.45}
            while sum(senal.values()) < 2:
                senal[rng.choice(list(senal))] = True
            h = int(rng.integers(0, 6)) if senal["madrugada"] else hora_habitual(c)
            if senal["dispositivo"]:
                disp = f"F{e}"  # dispositivo del atacante
            if senal["otra_ciudad"]:
                ciudad = otra_ciudad(np.array([cli.at[c, "ciudad"]], dtype=object), rng)[0]
            k = int(rng.choice([1, 2, 3, 4], p=[0.25, 0.30, 0.25, 0.20]))
            t = momento(dia, h)
            dest, bd = f"T{e}-0", rng.choice(bancos, p=p_bancos)
            for j in range(k):
                if j > 0 and rng.random() < 0.5:  # otra cuenta nueva (si no, repite la del atacante)
                    dest, bd = f"T{e}-{j}", rng.choice(bancos, p=p_bancos)
                r = rng.random()
                if r < 0.50:    # alto respecto de su promedio (a veces intenta vaciar la cuenta)
                    monto = media * rng.uniform(2, 8) if rng.random() < 0.7 else cli.at[c, "ingreso"] * rng.uniform(0.3, 1.5)
                elif r < 0.80:  # parecido al habitual
                    monto = base * rng.uniform(0.6, 2.0)
                else:           # menor al habitual
                    monto = base * rng.uniform(0.2, 0.6)
                tx.append((t, dest, bd, monto))
                t = t + pd.Timedelta(minutes=float(rng.uniform(1, 20)))

        elif tipo == "rafaga_de_transferencias":  # fraccionamiento: muchas transferencias chicas
            if rng.random() < 0.35:
                disp = f"F{e}"
            h = int(rng.integers(0, 6)) if rng.random() < 0.25 else hora_habitual(c)
            k = int(rng.integers(3, 8))
            n_dest = int(rng.integers(1, 3))  # cuentas que se repiten dentro de la ráfaga
            fijas = [(f"R{e}-{j}", rng.choice(bancos, p=p_bancos)) for j in range(n_dest)]
            t = momento(dia, h)
            for j in range(k):
                if rng.random() < 0.6:   # destino nuevo distinto
                    dest, bd = f"R{e}-n{j}", rng.choice(bancos, p=p_bancos)
                else:
                    dest, bd = fijas[int(rng.integers(n_dest))]
                tx.append((t, dest, bd, base * rng.uniform(0.2, 0.8)))
                t = t + pd.Timedelta(minutes=float(rng.uniform(0.5, 4)))

        elif tipo == "cuenta_mula":  # el EMISOR es la mula: cuenta nueva o dormida con actividad de golpe
            c_dormida = dormida(dia) if rng.random() < 0.40 else None
            if c_dormida is not None:   # cliente esporádico sin movimientos en 30+ días
                c = c_dormida
                emisor = {"cuenta_emisor_id": cli.at[c, "emisor"], "banco_origen": cli.at[c, "banco"],
                          "ciudad_habitual": cli.at[c, "ciudad"], "alta_cuenta_origen": cli.at[c, "alta_cuenta"]}
                ciudad = cli.at[c, "ciudad"]
                if rng.random() < 0.5:
                    disp = f"F{e}"
                h = hora_habitual(c)
            else:                       # cuenta abierta hace 0 a 60 días, sin transferencias previas
                ciudad_m = rng.choice(list(CIUDADES), p=np.array(list(CIUDADES.values())) / sum(CIUDADES.values()))
                emisor = {"cuenta_emisor_id": f"EMI-{siguiente_emisor:05d}", "banco_origen": rng.choice(bancos, p=p_bancos),
                          "ciudad_habitual": ciudad_m,
                          "alta_cuenta_origen": dia - pd.Timedelta(days=float(rng.uniform(0, 60)))}
                siguiente_emisor += 1
                ciudad = ciudad_m
                disp = f"F{e}"
                h = int(rng.choice(24, p=PERFIL_HORA))
            if rng.random() < 0.25:
                h = int(rng.integers(0, 6))
            k = int(rng.choice([2, 3, 4, 5], p=[0.35, 0.30, 0.20, 0.15]))
            t = momento(dia, h)
            dest, bd = f"M{e}-0", rng.choice(bancos, p=p_bancos)
            for j in range(k):
                if j > 0 and rng.random() < 0.9:
                    dest, bd = f"M{e}-{j}", rng.choice(bancos, p=p_bancos)
                monto = rng.lognormal(np.log(2_500_000), 0.5) if rng.random() < 0.75 else rng.uniform(500_000, 1_200_000)
                tx.append((t, dest, bd, monto))
                t = t + pd.Timedelta(minutes=float(rng.uniform(5, 180)))

        else:  # camuflado: imita el comportamiento normal del cliente, con 1 o 2 rarezas leves
            # Nunca tiene las señales fuertes de las otras tipologías: usa SU dispositivo, no opera de
            # madrugada (0-5 h), la cuenta tiene 60 días o más y hace como mucho 2 transferencias.
            # Cubre las estafas por WhatsApp o Marketplace (la víctima autoriza el pago) y las cuentas
            # de contactos habituales que fueron comprometidas.
            n_rarezas = 2 if rng.random() < P_CAMUFLADO_DOS_RAREZAS else 1
            rarezas = set(rng.choice(rarezas_cam, n_rarezas, replace=False, p=p_rarezas_cam))
            h = hora_habitual(c)
            for _ in range(50):  # su horario habitual, pero nunca de madrugada
                if h >= 6:
                    break
                h = hora_habitual(c)
            h = max(h, 6)
            if "hora_borde" in rarezas:
                h = int(rng.choice([6, 7, 22, 23]))
            if "otra_ciudad" in rarezas:
                ciudad = otra_ciudad(np.array([cli.at[c, "ciudad"]], dtype=object), rng)[0]
            habitual = None if "destinatario_nuevo" in rarezas else contacto_habitual(c, dia)
            if habitual is None:
                dest, bd = f"Z{e}", rng.choice(bancos, p=p_bancos)
            else:   # cuenta de un contacto habitual que fue comprometida
                dest, bd = habitual
            if "monto_mayor" in rarezas:
                monto = media * rng.uniform(1.3, 2.5)
            else:   # parecido a su monto típico
                monto = base * rng.uniform(0.8, 1.5)
            t = momento(dia, h)
            tx.append((t, dest, bd, monto))
            if "segundo_pago" in rarezas:  # "falta un pago más": mismo destino, entre 30 min y 3 h después
                t = t + pd.Timedelta(hours=float(rng.uniform(0.5, 3)))
                if t.hour < 6:             # si caería de madrugada, lo hace a la mañana siguiente
                    t = t.normalize() + pd.Timedelta(hours=float(rng.uniform(6.5, 9)))
                tx.append((t, dest, bd, monto * rng.uniform(0.5, 1.2)))

        montos = redondear(np.array([m for *_, m in tx]), rng)
        for (t, dest, bd, _), m in zip(tx, montos):
            filas.append({"timestamp": t, **emisor, "banco_destino": bd, "cuenta_destino_id": dest,
                          "ciudad": ciudad, "dispositivo_id": disp, "monto_gs": int(m),
                          "es_fraude": 1, "tipo_fraude": tipo})
    fr = pd.DataFrame(filas)
    fr["timestamp"] = pd.to_datetime(fr["timestamp"]).astype("datetime64[ns]")
    fr["alta_cuenta_origen"] = pd.to_datetime(fr["alta_cuenta_origen"]).astype("datetime64[ns]")

    # "dispositivo propio" = el último dispositivo que el cliente usó antes de ese momento
    propio = fr["dispositivo_id"] == "PROPIO"
    hist = df[["timestamp", "cuenta_emisor_id", "dispositivo_id"]].sort_values("timestamp")
    hist["timestamp"] = hist["timestamp"].astype("datetime64[ns]")
    q = fr.loc[propio, ["timestamp", "cuenta_emisor_id"]].reset_index().sort_values("timestamp")
    ult = pd.merge_asof(q, hist, on="timestamp", by="cuenta_emisor_id", direction="backward")
    sin_hist = ult["dispositivo_id"].isna()
    ult.loc[sin_hist, "dispositivo_id"] = [f"D{int(e[4:])}-0" for e in ult.loc[sin_hist, "cuenta_emisor_id"]]
    fr.loc[ult["index"].to_numpy(), "dispositivo_id"] = ult["dispositivo_id"].to_numpy()
    return fr


def _calcular_contexto(df: pd.DataFrame) -> pd.DataFrame:
    """Variables de contexto que el banco emisor conoce al momento de autorizar la transferencia.
    Cada valor se calcula SOLO con transferencias ANTERIORES del mismo emisor (sin datos futuros)."""
    df = df.sort_values(["cuenta_emisor_id", "timestamp"], kind="stable").reset_index(drop=True)
    cod = pd.factorize(df["cuenta_emisor_id"])[0].astype(np.int64)
    seg = (df["timestamp"].astype("int64") // 10**9).to_numpy()
    seg = seg - seg.min()
    clave = cod * 10**9 + seg  # ordenada: emisor y luego tiempo
    i = np.arange(len(df))

    def ventana(segundos):
        # primer índice del mismo emisor dentro de la ventana [t - segundos, t]
        return np.searchsorted(clave, clave - segundos, side="left")

    df["n_tx_1h"] = i - ventana(3600)       # transferencias previas en la última hora
    df["n_tx_24h"] = i - ventana(86400)     # transferencias previas en las últimas 24 h
    izq = ventana(30 * 86400)
    cs = np.concatenate([[0], np.cumsum(df["monto_gs"].to_numpy(dtype=float))])
    n_prev = i - izq
    suma_prev = cs[i] - cs[izq]
    # sin transferencias previas en 30 días -> 0 (la feature sin_historial lo marca)
    df["monto_promedio_30d_gs"] = np.where(n_prev > 0, np.round(suma_prev / np.maximum(n_prev, 1)), 0).astype(np.int64)

    # destinatario nuevo: no existe una transferencia ANTERIOR de este emisor a esta cuenta
    df["destinatario_nuevo"] = ~df.duplicated(["cuenta_emisor_id", "cuenta_destino_id"], keep="first")
    # dispositivo usado por primera vez (por este emisor) hace menos de 24 h
    primera_vez = df.groupby(["cuenta_emisor_id", "dispositivo_id"])["timestamp"].transform("min")
    df["dispositivo_nuevo"] = (df["timestamp"] - primera_vez) <= pd.Timedelta(hours=24)
    df["antiguedad_cuenta_origen_dias"] = ((df["timestamp"] - df["alta_cuenta_origen"]).dt.days).clip(lower=0)

    # se conserva solo el período de simulación (jul 2025 - jun 2026); junio 2025 fue historial previo
    df = df[(df["timestamp"] >= INICIO) & (df["timestamp"] < FIN)]
    df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
    df.insert(0, "transaction_id", [f"TX-{i + 1:08d}" for i in range(len(df))])
    return df.drop(columns=["alta_cuenta_origen"])


def _anonimizar(df: pd.DataFrame, rng) -> pd.DataFrame:
    """Reemplaza los identificadores internos de la simulación por códigos opacos, para que
    ningún ID revele si la cuenta o el dispositivo pertenecen a un escenario de fraude."""
    for col, prefijo, digitos in [("cuenta_destino_id", "CTA-", 8), ("dispositivo_id", "DEV-", 7)]:
        codigos, unicos = pd.factorize(df[col])
        nuevos = rng.permutation(len(unicos)) + 10 ** (digitos - 1)
        df[col] = np.array([f"{prefijo}{v}" for v in nuevos], dtype=object)[codigos]
    df["monto_gs"] = df["monto_gs"].astype(np.int64)
    df["es_fraude"] = df["es_fraude"].astype(np.int64)
    return df[COLUMNAS_DATASET]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clientes", type=int, default=8_000)
    ap.add_argument("--tasa-fraude", type=float, default=0.0008)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    print(f"Generando transferencias SPI para {args.clientes:,} clientes...")
    df = generar(args.clientes, args.tasa_fraude, args.seed)
    print(f"  {len(df):,} transferencias | fraude: {df['es_fraude'].sum():,} ({df['es_fraude'].mean():.4%})")
    print(df.loc[df["es_fraude"] == 1, "tipo_fraude"].value_counts().to_string())
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SALIDA, index=False, date_format="%Y-%m-%d %H:%M:%S")
    df.sample(5000, random_state=1).sort_values("timestamp").to_csv(
        MUESTRA, index=False, date_format="%Y-%m-%d %H:%M:%S")
    # CSV del simulador de la demo: período de prueba (may-jun 2026), nunca usado para entrenar
    prueba = df[df["timestamp"] >= INICIO_PRUEBA]
    demo = pd.concat([prueba[prueba["es_fraude"] == 1],
                      prueba[prueba["es_fraude"] == 0].sample(2500, random_state=7)]).sort_values("timestamp")
    DEMO.parent.mkdir(parents=True, exist_ok=True)
    demo.to_csv(DEMO, index=False, date_format="%Y-%m-%dT%H:%M:%S")
    print(f"Guardado: {SALIDA}, {MUESTRA} y {DEMO}")


if __name__ == "__main__":
    main()
