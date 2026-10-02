# Documentación de generación de datos sintéticos SPI

## 1. Propósito

Este documento describe el proceso de generación de datos sintéticos de transferencias SPI para pruebas, análisis exploratorio y entrenamiento o evaluación de modelos de detección de fraude.

El generador produce un conjunto de operaciones con comportamiento transaccional coherente por perfil de usuario. Incluye transacciones legítimas con variabilidad controlada y una cantidad exacta de operaciones fraudulentas inyectadas mediante escenarios definidos.

El objetivo no es reproducir transacciones reales ni identificar personas. Los datos son sintéticos y utilizan identificadores, cuentas, direcciones IP, dispositivos y coordenadas generados artificialmente.

## 2. Resultados generados

La ejecución genera dos archivos CSV dentro del directorio `datos_generados`:

| Archivo | Finalidad |
|---|---|
| `transferencias.csv` | Dataset transaccional crudo, con los atributos operativos y las etiquetas de fraude. |
| `transferencias_modelo.csv` | Dataset para análisis/modelado; contiene las columnas del dataset crudo más variables derivadas de monto, horario y geolocalización. |

Ambos archivos conservan las etiquetas `es_fraude` y `escenario_fraude`. Esto permite usar el conjunto en un contexto supervisado y también auditar cómo se generó cada caso fraudulento.

## 3. Configuración base

La configuración central controla el tamaño, período temporal y límites monetarios de la simulación.

| Parámetro | Valor | Descripción |
|---|---:|---|
| `SEMILLA` | 42 | Semilla para `random` y `numpy.random`, para hacer la generación reproducible. |
| `cantidad_usuarios` | 230 | Cantidad de cuentas emisoras sintéticas. |
| `cantidad_transferencias` | 5.000 | Cantidad total exacta de operaciones generadas. |
| `cantidad_fraudes` | 25 | Cantidad exacta de transacciones marcadas como fraude. |
| `fecha_inicio` | 2026-01-01 | Inicio del período simulado. |
| `dias_simulacion` | 30 | Duración del período de generación. |
| `monto_minimo_pyg` | 1 PYG | Monto mínimo admitido. |
| `monto_maximo_spi_pyg` | 10.000.000 PYG | Límite máximo de monto permitido. |

El rango temporal se construye seleccionando segundos aleatorios desde la fecha inicial hasta el último segundo del día 30. Posteriormente, la hora, minuto y segundo pueden ajustarse para respetar el patrón normal del segmento o para inyectar señales de fraude.

## 4. Población sintética

Cada usuario representa una cuenta emisora con:

- `id_cuenta_emisor`: identificador sintético en formato `CTA-EMI-XXXXXX`.
- `segmento_generador`: perfil de comportamiento asignado aleatoriamente según pesos.
- `frecuencia_mensual`: cantidad de transferencias que emitirá durante la simulación.
- `dispositivo_habitual`: identificador persistente en formato `DISP-HAB-XXXXXX`.

La frecuencia inicial de cada usuario se toma dentro del rango definido para su segmento. Luego, se ajusta de forma iterativa, sin salir de los mínimos y máximos del perfil, hasta que la suma de frecuencias sea exactamente 5.000.

### 4.1 Segmentos

| Segmento | Peso de usuarios | Frecuencia mensual | Monto medio | Rango normal de monto | Horario activo | Radio geográfico normal |
|---|---:|---:|---:|---:|---|---:|
| `S1_PERSONAL_COTIDIANO` | 55 % | 3–14 | 180.000 PYG | 10.000–700.000 PYG | 07:00–22:00 | 25 km |
| `S2_PERSONAL_MAYOR_MOVIMIENTO` | 20 % | 8–28 | 900.000 PYG | 50.000–4.500.000 PYG | 06:00–23:00 | 80 km |
| `S3_MICROEMPRENDEDOR` | 18 % | 18–65 | 1.300.000 PYG | 50.000–6.000.000 PYG | 07:00–21:00 | 60 km |
| `S4_PYME_PAGADORA` | 7 % | 45–130 | 3.800.000 PYG | 150.000–9.500.000 PYG | 08:00–18:00 | 40 km |

Los montos tienen además una desviación estándar por segmento, utilizada para generar operaciones a partir de una distribución normal y para calcular el z-score monetario en el dataset de modelado.

### 4.2 Métodos de iniciación

El campo `metodo_iniciacion` toma los valores `MANUAL`, `ALIAS` o `QR`, con pesos específicos para cada segmento.

Este atributo se conserva para trazabilidad operativa, pero no se genera ninguna feature de anomalía basada en el método. En particular, el generador valida que no exista la columna `metodo_inusual_segmento` en el dataset de modelo.

## 5. Generación de transacciones legítimas

Inicialmente, las 5.000 transacciones se generan como operaciones normales. Cada registro incluye una cuenta receptora, entidad receptora, monto, método de iniciación, dispositivo, IP y ubicación geográfica sintéticos.

### 5.1 Monto

El monto base se genera con una distribución normal definida por la media y desviación estándar del segmento. Después se limita al rango normal mínimo y máximo del perfil.

Existe una probabilidad de monto alto legítimo por segmento:

| Segmento | Probabilidad de monto alto legítimo | Factor aplicado |
|---|---:|---|
| `S1_PERSONAL_COTIDIANO` | 1,5 % | 1,5–3,5 |
| `S2_PERSONAL_MAYOR_MOVIMIENTO` | 5,0 % | 1,5–3,0 |
| `S3_MICROEMPRENDEDOR` | 8,0 % | 1,3–2,5 |
| `S4_PYME_PAGADORA` | 10,0 % | 1,1–1,5 |

El resultado siempre respeta el mínimo global de 1 PYG y el máximo normal del segmento en la generación legítima.

### 5.2 Horario

La hora se genera normalmente dentro del intervalo activo del segmento. Sin embargo, un 2 % de las transacciones legítimas puede ocurrir fuera del horario habitual. Esta variabilidad evita que una operación fuera de horario implique fraude de forma determinista.

### 5.3 Geolocalización

Cada segmento dispone de ciudades habituales y de un radio máximo considerado normal. Las coordenadas normales se generan tomando una ciudad habitual y agregando ruido gaussiano a latitud y longitud.

Un 1,5 % de las transacciones legítimas se genera fuera del perfil geográfico del segmento. Para hacerlo, el proceso elige una ciudad no habitual y verifica que la distancia mínima hasta las zonas habituales sea mayor que el radio normal del perfil.

La distancia geográfica se calcula mediante la fórmula de Haversine, utilizando un radio terrestre de 6.371 km.

### 5.4 Dispositivo

Cada usuario posee un dispositivo habitual. Las probabilidades de cambio de dispositivo legítimo son:

| Segmento | Probabilidad de cambio legítimo |
|---|---:|
| `S1_PERSONAL_COTIDIANO` | 2 % |
| `S2_PERSONAL_MAYOR_MOVIMIENTO` | 3 % |
| `S3_MICROEMPRENDEDOR` | 4 % |
| `S4_PYME_PAGADORA` | 5 % |

Si ocurre un cambio, se asigna un identificador `DISP-XXXXXX` distinto al dispositivo habitual. El indicador `cambio_de_dispositivo` se mantiene consistente con esa comparación.

## 6. Inyección de fraude

Una vez creadas todas las transacciones normales, el proceso selecciona aleatoriamente 25 índices únicos y reemplaza cada transacción seleccionada por una versión modificada según un escenario de fraude permitido para el segmento del emisor.

Los escenarios se eligen con ponderación. `F02_INGENIERIA_SOCIAL` no es aplicable al segmento `S4_PYME_PAGADORA`; en los demás casos, los escenarios son aplicables a todos los segmentos.

| Escenario | Peso | Idea principal |
|---|---:|---|
| `F01_TOMA_CUENTA` | 35 % | Compromiso de cuenta con múltiples señales fuertes. |
| `F02_INGENIERIA_SOCIAL` | 30 % | Monto anómalo manteniendo el contexto habitual de operación. |
| `F03_OPERACION_NOCTURNA` | 20 % | Actividad nocturna más una o dos señales adicionales. |
| `F04_ANOMALIA_COMBINADA` | 15 % | Monto moderadamente anómalo junto con varias anomalías contextuales. |

### 6.1 F01 — Toma de cuenta

Este escenario fuerza cuatro señales simultáneas:

- Monto fraudulento con z-score documentado entre 3,0 y 7,0.
- Monto fuera del rango normal del segmento.
- Hora fuera del rango activo del segmento.
- Geolocalización fuera de la zona habitual.
- Dispositivo distinto al habitual.

En el dataset de modelo, los registros F01 deben tener `monto_fuera_rango_segmento = 1`, `hora_fuera_rango_segmento = 1`, `geo_fuera_zona_segmento = 1` y `cambio_de_dispositivo = 1`.

### 6.2 F02 — Ingeniería social

Este escenario representa una operación cuyo principal indicador es el monto, sin alterar necesariamente el contexto conductual del usuario:

- Monto fraudulento con z-score documentado entre 2,5 y 6,0.
- Monto fuera del rango normal del segmento.
- Hora dentro del rango habitual.
- Geolocalización dentro de la zona habitual.
- Uso del dispositivo habitual.

La intención es incluir casos donde una anomalía monetaria relevante no esté acompañada de señales geográficas, horarias ni de dispositivo.

### 6.3 F03 — Operación nocturna

Este escenario tiene una regla principal obligatoria: la operación se realiza entre las 00:00 y las 05:59.

Además, se selecciona exactamente una o dos señales adicionales entre:

- `monto`: reemplaza el monto por uno con z-score entre 2,5 y 3,5, sin exigir que quede fuera del rango normal del segmento.
- `geo`: mueve la operación a una ubicación fuera de la zona habitual.
- `dispositivo`: asigna un dispositivo distinto al habitual.

Las señales seleccionadas se guardan en `senales_f03_inyectadas` como una lista separada por `|`, por ejemplo: `geo|monto`.

Si `monto` no se selecciona, el generador conserva el monto normal que tenía originalmente la transacción. Por ello, en F03 el z-score de monto no debe interpretarse como señal fraudulenta cuando `monto` no aparece en `senales_f03_inyectadas`.

### 6.4 F04 — Anomalía combinada

Este escenario aplica:

- Un monto con z-score entre 1,5 y 3,0.
- Dos o tres señales seleccionadas entre horario fuera de rango, geolocalización fuera de zona y cambio de dispositivo.

A diferencia de F01 y F02, el monto no tiene obligación de superar el máximo normal del segmento. La validación exige que al menos dos de las tres señales contextuales estén presentes.

## 7. Estructura de datos

### 7.1 Columnas base

| Columna | Descripción |
|---|---|
| `id_transaccion` | Identificador único de transacción, formato `TX000001`. |
| `fecha_hora` | Fecha y hora de la operación simulada. |
| `id_cuenta_emisor` | Cuenta sintética del emisor. |
| `id_cuenta_receptor` | Cuenta sintética del receptor. |
| `id_entidad_receptor` | Entidad receptora sintética, formato `ENTIDAD_XX`. |
| `monto_pyg` | Monto de la operación en guaraníes. |
| `metodo_iniciacion` | Método de inicio: `MANUAL`, `ALIAS` o `QR`. |
| `id_dispositivo_emisor` | Dispositivo utilizado en la operación. |
| `cambio_de_dispositivo` | Indicador binario: 1 si difiere del dispositivo habitual. |
| `direccion_ip_emisor` | Dirección IP sintética. |
| `geo_latitud_emisor` | Latitud sintética de origen. |
| `geo_longitud_emisor` | Longitud sintética de origen. |
| `es_fraude` | Etiqueta binaria: 1 para fraude y 0 para transacción legítima. |
| `segmento_generador` | Segmento utilizado para generar el comportamiento. |
| `escenario_fraude` | Escenario aplicado: `NINGUNO`, `F01`, `F02`, `F03` o `F04`. |
| `senales_f03_inyectadas` | Auditoría de señales extra de F03; vacío para otros casos. |

### 7.2 Variables derivadas del dataset de modelo

| Columna | Descripción |
|---|---|
| `zscore_monto_segmento` | Distancia del monto respecto de la media segmental, expresada en desviaciones estándar. |
| `monto_fuera_rango_segmento` | Indicador binario de monto menor al mínimo o mayor al máximo normal del segmento. |
| `hora_sin` | Transformación senoidal de la hora del día, útil para representar la naturaleza cíclica del tiempo. |
| `hora_cos` | Transformación cosenoidal de la hora del día, complementaria a `hora_sin`. |
| `hora_fuera_rango_segmento` | Indicador binario de operación fuera de las horas activas del segmento. |
| `geo_fuera_zona_segmento` | Indicador binario de ubicación a más del radio normal del segmento. |

Las transformaciones temporales se calculan como:

```text
hora_sin = sin(2π × hora / 24)
hora_cos = cos(2π × hora / 24)
```

## 8. Validaciones implementadas

Antes de exportar los archivos, el generador ejecuta validaciones mediante `assert`. Estas validaciones detienen el proceso si se detecta una inconsistencia.

### 8.1 Validaciones generales

- Deben existir exactamente 230 usuarios.
- Deben existir exactamente 5.000 transacciones.
- Deben existir exactamente 25 fraudes.
- La suma de frecuencias individuales debe ser 5.000.
- Todos los montos deben estar entre 1 y 10.000.000 PYG.

### 8.2 Validación de dispositivo

Para cada transacción se verifica:

```text
cambio_de_dispositivo == int(id_dispositivo_emisor != dispositivo_habitual)
```

Esto garantiza que el indicador binario no contradiga el identificador de dispositivo almacenado.

### 8.3 Validación por escenario

- F01: debe presentar monto fuera de rango, horario fuera de rango, geo fuera de zona y cambio de dispositivo.
- F02: debe presentar monto fuera de rango, pero mantener horario, geolocalización y dispositivo dentro del perfil habitual.
- F03: debe ser nocturno, contener una o dos señales adicionales y mantener coherencia entre las señales declaradas y las variables derivadas.
- F04: debe tener z-score monetario entre 1,5 y 3,0 y al menos dos anomalías entre horario, geolocalización y dispositivo.

## 9. Flujo de ejecución

El proceso principal sigue esta secuencia:

1. Inicializa las semillas aleatorias.
2. Crea 230 usuarios y asigna segmentos, frecuencias y dispositivos habituales.
3. Ajusta las frecuencias para obtener exactamente 5.000 transferencias.
4. Genera todas las transacciones como operaciones legítimas.
5. Selecciona 25 transacciones únicas al azar.
6. Inyecta un escenario de fraude válido según el segmento de cada transacción seleccionada.
7. Ordena las operaciones por `fecha_hora`.
8. Construye las variables derivadas para el dataset de modelado.
9. Ejecuta las validaciones de consistencia.
10. Exporta los dos archivos CSV al directorio `datos_generados`.
11. Imprime un resumen con usuarios, transferencias, fraudes y distribución de escenarios.

## 10. Ejecución

El script se ejecuta directamente desde un entorno Python que tenga instaladas las dependencias requeridas:

```bash
python generador_datos_spi.py
```

Dependencias:

```bash
pip install numpy pandas
```

Al finalizar correctamente, la consola mostrará un mensaje de generación validada, las cantidades resultantes y el conteo de fraudes por escenario.

## 11. Consideraciones para modelado

- El dataset está etiquetado; `es_fraude` es la variable objetivo para un modelo supervisado.
- `escenario_fraude` y `senales_f03_inyectadas` son campos de auditoría y explicabilidad de la simulación. Deben excluirse de los predictores para evitar fuga de información.
- `segmento_generador` también representa conocimiento interno del generador. Si el caso de uso pretende simular una producción realista, conviene no utilizarlo directamente como predictor, salvo que exista una segmentación equivalente disponible en producción.
- `metodo_iniciacion` se conserva para trazabilidad. El generador no presupone que un método sea inusual o fraudulento.
- Las variables `hora_sin` y `hora_cos` permiten que algoritmos numéricos modelen continuidad entre horas cercanas al cambio de día, como 23:00 y 00:00.
- La presencia de anomalías legítimas de horario, geografía y dispositivo ayuda a evitar una separación completamente determinista entre fraude y no fraude.

## 12. Limitaciones

Este generador está diseñado para coherencia controlada y pruebas de pipelines, no para reproducir toda la complejidad de un sistema real de pagos.

Entre sus simplificaciones se encuentran:

- Las cuentas receptoras y entidades se generan de forma aleatoria, sin perfiles propios ni historial receptor.
- Las direcciones IP siguen un patrón sintético simple y no representan redes, ASN, reputación ni geolocalización IP real.
- La geolocalización se basa en centros urbanos y ruido gaussiano; no representa movilidad real ni precisión de GPS.
- Los escenarios de fraude están etiquetados explícitamente y responden a reglas conocidas, por lo que deben excluirse los campos de auditoría al entrenar modelos predictivos.

## 13. Reproducibilidad y auditoría

Con la misma versión del script, dependencias compatibles y semilla configurada en `42`, el proceso está diseñado para ser reproducible.

La trazabilidad de los fraudes se obtiene mediante:

- `es_fraude` para distinguir fraude de operación normal.
- `escenario_fraude` para identificar el tipo de inyección aplicado.
- `senales_f03_inyectadas` para revisar las señales extra seleccionadas específicamente en F03.
- Las validaciones automáticas que aseguran cantidades, límites y coherencia de cada escenario.
