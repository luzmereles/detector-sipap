"""Esquemas de entrada/salida de la API (validación automática con Pydantic)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

LIMITE_MONTO_GS = 10_000_000  # límite operativo por transferencia (supuesto del proyecto)

EJEMPLO = {
    "transaction_id": "TX-DEMO-0001",
    "timestamp": "2025-12-20T03:14:00",
    "cuenta_emisor_id": "EMI-00123",
    "banco_origen": "Banco Itaú",
    "banco_destino": "ueno bank",
    "cuenta_destino_id": "CTA-10458821",
    "ciudad": "Ciudad del Este",
    "ciudad_habitual": "Asunción",
    "dispositivo_id": "DEV-1047731",
    "monto_gs": 4_500_000,
    "monto_promedio_30d_gs": 380_000,
    "n_tx_1h": 2,
    "n_tx_24h": 3,
    "destinatario_nuevo": True,
    "dispositivo_nuevo": True,
    "antiguedad_cuenta_origen_dias": 1450,
}


class Transaccion(BaseModel):
    """Transferencia SPI enriquecida con el contexto que el banco emisor conoce al autorizarla.
    Mismo esquema que data/transacciones_spi.csv.gz (sin las etiquetas es_fraude / tipo_fraude).
    Los identificadores y los bancos son descriptivos: el modelo no los usa."""

    transaction_id: str | None = Field(None, max_length=64)
    timestamp: datetime | None = Field(None, description="Fecha y hora local (Paraguay). Si se omite, se usa la hora actual.")
    cuenta_emisor_id: str | None = Field(None, max_length=64)
    banco_origen: str | None = Field(None, max_length=80)
    banco_destino: str | None = Field(None, max_length=80)
    cuenta_destino_id: str | None = Field(None, max_length=64)
    ciudad: str = Field(..., min_length=2, max_length=80, description="Ciudad desde donde se opera")
    ciudad_habitual: str = Field(..., min_length=2, max_length=80)
    dispositivo_id: str | None = Field(None, max_length=64)
    monto_gs: int = Field(..., gt=0, le=LIMITE_MONTO_GS,
                          description="Monto en guaraníes (máximo Gs. 10.000.000 por transferencia)")
    n_tx_1h: int = Field(0, ge=0, le=10_000)
    n_tx_24h: int = Field(0, ge=0, le=100_000)
    monto_promedio_30d_gs: float | None = Field(None, ge=0, description="0 (o null) si el cliente no tiene historial en 30 días")
    destinatario_nuevo: bool
    dispositivo_nuevo: bool
    antiguedad_cuenta_origen_dias: int = Field(..., ge=0, le=36_500)

    model_config = {"json_schema_extra": {"examples": [EJEMPLO]}}

    @model_validator(mode="after")
    def coherencia(self):
        if self.n_tx_24h < self.n_tx_1h:
            raise ValueError("n_tx_24h no puede ser menor que n_tx_1h")
        return self


class Motivo(BaseModel):
    variable: str
    descripcion: str
    valor: str
    aporte: float = Field(..., description="Aporte SHAP al riesgo (log-odds). Positivo = aumenta el riesgo")


class Resultado(BaseModel):
    transaction_id: str | None
    risk_score: float = Field(..., ge=0, le=100, description="Puntaje de riesgo 0-100")
    probabilidad: float
    decision: Literal["APROBAR", "REVISAR", "BLOQUEAR"]
    motivos: list[Motivo]
    reglas_aplicadas: list[str]
    latencia_ms: float
    version_modelo: str


class Lote(BaseModel):
    transacciones: list[Transaccion] = Field(..., min_length=1, max_length=1000)


class ResultadoLote(BaseModel):
    resultados: list[Resultado]
    latencia_total_ms: float
