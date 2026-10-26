"""
================================================================================
GENERADOR DE DATOS SINTÉTICOS DE FRAUDE - TRANSFERENCIAS SPI (SIPAP/QR)
================================================================================
Alcance: Transferencias instantáneas SPI del lado emisor.
Límite regulatorio: ₲ 10.000.000 por transacción (BCP, marzo 2026).
Monto mínimo: ₲ 1.000.
Genera: dataset_completo.csv, train.csv, valid.csv, test.csv
        (split cronológico 60/20/20).
================================================================================
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ==============================================================================
# CONFIGURACIÓN GLOBAL
# ==============================================================================
SEED = 42
N_TOTAL = 1_000_000           # Total de transacciones
FRAUD_RATE = 0.001            # 0.1% de fraude
RUIDO_FRAUDE = 0.08           # 8% de ruido en filas fraudulentas
LIMITE_SPI = 10_000_000       # ₲ 10 millones (BCP, marzo 2026)
MONTO_MINIMO = 1_000          # ₲ 1.000
DIAS_SIMULACION = 90          # 3 meses de datos

np.random.seed(SEED)
fecha_inicio = datetime(2026, 1, 1)

# ==============================================================================
# FUNCIONES AUXILIARES
# ==============================================================================
def generar_monto(minimo=MONTO_MINIMO, maximo=LIMITE_SPI, prob_redondo=0.30):
    """
    Genera un monto entero en Guaraníes.
    - 70%: no redondo (ej. 79898, 122298)
    - 30%: redondo a la unidad de mil (ej. 60000, 100000, 500000)
    """
    monto = np.random.lognormal(mean=12.5, sigma=1.2)
    if np.random.rand() < prob_redondo:
        monto = round(monto / 1000) * 1000
    else:
        monto = int(monto)
    return int(np.clip(monto, minimo, maximo))


def generar_timestamp(dias_max=DIAS_SIMULACION, hora_media=14, hora_std=4):
    """
    Genera un timestamp entero (sin microsegundos flotantes).
    """
    dia = int(np.random.randint(0, dias_max))
    hora = int(np.clip(np.random.normal(hora_media, hora_std), 0, 23))
    minuto = int(np.random.randint(0, 60))
    segundo = int(np.random.randint(0, 60))
    return fecha_inicio + timedelta(days=dia, hours=hora, minutes=minuto, seconds=segundo)


def aplicar_ruido(valor, prob_ruido=RUIDO_FRAUDE):
    """Invierte un binario con probabilidad prob_ruido."""
    return 1 - valor if np.random.rand() < prob_ruido else valor


# ==============================================================================
# 1. LÍNEA BASE: TRANSACCIONES NORMALES (99.9%)
# ==============================================================================
n_fraudes = int(N_TOTAL * FRAUD_RATE)
n_normales = N_TOTAL - n_fraudes

print(f"Generando {n_normales:,} transacciones normales...")
timestamps_normales = sorted([generar_timestamp() for _ in range(n_normales)])

# Montos enteros con mezcla redondo/no redondo
montos = np.array([generar_monto() for _ in range(n_normales)])

# Features temporales
horas = np.array([t.hour for t in timestamps_normales])
dias_semana = np.array([t.weekday() for t in timestamps_normales])
dias_mes = np.array([t.day for t in timestamps_normales])

# Comportamiento base del usuario
dispositivo_nuevo = np.random.binomial(1, 0.05, n_normales)
ubicacion_inusual = np.random.binomial(1, 0.03, n_normales)
destinatario_nuevo = np.random.binomial(1, 0.10, n_normales)
antiguedad_cuenta = np.random.randint(30, 3650, n_normales)

# Velocidad (conteos)
tx_5min = np.random.poisson(0.3, n_normales)
tx_1h = np.random.poisson(1.2, n_normales)
tx_24h = np.random.poisson(8, n_normales)

# Montos acumulados (enteros)
amount_1h = np.array([
    int(min(montos[i] * np.random.uniform(0.8, 2.5), LIMITE_SPI * 3))
    for i in range(n_normales)
])
amount_24h = np.array([
    int(min(amount_1h[i] * np.random.uniform(2, 6), LIMITE_SPI * 15))
    for i in range(n_normales)
])

# Promedio histórico (entero) y ratio
monto_promedio_30d = np.array([
    int(max(montos[i] * np.random.uniform(0.7, 1.4), MONTO_MINIMO))
    for i in range(n_normales)
])
ratio_monto = montos / monto_promedio_30d
unique_benef_24h = np.random.poisson(2.5, n_normales)

df_normal = pd.DataFrame({
    'timestamp': timestamps_normales,
    'monto_pyg': montos,
    'hora': horas,
    'es_fin_de_semana': (dias_semana >= 5).astype(int),
    'es_fin_de_mes': (dias_mes >= 25).astype(int),
    'es_horario_nocturno': ((horas < 6) | (horas >= 22)).astype(int),
    'hora_atipica': np.random.binomial(1, 0.04, n_normales),
    'dispositivo_nuevo': dispositivo_nuevo,
    'ubicacion_inusual': ubicacion_inusual,
    'antiguedad_cuenta_dias': antiguedad_cuenta,
    'tx_count_5min': tx_5min,
    'tx_count_1h': tx_1h,
    'tx_count_24h': tx_24h,
    'amount_sum_1h': amount_1h,
    'amount_sum_24h': amount_24h,
    'monto_promedio_usuario_30d': monto_promedio_30d,
    'ratio_monto_vs_promedio': ratio_monto,
    'destinatario_nuevo': destinatario_nuevo,
    'unique_beneficiaries_24h': unique_benef_24h,
    'es_fraude': 0,
    'escenario_fraude': 'normal'
})

# ==============================================================================
# 2. FRAUDES POR ESCENARIO (0.1%) - Distribución uniforme en el tiempo
# ==============================================================================
print(f"Generando {n_fraudes:,} transacciones fraudulentas...")

# Distribuir los fraudes uniformemente en los 90 días
dias_fraude = np.linspace(0, DIAS_SIMULACION - 1, n_fraudes)
np.random.shuffle(dias_fraude)

fraud_timestamps = []
for dia in dias_fraude:
    hora_base = np.random.choice([2, 3, 4, 10, 14, 18, 22])
    hora = int((hora_base + np.random.randint(-1, 2)) % 24)
    minuto = int(np.random.randint(0, 60))
    segundo = int(np.random.randint(0, 60))
    fraud_timestamps.append(
        fecha_inicio + timedelta(days=int(dia), hours=hora, minutes=minuto, seconds=segundo)
    )

escenarios = ['F1_toma_cuenta', 'F2_rafaga_salidas', 'F3_engano', 'F4_pruebas_pequenas']
escenario_asignado = np.random.choice(escenarios, n_fraudes, p=[0.30, 0.30, 0.25, 0.15])

fraud_rows = []
for i in range(n_fraudes):
    esc = escenario_asignado[i]
    ts = fraud_timestamps[i]
    hora = ts.hour

    # Valores por defecto
    dispositivo = 0; ubicacion = 0; hora_atip = 0
    ratio = 1.0; dest_nuevo = 0
    tx5 = np.random.poisson(0.3); tx1h = np.random.poisson(1); tx24 = np.random.poisson(5)
    unique_b = np.random.poisson(2)
    antig = np.random.randint(60, 3650)

    if esc == 'F1_toma_cuenta':
        dispositivo = 1; ubicacion = 1
        hora_atip = 1 if np.random.rand() < 0.7 else 0
        ratio = np.random.uniform(8, 40)
        monto_base = np.random.randint(2_000_000, LIMITE_SPI)
        if np.random.rand() < 0.6:
            monto_base = round(monto_base / 1000) * 1000
        dest_nuevo = 1; antig = np.random.randint(180, 3650)
        tx5 = 0; tx1h = np.random.randint(1, 3)

    elif esc == 'F2_rafaga_salidas':
        dispositivo = np.random.choice([0, 1], p=[0.5, 0.5])
        ubicacion = 1 if np.random.rand() < 0.6 else 0
        hora_atip = 1 if np.random.rand() < 0.5 else 0
        ratio = np.random.uniform(2, 10)
        monto_base = np.random.randint(200_000, 2_000_000)
        if np.random.rand() < 0.5:
            monto_base = round(monto_base / 1000) * 1000
        tx5 = np.random.randint(3, 8); tx1h = np.random.randint(6, 15); tx24 = np.random.randint(10, 25)
        unique_b = np.random.randint(5, 12)
        dest_nuevo = np.random.binomial(1, 0.7)

    elif esc == 'F3_engano':
        dispositivo = 0; ubicacion = 0
        hora_atip = 1 if np.random.rand() < 0.3 else 0
        ratio = np.random.uniform(3, 20)
        monto_base = np.random.randint(500_000, 5_000_000)
        if np.random.rand() < 0.3:
            monto_base = round(monto_base / 1000) * 1000
        dest_nuevo = 1
        tx5 = np.random.poisson(0.5); tx1h = np.random.randint(1, 4)
        antig = np.random.randint(30, 3650)

    elif esc == 'F4_pruebas_pequenas':
        dispositivo = np.random.choice([0, 1], p=[0.4, 0.6])
        ubicacion = 1 if np.random.rand() < 0.4 else 0
        hora_atip = 1 if np.random.rand() < 0.5 else 0
        ratio = np.random.uniform(0.8, 3)
        monto_base = np.random.randint(10_000, 150_000)
        if np.random.rand() < 0.4:
            monto_base = round(monto_base / 1000) * 1000
        tx5 = np.random.randint(2, 6); tx1h = np.random.randint(4, 10); tx24 = np.random.randint(8, 20)
        unique_b = np.random.randint(1, 4)
        dest_nuevo = np.random.binomial(1, 0.8)

    # Aplicar ruido
    dispositivo = aplicar_ruido(dispositivo)
    ubicacion = aplicar_ruido(ubicacion)
    hora_atip = aplicar_ruido(hora_atip)
    dest_nuevo = aplicar_ruido(dest_nuevo)

    # Monto final entero
    monto_final = int(np.clip(monto_base, MONTO_MINIMO, LIMITE_SPI))
    monto_prom = int(max(monto_final / max(ratio, 0.5), MONTO_MINIMO))

    # Montos acumulados enteros según escenario
    if esc == 'F2_rafaga_salidas':
        amt1h = int(min(monto_final * tx1h, LIMITE_SPI * 5))
        amt24h = int(min(monto_final * tx24, LIMITE_SPI * 20))
    elif esc == 'F4_pruebas_pequenas':
        amt1h = int(min(monto_final * tx1h * 1.2, LIMITE_SPI * 5))
        amt24h = int(min(monto_final * tx24 * 1.5, LIMITE_SPI * 20))
    else:
        amt1h = int(min(monto_final * 1.5, LIMITE_SPI * 5))
        amt24h = int(min(monto_final * 4, LIMITE_SPI * 20))

    fraud_rows.append({
        'timestamp': ts,
        'monto_pyg': monto_final,
        'hora': hora,
        'es_fin_de_semana': 1 if ts.weekday() >= 5 else 0,
        'es_fin_de_mes': 1 if ts.day >= 25 else 0,
        'es_horario_nocturno': 1 if hora < 6 or hora >= 22 else 0,
        'hora_atipica': hora_atip,
        'dispositivo_nuevo': dispositivo,
        'ubicacion_inusual': ubicacion,
        'antiguedad_cuenta_dias': antig,
        'tx_count_5min': tx5,
        'tx_count_1h': tx1h,
        'tx_count_24h': tx24,
        'amount_sum_1h': amt1h,
        'amount_sum_24h': amt24h,
        'monto_promedio_usuario_30d': monto_prom,
        'ratio_monto_vs_promedio': monto_final / monto_prom,
        'destinatario_nuevo': dest_nuevo,
        'unique_beneficiaries_24h': unique_b,
        'es_fraude': 1,
        'escenario_fraude': esc
    })

df_fraude = pd.DataFrame(fraud_rows)

# ==============================================================================
# 3. COMBINAR, ORDENAR CRONOLÓGICAMENTE Y SEPARAR 60/20/20
# ==============================================================================
df = pd.concat([df_normal, df_fraude], ignore_index=True)
df = df.sort_values('timestamp').reset_index(drop=True)

df_features = df.drop(columns=['timestamp'])

n = len(df_features)
train_end = int(n * 0.60)
valid_end = int(n * 0.80)

train_df = df_features.iloc[:train_end].copy()
valid_df = df_features.iloc[train_end:valid_end].copy()
test_df = df_features.iloc[valid_end:].copy()

# ==============================================================================
# 4. VERIFICACIONES DE CALIDAD
# ==============================================================================
print("\n" + "="*65)
print("VERIFICACIÓN DE DISTRIBUCIÓN")
print("="*65)

for name, subset in [('Train (60%)', train_df), ('Valid (20%)', valid_df), ('Test (20%)', test_df)]:
    n_fraudes_subset = int(subset['es_fraude'].sum())
    pct = subset['es_fraude'].mean() * 100
    print(f"{name:12} | {len(subset):>9,} filas | {n_fraudes_subset:>4} fraudes ({pct:.3f}%)")
    if n_fraudes_subset == 0:
        raise ValueError(f"❌ ERROR CRÍTICO: {name} no tiene fraudes.")

print("\n" + "="*65)
print("VERIFICACIÓN DE TIPOS DE DATOS")
print("="*65)
print(f"Tipo timestamp:       {df['timestamp'].dtype}")
print(f"Tipo monto_pyg:       {df['monto_pyg'].dtype}")
print(f"Tipo amount_sum_1h:   {df['amount_sum_1h'].dtype}")
print(f"Tipo monto_prom_30d:  {df['monto_promedio_usuario_30d'].dtype}")
print(f"Tipo ratio:           {df['ratio_monto_vs_promedio'].dtype}")

# Verificar que los timestamps no tengan microsegundos
tiene_microsegundos = df['timestamp'].apply(lambda x: x.microsecond != 0).any()
print(f"\n¿Hay microsegundos?   {tiene_microsegundos}")
print(f"Ejemplo timestamp:    {df['timestamp'].iloc[0]}")

# Verificar montos enteros
todos_enteros = df['monto_pyg'].apply(lambda x: float(x).is_integer()).all()
print(f"¿Todos los montos enteros? {todos_enteros}")
print(f"Monto mínimo:         ₲ {df['monto_pyg'].min():>12,.0f}")
print(f"Monto máximo:         ₲ {df['monto_pyg'].max():>12,.0f}")
print(f"Monto promedio:       ₲ {df['monto_pyg'].mean():>12,.0f}")

# Ejemplos de montos redondos vs no redondos
redondos = df[df['monto_pyg'] % 1000 == 0]['monto_pyg'].head(5).tolist()
no_redondos = df[df['monto_pyg'] % 1000 != 0]['monto_pyg'].head(5).tolist()
print(f"\nEjemplos redondos:    {[f'₲ {m:,.0f}' for m in redondos]}")
print(f"Ejemplos no redondos: {[f'₲ {m:,.0f}' for m in no_redondos]}")

# Ratio por clase
print(f"\nRatio promedio (global):   {df['ratio_monto_vs_promedio'].mean():.2f}")
print(f"Ratio promedio (fraudes):  {df[df['es_fraude']==1]['ratio_monto_vs_promedio'].mean():.2f}")
print(f"Ratio promedio (normales): {df[df['es_fraude']==0]['ratio_monto_vs_promedio'].mean():.2f}")

# Distribución de escenarios
print("\n" + "="*65)
print("DISTRIBUCIÓN DE ESCENARIOS DE FRAUDE")
print("="*65)
print(df[df['es_fraude']==1]['escenario_fraude'].value_counts().to_string())

# ==============================================================================
# 5. GUARDAR ARCHIVOS
# ==============================================================================
df.to_csv('data/dataset_completo.csv', index=False)
train_df.to_csv('data/train.csv', index=False)
valid_df.to_csv('data/valid.csv', index=False)
test_df.to_csv('data/test.csv', index=False)

print("\n" + "="*65)
print("✅ ARCHIVOS GENERADOS")
print("="*65)
print(f"  • dataset_completo.csv  ({len(df):,} filas)")
print(f"  • train.csv             ({len(train_df):,} filas)")
print(f"  • valid.csv             ({len(valid_df):,} filas)")
print(f"  • test.csv              ({len(test_df):,} filas)")
print("="*65)