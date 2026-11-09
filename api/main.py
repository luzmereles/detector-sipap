"""
API REST de puntuación de riesgo (RiskScore) para transferencias del SPI (Sistema de Pagos Instantáneos).

Ejecutar localmente (desde la raíz del proyecto):
    uvicorn api.main:app --reload --port 8000
Documentación interactiva (Swagger):  http://localhost:8000/docs
"""
from __future__ import annotations

import time
from collections import Counter, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from api.motor import MotorRiesgo
from api.schemas import Lote, Resultado, ResultadoLote, Transaccion

estado: dict = {"motor": None, "decisiones": Counter(), "latencias": deque(maxlen=1000), "inicio": time.time()}


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    estado["motor"] = MotorRiesgo()  # el modelo se carga UNA vez al iniciar
    yield


app = FastAPI(
    title="SPI — API de Riesgo de Fraude",
    description=(
        "Recibe una transferencia del Sistema de Pagos Instantáneos (SPI) de Paraguay, vista desde el banco "
        "emisor, y responde en milisegundos con un **RiskScore (0-100)**, la decisión "
        "(**APROBAR / REVISAR / BLOQUEAR**) y los motivos principales (valores SHAP). "
        "Límite operativo: Gs. 10.000.000 por transferencia."
    ),
    version="1.0.0",
    lifespan=ciclo_de_vida,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def medir_tiempo(request: Request, call_next):
    t0 = time.perf_counter()
    respuesta = await call_next(request)
    respuesta.headers["X-Tiempo-Respuesta-ms"] = f"{(time.perf_counter() - t0) * 1000:.2f}"
    return respuesta


@app.exception_handler(RequestValidationError)
async def error_validacion(request: Request, exc: RequestValidationError):
    errores = [{"campo": ".".join(str(p) for p in e["loc"][1:]) or "body", "error": e["msg"]}
               for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detalle": "Transacción inválida", "errores": errores})


@app.exception_handler(Exception)
async def error_interno(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detalle": "Error interno al evaluar la transacción",
                                                  "tipo": type(exc).__name__})


def _registrar(resultados: list[dict]):
    for r in resultados:
        estado["decisiones"][r["decision"]] += 1
        estado["latencias"].append(r["latencia_ms"])


# ------------------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse("/docs")


@app.get("/health", tags=["Sistema"], summary="Estado del servicio")
def health():
    return {"estado": "ok" if estado["motor"] else "cargando", "version_modelo": estado["motor"].version
            if estado["motor"] else None}


@app.get("/model/info", tags=["Sistema"], summary="Información del modelo, métricas y umbrales")
def model_info():
    m = estado["motor"].meta
    return {k: m[k] for k in ["version", "algoritmo", "features", "hiperparametros", "umbrales",
                              "metricas_test", "sobreajuste", "latencia_inferencia_ms",
                              "importancia_shap", "periodos", "impacto_test"]}


@app.get("/stats", tags=["Sistema"], summary="Decisiones tomadas desde que se inició la API")
def stats():
    lat = sorted(estado["latencias"])
    return {
        "total": sum(estado["decisiones"].values()),
        "decisiones": dict(estado["decisiones"]),
        "latencia_media_ms": round(sum(lat) / len(lat), 3) if lat else None,
        "latencia_p95_ms": round(lat[int(0.95 * (len(lat) - 1))], 3) if lat else None,
        "uptime_s": round(time.time() - estado["inicio"]),
    }


@app.post("/score", response_model=Resultado, tags=["Riesgo"],
          summary="Evaluar una transacción")
def score(tx: Transaccion):
    resultado = estado["motor"].evaluar([tx.model_dump()])
    _registrar(resultado)
    return resultado[0]


@app.post("/score/batch", response_model=ResultadoLote, tags=["Riesgo"],
          summary="Evaluar hasta 1000 transacciones en un solo llamado")
def score_batch(lote: Lote):
    t0 = time.perf_counter()
    resultados = estado["motor"].evaluar([t.model_dump() for t in lote.transacciones])
    _registrar(resultados)
    return {"resultados": resultados, "latencia_total_ms": round((time.perf_counter() - t0) * 1000, 3)}
