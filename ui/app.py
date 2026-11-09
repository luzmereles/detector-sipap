"""
Interfaz de demostración — Detector de fraude en transferencias SPI.
Ejecutar localmente:  streamlit run ui/app.py   (con la API corriendo en el puerto 8000)
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime, time as hora
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", API_URL)  # enlace que abre el navegador
RAIZ = Path(__file__).resolve().parents[1]
FLUJO_DEMO = RAIZ / "data" / "demo" / "flujo_demo.csv"
FIGURAS = RAIZ / "reports" / "figures"
COMPARACION = RAIZ / "reports" / "comparacion_modelos.csv"

ESTILO_DECISION = {  # color de estado + ícono + texto (nunca solo color)
    "APROBAR": ("#0ca30c", "✅", "Aprobar"),
    "REVISAR": ("#fab219", "⚠️", "Enviar a revisión"),
    "BLOQUEAR": ("#d03b3b", "⛔", "Bloquear"),
}
CIUDADES = ["Asunción", "Ciudad del Este", "San Lorenzo", "Luque", "Capiatá", "Lambaré",
            "Fernando de la Mora", "Encarnación", "Limpio", "Ñemby", "Pedro Juan Caballero",
            "Coronel Oviedo", "Concepción", "Villarrica", "Caaguazú", "Hernandarias", "Itauguá",
            "Mariano Roque Alonso"]
BANCOS = ["Banco Itaú", "Banco Continental", "ueno bank", "Banco Familiar", "Banco Basa", "Banco GNB",
          "Banco Atlas", "Visión Banco", "Sudameris Bank", "Banco Nacional de Fomento",
          "Interfisa Banco", "Banco Río"]

BASE = dict(fecha=date(2025, 12, 10), hora=hora(12, 30), monto_gs=85_437,
            banco_origen="Banco Itaú", banco_destino="Banco Continental", ciudad="Asunción",
            ciudad_habitual="Asunción", ant_origen=2000,
            con_historial=True, promedio=120_000, n_tx_1h=0, n_tx_24h=2, dest_nuevo=False, disp_nuevo=False)
CASOS = {
    "🧾 Pago habitual a un contacto conocido": {},
    "🌙 Toma de cuenta: madrugada, celular nuevo": dict(
        fecha=date(2025, 12, 20), hora=hora(3, 14), monto_gs=4_500_000, ciudad="Ciudad del Este",
        banco_destino="ueno bank", promedio=380_000, n_tx_1h=2, n_tx_24h=3,
        dest_nuevo=True, disp_nuevo=True),
    "📱 Estafa Marketplace / WhatsApp (de día, su celular)": dict(
        hora=hora(16, 5), monto_gs=1_200_000, promedio=250_000, n_tx_1h=0, n_tx_24h=1, dest_nuevo=True),
    "🏦 Cuenta mula: cuenta recién abierta que mueve mucho de golpe": dict(
        hora=hora(15, 20), monto_gs=3_216_800, ciudad="Luque", ciudad_habitual="Luque", ant_origen=12,
        promedio=2_870_000, n_tx_1h=1, n_tx_24h=1, dest_nuevo=True, disp_nuevo=True),
    "💸 Transferencia legítima grande (aguinaldo)": dict(
        fecha=date(2025, 12, 22), hora=hora(10, 15), monto_gs=6_000_000,
        promedio=900_000, n_tx_1h=0, n_tx_24h=1, dest_nuevo=False),
    "🧪 Caso límite: monto máximo permitido (Gs. 10.000.000)": dict(
        hora=hora(10, 0), monto_gs=10_000_000, promedio=2_000_000),
    "🧪 Caso límite: cliente nuevo sin historial": dict(
        hora=hora(19, 0), monto_gs=300_000, ant_origen=1, con_historial=False,
        n_tx_24h=0, dest_nuevo=True, disp_nuevo=True),
    "🧪 Caso límite: ráfaga de 15 transferencias en 1 hora": dict(
        hora=hora(14, 0), monto_gs=200_000, n_tx_1h=15, n_tx_24h=18, promedio=200_000),
}

st.set_page_config(page_title="Detector de fraude SPI", page_icon="🛡️", layout="wide")


# ------------------------------------------------------------------------------ utilidades
def gs(v: float) -> str:
    return f"Gs. {v:,.0f}".replace(",", ".")


@st.cache_data(ttl=10)
def estado_api():
    try:
        r = requests.get(f"{API_URL}/health", timeout=2)
        return r.ok, r.json()
    except requests.RequestException:
        return False, None


@st.cache_data(ttl=60)
def info_modelo():
    try:
        return requests.get(f"{API_URL}/model/info", timeout=5).json()
    except requests.RequestException:
        return None


def evaluar(tx: dict):
    try:
        r = requests.post(f"{API_URL}/score", json=tx, timeout=5)
    except requests.RequestException as e:
        return None, f"No se pudo conectar con la API ({API_URL}): {e.__class__.__name__}"
    if r.status_code == 422:
        errores = "; ".join(f"{e['campo']}: {e['error']}" for e in r.json().get("errores", []))
        return None, f"Datos inválidos — {errores}"
    if not r.ok:
        return None, f"La API respondió con error {r.status_code}"
    return r.json(), None


def badge(decision: str, grande: bool = False) -> str:
    color, icono, texto = ESTILO_DECISION[decision]
    tam = "1.6rem" if grande else "0.9rem"
    return (f"<span style='background:{color}22;border:2px solid {color};border-radius:8px;"
            f"padding:4px 12px;font-size:{tam};font-weight:700'>{icono} {texto}</span>")


def cargar_caso():
    valores = BASE | CASOS[st.session_state["caso"]]
    for k, v in valores.items():
        st.session_state[k] = v


# ------------------------------------------------------------------------------ encabezado
if "monto_gs" not in st.session_state:
    st.session_state["caso"] = next(iter(CASOS))
    cargar_caso()

st.title("🛡️ Detector de anomalías en transferencias SPI")
st.caption("Puntaje de riesgo en tiempo real para transferencias del Sistema de Pagos Instantáneos (SPI) "
           "de Paraguay, desde el banco emisor")

ok, salud = estado_api()
with st.sidebar:
    st.subheader("Estado del sistema")
    if ok:
        st.success(f"API conectada · modelo {salud['version_modelo']}")
    else:
        st.error(f"API no disponible en {API_URL}")
    meta = info_modelo() if ok else None
    if meta:
        u = meta["umbrales"]
        st.markdown("**Política de decisión**")
        st.markdown(f"- ⛔ Bloquear si score ≥ {u['umbral_bloqueo'] * 100:.1f}\n"
                    f"- ⚠️ Revisar si score ≥ {u['umbral_revision'] * 100:.1f}\n"
                    f"- ✅ Aprobar en otro caso")
        st.metric("Latencia del modelo", f"{meta['latencia_inferencia_ms']:.1f} ms")
    st.caption(f"[Documentación de la API (Swagger)]({PUBLIC_API_URL}/docs)")

tab1, tab2, tab3 = st.tabs(["🔎 Evaluar transferencia", "📡 Flujo en tiempo real", "📊 Modelo y métricas"])

# ------------------------------------------------------------------------------ pestaña 1
with tab1:
    st.selectbox("Cargar un caso de ejemplo", list(CASOS), key="caso", on_change=cargar_caso)
    izq, der = st.columns([3, 2], gap="large")
    with izq:
        with st.form("tx"):
            c1, c2, c3 = st.columns(3)
            c1.number_input("Monto (Gs., máx. 10.000.000)", min_value=0, step=10_000, key="monto_gs")
            c2.date_input("Fecha", key="fecha")
            c3.time_input("Hora", key="hora", step=300)
            c1, c2, c3 = st.columns(3)
            c1.selectbox("Banco origen", BANCOS, key="banco_origen")
            c2.selectbox("Banco destino", BANCOS, key="banco_destino")
            c3.number_input("Transferencias en la última hora", min_value=0, key="n_tx_1h")
            c1, c2, c3 = st.columns(3)
            c1.selectbox("Ciudad de la operación", CIUDADES, key="ciudad")
            c2.selectbox("Ciudad habitual del cliente", CIUDADES, key="ciudad_habitual")
            c3.number_input("Transferencias en 24 h", min_value=0, key="n_tx_24h")
            c1, c2, c3 = st.columns(3)
            c1.number_input("Antigüedad cuenta origen (días)", min_value=0, key="ant_origen")
            c2.number_input("Promedio 30 días (Gs.)", min_value=0, step=10_000, key="promedio")
            c3.checkbox("Cliente con historial", key="con_historial")
            c1, c2 = st.columns(2)
            c1.checkbox("Destinatario nuevo para el cliente", key="dest_nuevo")
            c2.checkbox("Dispositivo nuevo (< 24 h)", key="disp_nuevo")
            enviar = st.form_submit_button("Evaluar riesgo", type="primary", width="stretch")

    with der:
        if enviar:
            s = st.session_state
            tx = {
                "transaction_id": f"UI-{datetime.now():%H%M%S}",
                "timestamp": datetime.combine(s.fecha, s.hora).isoformat(),
                "banco_origen": s.banco_origen, "banco_destino": s.banco_destino,
                "ciudad": s.ciudad, "ciudad_habitual": s.ciudad_habitual,
                "monto_gs": int(s.monto_gs),
                "n_tx_1h": int(s.n_tx_1h), "n_tx_24h": int(s.n_tx_24h),
                "monto_promedio_30d_gs": float(s.promedio) if s.con_historial else None,
                "destinatario_nuevo": bool(s.dest_nuevo), "dispositivo_nuevo": bool(s.disp_nuevo),
                "antiguedad_cuenta_origen_dias": int(s.ant_origen),
            }
            with st.spinner("Evaluando..."):
                res, error = evaluar(tx)
            if error:
                st.error(error)
            else:
                st.markdown(badge(res["decision"], grande=True), unsafe_allow_html=True)
                st.write("")
                m1, m2 = st.columns(2)
                m1.metric("RiskScore", f"{res['risk_score']:.1f} / 100")
                m2.metric("Latencia", f"{res['latencia_ms']:.1f} ms")
                st.progress(min(res["risk_score"] / 100, 1.0))
                for regla in res["reglas_aplicadas"]:
                    st.warning(f"Regla de negocio: {regla}")
                if res["motivos"]:
                    st.markdown("**Principales motivos del riesgo (SHAP)**")
                    for mot in res["motivos"]:
                        st.markdown(f"- **{mot['descripcion'].capitalize()}**: {mot['valor']}  "
                                    f"<span style='color:gray'>(+{mot['aporte']:.2f})</span>",
                                    unsafe_allow_html=True)
                else:
                    st.info("Ninguna variable aumentó el riesgo de forma relevante.")
                with st.expander("Ver JSON de la respuesta"):
                    st.json(res)
        else:
            st.info("Elegí un caso de ejemplo o completá el formulario y presioná **Evaluar riesgo**.")

# ------------------------------------------------------------------------------ pestaña 2
with tab2:
    st.markdown("Simula el flujo de mayo y junio 2026 (período de **prueba**). "
                "La muestra tiene más fraudes de lo normal para que se vean durante la demo.")
    if not FLUJO_DEMO.exists():
        st.warning("No se encontró data/demo/flujo_demo.csv — ejecutá `python generar_datos.py`.")
    else:
        flujo = pd.read_csv(FLUJO_DEMO)
        c1, c2, c3 = st.columns([2, 2, 1])
        n = c1.slider("Cantidad de transferencias", 20, 500, 150, step=10)
        velocidad = c2.slider("Velocidad (transferencias por segundo)", 1, 50, 10)
        iniciar = c3.button("▶ Iniciar", type="primary", width="stretch")

        k1, k2, k3, k4, k5 = st.columns(5)
        ph = {"total": k1.empty(), "APROBAR": k2.empty(), "REVISAR": k3.empty(), "BLOQUEAR": k4.empty(),
              "lat": k5.empty()}
        resumen_ph = st.empty()
        st.markdown("**🚨 Últimas alertas (revisión o bloqueo)**")
        alertas_ph = st.empty()
        st.markdown("**📜 Últimas transferencias procesadas**")
        tabla_ph = st.empty()

        if iniciar:
            muestra = flujo.sample(n, random_state=int(time.time())).sort_values("timestamp")
            filas, cont = [], {"APROBAR": 0, "REVISAR": 0, "BLOQUEAR": 0}
            # mismo esquema que el dataset, sin las etiquetas (es_fraude, tipo_fraude)
            columnas_api = ["transaction_id", "timestamp", "cuenta_emisor_id", "banco_origen",
                            "banco_destino", "cuenta_destino_id", "ciudad", "ciudad_habitual",
                            "dispositivo_id", "monto_gs", "n_tx_1h", "n_tx_24h", "monto_promedio_30d_gs",
                            "destinatario_nuevo", "dispositivo_nuevo", "antiguedad_cuenta_origen_dias"]
            for _, fila in muestra.iterrows():
                tx = {k: (None if pd.isna(fila[k]) else fila[k]) for k in columnas_api}
                tx = {k: (v.item() if hasattr(v, "item") else v) for k, v in tx.items()}
                res, error = evaluar(tx)
                if error:
                    st.error(error)
                    break
                cont[res["decision"]] += 1
                filas.append({"hora": str(fila["timestamp"])[5:16], "id": fila["transaction_id"],
                              "monto": gs(fila["monto_gs"]),
                              "score": res["risk_score"], "decisión": ESTILO_DECISION[res["decision"]][1] + " " + res["decision"],
                              "real": "🚨 fraude" if fila["es_fraude"] else "legítima",
                              "motivo principal": res["motivos"][0]["descripcion"]
                              if res["motivos"] and res["decision"] != "APROBAR" else "",
                              "ms": res["latencia_ms"], "_dec": res["decision"], "_y": fila["es_fraude"]})
                df = pd.DataFrame(filas)
                ph["total"].metric("Procesadas", len(df))
                ph["APROBAR"].metric("✅ Aprobadas", cont["APROBAR"])
                ph["REVISAR"].metric("⚠️ En revisión", cont["REVISAR"])
                ph["BLOQUEAR"].metric("⛔ Bloqueadas", cont["BLOQUEAR"])
                ph["lat"].metric("Latencia media", f"{df['ms'].mean():.1f} ms")
                alertas = df[df["_dec"] != "APROBAR"].tail(5)
                if len(alertas):
                    alertas_ph.dataframe(alertas.drop(columns=["_dec", "_y"]).iloc[::-1], hide_index=True,
                                         width="stretch")
                tabla_ph.dataframe(df.drop(columns=["_dec", "_y"]).tail(12).iloc[::-1], hide_index=True,
                                   width="stretch")
                time.sleep(1 / velocidad)
            if filas:
                df = pd.DataFrame(filas)
                fr = df[df["_y"] == 1]
                det = (fr["_dec"] != "APROBAR").sum()
                falsas = ((df["_y"] == 0) & (df["_dec"] != "APROBAR")).sum()
                resumen_ph.success(f"Fin del flujo: {det} de {len(fr)} fraudes detenidos "
                                   f"(bloqueados o en revisión) · {falsas} transferencias legítimas "
                                   f"marcadas para revisión/bloqueo de {len(df) - len(fr)}.")

# ------------------------------------------------------------------------------ pestaña 3
with tab3:
    if not meta:
        st.warning("Conectá la API para ver la información del modelo.")
    else:
        mt, imp = meta["metricas_test"], meta["impacto_test"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Average precision (prueba)", f"{mt['average_precision']:.3f}",
                  help=f"PR-AUC calculada con average_precision_score · IC 95 %: {meta['sobreajuste']['pr_auc_test_ic95']}")
        c2.metric("ROC-AUC (prueba)", f"{mt['roc_auc']:.3f}")
        c3.metric("Fraudes detenidos", f"{imp['fraudes_bloqueados'] + imp['fraudes_a_revision']} / {imp['fraudes_test']}")
        c4.metric("Monto protegido", gs(imp["monto_fraude_detenido_gs"]),
                  f"{imp['monto_fraude_detenido_gs'] / imp['monto_fraude_total_gs']:.0%} del fraude")
        st.caption(f"Algoritmo: {meta['algoritmo']} · Entrenado con {meta['periodos']['train']}, "
                   f"validado en {meta['periodos']['validacion']}, probado en {meta['periodos']['test']}")
        if COMPARACION.exists():
            st.markdown("#### Comparación de modelos (etapa 1 y 2: validación mar-abr 2026 · etapa 3: prueba may-jun 2026)")
            st.dataframe(pd.read_csv(COMPARACION), hide_index=True, width="stretch")
        figuras = sorted(FIGURAS.glob("*.png")) if FIGURAS.exists() else []
        for i in range(0, len(figuras), 2):
            cols = st.columns(2)
            for col, fig in zip(cols, figuras[i:i + 2]):
                col.image(str(fig), width="stretch")
        with st.expander("Hiperparámetros elegidos por Optuna (etapa 2)"):
            st.json(meta["hiperparametros"])
