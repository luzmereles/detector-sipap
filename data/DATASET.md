# Data card — Transferencias SPI sintéticas (Paraguay, jul 2025 – jun 2026)

## 1. ¿Por qué un dataset sintético?

No existe un dataset público de transferencias del SPI (Sistema de Pagos Instantáneos) en Paraguay: los datos
transaccionales están protegidos por el secreto bancario y la normativa de protección de datos personales. Los
datasets públicos de fraude (PaySim, tarjetas europeas de Kaggle) no reflejan la realidad local (guaraníes, bancos
paraguayos, aguinaldo, fin de mes).

Por eso construimos un **generador reproducible basado en reglas de negocio** (`generar_datos.py`, semilla 42) que
simula clientes de bancos paraguayos e inyecta fraudes según tipologías conocidas. Así se controla la tasa de fraude
(< 0,1 %) y se conoce la etiqueta verdadera de cada transferencia.

## 2. Alcance

- **Solo transferencias interbancarias instantáneas del SPI**, vistas desde el **banco emisor**.
- No se distingue el canal de iniciación (app, web, PY-QR); no se incluyen pagos con tarjeta ni operaciones de POS.
- Cada columna es información que el banco emisor conoce o puede calcular **al autorizar** la transferencia. No se usa
  información interna del banco receptor (por ejemplo, la antigüedad de la cuenta destino).

## 3. Resumen

| Característica | Valor |
|---|---|
| Período | 1 de julio de 2025 – 30 de junio de 2026 (junio 2025 se simula solo como historial previo) |
| Transferencias | 1.692.473 |
| Fraudes | 1.331 transferencias en 505 casos (**0,0786 %**, ≈ 1 cada 1.270 transferencias) |
| Clientes emisores simulados | 8.000 (+ 58 cuentas mula abiertas para cometer fraude = 8.058 emisores) |
| Cuentas destino distintas | 215.208 |
| Bancos / ciudades | 12 / 18 |
| Moneda | Guaraníes (Gs.) |
| Archivo | `data/transacciones_spi.csv.gz` (CSV comprimido, ≈ 56 MB; pandas lo lee directo) |

**Un año de datos.** El período se amplió de 6 a 12 meses para que diciembre (aguinaldo, montos más altos) quede dentro
del **entrenamiento** y no distorsione la validación ni la prueba. Con un año, 8.000 clientes alcanzan para tener
cientos de fraudes en cada partición.

## 4. Columnas

| Columna | Tipo | Descripción |
|---|---|---|
| `transaction_id` | texto | Identificador único de la transferencia (`TX-00000001`) |
| `timestamp` | fecha-hora | Fecha y hora local de Paraguay |
| `cuenta_emisor_id` | texto | Cliente que origina el pago |
| `banco_origen` | texto | Entidad del ordenante |
| `banco_destino` | texto | Entidad del beneficiario |
| `cuenta_destino_id` | texto | Cuenta que recibe la transferencia |
| `ciudad` | texto | Ciudad desde donde se opera |
| `ciudad_habitual` | texto | Ciudad habitual del cliente |
| `dispositivo_id` | texto | Celular o navegador utilizado |
| `monto_gs` | entero | Importe de la transferencia en guaraníes |
| `n_tx_1h` | entero | Transferencias anteriores del cliente durante la última hora |
| `n_tx_24h` | entero | Transferencias anteriores del cliente durante las últimas 24 horas |
| `monto_promedio_30d_gs` | entero | Promedio de los montos del cliente en los últimos 30 días; **0 si no tiene historial** |
| `destinatario_nuevo` | booleano | Primera vez que el emisor transfiere a ese destinatario |
| `dispositivo_nuevo` | booleano | El dispositivo se usó por primera vez hace menos de 24 horas, según el historial disponible |
| `antiguedad_cuenta_origen_dias` | entero | Días desde la apertura de la cuenta del emisor |
| `es_fraude` | entero 0/1 | **Etiqueta objetivo**: 1 = fraude, 0 = legítima |
| `tipo_fraude` | texto | Tipología (`ninguno` en las legítimas). **Solo para análisis; no se usa para entrenar** |

Los identificadores de cuentas y dispositivos son códigos opacos (`CTA-…`, `DEV-…`) asignados al final de la
simulación, para que ningún ID revele si pertenece a un escenario de fraude.

**Sin valores faltantes.** Cuando un cliente no hizo transferencias en los 30 días anteriores, no existe un promedio;
en ese caso `monto_promedio_30d_gs = 0` y la feature `sin_historial = 1` (5.077 transferencias, 0,30 %: sobre todo
clientes nuevos y esporádicos).

### Coherencia temporal de las variables de contexto

Se calculan ordenando las transferencias de cada emisor por fecha y hora y usando **solo las anteriores** (incluido el
historial de junio 2025, que no se exporta):

- `n_tx_1h` / `n_tx_24h`: transferencias previas del emisor en `[t − 1 h, t)` y `[t − 24 h, t)`.
- `monto_promedio_30d_gs`: promedio de los montos previos del emisor en `[t − 30 días, t)`; 0 si no hay ninguno.
- `destinatario_nuevo`: verdadero **solo si no existe una transferencia anterior del mismo emisor a la misma cuenta**.
- `dispositivo_nuevo`: verdadero si ese emisor usó ese dispositivo por primera vez hace 24 h o menos.

El notebook `01_eda.ipynb` recalcula estas variables de forma independiente con ventanas móviles de pandas y verifica
que coincidan (0 diferencias).

## 5. Comportamiento legítimo simulado

### Población de clientes

| Perfil | % de clientes | Comportamiento |
|---|---|---|
| Regular | 80 % | cuenta abierta antes del período (7 % con menos de 90 días); opera con su frecuencia propia |
| Nuevo | 10 % | abre la cuenta durante el año (jul 2025 – may 2026) y no opera antes de abrirla. La mayoría opera poco; una minoría (25 %) hace de 2 a 5 transferencias en sus primeros días a contactos y cuentas nuevas |
| Esporádico | 10 % | 1 a 2 transferencias al mes; muchas veces no tiene historial en los últimos 30 días |

Los clientes nuevos activos y los esporádicos se parecen a propósito a una cuenta mula (cuenta reciente o sin
historial, varios destinatarios nuevos), pero hacen pagos legítimos de montos habituales.

### Hábitos

- **Capacidad económica**: ingreso mensual lognormal centrado en ~1,25 salarios mínimos (**Gs. 3.044.000**); el 5 % de
  los clientes tiene mayor capacidad (3 a 6 veces). El salario mínimo genera diversidad, **no limita** lo que se transfiere.
- **Frecuencia**: tasa diaria propia de cada cliente (gamma, media ≈ 0,66 transferencias por día en los regulares).
- **Tipos de operación** (internos, no se exportan): pagos cotidianos 51,5 %, envíos a familiares y amigos 37 %, pagos
  mayores (alquiler, cuotas) 10 % y compras grandes 1,5 %.
- **Límite operativo**: ninguna transferencia supera **Gs. 10.000.000**.
- **Importes realistas**: redondeo a múltiplos de 1, 100, 1.000, 10.000 o 50.000 Gs.; el 48 % no es múltiplo de 1.000
  (ej.: Gs. 5.699) y solo el 17 % es múltiplo de 10.000.
- **Calendario**: +40 % de movimiento a **fin de mes** (últimos 5 días); en **diciembre** (aguinaldo) +30 % de
  movimiento, un pico del 18 al 24 y **montos 25 % más altos** (monto medio Gs. 506.000 contra ~Gs. 414.000 el resto del año).
- **Sesiones de varios pagos seguidos**: algunos clientes pagan varias cuentas en pocos minutos (servicios, sueldo del
  personal doméstico), sobre todo a fin de mes, en horario diurno y a destinatarios habituales.
- **Horario**: picos al mediodía y a la salida del trabajo; 2 % de clientes "noctámbulos".
- **Viajes**: la ciudad de destino se elige de la lista general de ciudades, ponderada por población, sin la ciudad
  habitual del cliente.

### Ruido legítimo (casos legítimos que se parecen a fraude)

Es intencional: **ninguna señal por sí sola alcanza** para decidir que una transferencia es fraude.

| Señal en transferencias legítimas | % de las legítimas |
|---|---|
| Destinatario nuevo (comercio o contacto nuevo, primeros pagos de un cliente nuevo) | 24,0 % |
| Desde otra ciudad (viajes) | 5,0 % |
| Dispositivo nuevo (celular nuevo, reinstalar la app, otra computadora) | 1,8 % |
| De madrugada (0 a 5 h) | 1,8 % |
| 3 o más transferencias en la hora previa (sesiones de pagos) | 1,6 % |
| Sin historial en los últimos 30 días | 0,3 % |

## 6. Tipologías de fraude

Los porcentajes son de **casos** (505 en total). Un caso puede tener varias transferencias; el orden se mantiene
también en cantidad de transferencias. Cada tipología es una **combinación** de señales, y ninguna señal está presente
en todos los casos.

| Tipología | % de casos | Cómo se simula | Transferencias (% del fraude) |
|---|---|---|---|
| **Toma de cuenta** (phishing, robo de credenciales) | 40 % | Al atacante se le ve **al menos 2** de estas señales: dispositivo nuevo (~80 %), madrugada 0–5 h (~55 %), otra ciudad (~45 %). 1 a 4 transferencias, a cuentas nuevas. Monto: 50 % alto (varias veces su promedio o intento de vaciar la cuenta), 30 % parecido al habitual, 20 % menor | 503 (37,8 %) |
| **Ráfaga de transferencias** (fraccionamiento) | 15 % | 3 a 7 transferencias de **montos bajos** (20 % a 80 % del habitual) con 0,5 a 4 minutos entre sí, a varias cuentas; dispositivo nuevo 35 %, madrugada 25 % | 360 (27,0 %) |
| **Cuenta mula** (el **emisor** es la mula) | 20 % | Cuenta que mueve dinero de golpe: 60 % **recién abierta** (0 a 60 días, sin historial) y 40 % **dormida** (cliente esporádico sin movimientos en 30 días o más). 2 a 5 transferencias de montos altos (Gs. 1 a 6 millones, en general), 90 % a destinos nuevos; dispositivo nuevo en las cuentas recién abiertas y en la mitad de las dormidas | 308 (23,1 %) |
| **Ingeniería social** (estafas por WhatsApp o Marketplace) | 15 % | La víctima usa **su propio dispositivo** y **su horario habitual**; destinatario nuevo (~85 %), monto 1,5 a 4 veces su promedio; en el 40 % de los casos paga de nuevo horas después ("falta un pago más") | 110 (8,3 %) |
| **Camuflado** | 10 % | Imita dispositivo, horario, importe (0,8 a 1,8 veces su monto típico) y frecuencia normales; el 40 % va a la cuenta de un contacto habitual comprometida | 50 (3,8 %) |

Señales por tipología, en entrenamiento (% de transferencias; `reports/eda/07_senales_por_tipologia.png`):

| | Dispositivo nuevo | Madrugada | Otra ciudad | Destinatario nuevo | Sin historial | ≥ 3 tx en 1 h |
|---|---|---|---|---|---|---|
| Legítima | 2 | 2 | 5 | 26 | 0 | 2 |
| Toma de cuenta | 84 | 75 | 66 | 69 | 2 | 9 |
| Ráfaga | 40 | 23 | 2 | 81 | 0 | 37 |
| Cuenta mula | 83 | 19 | 0 | 94 | 33 | 0 |
| Ingeniería social | 0 | 6 | 3 | 59 | 2 | 0 |
| Camuflado | 0 | 0 | 3 | 75 | 6 | 0 |

**El monto no determina el fraude**: hay 427 fraudes menores a Gs. 100.000 (las ráfagas fraccionan) y 16.886
transferencias legítimas de Gs. 5 millones o más.

## 7. Calidad de los datos (EDA)

El dataset se genera **limpio desde su creación**. `notebooks/01_eda.ipynb` lo evalúa y exporta a `reports/eda/`:

| Archivo | Contenido |
|---|---|
| `01_calidad_integridad.png`, `calidad_columnas.csv`, `restricciones.csv` | faltantes, tipos, duplicados y 18 restricciones verificadas (todas se cumplen) |
| `02_distribucion_montos.png` | montos por clase, rangos y redondeo de los importes |
| `03_variables_principales.png` | transferencias por día, hora, día del mes, ventanas y antigüedad |
| `04_distribucion_clases.png` | clases, tasa de fraude por mes y tipologías |
| `05` a `07` | features según la clase y señales por tipología (solo entrenamiento) |
| `08_dispersion_pares.png`, `09_proyeccion_pca.png` | dispersión y proyección PCA para ver el solapamiento |
| `EDA.md` | resumen numérico generado por el notebook |

## 8. Partición temporal

División **temporal**, no aleatoria (definida en `features.py`):

| Conjunto | Período | Transferencias | Fraudes |
|---|---|---|---|
| Entrenamiento | jul 2025 – feb 2026 | 1.137.643 | 939 |
| Validación (primera prueba, ajuste de hiperparámetros y umbral) | mar – abr 2026 | 275.906 | 180 |
| Prueba (evaluación final, una sola vez) | may – jun 2026 | 278.924 | 212 |

La tasa de fraude varía entre meses (0,05 % – 0,10 %) porque los fraudes llegan en casos de varias transferencias.

## 9. Limitaciones y sesgos conocidos

- **Es sintético**: las métricas miden cuán bien el modelo aprende los patrones que *nosotras* definimos.
- Las proporciones de bancos y ciudades son aproximadas; los nombres de entidades son solo etiquetas. El banco **no**
  es una variable del modelo, para no introducir sesgos contra una entidad.
- La cuenta mula se modela desde el lado del emisor (el banco ve salir el dinero). Una mula que **recibe** de muchas
  víctimas no se puede ver con las features de una sola transferencia.
- La antigüedad de la cuenta origen se acota en 30 años, lo que deja un pequeño pico en ese valor (0,2 % de las transferencias).
- El fraude real evoluciona; el dataset refleja una foto fija.

## 10. Regenerar y archivos

```bash
python generar_datos.py      # unos minutos -> data/transacciones_spi.csv.gz, muestra_transacciones.csv, demo/flujo_demo.csv
```

| Archivo | Finalidad |
|---|---|
| `data/transacciones_spi.csv.gz` | dataset completo para el EDA y el entrenamiento |
| `data/muestra_transacciones.csv` | 5.000 filas al azar, mismo esquema, para Excel |
| `data/demo/flujo_demo.csv` | simulador de la demo: todos los fraudes del período de prueba (may – jun 2026) + 2.500 legítimas del mismo período |
