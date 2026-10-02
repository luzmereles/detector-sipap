# Detector de anomalías en transacciones del sistema de pagos (SIPAP / QR)

**Sector 4: Economía, Finanzas y Comercio Local — Proyecto 12**  
**Autoras:** Luz Mereles y Sol Nunez

## Objetivo

Identificar transferencias sospechosas o anómalas dentro de un flujo simulado de transacciones financieras, mediante un modelo de clasificación y una API de puntuación de riesgo (**RiskScore**) que determine si una transacción debe ser **aprobada, bloqueada o enviada a revisión**.

## Alcance

El proyecto se centra en la detección de anomalías en transferencias desde la perspectiva del **emisor**, considerando el comportamiento habitual asociado a su segmento y su perfil de operación.

Para ello, se utiliza un **dataset sintético** que simula transferencias del sistema de pagos y distintos escenarios de fraude. Las características utilizadas por el modelo se obtienen durante la generación de los datos, comparando cada transferencia con los parámetros normales definidos para el segmento del usuario y con información de su perfil.

La solución utiliza **XGBoost** como modelo supervisado de clasificación y posteriormente expone su resultado mediante una API.

## Flujo general del proyecto

```text
Investigación y definición
          ↓
Generación del dataset sintético
+ perfiles de usuario
+ características derivadas
          ↓
Entrenamiento y evaluación del modelo
          ↓
API de detección y RiskScore
          ↓
Interfaz + preparación de la demo
```

## Etapa 1: Investigación y definición

### Actividades de la etapa

* Definir el alcance y los objetivos del proyecto.
* Investigar el contexto de los sistemas de pagos SIPAP/SPI y QR en Paraguay.
* Definir los segmentos de usuarios y sus comportamientos normales.
* Definir los perfiles de usuario y los parámetros necesarios para representar su comportamiento habitual.
* Definir los campos de las transferencias.
* Definir las características que utilizará el modelo.
* Definir los escenarios y criterios de fraude.
* Establecer la metodología para la generación del dataset sintético.
* Definir la arquitectura general de la solución.

## Etapa 2: Generación del dataset sintético

En esta etapa se generan las transferencias, los perfiles de usuario y las características utilizadas posteriormente por el modelo.

La generación se realiza **por segmentos de comportamiento**, utilizando parámetros normales previamente definidos para cada segmento.

Durante la generación de cada transferencia se:

* Asigna y utiliza el segmento correspondiente al usuario.
* Mantiene el perfil del usuario, incluyendo su dispositivo habitual y sus indicadores de frecuencia.
* Generan los datos propios de la transferencia.
* Generan escenarios normales y fraudulentos.
* Inyectan las señales correspondientes a cada escenario de fraude.
* Calculan las características derivadas a partir de la comparación de la transferencia con el comportamiento normal de su segmento.
* Generan el conjunto de datos final utilizado para el entrenamiento.

### Características derivadas

Las características no se generan mediante una etapa independiente posterior ni mediante el procesamiento de ventanas históricas sobre el dataset terminado.

Se obtienen **durante la generación de los datos**, a partir de la información disponible en ese momento y de los parámetros normales del segmento.

Entre las características utilizadas se encuentran:

* `monto_pyg`
* `zscore_monto_segmento`
* `monto_fuera_rango_segmento`
* `hora_sin`
* `hora_cos`
* `hora_fuera_rango_segmento`
* `geo_fuera_zona_segmento`
* `cambio_de_dispositivo`

El objetivo es representar cuánto se desvía una transferencia respecto al comportamiento esperado para el segmento al que pertenece el usuario.

### Dataset generado

El dataset contiene tanto los datos originales de las transferencias como información necesaria para su trazabilidad y validación.

Los identificadores, datos de auditoría y variables utilizadas únicamente para trazabilidad no se utilizan como características de entrada del modelo.

## Etapa 3: Entrenamiento y evaluación del modelo

En esta etapa se utiliza el dataset generado en la etapa anterior para entrenar el modelo supervisado.

### Actividades de la etapa

* Preparar los conjuntos de entrenamiento, validación y prueba.
* Seleccionar las características que serán utilizadas como entrada del modelo.
* Entrenar el modelo **XGBoost**.
* Configurar el tratamiento del desbalance entre transacciones legítimas y fraudulentas.
* Evaluar el comportamiento del modelo.
* Analizar métricas de clasificación, especialmente aquellas relacionadas con la detección de fraude y los falsos positivos.
* Guardar el modelo entrenado para su utilización posterior en la API.

## Etapa 4: 




### Flujo de una transferencia en la API

```text
Transferencia recibida
        ↓
Perfil del usuario
        ↓
Parámetros normales del segmento
        ↓
Cálculo de características
        ↓
Modelo XGBoost
        ↓
RiskScore
        ↓
Decisión
 ┌────────────┬──────────────┬─────────────────┐
 │  Aprobada  │  Bloqueada   │ Revisión manual │
 └────────────┴──────────────┴─────────────────┘
```

## Estructura del proyecto

```text
detector-fraude-sipap/
├── data/                # Datasets generados y utilizados por el proyecto
├── src/                 # Código fuente de generación, entrenamiento y API
├── models/              # Modelos entrenados
├── docs/                # Documentación del proyecto
├── requirements.txt     # Dependencias
└── README.md            # Documentación principal
```

## Instalación

Instalar las dependencias del proyecto:

```bash
pip install -r requirements.txt
```