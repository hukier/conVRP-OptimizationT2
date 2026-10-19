# Guía de lectura de resultados experimentales

## 1. Propósito

Este documento explica cómo interpretar los resultados de los experimentos del modelo de ruteo consistente. Describe las columnas de los archivos CSV, el significado de la brecha de integralidad y del estado `OPTIMAL_LP_FIXED`, y relaciona cada grupo de resultados con los requisitos del enunciado.

## 2. Archivos de salida

El programa está configurado para generar:

- **`results.csv`**: resultados de las corridas baseline, configuraciones del solver, relajación continua, ajuste automático y prechequeo de tamaño.
- **`sensitivity.csv`**: resultados detallados del análisis de sensibilidad de capacidad por ruta y día.

En la salida compartida, las filas `sensitivity_capacity` aparecen también dentro de `results.csv`. Esto ocurre porque todas las filas de experimentos se guardan allí y, además, las filas de sensibilidad se guardan en `sensitivity.csv`. Por lo tanto, son las mismas observaciones repetidas en ambos archivos, no dos análisis distintos. Para evitar duplicación, se puede cambiar el guardado para excluir esas filas de `results.csv`.

Al volver a ejecutar el programa, las filas nuevas se agregan a los CSV existentes. Para generar resultados limpios, se deben respaldar, mover o eliminar los CSV anteriores antes de ejecutar otra vez.

## 3. Significado de las columnas

Los CSV reúnen distintos tipos de filas. Por eso una columna puede estar vacía cuando no aplica al experimento de esa fila.

### 3.1 Identificación y estado de la corrida

| Columna | Significado |
|---|---|
| `instance` | Nombre de la instancia analizada. En el archivo recibido, el encabezado aparece como `nstance`; debería corregirse a `instance`. |
| `experiment` | Tipo de experimento: `base`, `cuts_0`, `presolve_0`, `mipfocus_1`, `mipfocus_3`, `heuristics_0`, `relajado`, `tuned`, `sensitivity_capacity` o `preflight`. |
| `relaxation` | `True` cuando se resolvió la relajación continua; `False` para el modelo entero. Puede estar vacía en filas que no son corridas MIP/LP ordinarias. |
| `status` | Estado final reportado por Gurobi o por el prechequeo. Ejemplos: `OPTIMAL`, `OPTIMAL_LP_FIXED` y `SKIPPED_RESTRICTED_LICENSE_SIZE`. |
| `solutions_found` | Cantidad de soluciones factibles encontradas por Gurobi durante la corrida. |

### 3.2 Objetivo, cotas, gap y tiempo

| Columna | Significado |
|---|---|
| `objective` | Valor de la función objetivo de la solución encontrada, si existe una solución factible. |
| `best_bound` | Mejor cota dual del solver. En una corrida minimizada que termina óptima coincide, salvo redondeo, con `objective`. |
| `gap_pct` | Gap de optimalidad de Gurobi, expresado en porcentaje. Un valor de `0.0` indica que el solver cerró el gap dentro de su tolerancia. |
| `runtime_seconds` | Tiempo de optimización reportado para esa corrida, en segundos. No incluye necesariamente todo el tiempo de preparación o el tiempo empleado por `model.tune()`. |
| `threads` | Número de hilos configurado para la corrida. El requisito es usar `1`. |
| `time_limit_seconds` | Límite de tiempo de optimización, en segundos. El requisito es `600`. |
| `integrality_gap_pct` | Brecha entre la solución entera baseline y la relajación LP, calculada como `(z_MILP - z_LP) / z_MILP × 100`. |

### 3.3 Ajuste automático y comparaciones

| Columna | Significado |
|---|---|
| `tuning_wall_seconds` | Tiempo de pared consumido por la etapa `model.tune()`. |
| `tune_time_limit_seconds` | Límite asignado al proceso de tuning; en los resultados compartidos es `120` segundos. |
| `baseline_objective` | Objetivo del experimento baseline, usado como referencia para el tuning. |
| `baseline_runtime_seconds` | Tiempo del baseline. |
| `baseline_gap_pct` | Gap de optimalidad del baseline. |
| `best_manual_experiment` | Nombre de la configuración manual seleccionada para comparar con el tuning. |
| `best_manual_objective` | Objetivo de esa configuración manual. |
| `best_manual_runtime_seconds` | Tiempo de esa configuración manual. |
| `best_manual_gap_pct` | Gap de esa configuración manual. |
| `delta_vs_baseline` | Diferencia de objetivo: objetivo de `tuned` menos objetivo de `base`. Un valor negativo significa que `tuned` encontró un objetivo menor. |
| `runtime_delta_vs_baseline_seconds` | Diferencia de tiempo: tiempo de `tuned` menos tiempo de `base`. Un valor negativo significa que `tuned` fue más rápido. |
| `delta_vs_best_manual` | Diferencia de objetivo entre `tuned` y la configuración manual seleccionada. |
| `runtime_delta_vs_best_manual_seconds` | Diferencia de tiempo entre `tuned` y la configuración manual seleccionada. |

### 3.4 Sensibilidad de capacidad

| Columna | Significado |
|---|---|
| `route` | Vehículo o ruta asociado a la restricción de capacidad. |
| `day` | Día al que corresponde la restricción. |
| `capacity_rhs` | Lado derecho de la restricción de capacidad, es decir, la capacidad máxima `Q`. |
| `slack` | Holgura de la restricción. Cero indica que la capacidad se usa por completo; un valor positivo indica capacidad disponible. |
| `shadow_price_pi` | Precio sombra (`Pi`) de la restricción en el LP fijado. Mide el cambio marginal local del objetivo ante un cambio unitario en `Q`, dentro del rango de sensibilidad. |
| `SARHSLow` | Límite inferior del lado derecho para el cual se mantiene la base óptima actual del LP fijado. |
| `SARHSUp` | Límite superior correspondiente. `inf` indica que no se reporta un límite superior finito. |
| `fixed_lp_objective` | Valor objetivo del LP obtenido tras fijar las decisiones enteras de la solución MIP. |

### 3.5 Prechequeo del tamaño

| Columna | Significado |
|---|---|
| `variables` | Número de variables del modelo detectado antes de ejecutar la suite de experimentos. |
| `constraints` | Número de restricciones detectado en el prechequeo. |
| `license_limit` | Umbral de tamaño configurado para omitir instancias grandes cuando se usa una licencia restringida. |
| `note` | Explicación del resultado del prechequeo o de la acción sugerida. |

## 4. ¿Por qué la brecha de integralidad aparece solo en dos filas?

La brecha requiere comparar dos resultados: el baseline entero y la relajación LP. Por eso `integrality_gap_pct` se escribe solamente en las filas `base` y `relajado`. En los resultados compartidos, ambas filas muestran **74.5946 %**.

Las configuraciones `cuts_0`, `presolve_0`, `mipfocus_1`, `mipfocus_3` y `heuristics_0` son comparaciones entre corridas enteras, no comparaciones LP/MILP. El tuning, la sensibilidad y el prechequeo tampoco forman parte del cálculo; por eso esas filas dejan la columna vacía.

La fórmula usa el objetivo del baseline como valor entero. Si ese baseline no terminara óptimo, la cantidad sería una brecha respecto al mejor incumbente encontrado, no necesariamente respecto al óptimo entero global. En este caso el baseline reporta `OPTIMAL`, así que la comparación es con el óptimo hallado.

## 5. ¿Qué significa `OPTIMAL_LP_FIXED`?

El estado `OPTIMAL_LP_FIXED` indica que se aplicó `Model.fixed()` a una solución entera factible: Gurobi fijó las variables enteras según esa solución y resolvió el modelo resultante como un LP. `OPTIMAL_LP_FIXED` es una etiqueta descriptiva del programa; el estado nativo de Gurobi para la optimización resultante fue óptimo.

Este LP permite extraer `Pi`, `SARHSLow` y `SARHSUp` de las restricciones de capacidad. Su objetivo no es una nueva solución del problema entero, sino el objetivo del modelo con las decisiones enteras fijadas.

## 6. Qué requisitos cubren los resultados

### Relajación continua e integralidad

Las filas `base` y `relajado` cubren la comparación del modelo entero con la relajación continua. Se utilizan `objective`, `best_bound`, `gap_pct` e `integrality_gap_pct`. La relajación entrega una cota inferior para un problema de minimización porque amplía la región factible al permitir valores fraccionarios en las variables que eran binarias.

### Configuraciones manuales

Las filas `base`, `cuts_0`, `presolve_0`, `mipfocus_1`, `mipfocus_3` y `heuristics_0` cubren la comparación de configuraciones. Se reportan principalmente `objective`, `runtime_seconds` y `gap_pct`. Cada variante debe diferir del baseline únicamente en el parámetro indicado.

### Ajuste automático

La fila `tuned` cubre la ejecución de `model.tune()` y la comparación frente al baseline y la configuración manual seleccionada. Se usan las columnas `tuning_wall_seconds`, `tune_time_limit_seconds`, las métricas del solver y los deltas de objetivo/tiempo.

### Análisis de sensibilidad

Las filas `sensitivity_capacity` cubren el análisis de las restricciones de capacidad `Q` mediante `Model.fixed()`. Las columnas clave son `route`, `day`, `capacity_rhs`, `slack`, `shadow_price_pi`, `SARHSLow` y `SARHSUp`.

### Parámetros de ejecución

`threads = 1` y `time_limit_seconds = 600` documentan la configuración solicitada para las corridas de comparación. El límite de tuning (`tune_time_limit_seconds`) es un parámetro separado del límite de cada optimización.

## 7. Resumen de los resultados compartidos

- **Instancia C101 (`instance_1_c101_15c`)**: baseline y cinco configuraciones manuales terminaron `OPTIMAL` con objetivo **511.19** y gap **0 %**. `heuristics_0` fue la más rápida en esa ejecución (**9.03 s**); el baseline tardó **10.45 s**. Son tiempos de una sola corrida y no prueban por sí solos una ventaja reproducible.
- **Relajación C101**: objetivo LP **129.87**; brecha de integralidad **74.5946 %**. La cota inferior es válida, aunque relativamente débil frente al óptimo entero de esta instancia.
- **Tuning C101**: consumió aproximadamente **99.99 s** de tuning. La corrida posterior con el conjunto afinado reportó objetivo **511.19** y tiempo **10.40 s**, esencialmente igual al baseline. No se observa una mejora práctica clara en el tiempo de resolución de esta corrida.
- **Sensibilidad C101**: los nueve pares ruta-día tienen `Pi = 0`. Ocho tienen holgura positiva y uno está activo (ruta 2, día 2, holgura 0). Los rangos reportados son locales al LP fijado y no describen necesariamente el comportamiento del problema entero si cambia la capacidad.
- **Instancia RC101 (`instance_2_rc101_18c`)**: no se ejecutó la suite. El prechequeo reportó **2,199 variables** y **2,550 restricciones**, por encima del umbral configurado de **2,000**, con estado `SKIPPED_RESTRICTED_LICENSE_SIZE`.

## 8. Observaciones para presentar los resultados

1. Corregir el encabezado `nstance` a `instance`.
2. Presentar sensibilidad en un solo archivo para evitar filas duplicadas entre `results.csv` y `sensitivity.csv`.
3. Todas las configuraciones manuales alcanzaron el mismo objetivo óptimo. Para desempatar cuál fue más rápida, comparar `runtime_seconds`; en estos datos fue `heuristics_0`.
4. No interpretar `Pi = 0` como que la capacidad nunca importa. El precio sombra corresponde al LP con decisiones enteras fijadas y solo es válido localmente dentro del rango indicado por `SARHSLow` y `SARHSUp`.
5. Informar que RC101 fue omitida por el umbral de tamaño, por lo que las conclusiones numéricas compartidas corresponden únicamente a C101.
