# Diccionario de datos: tabla de transacciones

Este documento define y justifica la tabla de transacciones del dataset **sintético** del proyecto. Para cada campo se indica su definición, su nivel de respaldo (qué está verificado y qué es un supuesto del equipo) y el resultado del filtro de tres preguntas que se usó para decidir si el campo se incluye. Las características derivadas y el diseño del generador se documentarán por separado; aquí solo se justifica por qué cada campo existe.

---

## 1. Alcance y perspectiva

- **Datos sintéticos.** Los datos reales de transacciones SPI/QR con fraude etiquetado no son públicos. El dataset se generará con escenarios de fraude definidos por reglas de negocio probabilísticas, cuyos parámetros se declaran como supuestos ajustables (sección 6).
- **Perspectiva: motor antifraude de un banco emisor.** El sistema puntúa las transferencias iniciadas por los clientes de **un solo banco**. Por eso ve los datos de su propia app (dispositivo, IP, ubicación) y no ve el comportamiento de otros bancos. Esto es una decisión de alcance del proyecto, no una columna de la tabla.
- **Nombre del sistema.** El proyecto usa "SIPAP"; el BCP lo rebautizó **SIP** en 2026. Ambos nombres se refieren al mismo sistema.
- **Unidad de la tabla.** Una fila es una transferencia iniciada por un cliente del banco emisor y evaluada por el modelo.
- **Período simulado.** 52 semanas (15/09/2025 a 13/09/2026) con fechas **simuladas**: un año típico bajo el régimen actual del sistema, aplicado a todas las fechas.

## 2. Leyenda

**Nivel de respaldo**

| Nivel | Significado |
|---|---|
| **Verificado** | Respaldado por una fuente pública oficial o de prensa citada en la sección 8. |
| **Inferido** | Se deriva de un estándar público (ISO 20022, PY-QR), pero no se confirmó cómo lo registra cada banco. |
| **Supuesto** | Decisión del equipo sin fuente pública. Es un parámetro declarado y ajustable. |

**Filtro de las tres preguntas** 

1. **P1 · ¿Lo conoce el banco emisor en el instante *t*?** Si no, no puede ser característica.
2. **P2 · ¿Se puede justificar que existe?** Con fuente pública o con un supuesto declarado.
3. **P3 · ¿Se usará en el generador o como base de características?** Si no, sobra.

## 3. Resumen de campos

| # | Campo | Tipo | Nulo | Ejemplo | Rol |
|---|---|---|---|---|---|
| 1 | `id_transaccion` | VARCHAR | No | `TX000001` | Clave |
| 2 | `timestamp` | DATETIME | No | `2026-09-01 14:32:18` | Base de características |
| 3 | `id_cuenta_emisor` | VARCHAR | No | `CTA0001` | Clave de perfil |
| 4 | `id_cuenta_receptor` | VARCHAR | No | `CTA0045` | Base de características |
| 5 | `id_entidad_receptor` | VARCHAR | No | `ENT003` | Característica |
| 6 | `monto` | INTEGER | No | `185000` | Característica |
| 7 | `metodo_iniciacion` | VARCHAR | No | `MANUAL` | Característica |
| 8 | `id_dispositivo_emisor` | VARCHAR | No | `DEV00125` | Base de características |
| 9 | `direccion_ip_emisor` | VARCHAR | No | `10.24.7.33` | Opcional |
| 10 | `geo_latitud_emisor` | DECIMAL(10,6) | Sí | `-25.282197` | Base de características |
| 11 | `geo_longitud_emisor` | DECIMAL(10,6) | Sí | `-57.635098` | Base de características |
| 12 | `es_fraude` | TINYINT (0/1) | No | `0` | Etiqueta (variable objetivo) |

## 4. Detalle por campo

### 4.1 `id_transaccion`
- **Descripción:** identificador único de la transferencia.
- **Formato:** `TX` + número correlativo de 6 dígitos (formato sintético).
- **Respaldo: Inferido.** El SPI adopta mensajería ISO 20022, cuyos mensajes de pago llevan identificadores de mensaje, de instrucción y extremo a extremo. El formato `TX000001` es propio del dataset.
- **Filtro:** P1 sí (se asigna al iniciar la transferencia) · P2 sí · P3 no como característica.
- **Decisión:** **Incluir como clave.** Sirve para trazabilidad y no ingresará al modelo.

### 4.2 `timestamp`
- **Descripción:** fecha y hora en que se inicia la transferencia (hora local de Paraguay). Las fechas son **simuladas**.
- **Respaldo: Inferido + Verificado.** La fecha y hora de creación es un elemento estándar del mensaje ISO 20022. El SPI opera las 24 horas, los 7 días de la semana, así que la distribución horaria del generador deberá cubrir todo el día y no solo el horario bancario.
- **Filtro:** P1 sí · P2 sí · P3 sí.
- **Justificación de inclusión:** es la base para cualquier característica temporal (hora del día, día de la semana, desvío respecto del horario habitual del cliente, ventanas de actividad reciente). La estacionalidad (fin de mes, aguinaldo) quedará como **supuesto** del equipo.

### 4.3 `id_cuenta_emisor`
- **Descripción:** identificador (seudonimizado) de la cuenta desde la cual se debita el dinero.
- **Formato:** `CTA` + número. Simplificación: una cuenta corresponde a un cliente con un perfil de comportamiento.
- **Respaldo: Inferido.** La cuenta del ordenante es un dato estándar de la transferencia.
- **Filtro:** P1 sí · P2 sí · P3 sí (como clave de agregación histórica).
- **Justificación de inclusión:** sin este identificador no se puede construir el historial ni el perfil del cliente (monto habitual, horario habitual, destinos y dispositivos conocidos), que es la base de casi todas las características del detector.

### 4.4 `id_cuenta_receptor`
- **Descripción:** identificador de la cuenta que recibe los fondos.
- **Respaldo: Inferido + Verificado (alias).** Cuando el cliente usa un alias (CI, RUC, teléfono o correo), el sistema lo resuelve a los datos completos del destinatario. Por eso la tabla guarda la cuenta ya resuelta, sin importar cómo se ingresó.
- **Filtro:** P1 sí · P2 sí · P3 sí.
- **Justificación de inclusión:** permite detectar "destino nuevo para este cliente" y el patrón de muchos clientes transfiriendo al mismo destino en pocas horas (regla de cuenta mula, limitada a lo que ve este banco).

### 4.5 `id_entidad_receptor`
- **Descripción:** identificador del banco o entidad del beneficiario.
- **Formato:** `ENT` + número (códigos sintéticos). Para mayor realismo se puede basar la lista en las entidades participantes del sistema que publica el BCP.
- **Respaldo: Inferido.** La entidad del acreedor es un dato estándar de la transferencia, y el SPI conecta bancos, financieras y otras entidades.
- **Filtro:** P1 sí · P2 sí · P3 sí.
- **Justificación de inclusión:** permite distinguir transferencias a la misma entidad de las interbancarias. La proporción de transferencias por entidad es un **supuesto** declarado.

### 4.6 `monto`
- **Descripción:** importe de la transferencia en guaraníes (PYG), sin decimales.
- **Restricciones:** entero positivo, `1 ≤ monto ≤ 10000000`. Se guarda sin separador de miles (`185000`). El punto es solo de visualización.
- **Respaldo: Verificado.**
  - El tope por operación SPI se elevó de Gs. 5.000.000 a Gs. 10.000.000 con la Resolución N° 2, Acta N° 12, del 12/03/2026. El tope de 10.000.000 se aplica a todo el período simulado, aunque en las fechas reales anteriores a marzo de 2026 el tope era de 5.000.000 (verificar la fecha exacta de entrada en vigencia).
  - La guía PY-QR indica que las operaciones nacionales se realizan en guaraníes y que el importe no lleva decimales.
- **Filtro:** P1 sí · P2 sí · P3 sí.
- **Justificación de inclusión:** el monto relativo al perfil del cliente y la cercanía al tope son señales centrales del escenario de fraccionamiento.

### 4.7 `metodo_iniciacion`
- **Descripción:** forma en que el usuario inicia la operación.
- **Valores:**
  - `MANUAL`: el usuario ingresa los datos del destino (número de cuenta o alias).
  - `QR`: el usuario escanea un código QR (QR Sip / QR Hub).
- **Respaldo: Parcialmente verificado, parcialmente supuesto.**
  - *Verificado:* el QR Hub es un módulo integrado al SPI [3]. El pago con QR se ejecuta como transferencia directa entre la cuenta del pagador y la del comercio o beneficiario. El BCP reconoce públicamente distintas modalidades de iniciación y creó la marca SIP por esa razón. Su FAQ menciona la lectura de QR como una vía para iniciar pagos. Desde julio de 2026 algunos bancos permiten a sus clientes generar su propio QR para cobrar, por lo que el beneficiario no es necesariamente un comercio.
  - *Supuesto:* que el banco guarde este dato en el registro de la transacción y lo entregue al motor antifraude. No se encontró documentación pública que lo confirme.
- **Filtro:** P1 sí (bajo el supuesto declarado) · P2 sí (supuesto declarado) · P3 sí.
- **Justificación de inclusión:** cambia la interpretación de otras variables. Los pagos QR legítimos van con frecuencia a destinos nuevos y con montos distintos a los de una transferencia manual. Sin esta variable, el modelo trataría "destino nuevo" como riesgo en todos los casos. Los parámetros de comportamiento por método son **supuestos** del equipo.
- **Decisiones de diseño:** no se distinguen subtipos (QR estático/dinámico, alias/cuenta) porque no hay evidencia pública de que se registren. Alcance: solo QR dentro del SPI; los pagos QR anteriores vía procesadoras de tarjetas quedan fuera.

### 4.8 `id_dispositivo_emisor`
- **Descripción:** identificador del dispositivo desde el cual se inicia la operación.
- **Formato:** `DEV` + número (sintético).
- **Respaldo: Supuesto.** Es un dato interno del banco emisor y no forma parte de los mensajes públicos del SPI. No se identificó una fuente pública paraguaya que confirme qué captura cada banco.
- **Filtro:** P1 sí (bajo el supuesto declarado) · P2 sí (supuesto declarado) · P3 sí.
- **Justificación de inclusión:** "dispositivo nuevo para este cliente" es la señal central del escenario de toma de cuenta. El generador deberá modelar también el ruido legítimo: clientes que cambian de celular con baja frecuencia (parámetro ajustable, sección 6).

### 4.9 `direccion_ip_emisor`
- **Descripción:** dirección IP registrada para el origen de la operación.
- **Formato:** direcciones ficticias (por ejemplo, del rango privado `10.0.0.0/8`) para no exponer IP reales. Cada cliente tendrá un conjunto de IP habituales (hogar, datos móviles).
- **Respaldo: Supuesto.** Dato interno del banco, sin fuente pública.
- **Filtro:** P1 sí (bajo el supuesto declarado) · P2 sí (supuesto declarado) · P3 sí, como base de una característica derivada; la IP cruda no ingresará al modelo.
- **Limitación:** la característica derivada ("IP no vista antes para este cliente") es **ruidosa**, porque las IP móviles cambian seguido. La ciudad de la IP no se incluye (ver sección 5).

### 4.10 `geo_latitud_emisor` / 4.11 `geo_longitud_emisor`
- **Descripción:** coordenadas capturadas por la app al iniciar la operación, si el usuario otorgó el permiso.
- **Tipo:** DECIMAL(10,6), **admite nulos**.
- **Rango esperado:** territorio paraguayo (aprox. latitud entre -27,6 y -19,3; longitud entre -62,6 y -54,3).
- **Respaldo: Supuesto.** Dato interno de la app, sin fuente pública. El porcentaje de nulos es un parámetro ajustable del generador (por ejemplo, 20-30 %).
- **Filtro:** P1 sí (bajo el supuesto declarado) · P2 sí (supuesto declarado) · P3 sí.
- **Justificación de inclusión:** permite medir la distancia respecto de la ubicación habitual del cliente y detectar operaciones desde ubicaciones improbables. Que el campo admita nulos refleja que el permiso de ubicación puede no estar otorgado; el tratamiento de esos nulos se definirá con las características derivadas.
- **Nota de privacidad:** con datos reales, la ubicación es dato personal. Aquí las coordenadas son sintéticas.

### 4.12 `es_fraude`
- **Descripción:** etiqueta binaria (1 = fraude, 0 = legítima).
- **Origen:** la asignará el generador según el escenario que produjo la transacción. No saldrá de un umbral sobre las demás columnas.
- **Respaldo: Supuesto.** Los escenarios y sus probabilidades son reglas de negocio del equipo. La tasa objetivo (< 0,1 %) proviene del enunciado del proyecto.
- **Filtro:** no aplica (es la variable objetivo; nunca es característica).
- **Justificación de inclusión:** sin etiqueta no hay aprendizaje supervisado ni evaluación posible. En un despliegue real este campo no existiría: es justamente lo que el modelo predice.

## 5. Campos considerados y descartados

Los siguientes campos se evaluaron con el filtro de las tres preguntas y se descartaron. Se documentan para dejar constancia de la decisión.

| Campo descartado | Motivo |
|---|---|
| Ciudad/país de la IP | La geolocalización por IP es imprecisa y ruidosa; se usa la ubicación de la app (4.10-4.11) cuando esté disponible. |
| Subtipo de QR (estático/dinámico) | Sin evidencia pública de que los bancos lo registren; falla P1/P2. |
| Tipo de alias (CI/RUC/teléfono/correo) | El alias se resuelve antes de la evaluación; el subtipo no aporta a las reglas del generador; falla P3. |
| Tipo de cuenta (ahorro/corriente) | Sin fuente pública sobre su disponibilidad en el mensaje (falla P2) y no se usó en reglas (falla P3). |
| Canal NFC / otras modalidades | Anunciado para inicios de 2027, fuera del período simulado. |
| Datos del beneficiario (nombre, etc.) | Dato personal no necesario; el modelo trabaja con identificadores seudonimizados. |
| Comportamiento de otros bancos | Contradice la perspectiva de banco emisor único; el motor no lo observa en *t*; falla P1. |


## 6. Especificaciones

- Los datos serán sintéticos. La importancia que el modelo asigne a una variable dependerá de los supuestos del generador y no constituirá evidencia sobre fraude real.
- No se encontró un manual técnico público del SPI con la lista exacta de campos del mensaje. La correspondencia con los campos ISO 20022 es una **inferencia** a partir del estándar.
- La FAQ del BCP indica que los pagos con QR "actuales" (vía procesadoras) se hacen fuera del SPI.
- Los campos internos del banco (dispositivo, IP, ubicación) son supuestos declarados.
- Régimen simulado: el período aplica el régimen actual a todas las fechas. En la realidad, el QR Hub estaba en producción controlada a fines de junio de 2026, los bancos habilitaron el QR personal en julio de 2026 y el tope de 10 millones rige desde marzo de 2026.
- Este documento solo define y justifica la tabla base. Las características derivadas, los escenarios de fraude y la segmentación de clientes se documentarán en archivos separados.


## 7. Fuentes

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
