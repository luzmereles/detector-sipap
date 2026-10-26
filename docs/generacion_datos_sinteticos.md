# Documentación del generador de datos sintéticos de fraude en transferencias SPI

## 1. Descripción general

Este documento describe el generador de datos sintéticos para estudiar y entrenar modelos de detección de posibles fraudes en transferencias instantáneas SPI, dentro del contexto SIPAP/QR. El generador produce transacciones normales y transacciones etiquetadas como fraudulentas, construye variables temporales y de comportamiento, mezcla los registros, ordena los datos por fecha y crea conjuntos de entrenamiento, validación y prueba.

**Importante:** los registros son sintéticos. Representan reglas y distribuciones definidas en el código; no son operaciones bancarias reales ni constituyen evidencia empírica de cómo se comportan los clientes o los fraudes reales. Los parámetros regulatorios comentados en el código deben contrastarse con documentación oficial vigente antes de utilizarlos en un informe formal.

## 2. Alcance y supuestos

- **Ámbito:** transferencias SPI del lado emisor.
- **Fecha inicial simulada:** 1 de enero de 2026.
- **Duración configurada:** 90 días.
- **Cantidad objetivo:** 1.000.000 de transacciones.
- **Proporción objetivo de fraude:** 0,1 % (1.000 registros fraudulentos y 999.000 normales).
- **Importe mínimo configurado:** ₲ 1.000.
- **Límite por transacción configurado:** ₲ 10.000.000.
- **Semilla aleatoria:** `42`, para favorecer la reproducibilidad con las mismas versiones y condiciones de ejecución.
- **Ruido en indicadores binarios de fraude:** 8 %; cada indicador binario al que se aplica esta función puede invertirse aleatoriamente.
- **Salidas previstas:** `data/dataset_completo.csv`, `data/train.csv`, `data/valid.csv` y `data/test.csv`.

El límite de ₲ 10.000.000 aparece como supuesto/configuración del script con una referencia a BCP, marzo de 2026. La implementación no consulta una fuente regulatoria en tiempo real ni valida automáticamente esa referencia.

## 3. Flujo de generación

1. **Configurar parámetros globales:** cantidad de filas, proporción de fraude, límite de importe, duración y semilla.
2. **Generar la clase normal:** se generan fechas, importes y variables de comportamiento con distribuciones probabilísticas.
3. **Generar la clase fraudulenta:** se distribuyen los casos a lo largo de los 90 días y se asignan a uno de cuatro escenarios.
4. **Aplicar ruido:** se invierten con una probabilidad del 8 % algunos indicadores binarios de los registros fraudulentos.
5. **Combinar y ordenar:** se concatenan las clases y se ordenan por `timestamp`.
6. **Separar los conjuntos:** se usa una división cronológica 60/20/20.
7. **Comprobar y guardar:** se imprimen controles de distribución, tipos, importes y escenarios; finalmente se escriben los CSV.

### 3.1 Generación de importes

La función `generar_monto()` usa una distribución lognormal (`mean=12.5`, `sigma=1.2`). Para el 30 % de los casos, el importe se redondea a la unidad de mil; para el resto se convierte a entero sin ese redondeo. Después, el importe se limita al intervalo configurado de ₲ 1.000 a ₲ 10.000.000.

En los escenarios de fraude se utilizan rangos distintos según el escenario. Los importes finales se convierten a enteros y se recortan al mínimo y máximo configurados.

### 3.2 Generación de fechas y horas

Las fechas normales se generan dentro de los 90 días contados desde el 1 de enero de 2026, con hora aproximada a partir de una distribución normal centrada en las 14:00 y desviación estándar de 4 horas; la hora se limita al rango de 0 a 23. Los minutos y segundos son aleatorios. Los registros normales se ordenan por fecha antes de combinarse con los fraudes.

Los fraudes se distribuyen aproximadamente de forma uniforme entre los días de la simulación y sus horas se derivan de una selección entre 02:00, 03:00, 04:00, 10:00, 14:00, 18:00 y 22:00, con una variación de hasta una hora.

### 3.3 Escenarios fraudulentos

| Código | Escenario | Comportamiento simulado principal |
|---|---|---|
| `F1_toma_cuenta` | Toma de cuenta | Dispositivo nuevo y ubicación inusual inicialmente activados; destinatario nuevo; importe elevado respecto al promedio histórico. |
| `F2_rafaga_salidas` | Ráfaga de salidas | Muchas transferencias en ventanas cortas, acumulados altos y varios beneficiarios. |
| `F3_engano` | Engaño | Transferencia con importe elevado respecto al promedio y destinatario nuevo; dispositivo y ubicación no necesariamente inusuales. |
| `F4_pruebas_pequenas` | Pruebas pequeñas | Importes relativamente pequeños, varias operaciones y posible destinatario nuevo; representa pruebas de transferencia. |

La asignación de escenarios se realiza con estas probabilidades configuradas: F1 30 %, F2 30 %, F3 25 % y F4 15 %. Son proporciones de diseño, no tasas observadas en el mundo real.

## 4. Diccionario de datos

El dataset completo contiene las siguientes columnas. Los indicadores binarios se codifican como `0` (no) y `1` (sí), salvo `es_fraude`, cuya semántica se especifica por separado.

| Variable | Tipo esperado | Descripción | Interpretación / notas |
|---|---|---|---|
| `timestamp` | Fecha-hora | Fecha y hora simuladas de la transacción. | Se conserva en `dataset_completo.csv`. **No se incluye en `train.csv`, `valid.csv` ni `test.csv`**, porque el código elimina esta columna antes de separar los conjuntos. |
| `monto_pyg` | Entero | Importe de la transferencia en guaraníes paraguayos (PYG). | Configurado entre ₲ 1.000 y ₲ 10.000.000. |
| `hora` | Entero | Hora del día en que ocurre la transacción. | Valores de 0 a 23. |
| `es_fin_de_semana` | Entero binario | Indica si la fecha cae sábado o domingo. | `1` = fin de semana; `0` = día laborable. |
| `es_fin_de_mes` | Entero binario | Indica si el día del mes es 25 o posterior. | Es una definición operacional del generador, no una regla universal de fin de mes. |
| `es_horario_nocturno` | Entero binario | Indica si la hora es anterior a las 06:00 o igual/posterior a las 22:00. | `1` = horario nocturno según esta definición. |
| `hora_atipica` | Entero binario | Indicador sintético de que la hora es atípica. | En normales se genera con probabilidad del 4 %; en fraudes depende del escenario. No se calcula comparando con el historial individual real. |
| `dispositivo_nuevo` | Entero binario | Indica si se detecta un dispositivo nuevo. | En normales se genera con probabilidad del 5 %; en fraude se define por escenario y después puede invertirse por ruido. |
| `ubicacion_inusual` | Entero binario | Indica una ubicación inusual. | En normales se genera con probabilidad del 3 %; en fraude depende del escenario y puede invertirse por ruido. No hay coordenadas ni ubicación geográfica concreta. |
| `antiguedad_cuenta_dias` | Entero | Antigüedad simulada de la cuenta, en días. | En normales: entero aleatorio desde 30 hasta 3.649. En fraudes: depende del escenario o del valor inicial asignado. |
| `tx_count_5min` | Entero | Conteo sintético de transacciones en una ventana de cinco minutos. | En normales usa Poisson con media 0,3; los escenarios fraudulentos pueden asignar valores mayores. |
| `tx_count_1h` | Entero | Conteo sintético de transacciones en una hora. | En normales usa Poisson con media 1,2; en fraude se define según el escenario. |
| `tx_count_24h` | Entero | Conteo sintético de transacciones en 24 horas. | En normales usa Poisson con media 8; en fraude se define según el escenario o el valor inicial. |
| `amount_sum_1h` | Entero | Importe acumulado sintético en una hora, en PYG. | Se estima a partir del importe de la operación y factores aleatorios en normales; en fraude se deriva del escenario. Puede estar limitado a múltiplos del límite SPI. |
| `amount_sum_24h` | Entero | Importe acumulado sintético en 24 horas, en PYG. | Se deriva de `amount_sum_1h` en normales y de los parámetros del escenario en fraudes. Puede estar limitado a múltiplos del límite SPI. |
| `monto_promedio_usuario_30d` | Entero | Promedio sintético de importes del usuario durante 30 días, en PYG. | Es una característica simulada a partir del importe de la operación o de su ratio; no se calcula desde un historial real de transacciones. |
| `ratio_monto_vs_promedio` | Numérico decimal | Cociente entre `monto_pyg` y `monto_promedio_usuario_30d`. | Un valor 1 significa que el importe coincide con el promedio simulado; mayor que 1 indica que lo supera. En fraudes se construye usando un ratio objetivo por escenario, sujeto a conversiones a enteros. |
| `destinatario_nuevo` | Entero binario | Indica si el beneficiario es nuevo para el emisor. | En normales se genera con probabilidad del 10 %; en fraude depende del escenario y puede invertirse por ruido. |
| `unique_beneficiaries_24h` | Entero | Cantidad sintética de beneficiarios únicos en 24 horas. | En normales usa Poisson con media 2,5; en fraude se define según el escenario. |
| `es_fraude` | Entero binario | Etiqueta objetivo de clasificación. | `0` = transacción generada como normal; `1` = transacción generada como fraude. Es la variable objetivo habitual para el entrenamiento supervisado. |
| `escenario_fraude` | Cadena categórica | Clase de escenario asignada al registro. | Para normales vale `normal`; para fraudes toma uno de los cuatro códigos F1–F4. |


## 5. Archivos de salida y partición

| Archivo | Contenido | Columnas |
|---|---|---|
| `data/dataset_completo.csv` | Todas las transacciones combinadas y ordenadas cronológicamente. | Incluye `timestamp`. |
| `data/train.csv` | Primer 60 % de las filas ordenadas, para entrenamiento. | No incluye `timestamp`. |
| `data/valid.csv` | Siguiente 20 %, para validación y selección de modelos. | No incluye `timestamp`. |
| `data/test.csv` | Último 20 %, para evaluación final. | No incluye `timestamp`. |

El código calcula los cortes como el 60 % y el 80 % del total de filas. Debido a que la división se realiza después de ordenar por `timestamp`, es cronológica y no aleatoria. La distribución exacta de fraudes en cada partición depende de las fechas generadas; el script comprueba que cada partición contenga al menos un fraude.

**Nota importante sobre el tiempo:** aunque el orden de las filas de entrenamiento, validación y prueba conserva indirectamente la secuencia temporal, al eliminar `timestamp` no se puede reconstruir la fecha exacta de cada fila a partir de esos archivos. Si el modelo o el análisis necesita variables de calendario, conviene conservar `timestamp` en las particiones o derivar sus características antes de eliminarlo.

## 6. Controles de calidad implementados

Al ejecutarse, el generador imprime controles que incluyen:

- Cantidad de filas y número/proporción de fraudes en entrenamiento, validación y prueba.
- Comprobación de que ninguna partición esté vacía de fraudes.
- Tipos de datos de algunas columnas.
- Presencia de microsegundos en `timestamp`.
- Comprobación de que `monto_pyg` contenga importes enteros.
- Mínimo, máximo y promedio de los importes.
- Ejemplos de importes redondos y no redondos.
- Ratio promedio global y por clase.
- Distribución de los escenarios fraudulentos.

Estos controles son comprobaciones básicas, no una auditoría completa de calidad. No verifican todas las columnas, todos los valores ausentes, duplicados, consistencia entre variables ni todas las relaciones temporales.


## 7. Recomendaciones antes de entrenar un modelo

- Revisar valores ausentes, duplicados, tipos, rangos y consistencia entre columnas.
- Medir la proporción de fraude en cada partición, no solo en el conjunto completo.
- Evaluar métricas apropiadas para clases muy desbalanceadas: precision, recall, F1, PR-AUC y matriz de confusión. No depender únicamente de accuracy.
- Evitar incluir `escenario_fraude` como variable predictora si se usa como etiqueta auxiliar que revela cómo se construyó el fraude. Mantenerla para análisis y segmentación, según el objetivo del experimento.
- Asegurarse de que `es_fraude` no se incluya entre las variables de entrada.
- Si se requiere evaluación temporal, conservar la fecha o derivar variables temporales antes de retirarla.
- Comparar los resultados con reglas base simples y documentar las limitaciones de generalización.
- No describir el dataset como datos bancarios reales ni presentar sus porcentajes como tasas observadas.

## 8. Resumen de parámetros configurables

| Parámetro | Valor actual | Función |
|---|---:|---|
| `SEED` | `42` | Semilla del generador aleatorio. |
| `N_TOTAL` | `1_000_000` | Cantidad total objetivo de filas. |
| `FRAUD_RATE` | `0.001` | Proporción objetivo de fraudes: 0,1 %. |
| `RUIDO_FRAUDE` | `0.08` | Probabilidad de invertir cada indicador binario al que se aplica ruido. |
| `LIMITE_SPI` | `10_000_000` | Importe máximo configurado por transacción, en PYG. |
| `MONTO_MINIMO` | `1_000` | Importe mínimo, en PYG. |
| `DIAS_SIMULACION` | `90` | Duración del período simulado. |
| `fecha_inicio` | `2026-01-01` | Inicio del período simulado. |

## 9. Dependencias y ejecución

El script utiliza Python y las bibliotecas `numpy` y `pandas`, además de módulos estándar (`datetime`, `timedelta`). Debe existir la carpeta `data/` antes de guardar los archivos, ya que el código mostrado no la crea automáticamente.

Desde el directorio del proyecto, instalar las dependencias si todavía no están disponibles:

```bash
pip install numpy pandas
```
