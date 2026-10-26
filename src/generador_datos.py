"""
Generador de datos sintéticos - detección de fraude (lado del emisor).

Pasos:
  1. Simula cuentas con perfil propio (zona, horario, dispositivos, destinos frecuentes).
  2. Simula tráfico legítimo (con ruido: viajes, cambio de celular, compras grandes, etc.).
  3. Inyecta 3 escenarios de fraude (toma de cuenta, vaciado fraccionado, ingeniería social).
  4. Calcula las features con ventanas móviles usando SOLO historial previo de cada emisor.
  5. Exporta 3 CSV: completo, train (período temprano) y test (período final).

Uso:
    pip install numpy pandas
    python generar_datos.py                       # valores por defecto
    python generar_datos.py --cuentas 30000 --tasa-fraude 0.002
"""
import argparse
import os
from types import SimpleNamespace

import numpy as np
import pandas as pd

T0 = pd.Timestamp("2026-01-01")  # inicio de la simulación (incluye warm-up)

# lat, lon de ciudades de Paraguay y su peso poblacional aproximado
CIUDADES = np.array([
    [-25.2637, -57.5759],  # Asunción
    [-25.5097, -54.6111],  # Ciudad del Este
    [-27.3306, -55.8667],  # Encarnación
    [-22.5472, -55.7333],  # Pedro Juan Caballero
    [-25.7500, -56.4333],  # Villarrica
])
PESOS_CIUDAD = np.array([0.50, 0.20, 0.15, 0.07, 0.08])

UMBRAL_HORA_ATIPICA = 6.0   # horas de distancia circular respecto a su hora habitual
MIN_HIST_HORA = 3           # mínimo de tx previas para evaluar hora atípica

FEATURES = [
    "hora_sin", "hora_cos", "es_fin_de_semana", "es_horario_nocturno", "hora_atipica",
    "dispositivo_nuevo", "ip_nueva", "distancia_zona_habitual_km",
    "antiguedad_cuenta_dias",
    "tx_count_1h", "tx_count_24h", "amount_sum_1h", "amount_sum_24h",
    "monto_pyg", "monto_promedio_usuario_30d", "ratio_monto_vs_promedio",
    "is_new_beneficiary",
]
RAW = ["id_transaccion", "fecha_hora", "id_cuenta_emisor", "id_cuenta_receptor",
       "monto_pyg", "id_dispositivo_emisor", "direccion_ip_emisor",
       "geo_latitud_emisor", "geo_longitud_emisor"]
LABELS = ["es_fraude", "escenario_fraude"]


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def armar_df(a, ts, recv, monto, dev, ip, lat, lon):
    """Convierte arrays numéricos en el DataFrame de transacciones crudas."""
    ipv = (np.asarray(ip, dtype=np.int64) * 7919 + 16777216) % (2 ** 32)
    ips = [f"{(v >> 24) & 255}.{(v >> 16) & 255}.{(v >> 8) & 255}.{v & 255}"
           for v in ipv.tolist()]
    monto = np.maximum(1000, np.round(np.asarray(monto) / 1000) * 1000)
    return pd.DataFrame({
        "fecha_hora": T0 + pd.to_timedelta(np.asarray(ts).astype("int64"), unit="s"),
        "id_cuenta_emisor": [f"CTA-{x:07d}" for x in np.asarray(a).tolist()],
        "id_cuenta_receptor": [f"CTA-{x:07d}" for x in np.asarray(recv).tolist()],
        "monto_pyg": monto,
        "id_dispositivo_emisor": [f"DEV-{x:09d}" for x in np.asarray(dev).tolist()],
        "direccion_ip_emisor": ips,
        "geo_latitud_emisor": np.round(lat, 5),
        "geo_longitud_emisor": np.round(lon, 5),
    })


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dl = p2 - p1, np.radians(lon2 - lon1)
    h = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(h))


# --------------------------------------------------------------------------- #
# 1. Cuentas
# --------------------------------------------------------------------------- #
def generar_cuentas(n, rng, total_days):
    alta_day = np.where(rng.random(n) < 0.05,
                        rng.uniform(0, total_days - 7, n),       # cuentas nuevas
                        -rng.uniform(1, 1500, n))                # cuentas antiguas
    city = rng.choice(len(CIUDADES), n, p=PESOS_CIUDAD)
    noct = rng.random(n) < 0.08                                   # clientes nocturnos
    return SimpleNamespace(
        n=n,
        alta_day=alta_day,
        start_day=np.ceil(np.maximum(alta_day, 0)).astype(int),
        city=city,
        home_lat=CIUDADES[city, 0] + rng.normal(0, 0.03, n),
        home_lon=CIUDADES[city, 1] + rng.normal(0, 0.03, n),
        rate=rng.lognormal(np.log(0.25), 0.7, n),                 # tx por día
        mu=rng.lognormal(np.log(250_000), 0.8, n),                # monto típico (PYG)
        mean_hour=np.where(noct, rng.uniform(22, 28, n) % 24,
                           np.clip(rng.normal(14, 3, n), 6, 22)),
        std_hour=rng.uniform(1.5, 3.5, n),
        has_sec=rng.random(n) < 0.4,                              # segundo dispositivo
        cambio=rng.random(n) < 0.08,                              # cambia de celular
        switch_day=rng.uniform(5, total_days - 5, n),
        has_trip=rng.random(n) < 0.10,                            # viaja
        trip_start=rng.integers(0, max(total_days - 10, 1), n),
        trip_len=rng.integers(3, 11, n),
        trip_city=(city + rng.integers(1, len(CIUDADES), n)) % len(CIUDADES),
        fav=rng.integers(0, n, (n, 12)),                          # destinos frecuentes
        ndest=rng.integers(4, 13, n),
    )


# --------------------------------------------------------------------------- #
# 2. Tráfico legítimo
# --------------------------------------------------------------------------- #
def generar_legitimas(c, rng, total_days):
    n = c.n
    active = total_days - c.start_day
    n_tx = rng.poisson(c.rate * active)
    a = np.repeat(np.arange(n), n_tx)
    m = len(a)

    day = c.start_day[a] + np.floor(rng.random(m) * active[a]).astype(int)
    hour = (c.mean_hour[a] + c.std_hour[a] * rng.normal(size=m)) % 24
    ts = day * 86400 + np.floor(hour * 3600)

    # Ubicación (con viajes ocasionales)
    in_trip = c.has_trip[a] & (day >= c.trip_start[a]) & (day < c.trip_start[a] + c.trip_len[a])
    lat = np.where(in_trip, CIUDADES[c.trip_city[a], 0], c.home_lat[a]) + rng.normal(0, 0.01, m)
    lon = np.where(in_trip, CIUDADES[c.trip_city[a], 1], c.home_lon[a]) + rng.normal(0, 0.01, m)

    # Dispositivo e IP (cambio de celular, dispositivo secundario, wifi público)
    switched = c.cambio[a] & (day >= c.switch_day[a])
    k = np.where(switched, 2, np.where(c.has_sec[a] & (rng.random(m) < 0.15), 1, 0))
    dev = a * 10 + k
    kip = rng.choice(3, m, p=[0.60, 0.25, 0.15])
    ip = a * 10 + kip + np.where(switched, 3, 0)
    wifi = rng.random(m) < 0.03
    ip = np.where(wifi, 10 ** 7 + rng.integers(0, 5 * 10 ** 7, m), ip)

    # Beneficiario: 85 % destinos frecuentes, 15 % cualquier cuenta
    idx = np.floor(rng.random(m) ** 2 * c.ndest[a]).astype(int)
    recv = np.where(rng.random(m) < 0.85, c.fav[a, idx], rng.integers(0, n, m))
    recv = np.where(recv == a, (recv + 1) % n, recv)

    # Monto (con compras grandes ocasionales)
    monto = c.mu[a] * rng.lognormal(0, 0.6, m)
    grande = rng.random(m) < 0.03
    monto = np.where(grande, monto * rng.lognormal(np.log(5), 0.4, m), monto)

    df = armar_df(a, ts, recv, monto, dev, ip, lat, lon)
    df["es_fraude"] = 0
    df["escenario_fraude"] = "ninguno"
    return df


# --------------------------------------------------------------------------- #
# 3. Fraude
# --------------------------------------------------------------------------- #
def generar_fraude(c, rng, total_days, eval_day, objetivo_total):
    n = c.n
    # (participación en nº de tx fraudulentas, rango de tx por evento)
    cuotas = {"toma_cuenta": (0.40, (1, 3)),
              "vaciado_fraccionado": (0.40, (5, 12)),
              "ingenieria_social": (0.20, (1, 2))}
    cols = {k: [] for k in ["a", "ts", "recv", "monto", "dev", "ip", "lat", "lon", "esc"]}
    contador = 0

    def lejos():
        return rng.uniform(-27.5, -22.5), rng.uniform(-58.5, -54.5)

    for esc, (share, (lo, hi)) in cuotas.items():
        objetivo = int(round(share * objetivo_total))
        generados = 0
        while generados < objetivo:
            a = int(rng.integers(0, n))
            d0 = max(eval_day, int(c.start_day[a]))
            if d0 >= total_days - 1:
                continue
            day = int(rng.integers(d0, total_days))
            k = int(rng.integers(lo, hi + 1))
            sw = bool(c.cambio[a]) and day >= c.switch_day[a]
            dev_main = a * 10 + (2 if sw else 0)
            ip_main = a * 10 + (3 if sw else 0)
            dev_new, ip_new = 10 ** 8 + contador, 6 * 10 ** 7 + contador
            contador += 1
            mule = int(rng.integers(0, n))
            if mule == a:
                mule = (mule + 1) % n

            if esc == "toma_cuenta":
                hour = rng.uniform(0, 6) if rng.random() < 0.55 else rng.uniform(0, 24)
                off = np.concatenate([[0], np.cumsum(rng.uniform(1, 15, k - 1))]) * 60
                usa_new = rng.random() < 0.90
                dev = np.full(k, dev_new if usa_new else dev_main)
                ip = np.full(k, ip_new)
                if rng.random() < 0.75:
                    la, lo_ = lejos()
                else:
                    la, lo_ = c.home_lat[a], c.home_lon[a]
                lat = np.full(k, la) + rng.normal(0, 0.01, k)
                lon = np.full(k, lo_) + rng.normal(0, 0.01, k)
                recv = np.full(k, mule) if rng.random() < 0.7 else rng.integers(0, n, k)
                monto = c.mu[a] * rng.lognormal(np.log(6), 0.6, k)

            elif esc == "vaciado_fraccionado":
                hour = rng.uniform(0, 6) if rng.random() < 0.5 else rng.uniform(0, 24)
                off = np.concatenate([[0], np.cumsum(rng.uniform(1, 6, k - 1))]) * 60
                propio = rng.random() < 0.5            # acceso remoto al dispositivo de la víctima
                dev = np.full(k, dev_main if propio else dev_new)
                ip = np.full(k, ip_main if propio else ip_new)
                if rng.random() < 0.70:
                    la, lo_ = c.home_lat[a], c.home_lon[a]
                else:
                    la, lo_ = lejos()
                lat = np.full(k, la) + rng.normal(0, 0.01, k)
                lon = np.full(k, lo_) + rng.normal(0, 0.01, k)
                if rng.random() < 0.6:
                    recv = np.full(k, mule)
                else:
                    mule2 = (mule + 1 + int(rng.integers(0, n - 2))) % n
                    recv = np.where(np.arange(k) % 2 == 0, mule, mule2)
                monto = c.mu[a] * rng.lognormal(np.log(1.5), 0.35, k)

            else:  # ingenieria_social: la propia víctima paga, todo parece normal salvo destino/monto
                hour = (c.mean_hour[a] + c.std_hour[a] * rng.normal()) % 24
                off = np.concatenate([[0], np.cumsum(rng.uniform(2, 20, k - 1))]) * 60
                dev = np.full(k, dev_main)
                ip = np.full(k, ip_main)
                lat = c.home_lat[a] + rng.normal(0, 0.01, k)
                lon = c.home_lon[a] + rng.normal(0, 0.01, k)
                recv = np.full(k, mule)
                monto = c.mu[a] * rng.lognormal(np.log(3), 0.5, k)

            ts = day * 86400 + np.floor(hour * 3600) + off
            cols["a"].append(np.full(k, a)); cols["ts"].append(ts)
            cols["recv"].append(recv); cols["monto"].append(monto)
            cols["dev"].append(dev); cols["ip"].append(ip)
            cols["lat"].append(lat); cols["lon"].append(lon)
            cols["esc"].append(np.full(k, esc))
            generados += k

    cat = {k: np.concatenate(v) for k, v in cols.items()}
    df = armar_df(cat["a"], cat["ts"], cat["recv"], cat["monto"],
                  cat["dev"], cat["ip"], cat["lat"], cat["lon"])
    df["es_fraude"] = 1
    df["escenario_fraude"] = cat["esc"]
    return df


# --------------------------------------------------------------------------- #
# 4. Features (solo historial previo del emisor)
# --------------------------------------------------------------------------- #
def calcular_features(df, alta_map):
    df = df.sort_values(["id_cuenta_emisor", "fecha_hora", "id_transaccion"],
                        kind="stable").reset_index(drop=True)
    n = len(df)
    t = (df["fecha_hora"] - T0).dt.total_seconds().to_numpy()
    amt = df["monto_pyg"].to_numpy(float)
    lat = df["geo_latitud_emisor"].to_numpy(float)
    lon = df["geo_longitud_emisor"].to_numpy(float)
    hf = (df["fecha_hora"].dt.hour + df["fecha_hora"].dt.minute / 60
          + df["fecha_hora"].dt.second / 3600).to_numpy()
    ang = hf * 2 * np.pi / 24

    out = {k: np.full(n, np.nan) for k in
           ["c1h", "c24h", "s1h", "s24h", "avg30", "dist", "atip"]}

    cuentas, starts = np.unique(df["id_cuenta_emisor"].to_numpy(), return_index=True)
    ends = np.append(starts[1:], n)

    for s, e in zip(starts, ends):
        L = e - s
        i = np.arange(L)
        tt, a_ = t[s:e], amt[s:e]
        cs = np.concatenate([[0.0], np.cumsum(a_)])

        for nombre, win in (("1h", 3600), ("24h", 86400), ("30d", 30 * 86400)):
            lo = np.searchsorted(tt, tt - win, side="left")
            cnt, suma = i - lo, cs[i] - cs[lo]
            if nombre == "1h":
                out["c1h"][s:e], out["s1h"][s:e] = cnt, suma
            elif nombre == "24h":
                out["c24h"][s:e], out["s24h"][s:e] = cnt, suma
            else:
                out["avg30"][s:e] = np.where(cnt > 0, suma / np.maximum(cnt, 1), np.nan)

        # Centroide histórico de ubicación
        csl = np.concatenate([[0.0], np.cumsum(lat[s:e])])
        cso = np.concatenate([[0.0], np.cumsum(lon[s:e])])
        den = np.maximum(i, 1)
        clat = np.where(i > 0, csl[i] / den, np.nan)
        clon = np.where(i > 0, cso[i] / den, np.nan)
        out["dist"][s:e] = haversine(lat[s:e], lon[s:e], clat, clon)

        # Hora habitual (media circular) y distancia circular a la hora actual
        css = np.concatenate([[0.0], np.cumsum(np.sin(ang[s:e]))])
        csc = np.concatenate([[0.0], np.cumsum(np.cos(ang[s:e]))])
        mean_h = (np.arctan2(css[i], csc[i]) * 24 / (2 * np.pi)) % 24
        d = np.abs(((hf[s:e] - mean_h + 12) % 24) - 12)
        out["atip"][s:e] = ((i >= MIN_HIST_HORA) & (d > UMBRAL_HORA_ATIPICA)).astype(float)

    # Primera aparición del par (emisor, X) = "nuevo"
    nuevo_disp = ~df.duplicated(["id_cuenta_emisor", "id_dispositivo_emisor"])
    nueva_ip = ~df.duplicated(["id_cuenta_emisor", "direccion_ip_emisor"])
    nuevo_benef = ~df.duplicated(["id_cuenta_emisor", "id_cuenta_receptor"])

    f = pd.DataFrame(index=df.index)
    fh = df["fecha_hora"]
    f["hora_sin"] = np.sin(ang)
    f["hora_cos"] = np.cos(ang)
    f["es_fin_de_semana"] = (fh.dt.dayofweek >= 5).astype(int)
    f["es_horario_nocturno"] = (hf < 6).astype(int)
    f["hora_atipica"] = out["atip"].astype(int)
    f["dispositivo_nuevo"] = nuevo_disp.astype(int)
    f["ip_nueva"] = nueva_ip.astype(int)
    f["distancia_zona_habitual_km"] = out["dist"]
    alta = df["id_cuenta_emisor"].map(alta_map)
    f["antiguedad_cuenta_dias"] = np.floor(
        np.maximum((fh - alta).dt.total_seconds() / 86400, 0)).astype(int)
    f["tx_count_1h"] = out["c1h"].astype(int)
    f["tx_count_24h"] = out["c24h"].astype(int)
    f["amount_sum_1h"] = out["s1h"]
    f["amount_sum_24h"] = out["s24h"]
    f["monto_pyg"] = amt
    f["monto_promedio_usuario_30d"] = out["avg30"]
    f["ratio_monto_vs_promedio"] = np.where(out["avg30"] > 0, amt / out["avg30"], np.nan)
    f["is_new_beneficiary"] = nuevo_benef.astype(int)
    f = f.drop(columns=["monto_pyg"])  # ya está en las columnas crudas

    res = pd.concat([df, f], axis=1)
    return res


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuentas", type=int, default=15000)
    ap.add_argument("--dias", type=int, default=90, help="días del período de evaluación")
    ap.add_argument("--warmup", type=int, default=30, help="días previos solo para historial")
    ap.add_argument("--tasa-fraude", type=float, default=0.001)
    ap.add_argument("--test-frac", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    total_days = args.warmup + args.dias
    eval_day = args.warmup
    eval_start = T0 + pd.Timedelta(days=eval_day)

    print("Generando cuentas y tráfico legítimo...")
    c = generar_cuentas(args.cuentas, rng, total_days)
    legit = generar_legitimas(c, rng, total_days)
    n_legit_eval = int((legit["fecha_hora"] >= eval_start).sum())
    objetivo = int(round(args.tasa_fraude * n_legit_eval / (1 - args.tasa_fraude)))

    print(f"Inyectando ~{objetivo} transacciones fraudulentas...")
    fraude = generar_fraude(c, rng, total_days, eval_day, objetivo)

    df = pd.concat([legit, fraude], ignore_index=True)
    df = df.sort_values("fecha_hora", kind="stable").reset_index(drop=True)
    df["id_transaccion"] = [f"TX{i:09d}" for i in range(len(df))]

    print("Calculando features (ventanas móviles)...")
    alta_map = pd.Series(T0 + pd.to_timedelta(c.alta_day, unit="D"),
                         index=[f"CTA-{i:07d}" for i in range(c.n)])
    df = calcular_features(df, alta_map)

    # Descartar el warm-up (solo sirvió para construir historial)
    df = df[df["fecha_hora"] >= eval_start].sort_values(
        ["fecha_hora", "id_transaccion"]).reset_index(drop=True)

    cols = RAW + [f for f in FEATURES if f != "monto_pyg"] + LABELS
    df = df[cols].round({"amount_sum_1h": 0, "amount_sum_24h": 0,
                         "monto_promedio_usuario_30d": 0,
                         "ratio_monto_vs_promedio": 4,
                         "distancia_zona_habitual_km": 3,
                         "hora_sin": 5, "hora_cos": 5})

    # Split temporal: train = período temprano, test = período final
    corte = eval_start + pd.Timedelta(days=args.dias * (1 - args.test_frac))
    train = df[df["fecha_hora"] < corte]
    test = df[df["fecha_hora"] >= corte]

    os.makedirs(args.out_dir, exist_ok=True)
    df.to_csv(os.path.join(args.out_dir, "transacciones_completo.csv"), index=False)
    train.to_csv(os.path.join(args.out_dir, "transacciones_train.csv"), index=False)
    test.to_csv(os.path.join(args.out_dir, "transacciones_test.csv"), index=False)

    print("\n=== Resumen ===")
    for nombre, d in (("completo", df), ("train", train), ("test", test)):
        print(f"{nombre:9s}: {len(d):>9,} filas | fraudes: {int(d.es_fraude.sum()):>5,} "
              f"({d.es_fraude.mean():.3%})")
    print("\nFraude por escenario (completo):")
    print(df[df.es_fraude == 1]["escenario_fraude"].value_counts().to_string())
    print(f"\nCorte train/test: {corte}")
    print("\nFeatures para el modelo:\n", FEATURES)


if __name__ == "__main__":
    main()