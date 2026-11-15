# Experimentos conVRP con CPLEX

Script `experiments_cplex.py`: ejecuta de forma automática y reproducible la suite de experimentos del modelo conVRP usando CPLEX (docplex + API nativa `cplex`). Es el equivalente del script de Gurobi.

## Qué hace

Para cada instancia y cada réplica (semilla) ejecuta:

| Experimento | Descripción |
| --- | --- |
| `base` | MILP con parámetros por defecto |
| `cuts_0` | `Cuts=0` |
| `presolve_0` | `Presolve=0` |
| `mipfocus_1` | `MIPFocus=1` |
| `mipfocus_3` | `MIPFocus=3` |
| `heuristics_0` | `Heuristics=0` |
| `relajado` | Relajación continua (LP) y brecha de integralidad |
| `tuned` | Herramienta de tuning de CPLEX + re-resolución con la mejor configuración |
| `sensitivity_capacity` | Fija X y Z al incumbente del `base`, resuelve el LP y extrae precio sombra, holgura y rango del RHS de `Capacidad_{r}_{t}` |

Parámetros fijos en todas las corridas: `Threads=1`, `TimeLimit=600 s`. El tuning tiene un límite total aparte de `120 s`.

## Requisitos

- Python 3.9+
- CPLEX (con la API de Python `cplex` y `docplex` instalados)
- `pandas`

```bash
pip install -r requirements.txt # desde la raiz 
```

## Estructura del repositorio

```
repo/
├── data/
│   ├── instance_1_c101_15c.json
│   └── instance_2_rc101_15c.json
├── results/
└── src/
    ├── experiments_cplex.py
    ├── instance_loader.py       # load_instance(path)
    └── cplex_model.py           # build_model(instance, params, relax)
```

`DATA_DIR` y `RESULTS_DIR` se calculan respecto a la carpeta padre de `src/`. Se pueden cambiar con `--data-dir` y `--results-dir`.

## Uso

Ejecutar desde `src/`:

```bash
# Corrida simple (1 réplica, seed 0), con resumen por pantalla
python experiments_cplex.py -v

# 5 réplicas con semillas 0..4 y una etiqueta para identificar la corrida
python experiments_cplex.py --repeats 5 --seed-base 0 --tag final -v

# Sin tuning (mucho más rápido)
python experiments_cplex.py --repeats 3 --skip-tuning

# Solo una instancia
python experiments_cplex.py --instances instance_1_c101_15c.json

# Licencia completa: omitir la verificación de tamaño
python experiments_cplex.py --allow-large
```

Prueba rápida recomendada antes de una corrida larga:

```bash
python experiments_cplex.py --repeats 1 --skip-tuning -v --tag prueba
```

### Argumentos

| Argumento | Por defecto | Descripción |
| --- | --- | --- |
| `--data-dir` | `<repo>/data` | Carpeta con las instancias |
| `--results-dir` | `<repo>/results` | Carpeta de resultados |
| `--instances` | las 2 instancias 15c | Nombres de archivo dentro de `--data-dir` |
| `--repeats` | `1` | Número de réplicas |
| `--seed-base` | `0` | Primera semilla; la réplica `i` usa `seed_base + i` |
| `--tag` | vacío | Etiqueta añadida al `run_id` |
| `--skip-tuning` | desactivado | No ejecutar el tuning |
| `--allow-large` | desactivado | Omitir la verificación del límite de licencia |
| `--no-master` | desactivado | No agregar a los CSV acumulados `*_all.csv` |
| `-v`, `--verbose` | desactivado | Imprimir resumen por corrida |

## Archivos de salida

Cada ejecución genera un `run_id` con la fecha y hora (`YYYYMMDD_HHMMSS`, más `_<tag>` si se usa `--tag`):

```
results/
├── cplex/
│   └── 20261115_143000_final/
│       ├── cplex_results_20261115_143000_final.csv
│       ├── cplex_sensitivity_20261115_143000_final.csv
│       └── cplex_run_20261115_143000_final.json
├── cplex_results_all.csv          # acumulado de todas las ejecuciones
└── cplex_sensitivity_all.csv
```

- **`cplex_results_<run_id>.csv`**: una fila por (instancia, réplica, experimento).
- **`cplex_sensitivity_<run_id>.csv`**: una fila por (instancia, réplica, ruta, día).
- **`cplex_run_<run_id>.json`**: metadatos para reproducir la corrida (versión de CPLEX, host, versión de Python, semillas, argumentos, configuraciones, límites).
- **`*_all.csv`**: se agregan filas en cada ejecución; se distinguen por `run_id`.

Los archivos se guardan después de cada instancia y réplica, así que si algo falla no se pierde lo ya calculado.

## Columnas principales

**Identificación:** `solver`, `run_id`, `timestamp`, `replicate`, `seed`, `instance`, `experiment`, `relaxation`

**Métricas:** `status`, `objective`, `best_bound`, `gap_pct`, `runtime_seconds`, `wall_seconds`, `nodes`, `has_solution`, `num_vars`, `num_constraints`, `threads`, `time_limit_seconds`

**Relajación:** `integrality_gap_pct` (en las filas `base` y `relajado`)

**Solo en `tuned`:** `tune_status`, `tuning_wall_seconds`, `tune_time_limit_seconds`, `tuned_params` (JSON con los parámetros cambiados), `baseline_*`, `best_manual_*`, `delta_vs_baseline`, `runtime_delta_vs_baseline_seconds`, `delta_vs_best_manual`, `runtime_delta_vs_best_manual_seconds`

**Solo en sensibilidad:** `route`, `day`, `capacity_rhs`, `slack`, `shadow_price_pi`, `SARHSLow`, `SARHSUp`, `fixed_lp_objective`

## Reproducibilidad

- Con `Threads=1` y la misma semilla, cada (instancia, experimento) es reproducible en la misma versión de CPLEX.
- Para reproducir una corrida, revisa el `.json` de metadatos y ejecuta con los mismos `--seed-base`, `--repeats` e instancias.
- Las réplicas con distintas semillas sirven para medir la variabilidad entre corridas.

## Análisis de resultados (ejemplo)

```python
import pandas as pd

df = pd.read_csv("results/cplex_results_all.csv")

resumen = (
    df[df["experiment"] != "relajado"]
    .groupby(["instance", "experiment"])
    .agg(
        obj_media=("objective", "mean"),
        obj_std=("objective", "std"),
        tiempo_medio=("runtime_seconds", "mean"),
        gap_medio=("gap_pct", "mean"),
        n=("replicate", "count"),
    )
)
print(resumen)

# Brecha de integralidad
print(df[df["experiment"] == "base"][["instance", "seed", "integrality_gap_pct"]])

# Sensibilidad de capacidad
sens = pd.read_csv("results/cplex_sensitivity_all.csv")
print(sens[["instance", "route", "day", "shadow_price_pi", "SARHSLow", "SARHSUp"]].head())
```

## Notas y limitaciones

- `status` es el texto de estado de CPLEX (por ejemplo "integer optimal solution" o "time limit exceeded").
- Si una corrida no encuentra solución factible, `objective` queda vacío y `has_solution` es `False`.
- El "mejor manual" se elige por menor objetivo y, en caso de empate, menor tiempo (asume un problema de minimización).
- Si una instancia excede el límite de licencia y no se usa `--allow-large`, se registra una fila con `experiment = preflight` y `status = SKIPPED_RESTRICTED_LICENSE_SIZE`.
- El tuning puede tardar mucho con muchas réplicas (hasta 120 s por réplica e instancia, más la re-resolución de hasta 600 s). Usa `--skip-tuning` para pruebas.
- El script espera que `build_model(instance, params, relax)` devuelva `(model, variables)` con `variables["X"]` y `variables["Z"]`, y que `instance` tenga las claves `name`, `vehicles` y `days`.
