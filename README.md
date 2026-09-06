# Detector de anomalías en transacciones del sistema de pagos (SIPAP / QR)

**Sector 4: Economía, Finanzas y Comercio Local — Proyecto 12**

**Autoras:** Luz Mereles y Sol Nunez

## Objetivo

Identificar transferencias sospechosas o anómalas dentro de un flujo simulado de transacciones financieras, mediante una API de puntuación de riesgo (RiskScore) que determine si una transacción debe ser **aprobada, bloqueada o enviada a revisión**.

## Alcance

El análisis se centra exclusivamente en el **comportamiento histórico del emisor de la transacción**, considerando sus patrones habituales de operación para identificar posibles anomalías.

## Etapa 1: Investigación y generación del dataset

### Actividades de la etapa

* Definir el alcance del proyecto y tomar decisiones de diseño.
* Definir criterios de fraude y anomalía tomando como referencia el entorno de pagos SIPAP/SPI.
* Generar un dataset sintético de transacciones y perfiles de usuario.
* Estructurar el proyecto y organizar los archivos necesarios para las siguientes etapas.

### Estructura del proyecto

```text
detector-fraude-sipap/
├── data/              # Datasets utilizados por el proyecto
├── src/               # Scripts de generación y entrenamiento
├── docs/              # Documentación 
├── requirements.txt   # Dependencias
└── README.md          # Documentación principal
```

## Instalación

Instalar las dependencias del proyecto:

```
pip install -r requirements.txt
```
