# Resultados (generado por notebooks/02_entrenamiento.ipynb)

Modelo final (API): **XGBoost ponderado ajustado (Optuna + umbral)** · versión 20261031-1621

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
| max_depth        |  7       |
| learning_rate    |  0.12108 |
| min_child_weight |  1.36968 |
| subsample        |  0.90016 |
| colsample_bytree |  0.90213 |
| reg_lambda       |  0.05939 |
| gamma            |  0.43322 |
| scale_pos_weight | 25.9293  |
| n_estimators     | 24       |

Umbral de clasificación (máximo F1 en validación): **0.8290** · política de la API: bloquear si score ≥ 0.8818, revisar si score ≥ 0.1094

| modelo                     | etapa           |   umbral |   average_precision |   roc_auc |     f1 |   precision |   recall |   tp |   fp |   fn |
|:---------------------------|:----------------|---------:|--------------------:|----------:|-------:|------------:|---------:|-----:|-----:|-----:|
| XGBoost ponderado          | 1 · sin ajustes |    0.5   |              0.4618 |    0.9421 | 0.1506 |      0.0845 |   0.6944 |  125 | 1355 |   55 |
| XGBoost ponderado ajustado | 2 · ajustado    |    0.829 |              0.5614 |    0.9617 | 0.5887 |      0.8137 |   0.4611 |   83 |   19 |   97 |

## Etapa 3 — evaluación final en prueba (una sola vez)

| modelo                     | conjunto   |   umbral |   average_precision |   roc_auc |    f1 |   precision |   recall |   tp |   fp |   fn |     tn |
|:---------------------------|:-----------|---------:|--------------------:|----------:|------:|------------:|---------:|-----:|-----:|-----:|-------:|
| XGBoost ponderado ajustado | prueba     |    0.829 |              0.4887 |    0.9685 | 0.475 |      0.7037 |   0.3585 |   76 |   32 |  136 | 278680 |

Average precision en prueba: **0.4887** (IC 95 % bootstrap: 0.4262 – 0.5525) · entrenamiento 0.6879 · validación 0.5614

### Política de la API en prueba

| es_fraude   |   APROBAR |   REVISAR |   BLOQUEAR |
|:------------|----------:|----------:|-----------:|
| Legítima    |    277407 |      1296 |          9 |
| Fraude      |        56 |        91 |         65 |

- Fraudes detenidos: 156 de 212 (65 bloqueados, 91 a revisión)
- Monto de fraude detenido: Gs. 231.555.504 de Gs. 267.643.425 (86.5%)
- Legítimas bloqueadas: 9 · legítimas a revisión: 1296 · precisión de los bloqueos: 0.8784
- Latencia de inferencia: 1.659 ms por transferencia

### Detección por tipología (prueba)

| tipo_fraude              |   recall |   n |
|:-------------------------|---------:|----:|
| toma_de_cuenta           |    0.982 |  57 |
| rafaga_de_transferencias |    0.671 |  70 |
| cuenta_mula              |    0.883 |  60 |
| ingenieria_social        |    0     |  17 |
| camuflado                |    0     |   8 |

### Importancia de las features (media de |SHAP|, prueba)

|                          |   global |   sobre_fraudes |
|:-------------------------|---------:|----------------:|
| dispositivo_nuevo        |   0.253  |          2.176  |
| hora                     |   0.1172 |          0.9012 |
| n_tx_1h                  |   0.1941 |          0.7762 |
| destinatario_nuevo       |   0.353  |          0.6201 |
| log_monto                |   0.2051 |          0.4991 |
| ciudad_distinta          |   0.0274 |          0.2231 |
| log_ratio_monto_promedio |   0.0655 |          0.1821 |
| log_antiguedad_origen    |   0.0372 |          0.1619 |
| es_nocturna              |   0.009  |          0.0938 |
| sin_historial            |   0.0076 |          0.0712 |
| dia_semana               |   0.0165 |          0.048  |
| n_tx_24h                 |   0.0305 |          0.0439 |
| es_fin_de_mes            |   0.0082 |          0.031  |
| es_fin_de_semana         |   0.0049 |          0.0084 |
