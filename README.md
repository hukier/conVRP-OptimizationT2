# conVRP-OptimizationT2

Tarea 2 de la asignatura "Optimización" de la Universidad de Concepcion.

## Instrucciones de Ejecución

Para ejecutar los archivos de experimentos usar los siguientes comandos:

```bash
# instalar librerías
pip install -r requirements.txt 

# ejecutar experimentos
python3 ./src/experiments.py

# adicional: graficar resultados
python3 ./src/graph_generator.py ./results/results.csv --output-dir ./results/graficos_finales
```

Los resultados son guardados en ./results/ con el nombre `resultados.csv` y `sensitivity.csv`.
