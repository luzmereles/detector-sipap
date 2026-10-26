"""
================================================================================
ANÁLISIS EXPLORATORIO DE DATOS (EDA) - DETECTOR DE FRAUDE SPI
================================================================================
Uso: python eda.py
Entrada: dataset_completo.csv
Salida: Gráficos en pantalla + carpeta 'eda_outputs/' con los PNG
================================================================================
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
sns.set_theme(style="whitegrid", palette="deep")
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 10

OUTPUT_DIR = Path('eda_outputs')
OUTPUT_DIR.mkdir(exist_ok=True)

# ==============================================================================
# 1. CARGA Y VALIDACIÓN BÁSICA
# ==============================================================================
print("="*70)
print(" CARGANDO DATASET")
print("="*70)

df = pd.read_csv('data/dataset_completo.csv')

print(f"Filas:          {len(df):,}")
print(f"Columnas:       {len(df.columns)}")
print(f"Memoria:        {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
print(f"\nColumnas:       {list(df.columns)}")

# Separar features y etiquetas
label_cols = ['es_fraude', 'escenario_fraude']
feature_cols = [c for c in df.columns if c not in label_cols]

# ==============================================================================
# 2. RESUMEN DE CALIDAD
# ==============================================================================
print("\n" + "="*70)
print(" RESUMEN DE CALIDAD")
print("="*70)

# Nulos
nulos = df.isnull().sum()
if nulos.sum() == 0:
    print("✅ Sin valores nulos")
else:
    print(f"⚠️ Columnas con nulos:\n{nulos[nulos > 0]}")

# Duplicados
dup = df.duplicated().sum()
print(f"{'✅' if dup == 0 else '⚠️'} Duplicados: {dup}")

# Tipos de datos
print(f"\nTipos de datos:")
print(df.dtypes.value_counts().to_string())

# Desbalance
n_fraudes = int(df['es_fraude'].sum())
pct_fraude = df['es_fraude'].mean() * 100
print(f"\n{'='*70}")
print(f" DESBALANCE DE CLASES")
print(f"{'='*70}")
print(f"Normales:  {len(df) - n_fraudes:>9,} ({100 - pct_fraude:.3f}%)")
print(f"Fraudes:   {n_fraudes:>9,} ({pct_fraude:.3f}%)")
print(f"Ratio de desbalance (neg/pos): {(len(df) - n_fraudes) / max(n_fraudes, 1):.0f}:1")

# ==============================================================================
# 3. GRÁFICO 1: DISTRIBUCIÓN DE CLASES Y ESCENARIOS
# ==============================================================================
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# 3.1 Conteo de clases
ax = axes[0]
counts = df['es_fraude'].value_counts().sort_index()
bars = ax.bar(['Normal', 'Fraude'], counts.values, color=['#2ecc71', '#e74c3c'], edgecolor='black')
for bar, val in zip(bars, counts.values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.02,
            f'{val:,}', ha='center', va='bottom', fontweight='bold')
ax.set_title('Distribución de Clases (conteo)', fontweight='bold')
ax.set_ylabel('N° transacciones')
ax.set_yscale('log')

# 3.2 Proporción de clases (pie)
ax = axes[1]
ax.pie(counts.values, labels=['Normal', 'Fraude'], autopct='%.3f%%',
       colors=['#2ecc71', '#e74c3c'], startangle=90, explode=(0, 0.15),
       textprops={'fontweight': 'bold'})
ax.set_title('Proporción de Clases', fontweight='bold')

# 3.3 Escenarios de fraude
ax = axes[2]
esc_counts = df[df['es_fraude'] == 1]['escenario_fraude'].value_counts()
bars = ax.barh(esc_counts.index, esc_counts.values, color='#e74c3c', edgecolor='black')
for bar, val in zip(bars, esc_counts.values):
    ax.text(bar.get_width() * 1.02, bar.get_y() + bar.get_height()/2,
            f'{val:,}', va='center', fontweight='bold')
ax.set_title('Escenarios de Fraude (conteo)', fontweight='bold')
ax.set_xlabel('N° casos')

plt.tight_layout()
plt.savefig(OUTPUT_DIR / '01_distribucion_clases.png', dpi=120, bbox_inches='tight')
plt.show()

# ==============================================================================
# 4. GRÁFICO 2: MATRIZ DE CORRELACIÓN (solo features numéricas)
# ==============================================================================
fig, ax = plt.subplots(figsize=(16, 12))

corr = df[feature_cols + ['es_fraude']].corr()

# Máscara triangular
mask = np.triu(np.ones_like(corr, dtype=bool))

sns.heatmap(corr, mask=mask, cmap='RdBu_r', center=0, annot=True,
            fmt='.2f', linewidths=0.5, ax=ax,
            cbar_kws={'label': 'Correlación de Pearson'},
            annot_kws={'size': 7})

ax.set_title('Matriz de Correlación (features + etiqueta)',
             fontweight='bold', fontsize=14, pad=20)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / '02_matriz_correlacion.png', dpi=120, bbox_inches='tight')
plt.show()

# Correlaciones más fuertes con es_fraude
print("\n" + "="*70)
print(" TOP 10 CORRELACIONES CON es_fraude")
print("="*70)
top_corr = corr['es_fraude'].drop('es_fraude').abs().sort_values(ascending=False).head(10)
for feat, val in top_corr.items():
    print(f"  {feat:35} {corr.loc[feat, 'es_fraude']:+.4f}")

# ==============================================================================
# 5. GRÁFICO 3: BOXPLOTS / VIOLIN PLOTS DE FEATURES CLAVE POR CLASE
# ==============================================================================
key_features = [
    'monto_pyg', 'ratio_monto_vs_promedio', 'tx_count_1h',
    'tx_count_24h', 'amount_sum_1h', 'unique_beneficiaries_24h'
]

fig, axes = plt.subplots(2, 3, figsize=(18, 10))
axes = axes.flatten()

for i, feat in enumerate(key_features):
    ax = axes[i]
    # Usar log1p para features con rango muy amplio
    if feat in ['monto_pyg', 'amount_sum_1h', 'ratio_monto_vs_promedio']:
        data = df[[feat, 'es_fraude']].copy()
        data[feat] = np.log1p(data[feat])
        ylabel = f'log1p({feat})'
    else:
        data = df[[feat, 'es_fraude']]
        ylabel = feat

    sns.boxplot(data=data, x='es_fraude', y=feat,
                palette=['#2ecc71', '#e74c3c'], ax=ax,
                showfliers=False, width=0.6)
    ax.set_title(f'{feat}\n(fraudes en rojo)', fontweight='bold')
    ax.set_xlabel('es_fraude (0=Normal, 1=Fraude)')
    ax.set_ylabel(ylabel)

plt.suptitle('Distribución de Features Clave por Clase', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / '03_boxplots_features.png', dpi=120, bbox_inches='tight')
plt.show()

# ==============================================================================
# 6. GRÁFICO 4: SCATTER PLOTS (los "de puntos" que pediste)
# ==============================================================================
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# 6.1 Monto vs Ratio (la separación más importante)
ax = axes[0, 0]
normal = df[df['es_fraude'] == 0].sample(min(5000, len(df[df['es_fraude']==0])), random_state=42)
fraude = df[df['es_fraude'] == 1]
ax.scatter(np.log1p(normal['monto_pyg']), np.log1p(normal['ratio_monto_vs_promedio']),
           alpha=0.15, s=8, c='#2ecc71', label='Normal', edgecolors='none')
ax.scatter(np.log1p(fraude['monto_pyg']), np.log1p(fraude['ratio_monto_vs_promedio']),
           alpha=0.6, s=20, c='#e74c3c', label='Fraude', edgecolors='black', linewidth=0.3)
ax.set_xlabel('log1p(monto_pyg)')
ax.set_ylabel('log1p(ratio_monto_vs_promedio)')
ax.set_title('Monto vs Ratio (separación de clases)', fontweight='bold')
ax.legend(markerscale=3)

# 6.2 Tx count 1h vs Amount sum 1h
ax = axes[0, 1]
ax.scatter(normal['tx_count_1h'], np.log1p(normal['amount_sum_1h']),
           alpha=0.15, s=8, c='#2ecc71', label='Normal', edgecolors='none')
ax.scatter(fraude['tx_count_1h'], np.log1p(fraude['amount_sum_1h']),
           alpha=0.6, s=20, c='#e74c3c', label='Fraude', edgecolors='black', linewidth=0.3)
ax.set_xlabel('tx_count_1h')
ax.set_ylabel('log1p(amount_sum_1h)')
ax.set_title('Velocidad vs Monto acumulado 1h', fontweight='bold')
ax.legend(markerscale=3)
ax.set_xlim(0, 25)

# 6.3 Hora del día vs Ratio
ax = axes[1, 0]
ax.scatter(normal['hora'], np.log1p(normal['ratio_monto_vs_promedio']),
           alpha=0.1, s=6, c='#2ecc71', label='Normal', edgecolors='none')
ax.scatter(fraude['hora'], np.log1p(fraude['ratio_monto_vs_promedio']),
           alpha=0.5, s=18, c='#e74c3c', label='Fraude', edgecolors='black', linewidth=0.3)
ax.set_xlabel('Hora del día')
ax.set_ylabel('log1p(ratio_monto_vs_promedio)')
ax.set_title('Hora vs Ratio', fontweight='bold')
ax.legend(markerscale=3)
ax.set_xticks(range(0, 24, 3))

# 6.4 Antigüedad de cuenta vs Monto
ax = axes[1, 1]
ax.scatter(normal['antiguedad_cuenta_dias'], np.log1p(normal['monto_pyg']),
           alpha=0.1, s=6, c='#2ecc71', label='Normal', edgecolors='none')
ax.scatter(fraude['antiguedad_cuenta_dias'], np.log1p(fraude['monto_pyg']),
           alpha=0.5, s=18, c='#e74c3c', label='Fraude', edgecolors='black', linewidth=0.3)
ax.set_xlabel('Antigüedad cuenta (días)')
ax.set_ylabel('log1p(monto_pyg)')
ax.set_title('Antigüedad vs Monto', fontweight='bold')
ax.legend(markerscale=3)

plt.suptitle('Scatter Plots: Separación de Clases en el Espacio de Features',
             fontsize=15, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / '04_scatter_plots.png', dpi=120, bbox_inches='tight')
plt.show()

# ==============================================================================
# 7. GRÁFICO 5: HISTOGRAMAS DE FEATURES BINARIAS POR CLASE
# ==============================================================================
bin_features = [
    'dispositivo_nuevo', 'ubicacion_inusual', 'destinatario_nuevo',
    'hora_atipica', 'es_horario_nocturno', 'es_fin_de_semana', 'es_fin_de_mes'
]

fig, axes = plt.subplots(2, 4, figsize=(20, 10))
axes = axes.flatten()

for i, feat in enumerate(bin_features):
    ax = axes[i]
    # Tasa de positividad por clase
    rates = df.groupby('es_fraude')[feat].mean() * 100
    bars = ax.bar(['Normal', 'Fraude'], rates.values,
                  color=['#2ecc71', '#e74c3c'], edgecolor='black')
    for bar, val in zip(bars, rates.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{val:.1f}%', ha='center', fontweight='bold')
    ax.set_title(feat, fontweight='bold')
    ax.set_ylabel('% de casos con valor=1')
    ax.set_ylim(0, 105)

# Ocultar el último subplot vacío
axes[-1].axis('off')

plt.suptitle('Tasa de Activación de Features Binarias por Clase',
             fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / '05_features_binarias.png', dpi=120, bbox_inches='tight')
plt.show()

# Tabla resumen
print("\n" + "="*70)
print(" TASA DE ACTIVACIÓN DE FEATURES BINARIAS (% valor=1)")
print("="*70)
resumen = df.groupby('es_fraude')[bin_features].mean() * 100
resumen.index = ['Normal', 'Fraude']
print(resumen.round(2).to_string())

# ==============================================================================
# 8. GRÁFICO 6: PERFIL POR ESCENARIO DE FRAUDE
# ==============================================================================
scenarios = ['F1_toma_cuenta', 'F2_rafaga_salidas', 'F3_engano', 'F4_pruebas_pequenas']
df_esc = df[df['escenario_fraude'].isin(scenarios)]

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
axes = axes.flatten()

profile_features = ['dispositivo_nuevo', 'ubicacion_inusual', 'destinatario_nuevo', 'hora_atipica']

for i, feat in enumerate(profile_features):
    ax = axes[i]
    rates = df_esc.groupby('escenario_fraude')[feat].mean() * 100
    rates = rates.reindex(scenarios)
    bars = ax.barh(rates.index, rates.values, color='#e74c3c', edgecolor='black')
    for bar, val in zip(bars, rates.values):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                f'{val:.1f}%', va='center', fontweight='bold')
    ax.set_title(f'{feat} por escenario', fontweight='bold')
    ax.set_xlabel('% valor=1')
    ax.set_xlim(0, 105)

plt.suptitle('Perfil de Features Binarias por Escenario de Fraude',
             fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / '06_perfil_escenarios.png', dpi=120, bbox_inches='tight')
plt.show()

# ==============================================================================
# 9. GRÁFICO 7: DISTRIBUCIÓN DE MONTOS Y TIPOS (redondos vs no redondos)
# ==============================================================================
fig, axes = plt.subplots(1, 3, figsize=(20, 5))

# 9.1 Histograma de montos (normal y fraude)
ax = axes[0]
ax.hist(np.log1p(df[df['es_fraude'] == 0]['monto_pyg']), bins=80,
        alpha=0.6, color='#2ecc71', label='Normal', density=True)
ax.hist(np.log1p(df[df['es_fraude'] == 1]['monto_pyg']), bins=80,
        alpha=0.6, color='#e74c3c', label='Fraude', density=True)
ax.set_xlabel('log1p(monto_pyg)')
ax.set_ylabel('Densidad')
ax.set_title('Distribución de montos por clase', fontweight='bold')
ax.legend()

# 9.2 Proporción redondos vs no redondos (global)
ax = axes[1]
redondo_global = (df['monto_pyg'] % 1000 == 0).mean() * 100
no_redondo_global = 100 - redondo_global
ax.pie([redondo_global, no_redondo_global],
       labels=['Redondo\n(múltiplo de 1000)', 'No redondo'],
       autopct='%.1f%%', colors=['#3498db', '#f39c12'],
       startangle=90, textprops={'fontweight': 'bold'})
ax.set_title('Tipo de monto (global)', fontweight='bold')

# 9.3 Proporción redondos por clase
ax = axes[2]
redondo_por_clase = df.groupby('es_fraude')['monto_pyg'].apply(
    lambda x: (x % 1000 == 0).mean() * 100
)
bars = ax.bar(['Normal', 'Fraude'], redondo_por_clase.values,
              color=['#2ecc71', '#e74c3c'], edgecolor='black')
for bar, val in zip(bars, redondo_por_clase.values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
            f'{val:.1f}%', ha='center', fontweight='bold')
ax.set_title('Montos redondos por clase', fontweight='bold')
ax.set_ylabel('% de montos redondos')
ax.set_ylim(0, 100)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / '07_montos_tipos.png', dpi=120, bbox_inches='tight')
plt.show()

# ==============================================================================
# 10. GRÁFICO 8: COHERENCIA MATEMÁTICA (ratio vs monto/promedio)
# ==============================================================================
# Verificar que ratio_monto_vs_promedio ≈ monto_pyg / monto_promedio_usuario_30d
ratio_calculado = df['monto_pyg'] / df['monto_promedio_usuario_30d'].clip(lower=1)
diferencia = (df['ratio_monto_vs_promedio'] - ratio_calculado).abs()

fig, axes = plt.subplots(1, 2, figsize=(16, 5))

# 10.1 Dispersión del error
ax = axes[0]
ax.scatter(ratio_calculado, df['ratio_monto_vs_promedio'],
           alpha=0.1, s=5, c='#3498db')
ax.plot([0, ratio_calculado.max()], [0, ratio_calculado.max()],
        'r--', label='y = x (coherencia perfecta)')
ax.set_xlabel('ratio calculado (monto / promedio)')
ax.set_ylabel('ratio_monto_vs_promedio (columna)')
ax.set_title('Coherencia del ratio', fontweight='bold')
ax.legend()
ax.set_xlim(0, 60)
ax.set_ylim(0, 60)

# 10.2 Histograma del error absoluto
ax = axes[1]
ax.hist(diferencia, bins=50, color='#3498db', edgecolor='black')
ax.axvline(diferencia.mean(), color='red', linestyle='--',
           label=f'Error medio: {diferencia.mean():.4f}')
ax.set_xlabel('|ratio_columna - ratio_calculado|')
ax.set_ylabel('Frecuencia')
ax.set_title('Distribución del error de coherencia', fontweight='bold')
ax.legend()

plt.tight_layout()
plt.savefig(OUTPUT_DIR / '08_coherencia_ratio.png', dpi=120, bbox_inches='tight')
plt.show()

print("\n" + "="*70)
print(" COHERENCIA MATEMÁTICA DEL RATIO")
print("="*70)
print(f"Error medio absoluto:    {diferencia.mean():.6f}")
print(f"Error máximo:            {diferencia.max():.6f}")
print(f"Filas con error > 0.01:  {(diferencia > 0.01).sum():,} ({(diferencia > 0.01).mean()*100:.2f}%)")

# ==============================================================================
# 11. RESUMEN ESTADÍSTICO POR CLASE
# ==============================================================================
print("\n" + "="*70)
print(" RESUMEN ESTADÍSTICO POR CLASE")
print("="*70)
resumen_stats = df.groupby('es_fraude')[feature_cols].agg(['mean', 'median', 'std']).T
resumen_stats.columns = ['Normal_mean', 'Fraude_mean',
                          'Normal_median', 'Fraude_median',
                          'Normal_std', 'Fraude_std']
resumen_stats['ratio_fraude_normal'] = (
    resumen_stats['Fraude_mean'] / resumen_stats['Normal_mean'].replace(0, np.nan)
)
print(resumen_stats.round(2).to_string())

# ==============================================================================
# 12. VEREDICTO FINAL
# ==============================================================================
print("\n" + "="*70)
print(" VEREDICTO DE CALIDAD")
print("="*70)

checks = []

# Check 1: desbalance esperado
checks.append(('Desbalance ~0.1%', 0.09 <= pct_fraude <= 0.11))

# Check 2: sin nulos
checks.append(('Sin valores nulos', nulos.sum() == 0))

# Check 3: sin duplicados
checks.append(('Sin duplicados', dup == 0))

# Check 4: montos enteros
checks.append(('Montos enteros', df['monto_pyg'].apply(lambda x: float(x).is_integer()).all()))

# Check 5: montos dentro del límite SPI
checks.append(('Montos ≤ ₲ 10M', (df['monto_pyg'] <= 10_000_000).all()))

# Check 6: montos ≥ ₲ 1.000
checks.append(('Montos ≥ ₲ 1.000', (df['monto_pyg'] >= 1_000).all()))

# Check 7: coherencia del ratio
checks.append(('Coherencia del ratio (error < 0.01)', (diferencia > 0.01).mean() < 0.05))

# Check 8: hay fraude en los 4 escenarios
checks.append(('4 escenarios presentes', df[df['es_fraude']==1]['escenario_fraude'].nunique() == 4))

# Check 9: ratio de fraude claramente mayor en fraudes
checks.append(('Ratio mayor en fraudes',
               df[df['es_fraude']==1]['ratio_monto_vs_promedio'].mean() >
               df[df['es_fraude']==0]['ratio_monto_vs_promedio'].mean() * 3))

for nombre, ok in checks:
    print(f"  {'✅' if ok else '❌'} {nombre}")

print(f"\n{'='*70}")
if all(ok for _, ok in checks):
    print(" ✅ DATASET APROBADO PARA ENTRENAMIENTO")
else:
    print(" ⚠️ REVISAR LOS CHECKS FALLIDOS ANTES DE ENTRENAR")
print(f"{'='*70}")

# Gráficos guardados
print(f"\n📁 Gráficos guardados en: {OUTPUT_DIR.resolve()}")
for f in sorted(OUTPUT_DIR.glob('*.png')):
    print(f"   • {f.name}")