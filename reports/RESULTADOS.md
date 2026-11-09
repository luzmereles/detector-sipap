# Resultados (generado por notebooks/02_entrenamiento.ipynb)

Modelo final (API): **XGBoost ponderado ajustado (Optuna + umbral)** · versión 20261108-1807

## Partición temporal

|               | período             |   transferencias |   fraudes |   % fraude |
|:--------------|:--------------------|-----------------:|----------:|-----------:|
| entrenamiento | jul 2025 – feb 2026 |          1137643 |       939 |     0.0825 |
| validación    | mar – abr 2026      |           275906 |       180 |     0.0652 |
| prueba        | may – jun 2026      |           278924 |       212 |     0.076  |

## Etapa 1 — primera prueba en validación (sin ajustes, umbral 0,5)

| modelo              | conjunto   |   umbral |   average_precision |   roc_auc |     f1 |   precision |   recall |   tp |    fp |   fn |     tn |
|:--------------------|:-----------|---------:|--------------------:|----------:|-------:|------------:|---------:|-----:|------:|-----:|-------:|
| Regresión logística | validación |      0.5 |              0.1322 |    0.9522 | 0.0169 |      0.0085 |   0.8111 |  146 | 16982 |   34 | 258744 |
| XGBoost + SMOTE     | validación |      0.5 |              0.3996 |    0.9408 | 0.1593 |      0.092  |   0.5944 |  107 |  1056 |   73 | 274670 |
| XGBoost ponderado   | validación |      0.5 |              0.4618 |    0.9421 | 0.1506 |      0.0845 |   0.6944 |  125 |  1355 |   55 | 274371 |

## Etapa 2 — ajuste del XGBoost ponderado (validación)

Hiperparámetros elegidos por Optuna (40 pruebas, average precision en validación):

|                  |    valor |
|:-----------------|---------:|
| max_depth        |  5       |
| learning_rate    |  0.08136 |
| min_child_weight | 11.6449  |
| subsample        |  0.66925 |
| colsample_bytree |  0.72202 |
| reg_lambda       |  1.96585 |
| gamma            |  2.23717 |
| scale_pos_weight | 12.4893  |
| n_estimators     | 92       |

Umbral de clasificación (máximo F1 en validación): **0.7874** · política de la API: bloquear si score ≥ 0.8985, revisar si score ≥ 0.0765

| modelo                     | etapa           |   umbral |   average_precision |   roc_auc |     f1 |   precision |   recall |   tp |   fp |   fn |
|:---------------------------|:----------------|---------:|--------------------:|----------:|-------:|------------:|---------:|-----:|-----:|-----:|
| XGBoost ponderado          | 1 · sin ajustes |   0.5    |              0.4618 |    0.9421 | 0.1506 |      0.0845 |   0.6944 |  125 | 1355 |   55 |
| XGBoost ponderado ajustado | 2 · ajustado    |   0.7874 |              0.5582 |    0.9624 | 0.5878 |      0.75   |   0.4833 |   87 |   29 |   93 |

## Etapa 3 — evaluación final en prueba

| modelo                     | conjunto   |   umbral |   average_precision |   roc_auc |     f1 |   precision |   recall |   tp |   fp |   fn |     tn |
|:---------------------------|:-----------|---------:|--------------------:|----------:|-------:|------------:|---------:|-----:|-----:|-----:|-------:|
| XGBoost ponderado ajustado | prueba     |   0.7874 |              0.5289 |    0.9705 | 0.5153 |      0.7368 |   0.3962 |   84 |   30 |  128 | 278682 |

Average precision en prueba: **0.5289** (IC 95 % bootstrap: 0.4684 – 0.5917) · entrenamiento 0.6484 · validación 0.5582 · hojas que suben el riesgo apoyadas en 1 o 2 casos de fraude: 5.7 %

### Política de la API en prueba

| es_fraude   |   APROBAR |   REVISAR |   BLOQUEAR |
|:------------|----------:|----------:|-----------:|
| Legítima    |    277361 |      1343 |          8 |
| Fraude      |        50 |        98 |         64 |

- Fraudes detenidos: 162 de 212 (64 bloqueados, 98 a revisión)
- Monto de fraude detenido: Gs. 231.378.511 de Gs. 267.643.425 (86.5%)
- Legítimas bloqueadas: 8 · legítimas a revisión: 1343 · precisión de los bloqueos: 0.8889
- Latencia de inferencia: 1.553 ms por transferencia

### Detección por tipología (prueba)

| tipo_fraude              |   recall |   n |
|:-------------------------|---------:|----:|
| toma_de_cuenta           |    1     |  57 |
| rafaga_de_transferencias |    0.743 |  70 |
| cuenta_mula              |    0.883 |  60 |
| ingenieria_social        |    0     |  17 |
| camuflado                |    0     |   8 |

### Importancia de las features (media de |SHAP|, prueba)

|                          |   global |   sobre_fraudes |
|:-------------------------|---------:|----------------:|
| dispositivo_nuevo        |   0.4199 |          2.3664 |
| hora                     |   0.2081 |          1.1269 |
| n_tx_1h                  |   0.4847 |          1.1199 |
| destinatario_nuevo       |   1.0204 |          0.9835 |
| log_monto                |   0.451  |          0.7108 |
| ciudad_distinta          |   0.0582 |          0.3097 |
| log_ratio_monto_promedio |   0.1629 |          0.3026 |
| log_antiguedad_origen    |   0.1141 |          0.2477 |
| es_nocturna              |   0.0319 |          0.17   |
| sin_historial            |   0.0141 |          0.1165 |
| n_tx_24h                 |   0.1356 |          0.0871 |
| dia_semana               |   0.0632 |          0.0832 |
| es_fin_de_mes            |   0.0205 |          0.0559 |
| es_fin_de_semana         |   0.0122 |          0.0113 |
