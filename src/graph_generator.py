import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt

CONFIGURACIONES = {
    "base": "Baseline",
    "cuts_0": "Cuts=0",
    "presolve_0": "Presolve=0",
    "mipfocus_1": "MIPFocus=1",
    "mipfocus_3": "MIPFocus=3",
    "heuristics_0": "Heuristics=0",
    "tuned": "Tune",
}


def leer_resultados(archivo):
    with open(archivo, encoding="utf-8-sig", newline="") as f:
        muestra = f.read(4096)
        f.seek(0)
        separador = ";" if muestra.splitlines()[0].count(";") > muestra.splitlines()[0].count(",") else ","
        filas = list(csv.DictReader(f, delimiter=separador))

    datos = {}
    for fila in filas:
        instancia = fila.get("instance", "").strip()
        experimento = fila.get("experiment", "").strip()
        if not instancia:
            continue
        if experimento not in CONFIGURACIONES and experimento != "relajado":
            continue  # Ignorar filas de sensibilidad u otros experimentos.
        if not fila.get("objective", "").strip():
            continue
        datos.setdefault(instancia, {})[experimento] = fila
    if not datos:
        raise ValueError("No se encontraron experimentos en el CSV.")
    return datos


def grafico_tiempos(datos, carpeta):
    fig, ejes = plt.subplots(1, len(datos), figsize=(max(8, 6 * len(datos)), 5), squeeze=False)
    for eje, (instancia, filas) in zip(ejes[0], datos.items()):
        configuraciones = [c for c in CONFIGURACIONES if c in filas and filas[c].get("runtime_seconds", "").strip()]
        tiempos = [float(filas[c]["runtime_seconds"]) for c in configuraciones]
        barras = eje.bar(range(len(tiempos)), tiempos)
        eje.set_xticks(range(len(tiempos)), [CONFIGURACIONES[c] for c in configuraciones], rotation=40, ha="right")
        eje.set_title(instancia)
        eje.set_ylabel("Tiempo de resolución (s)")
        eje.grid(axis="y", alpha=0.25)
        eje.set_axisbelow(True)
        eje.bar_label(barras, fmt="%.2f", padding=3, fontsize=8)
        eje.set_ylim(0, max(tiempos, default=1) * 1.18)
    fig.suptitle("Tiempo de resolución por configuración")
    fig.text(0.5, 0.01, "Tune: solo tiempo de resolución posterior al ajuste (no incluye model.tune()).",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.055, 1, 0.96))
    destino = carpeta / "tiempos_configs.png"
    fig.savefig(destino, dpi=200)
    plt.close(fig)
    return destino


def grafico_relajacion(datos, carpeta):
    instancias = [nombre for nombre, filas in datos.items() if "base" in filas and "relajado" in filas]
    if not instancias:
        print("Sin filas 'base' y 'relajado': se omite el gráfico LP vs. MILP.")
        return None
    lp = [float(datos[i]["relajado"]["objective"]) for i in instancias]
    milp = [float(datos[i]["base"]["objective"]) for i in instancias]
    x = list(range(len(instancias)))
    fig, eje = plt.subplots(figsize=(max(7, 3.8 * len(instancias)), 5))
    b1 = eje.bar([v - 0.2 for v in x], lp, 0.4, label="Relajación LP")
    b2 = eje.bar([v + 0.2 for v in x], milp, 0.4, label="Modelo entero (MILP)")
    eje.set_xticks(x, instancias)
    eje.set_ylabel("Distancia total (valor objetivo)")
    eje.set_title("Relajación continua vs. modelo entero")
    eje.legend()
    eje.grid(axis="y", alpha=0.25)
    eje.set_axisbelow(True)
    eje.bar_label(b1, fmt="%.2f", padding=3)
    eje.bar_label(b2, fmt="%.2f", padding=3)
    for idx, (v_lp, v_milp) in enumerate(zip(lp, milp)):
        brecha = (v_milp - v_lp) / v_milp * 100 if v_milp else 0
        eje.text(idx, max(v_lp, v_milp) * 1.1, f"Brecha: {brecha:.1f}%", ha="center", fontsize=10)
    eje.set_ylim(0, max(milp) * 1.25)
    fig.tight_layout()
    destino = carpeta / "relajacion_vs_milp.png"
    fig.savefig(destino, dpi=200)
    plt.close(fig)
    return destino


def main():
    parser = argparse.ArgumentParser(description="Gráficos esenciales de resultados conVRP")
    parser.add_argument("csv", help="Archivo results.csv de los experimentos")
    parser.add_argument("--output-dir", default="graficos_finales", help="Carpeta de salida")
    args = parser.parse_args()
    carpeta = Path(args.output_dir)
    carpeta.mkdir(parents=True, exist_ok=True)
    datos = leer_resultados(args.csv)
    for grafico in (grafico_tiempos(datos, carpeta), grafico_relajacion(datos, carpeta)):
        if grafico:
            print(f"Generado: {grafico}")


if __name__ == "__main__":
    main()
