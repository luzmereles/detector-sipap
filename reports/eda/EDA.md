# EDA del dataset sintético SPI (generado por notebooks/01_eda.ipynb)

- Transferencias: **1.689.911** · fraudes: **1.362** (0.0806%)
- Período: 01/07/2025 00:01 – 30/06/2026 23:59
- Emisores: 8.040 · cuentas destino: 169.771 · bancos: 12 · ciudades: 18
- Monto: mínimo Gs. 1.000, mediana Gs. 118.143, máximo Gs. 10.000.000
- Importes que no son múltiplo de 1.000: 48.0% · múltiplos de 10.000: 16.6%
- Transferencias legítimas de Gs. 5 millones o más: 16.632 · fraudes menores a Gs. 100.000: 555
- Transferencias sin historial (monto_promedio_30d_gs = 0): 5.143
- Proyección PCA: las 2 primeras componentes explican 26.1% de la varianza

## Partición temporal

|               |   transferencias |   fraudes |
|:--------------|-----------------:|----------:|
| entrenamiento |          1136689 |       955 |
| validacion    |           275444 |       157 |
| prueba        |           277778 |       250 |

## Transferencias fraudulentas por tipología

| tipo_fraude              | transferencias   | porcentaje   | monto_mediano_gs   | monto_minimo_gs   | monto_maximo_gs   |
|:-------------------------|:-----------------|:-------------|:-------------------|:------------------|:------------------|
| toma_de_cuenta           | 469              | 34.4         | 435.000            | 7.915             | 9.860.000         |
| rafaga_de_transferencias | 558              | 41.0         | 65.519             | 10.700            | 587.235           |
| cuenta_mula              | 280              | 20.6         | 1.964.436          | 502.300           | 7.188.800         |
| camuflado                | 55               | 4.0          | 230.000            | 34.000            | 1.507.600         |

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
| n_tx_1h = transferencias previas del emisor en [t-1h, t)                               |             0 | ✓        | recalculado con pandas.rolling en 1,689,863 filas (desde 01/07 01:00; antes depende del historial de junio 2025) |
| n_tx_24h = transferencias previas del emisor en [t-24h, t)                             |             0 | ✓        | recalculado con pandas.rolling en 1,685,813 filas (desde 02/07 00:00; antes depende del historial de junio 2025) |
| monto_promedio_30d_gs = promedio de montos previos en 30 días                          |             0 | ✓        | recalculado en 1,560,945 filas (desde 31/07)                                                                     |
| destinatario_nuevo = True solo en la primera transferencia emisor->destino             |             0 | ✓        |                                                                                                                  |
| Primera aparición del par en el dataset marcada como no nueva => ya pagó en junio 2025 |             0 | ✓        | 63,940 pares con historial previo en junio 2025 (fuera del CSV); no es un error                                  |
| dispositivo_nuevo = True solo si se vio por primera vez hace <= 24 h                   |             0 | ✓        |                                                                                                                  |

## Calidad por columna

| columna                       | tipo_de_dato   |   faltantes |   pct_faltantes |   valores_distintos |
|:------------------------------|:---------------|------------:|----------------:|--------------------:|
| transaction_id                | str            |           0 |               0 |             1689911 |
| timestamp                     | datetime64[us] |           0 |               0 |             1620947 |
| cuenta_emisor_id              | str            |           0 |               0 |                8040 |
| banco_origen                  | str            |           0 |               0 |                  12 |
| banco_destino                 | str            |           0 |               0 |                  12 |
| cuenta_destino_id             | str            |           0 |               0 |              169771 |
| ciudad                        | str            |           0 |               0 |                  18 |
| ciudad_habitual               | str            |           0 |               0 |                  18 |
| dispositivo_id                | str            |           0 |               0 |               19181 |
| monto_gs                      | int64          |           0 |               0 |              345872 |
| n_tx_1h                       | int64          |           0 |               0 |                  13 |
| n_tx_24h                      | int64          |           0 |               0 |                  18 |
| monto_promedio_30d_gs         | int64          |           0 |               0 |              739979 |
| destinatario_nuevo            | bool           |           0 |               0 |                   2 |
| dispositivo_nuevo             | bool           |           0 |               0 |                   2 |
| antiguedad_cuenta_origen_dias | int64          |           0 |               0 |               10610 |
| es_fraude                     | int64          |           0 |               0 |                   2 |
| tipo_fraude                   | str            |           0 |               0 |                   5 |

## Features según la clase (entrenamiento, jul 2025 - feb 2026)

|                          |   legitima_mean |   legitima_median |   fraude_mean |   fraude_median |
|:-------------------------|----------------:|------------------:|--------------:|----------------:|
| log_monto                |         11.8772 |           11.6953 |       12.5002 |         11.9223 |
| log_ratio_monto_promedio |         -0.8198 |           -0.927  |       -0.5922 |         -0.8787 |
| sin_historial            |          0.0029 |            0      |        0.0712 |          0      |
| hora                     |         14.2973 |           14      |       10.8743 |         12      |
| es_nocturna              |          0.018  |            0      |        0.3403 |          0      |
| dia_semana               |          2.8888 |            3      |        2.9738 |          3      |
| es_fin_de_semana         |          0.257  |            0      |        0.266  |          0      |
| es_fin_de_mes            |          0.224  |            0      |        0.2021 |          0      |
| log_antiguedad_origen    |          7.1005 |            7.2182 |        6.6579 |          7.051  |
| n_tx_1h                  |          0.1512 |            0      |        1.3455 |          1      |
| n_tx_24h                 |          1.1464 |            1      |        2.0618 |          2      |
| destinatario_nuevo       |          0.1997 |            0      |        0.7969 |          1      |
| dispositivo_nuevo        |          0.0099 |            0      |        0.6199 |          1      |
| ciudad_distinta          |          0.0503 |            0      |        0.2461 |          0      |
