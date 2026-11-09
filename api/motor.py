"""
Motor de riesgo: carga el modelo una sola vez, calcula el RiskScore,
aplica la política de decisión y explica cada resultado con valores SHAP.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import xgboost as xgb

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))  # features.py (el mismo que usa el notebook de entrenamiento)
from features import DESCRIPCION, FEATURES, construir_features  # noqa: E402

DIR_MODELO = Path(os.getenv("MODEL_DIR", RAIZ / "models"))
TZ_PY = ZoneInfo("America/Asuncion")

# Regla de negocio que complementa al modelo (motor híbrido).
# Nunca baja una decisión, solo puede subirla a REVISAR.
# (El límite de Gs. 10.000.000 por transferencia se valida antes, en api/schemas.py: 422.)
LIMITE_RAFAGA_1H = 10
ORDEN = {"APROBAR": 0, "REVISAR": 1, "BLOQUEAR": 2}


def _gs(v: float) -> str:
    return f"{v:,.0f} Gs.".replace(",", ".")


class MotorRiesgo:
    def __init__(self, directorio: Path = DIR_MODELO):
        self.booster = xgb.Booster()
        self.booster.load_model(directorio / "modelo_xgb.json")
        self.meta = json.loads((directorio / "metadata.json").read_text(encoding="utf-8"))
        self.umbrales = self.meta["umbrales"]
        self.version = self.meta["version"]
        # calentamiento: la primera predicción siempre es más lenta
        self.booster.predict(xgb.DMatrix(np.zeros((1, len(FEATURES))), feature_names=FEATURES))

    # ------------------------------------------------------------------
    def evaluar(self, transacciones: list[dict]) -> list[dict]:
        t0 = time.perf_counter()
        df = pd.DataFrame(transacciones)
        ahora = datetime.now(TZ_PY).replace(tzinfo=None)
        df["timestamp"] = [self._hora_local(t, ahora) for t in df["timestamp"]]
        X = construir_features(df)
        dm = xgb.DMatrix(X, feature_names=FEATURES)
        prob = self.booster.predict(dm)
        contrib = self.booster.predict(dm, pred_contribs=True)[:, :-1]
        lat = (time.perf_counter() - t0) * 1000 / len(df)

        salida = []
        for i, fila in enumerate(transacciones):
            p = float(prob[i])
            decision = self._decision(p)
            reglas = []
            if fila["n_tx_1h"] >= LIMITE_RAFAGA_1H:
                reglas.append(f"Ráfaga: {fila['n_tx_1h']} transferencias en la última hora")
            if reglas and ORDEN[decision] < ORDEN["REVISAR"]:
                decision = "REVISAR"
            salida.append({
                "transaction_id": fila.get("transaction_id"),
                "risk_score": round(p * 100, 1),
                "probabilidad": round(p, 6),
                "decision": decision,
                "motivos": self._motivos(contrib[i], X.iloc[i], fila),
                "reglas_aplicadas": reglas,
                "latencia_ms": round(lat, 3),
                "version_modelo": self.version,
            })
        return salida

    # ------------------------------------------------------------------
    def _decision(self, p: float) -> str:
        if p >= self.umbrales["umbral_bloqueo"]:
            return "BLOQUEAR"
        if p >= self.umbrales["umbral_revision"]:
            return "REVISAR"
        return "APROBAR"

    @staticmethod
    def _hora_local(t, ahora):
        if t is None or (isinstance(t, float) and np.isnan(t)):
            return ahora
        t = pd.Timestamp(t)
        return t.tz_convert(TZ_PY).tz_localize(None) if t.tzinfo else t

    @staticmethod
    def _valor_legible(var: str, x: pd.Series, fila: dict) -> str:
        si_no = lambda b: "sí" if b else "no"  # noqa: E731
        prom = fila.get("monto_promedio_30d_gs")
        return {
            "log_monto": _gs(fila["monto_gs"]),
            "log_ratio_monto_promedio": f"{fila['monto_gs'] / prom:.1f}x su promedio ({_gs(prom)})" if prom else "sin promedio",
            "sin_historial": si_no(x["sin_historial"]),
            "hora": f"{int(x['hora']):02d} hs",
            "es_nocturna": si_no(x["es_nocturna"]),
            "dia_semana": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][int(x["dia_semana"])],
            "es_fin_de_semana": si_no(x["es_fin_de_semana"]),
            "es_fin_de_mes": si_no(x["es_fin_de_mes"]),
            "log_antiguedad_origen": f"{fila['antiguedad_cuenta_origen_dias']} días",
            "n_tx_1h": str(fila["n_tx_1h"]),
            "n_tx_24h": str(fila["n_tx_24h"]),
            "destinatario_nuevo": si_no(fila["destinatario_nuevo"]),
            "dispositivo_nuevo": si_no(fila["dispositivo_nuevo"]),
            "ciudad_distinta": f"{fila['ciudad']} (habitual: {fila['ciudad_habitual']})",
        }[var]

    def _motivos(self, aportes: np.ndarray, x: pd.Series, fila: dict, k: int = 3) -> list[dict]:
        orden = np.argsort(-aportes)[:k]
        return [{"variable": FEATURES[j], "descripcion": DESCRIPCION[FEATURES[j]],
                 "valor": self._valor_legible(FEATURES[j], x, fila), "aporte": round(float(aportes[j]), 3)}
                for j in orden if aportes[j] > 0]
