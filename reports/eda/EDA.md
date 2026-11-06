# EDA del dataset sintético SPI (generado por notebooks/01_eda.ipynb)

- Transferencias: **1.692.473** · fraudes: **1.331** (0.0786%)
- Período: 01/07/2025 00:01 – 30/06/2026 23:59
- Emisores: 8.058 · cuentas destino: 215.208 · bancos: 12 · ciudades: 18
- Monto: mínimo Gs. 1.000, mediana Gs. 118.268, máximo Gs. 10.000.000
- Importes que no son múltiplo de 1.000: 48.0% · múltiplos de 10.000: 16.6%
- Transferencias legítimas de Gs. 5 millones o más: 16.886 · fraudes menores a Gs. 100.000: 427
- Transferencias sin historial (monto_promedio_30d_gs = 0): 5.077
- Proyección PCA: las 2 primeras componentes explican 26.1% de la varianza

## Partición temporal

|               |   transferencias |   fraudes |
|:--------------|-----------------:|----------:|
| entrenamiento |          1137643 |       939 |
| validacion    |           275906 |       180 |
| prueba        |           278924 |       212 |

## Transferencias fraudulentas por tipología

| tipo_fraude              | transferencias   | porcentaje   | monto_mediano_gs   | monto_minimo_gs   | monto_maximo_gs   |
|:-------------------------|:-----------------|:-------------|:-------------------|:------------------|:------------------|
| toma_de_cuenta           | 503              | 37.8         | 325.714            | 8.800             | 9.250.000         |
| rafaga_de_transferencias | 360              | 27.0         | 54.890             | 10.000            | 540.000           |
| cuenta_mula              | 308              | 23.1         | 2.302.969          | 500.000           | 8.056.000         |
| ingenieria_social        | 110              | 8.3          | 872.878            | 156.529           | 6.989.244         |
| camuflado                | 50               | 3.8          | 160.000            | 69.300            | 700.000           |

## Restricciones verificadas

| restriccion                                                                            |   violaciones | cumple   | detalle                                                                                                          |
|:---------------------------------------------------------------------------------------|--------------:|:---------|:-----------------------------------------------------------------------------------------------------------------|
| Columnas = esquema definido (18, en orden)                                             |             0 | ✓        |                                                                                                                  |
| transaction_id único                                                                   |             0 | ✓        |                                                                                                                  |
| Filas duplicadas completas                                                             |             0 | ✓        |                                                                                                                  |
| timestamp dentro de jul 2025 - jun 2026                                                |             0 | ✓        |                                                                                                                  |
| monto_gs entre 1.000 y 10.000.000 Gs.                                                  |             0 | ✓        |                                                                                                                  |
| Ninguna columna con valores faltantes                                                  |             0 | ✓        | monto_promedio_30d_gs = 0 cuando el cliente no tiene historial (sin_historial = 1)                               |
| n_tx_1h >= 0 y n_tx_24h >= n_tx_1h                                                     |             0 | ✓        |                                                                                                                  |
| monto_promedio_30d_gs >= 0                                                             |             0 | ✓        |                                                                                                                  |
| Promedio = 0 => sin transferencias en las últimas 24 h                                 |             0 | ✓        |                                                                                                                  |
| antiguedad_cuenta_origen_dias >= 0                                                     |             0 | ✓        |                                                                                                                  |
| es_fraude en {0, 1}                                                                    |             0 | ✓        |                                                                                                                  |
| tipo_fraude = 'ninguno' <=> es_fraude = 0                                              |             0 | ✓        |                                                                                                                  |
| n_tx_1h = transferencias previas del emisor en [t-1h, t)                               |             0 | ✓        | recalculado con pandas.rolling en 1,692,409 filas (desde 01/07 01:00; antes depende del historial de junio 2025) |
| n_tx_24h = transferencias previas del emisor en [t-24h, t)                             |             0 | ✓        | recalculado con pandas.rolling en 1,688,298 filas (desde 02/07 00:00; antes depende del historial de junio 2025) |
| monto_promedio_30d_gs = promedio de montos previos en 30 días                          |             0 | ✓        | recalculado en 1,563,674 filas (desde 31/07)                                                                     |
| destinatario_nuevo = True solo en la primera transferencia emisor->destino             |             0 | ✓        |                                                                                                                  |
| Primera aparición del par en el dataset marcada como no nueva => ya pagó en junio 2025 |             0 | ✓        | 62,115 pares con historial previo en junio 2025 (fuera del CSV); no es un error                                  |
| dispositivo_nuevo = True solo si se vio por primera vez hace <= 24 h                   |             0 | ✓        |                                                                                                                  |

## Calidad por columna

| columna                       | tipo_de_dato   |   faltantes |   pct_faltantes |   valores_distintos |
|:------------------------------|:---------------|------------:|----------------:|--------------------:|
| transaction_id                | str            |           0 |               0 |             1692473 |
| timestamp                     | datetime64[us] |           0 |               0 |             1623820 |
| cuenta_emisor_id              | str            |           0 |               0 |                8058 |
| banco_origen                  | str            |           0 |               0 |                  12 |
| banco_destino                 | str            |           0 |               0 |                  12 |
| cuenta_destino_id             | str            |           0 |               0 |              215208 |
| ciudad                        | str            |           0 |               0 |                  18 |
| ciudad_habitual               | str            |           0 |               0 |                  18 |
| dispositivo_id                | str            |           0 |               0 |               28340 |
| monto_gs                      | int64          |           0 |               0 |              346804 |
| n_tx_1h                       | int64          |           0 |               0 |                  12 |
| n_tx_24h                      | int64          |           0 |               0 |                  21 |
| monto_promedio_30d_gs         | int64          |           0 |               0 |              739762 |
| destinatario_nuevo            | bool           |           0 |               0 |                   2 |
| dispositivo_nuevo             | bool           |           0 |               0 |                   2 |
| antiguedad_cuenta_origen_dias | int64          |           0 |               0 |               10585 |
| es_fraude                     | int64          |           0 |               0 |                   2 |
| tipo_fraude                   | str            |           0 |               0 |                   6 |

## Features según la clase (entrenamiento, jul 2025 - feb 2026)

|                          |   legitima_mean |   legitima_median |   fraude_mean |   fraude_median |
|:-------------------------|----------------:|------------------:|--------------:|----------------:|
| log_monto                |         11.8765 |           11.6953 |       12.7274 |         12.5434 |
| log_ratio_monto_promedio |         -0.8241 |           -0.9316 |       -0.3462 |         -0.4358 |
| sin_historial            |          0.0029 |            0      |        0.082  |          0      |
| hora                     |         14.2956 |           14      |        9.8701 |         10      |
| es_nocturna              |          0.0182 |            0      |        0.4058 |          0      |
| dia_semana               |          2.8892 |            3      |        2.9137 |          3      |
| es_fin_de_semana         |          0.2571 |            0      |        0.2609 |          0      |
| es_fin_de_mes            |          0.2243 |            0      |        0.2247 |          0      |
| log_antiguedad_origen    |          7.0936 |            7.2152 |        6.5396 |          7.1301 |
| n_tx_1h                  |          0.1521 |            0      |        1.033  |          1      |
| n_tx_24h                 |          1.1454 |            1      |        1.7391 |          1      |
| destinatario_nuevo       |          0.2622 |            0      |        0.7742 |          1      |
| dispositivo_nuevo        |          0.0179 |            0      |        0.6241 |          1      |
| ciudad_distinta          |          0.0502 |            0      |        0.2694 |          0      |
