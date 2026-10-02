# Diccionario de datos, especificación y justificación de campos

## 1. Propósito del documento

Este documento define el diccionario de datos del generador sintético de transferencias SPI y explica la especificación funcional de cada campo. También documenta la justificación analítica de las variables para un caso de detección de fraude en transferencias digitales.

El diseño combina atributos de identificación transaccional, contexto temporal, comportamiento monetario, dispositivo, red y geolocalización. Esta combinación sigue una lógica de monitoreo basada en comportamiento: evaluar la operación actual frente al perfil esperado de una cuenta y añadir señales de identidad/contexto digital, tales como dispositivo, IP y ubicación. La orientación es consistente con guías de monitoreo transaccional que consideran valor, naturaleza y origen/destino de la operación, y con enfoques de perfilado que usan dispositivo, dirección IP, geolocalización y patrones de uso para detectar anomalías.

## 2. Alcance y convenciones

### 2.1 Granularidad

Cada fila representa una transferencia individual iniciada por una cuenta emisora en el período de simulación. No existe una tabla separada de usuarios o cuentas en los archivos de salida: los atributos del usuario utilizados durante la generación se reflejan indirectamente mediante `id_cuenta_emisor`, `segmento_generador`, el dispositivo y las variables derivadas.


### 2.2 Convenciones técnicas

| Convención | Especificación |
|---|---|
| Codificación de salida | UTF-8 mediante `pandas.to_csv` |
| Formato temporal | Serialización CSV de `datetime`; se recomienda interpretar como `datetime` sin zona horaria |
| Coordenadas | WGS 84, latitud/longitud decimal en grados |
| Campos binarios | `0` = no / normal; `1` = sí / condición presente |
| Etiqueta objetivo | `es_fraude` |
| Datos personales | No se generan datos personales reales; IDs, IPs, cuentas y ubicaciones son sintéticos |

### 2.3 Clasificación de uso

Para evitar fuga de información, los campos se clasifican en cuatro grupos:

| Clasificación | Uso recomendado |
|---|---|
| Operativo | Identificación, trazabilidad, búsqueda o unión de registros; normalmente no como predictor directo. |
| Predictor potencial | Puede utilizarse como entrada de reglas o modelos, sujeto a disponibilidad en tiempo real y gobierno de datos. |
| Etiqueta/auditoría | Debe excluirse del entrenamiento predictivo; sirve para supervisión, evaluación y explicación de la simulación. |
| Feature derivada | Variable calculada a partir de datos transaccionales y perfiles; apta para modelado si puede reproducirse en producción sin conocer la etiqueta. |

## 3. Diseño de señales

La selección de campos responde a cuatro dimensiones de riesgo:

| Dimensión | Campos representativos | Razonamiento |
|---|---|---|
| Monetaria | `monto_pyg`, `zscore_monto_segmento`, `monto_fuera_rango_segmento` | Un monto atípico respecto al comportamiento esperado puede incrementar el riesgo. |
| Temporal | `fecha_hora`, `hora_sin`, `hora_cos`, `hora_fuera_rango_segmento` | Los horarios inusuales son una señal contextual; no deben interpretarse de manera aislada. |
| Identidad y dispositivo | `id_dispositivo_emisor`, `cambio_de_dispositivo`, `direccion_ip_emisor` | Un dispositivo novedoso o inconsistente puede indicar compromiso de cuenta; conviene combinarlo con otras señales. |
| Geográfica y contraparte | `geo_latitud_emisor`, `geo_longitud_emisor`, `geo_fuera_zona_segmento`, receptor y entidad | Una ubicación atípica, junto con monto, tiempo, contraparte o dispositivo, aporta contexto para priorizar alertas. |

En la práctica, el perfilado conductual se usa para mantener patrones de monto, horario y ubicación, mientras que los perfiles también pueden incorporar cuenta, dispositivo y eventos no monetarios. Las guías de inclusión financiera del FATF mencionan explícitamente el monitoreo de cambios de dispositivo y ubicación, además de perfiles de comportamiento, IP y geolocalización.

## 4. Diccionario de datos: campos base

Las siguientes columnas existen en `transferencias.csv` y también se conservan en `transferencias_modelo.csv`.

| Campo | Tipo lógico | Dominio / formato | Nulo | Clasificación | Especificación y justificación |
|---|---|---|---|---|---|
| `id_transaccion` | Texto | `TX` + 6 dígitos; ej. `TX000001` | No | Operativo | Identificador único de la transferencia generada. Permite trazabilidad, auditoría, deduplicación y vinculación con alertas o decisiones. No debe usarse como predictor: es un identificador artificial y puede inducir sobreajuste por orden de generación. |
| `fecha_hora` | Fecha-hora | Fecha y hora entre el inicio y fin de los 30 días simulados | No | Predictor potencial | Marca temporal de la operación. Es la fuente para extraer hora del día, día de semana, antigüedad, velocidad y secuencias. El generador utiliza la hora para comparar cada operación con el rango activo del segmento. El perfilado de hábitos considera las horas y los días típicos de transacción.[web:9] |
| `id_cuenta_emisor` | Texto | `CTA-EMI-` + 6 dígitos | No | Operativo / clave de agregación | Identificador sintético de la cuenta que inicia la transferencia. Es esencial para construir perfiles históricos, frecuencias, montos acumulados, dispositivos conocidos y reglas de velocidad. Debe tratarse como clave, no como variable categórica cruda de un modelo, salvo una codificación agregada entrenada correctamente. |
| `id_cuenta_receptor` | Texto | `CTA-REC-` + 6 dígitos | No | Operativo / predictor potencial | Identificador de la cuenta beneficiaria. En sistemas reales permite analizar beneficiarios nuevos, recurrencia, concentración de receptores, redes y patrones de mulas. En este generador se asigna aleatoriamente; por ello, no contiene un comportamiento receptor persistente y su valor predictivo sintético es limitado. |
| `id_entidad_receptor` | Texto | `ENTIDAD_01` a `ENTIDAD_06` | No | Predictor potencial | Identifica la entidad receptora sintética. Permite segmentar flujos por institución, analizar distribución de destinos y, en implementaciones reales, asociar señales de riesgo o patrones de contrapartes. Aquí se genera aleatoriamente, por lo que no se debe inferir riesgo real por entidad. |
| `monto_pyg` | Entero | 1 a 10.000.000 | No | Predictor potencial | Importe de la transferencia en guaraníes. Es un atributo fundamental de monitoreo: el valor de una transacción permite comparar la operación actual con el perfil habitual y con límites o umbrales. El FATF señala que el monitoreo usa parámetros como el valor y la naturaleza de la transacción.[web:4] Se recomienda transformarlo para modelado, por ejemplo con `log1p`, percentiles por cuenta o z-scores históricos. |
| `metodo_iniciacion` | Categórico | `MANUAL`, `ALIAS`, `QR` | No | Operativo / trazabilidad | Canal o mecanismo de inicio de la transferencia. Se conserva para trazabilidad y análisis descriptivo. El generador no crea una feature de “método inusual” y valida su ausencia; por tanto, no se debe atribuir riesgo intrínseco a un método solo por su categoría. En producción podría utilizarse con un historial suficiente y una evaluación de sesgo. |
| `id_dispositivo_emisor` | Texto | `DISP-HAB-XXXXXX` o `DISP-XXXXXX` | No | Operativo / predictor potencial | Identificador sintético del dispositivo desde el que se origina la operación. Permite construir la noción de dispositivo conocido/nuevo. El reconocimiento de dispositivos y la detección de dispositivos sospechosos son componentes comunes de arquitecturas de fraude en tiempo real.[web:5] No se recomienda entrenar con el ID crudo; sí con features como primer uso, cantidad de cuentas por dispositivo o historial de confianza. |
| `cambio_de_dispositivo` | Entero binario | `0`, `1` | No | Predictor potencial | Vale `1` si el dispositivo emisor difiere del dispositivo habitual del usuario. Es una señal directa de desviación de identidad y comportamiento. La guía del FATF contempla el monitoreo de cambios de dispositivo y ubicación dentro del monitoreo transaccional.[web:4] Debe usarse junto con contexto de geolocalización, autenticación y comportamiento, pues los cambios legítimos existen. |
| `direccion_ip_emisor` | Texto | IPv4 sintética en prefijo `181.*.*.*` | No | Operativo / predictor potencial | Dirección IP sintética de origen. En implementaciones reales permite enriquecer con ASN, país, reputación, VPN/TOR, centro de datos y consistencia con la geolocalización. El propio FATF menciona IP y geolocalización como datos complementarios para decisiones de autorización y debida diligencia continua.[web:12] En este generador todas las IP siguen un patrón artificial; no debe usarse para extraer reputación real. |
| `geo_latitud_emisor` | Decimal | Latitud WGS 84, 6 decimales | No | Predictor potencial | Coordenada de origen sintética. Se utiliza con longitud para medir distancia a las zonas habituales del segmento. La geolocalización puede enriquecer decisiones de autorización y monitoreo continuo cuando existe base legal, consentimiento y controles adecuados.[web:12] |
| `geo_longitud_emisor` | Decimal | Longitud WGS 84, 6 decimales | No | Predictor potencial | Coordenada de origen sintética. Debe analizarse en conjunto con la latitud; por sí sola no tiene significado geográfico. En el generador, ambas coordenadas son usadas para calcular la distancia Haversine frente a las zonas habituales. |
| `es_fraude` | Entero binario | `0`, `1` | No | Etiqueta | Variable objetivo: `1` identifica una transacción intervenida por uno de los escenarios de fraude y `0` una transacción no intervenida. Debe excluirse de las entradas de entrenamiento y utilizarse para supervisión, evaluación, matrices de confusión, precisión, recall, PR-AUC y otros indicadores. |
| `segmento_generador` | Categórico | `S1_PERSONAL_COTIDIANO`, `S2_PERSONAL_MAYOR_MOVIMIENTO`, `S3_MICROEMPRENDEDOR`, `S4_PYME_PAGADORA` | No | Auditoría / posible fuga | Perfil interno usado para construir frecuencia, distribución de montos, horarios, zonas y método de iniciación. Es útil para explicar el generador y calcular features segmentales. No debe emplearse directamente como predictor en un escenario realista si el equivalente no existe en producción; hacerlo podría introducir información privilegiada. |
| `escenario_fraude` | Categórico | `NINGUNO`, `F01_TOMA_CUENTA`, `F02_INGENIERIA_SOCIAL`, `F03_OPERACION_NOCTURNA`, `F04_ANOMALIA_COMBINADA` | No | Etiqueta / auditoría | Identifica el mecanismo de inyección aplicado a una operación etiquetada. Es útil para desagregar desempeño del modelo por tipología y verificar la coherencia de las señales. Debe excluirse de entrenamiento, ya que revela directamente la condición fraudulenta. |
| `senales_f03_inyectadas` | Texto | Vacío o combinación de `monto`, `geo`, `dispositivo`, separada por `|` | No | Etiqueta / auditoría | Registra las señales adicionales aplicadas únicamente al escenario F03. Por ejemplo, `geo|monto`. Permite validar que F03 tenga exactamente una o dos señales extra. Es información del proceso de generación y produce fuga de información si se usa como predictor. |

## 5. Diccionario de datos: features derivadas

Las siguientes columnas se agregan únicamente en `transferencias_modelo.csv`.

| Campo | Tipo lógico | Dominio / fórmula | Nulo | Clasificación | Especificación y justificación |
|---|---|---|---|---|---|
| `zscore_monto_segmento` | Decimal | `(monto_pyg - media_segmento) / desviacion_segmento` | No | Feature derivada | Mide cuántas desviaciones estándar se aleja el monto de la media del segmento generador. Permite normalizar importes entre perfiles con escalas muy distintas. Es una forma sintética de representar el principio de comparación contra una línea base de comportamiento. Para uso real, conviene calcularlo contra un baseline histórico por cliente/cuenta, idealmente con estadísticas robustas y ventanas temporales. |
| `monto_fuera_rango_segmento` | Entero binario | `1` si el monto es menor al mínimo o mayor al máximo normal del segmento; de lo contrario `0` | No | Feature derivada | Representa una regla de fuera de perfil monetario. Facilita modelos basados en reglas y aporta interpretabilidad: indica que el importe excede los límites normales definidos para ese segmento. Debe calibrarse en producción con perfiles empíricos y no con rangos fijos artificiales. |
| `hora_sin` | Decimal | `sin(2π × hora / 24)` | No | Feature derivada | Codificación cíclica de la hora. Evita que un modelo interprete 23:00 y 00:00 como horas muy distantes cuando son contiguas en el ciclo diario. Es útil en modelos numéricos que no procesan directamente la naturaleza circular del tiempo. |
| `hora_cos` | Decimal | `cos(2π × hora / 24)` | No | Feature derivada | Complementa `hora_sin` para ubicar de manera única cada hora dentro del ciclo de 24 horas. Debe utilizarse junto con `hora_sin`, no de manera aislada. |
| `hora_fuera_rango_segmento` | Entero binario | `1` si la hora está fuera del rango activo del segmento; de lo contrario `0` | No | Feature derivada | Señala una desviación temporal contra el perfil esperado. Los patrones de horario forman parte de los perfiles conductuales de fraude.[web:9] No equivale por sí sola a fraude: el generador preserva un 2 % de operaciones legítimas fuera de horario precisamente para introducir solapamiento realista. |
| `geo_fuera_zona_segmento` | Entero binario | `1` si la distancia mínima a una zona habitual supera el radio permitido del segmento; de lo contrario `0` | No | Feature derivada | Resume la desviación geográfica calculada con Haversine. La ubicación es una señal contextual que puede apoyar análisis de consistencia, anomalías y detección de desplazamientos improbables. Las arquitecturas de fraude suelen combinar geolocalización, dispositivos y patrones de comportamiento en lugar de depender de una sola señal.[web:5][web:9] |


## 8. Consideraciones de privacidad y gobierno

Aunque el dataset es sintético, el esquema contiene tipos de datos que, en un ambiente real, son sensibles o potencialmente personales: identificadores de cuenta, dispositivo, dirección IP y coordenadas de ubicación.

Para una implementación real se recomienda:

- Aplicar minimización de datos: recolectar solo lo necesario para una finalidad legítima de prevención de fraude.
- Pseudonimizar identificadores de cuenta, dispositivo e IP antes de usos analíticos que no requieran el valor original.
- Definir retención, control de acceso, auditoría de consultas y separación de entornos.
- Evaluar la base legal, transparencia y consentimiento aplicables para datos de ubicación.
- Validar calidad, precisión y resistencia a manipulación de señales como IP o geolocalización.



## 9. Especificaciones

- Los datos serán sintéticos. La importancia que el modelo asigne a una variable dependerá de los supuestos del generador y no constituirá evidencia sobre fraude real.
- No se encontró un manual técnico público del SPI con la lista exacta de campos del mensaje. La correspondencia con los campos ISO 20022 es una **inferencia** a partir del estándar.
- Los campos internos del banco (dispositivo, IP, coordenadas) son supuestos declarados.



## 11. Fuentes

| Ref. | Fuente | Se usó para |
|---|---|---|
| [1] | Ferrere, "El BCP potencia los pagos instantáneos con la actualización del SIPAP" (27/03/2026). https://www.ferrere.com/es/novedades/el-bcp-potencia-los-pagos-instantaneos-con-la-actualizacion-del-sipap/ | ISO 20022, tope de Gs. 10.000.000, QR Hub |
| [2] | BCP, "BCP actualiza el Reglamento del SIPAP y eleva el límite de las transferencias instantáneas a ₲ 10 millones". https://www.bcp.gov.py/web/institucional/w/bcp-actualiza-el-reglamento-del-sipap-y-eleva-el-limite-de-las-transferencias-instantaneas-a-g-10-millones | Tope, operación 24/7 |
| [3] | BCP, Reglamento General de los Sistemas de Pagos del Paraguay (Resolución N° 2, Acta N° 12, 12/03/2026). https://www.bcp.gov.py/documents/d/institucional/resolucion-2-acta-12-pdf | QR Hub como módulo integrado al SPI |
| [4] | BCP, "Sistemas de Pago y Tesorería" (preguntas frecuentes). https://www.bcp.gov.py/sistemas-de-pago-y-tesoreria | Alias, modalidades de iniciación, QR fuera del SPI, participantes |
| [5] | BCP, Circular SGGOF N° 008/2024 y Guía de Implementación QR Estándar (PY-QR) v2.3. https://www.bcp.gov.py/documents/20120/42554/Circular+SGGOF+008-2024+&+Gu%C3%ADa+de+Implementaci%C3%B3n+PY-QR.pdf/cf4bb4ad-92e2-1b2d-5d4f-d6b66150efa2?t=1739374690239 | Moneda, formato del monto, campos del QR |
| [6] | Perspectivas, "Desde mayo se podrá 'sipear' por QR y, al inicio del 2027, vía NFC" (abril 2026). https://perspectivas.com.py/noticias/transferencias-desde-mayo-se-podra-sipear-por-qr-y-al-inicio-del-2027-via-nfc-por-aproximacion | Marca SIP y modalidades de iniciación |
| [7] | La Nación, "Bancos habilitan QR interoperable para transferencias de dinero" (30/07/2026). https://www.lanacion.com.py/negocios/2026/07/30/bancos-habilitan-qr-interoperable-para-transferencias-de-dinero/ | QR generado por clientes |
| [8] | La Nación, "Siete claves para entender la expansión de los pagos a través del QR Hub del BCP" (31/08/2026). https://www.lanacion.com.py/negocios/2026/08/31/siete-claves-para-entender-la-expansion-de-los-pagos-a-traves-del-qr-hub-del-bcp/ | Pago QR como transferencia directa |
| [9] | La Nación, "QR Hub entra en fase final de pruebas..." (22/06/2026). https://www.lanacion.com.py/negocios/2026/06/22/qr-hub-entra-en-fase-final-de-pruebas-y-el-bcp-acelera-la-modernizacion-de-los-pagos-digitales/ | Cronología del QR Hub |
| [10] | ABC Color, "BCP rebautiza SIPAP, que ahora se llama SIP" (27/04/2026). https://www.abc.com.py/negocios/2026/04/27/bcp-rebautiza-sipap-que-ahora-se-llama-sip-en-que-afecta-a-los-usuarios/ | Cambio de nombre |
| [11] | pacs008.com, "Mensajes pacs explicados" (referencia técnica ISO 20022). https://pacs008.com/es/pacs-explained/ | Estructura del mensaje de transferencia |
