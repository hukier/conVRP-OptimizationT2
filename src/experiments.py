"""Experimentos reproducibles del modelo conVRP.

Las corridas MIP y LP usan siempre Threads=1 y TimeLimit=600. El ajuste
automático tiene un límite total separado (TuneTimeLimit) de 120 segundos.
"""

import argparse
from pathlib import Path
from time import perf_counter

import pandas as pd
from gurobipy import GRB

from instance_loader import load_instance
from model import build_model
from solver import run_model, STATUS_NAMES


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTANCE_DIR = REPO_ROOT / "data"
RESULTS_DIR = REPO_ROOT / "results"
RESULTS_FILE = RESULTS_DIR / "results.csv"
SENSITIVITY_FILE = RESULTS_DIR / "sensitivity.csv"

INSTANCE_FILES = ("instance_1_c101_15c.json", "instance_2_rc101_18c.json")
TUNE_TIME_LIMIT = 120
RESTRICTED_LICENSE_LIMIT = 2000

CONFIGURATIONS = {
    "base": {},
    "cuts_0": {"Cuts": 0},
    "presolve_0": {"Presolve": 0},
    "mipfocus_1": {"MIPFocus": 1},
    "mipfocus_3": {"MIPFocus": 3},
    "heuristics_0": {"Heuristics": 0},
}


def _solution_metrics(model, instance_name, experiment, relax=False):
    """Extrae métricas sin consultar ObjVal cuando no existe incumbente."""
    has_solution = model.SolCount > 0
    try:
        gap_pct = (
            model.MIPGap * 100
            if has_solution and model.IsMIP
            else (0.0 if has_solution and model.Status == GRB.OPTIMAL else None)
        )
    except Exception:
        gap_pct = None

    return {
        "instance": instance_name,
        "experiment": experiment,
        "relaxation": relax,
        "status": STATUS_NAMES.get(model.Status, str(model.Status)),
        "objective": model.ObjVal if has_solution else None,
        "best_bound": model.ObjBound,
        "gap_pct": gap_pct,
        "runtime_seconds": model.Runtime,
        "solutions_found": model.SolCount,
        "threads": model.Params.Threads,
        "time_limit_seconds": model.Params.TimeLimit,
    }


def _run_tuning(instance, build_model_fn, baseline_result, best_manual):
    """Ejecuta el tuner y vuelve a resolver con su mejor configuración."""
    model, _ = build_model_fn(instance, params={}, relax=False)
    model.Params.Threads = 1
    model.Params.TimeLimit = 600
    model.Params.TuneTimeLimit = TUNE_TIME_LIMIT
    model.Params.TuneResults = 1

    start = perf_counter()
    model.tune()
    tuning_wall_seconds = perf_counter() - start

    if model.TuneResultCount < 1:
        row = {
            "instance": instance["name"],
            "experiment": "tuned",
            "status": "NO_TUNE_RESULT",
            "objective": None,
            "best_bound": None,
            "gap_pct": None,
            "runtime_seconds": None,
            "tuning_wall_seconds": tuning_wall_seconds,
        }
        model.dispose()
        return row

    model.getTuneResult(0)
    # Blindar los parámetros de comparación tras recuperar el set afinado.
    model.Params.Threads = 1
    model.Params.TimeLimit = 600
    model.optimize()
    row = _solution_metrics(model, instance["name"], "tuned")
    row["tuning_wall_seconds"] = tuning_wall_seconds
    row["tune_time_limit_seconds"] = TUNE_TIME_LIMIT
    row["baseline_objective"] = baseline_result["objective"]
    row["baseline_runtime_seconds"] = baseline_result["runtime_seconds"]
    row["baseline_gap_pct"] = baseline_result["gap_pct"]
    row["best_manual_experiment"] = best_manual["experiment"] if best_manual else None
    row["best_manual_objective"] = best_manual["objective"] if best_manual else None
    row["best_manual_runtime_seconds"] = (
        best_manual["runtime_seconds"] if best_manual else None
    )
    row["best_manual_gap_pct"] = best_manual["gap_pct"] if best_manual else None
    if row["objective"] is not None and baseline_result["objective"] is not None:
        row["delta_vs_baseline"] = row["objective"] - baseline_result["objective"]
    else:
        row["delta_vs_baseline"] = None
    if (
        row["runtime_seconds"] is not None
        and baseline_result["runtime_seconds"] is not None
    ):
        row["runtime_delta_vs_baseline_seconds"] = (
            row["runtime_seconds"] - baseline_result["runtime_seconds"]
        )
    if (
        row["objective"] is not None
        and best_manual
        and best_manual["objective"] is not None
    ):
        row["delta_vs_best_manual"] = row["objective"] - best_manual["objective"]
    else:
        row["delta_vs_best_manual"] = None
    if row["runtime_seconds"] is not None and best_manual:
        row["runtime_delta_vs_best_manual_seconds"] = (
            row["runtime_seconds"] - best_manual["runtime_seconds"]
        )
    model.dispose()
    return row


def sensitivity_capacity(model, instance):
    """Fija enteras y extrae Pi, holgura y rangos RHS de capacidad."""
    if model.SolCount == 0:
        return [
            {
                "instance": instance["name"],
                "experiment": "sensitivity_capacity",
                "status": "NO_INTEGER_SOLUTION",
            }
        ]

    fixed_model = model.fixed()
    fixed_model.Params.Threads = 1
    fixed_model.Params.TimeLimit = 600
    fixed_model.optimize()

    if fixed_model.Status != GRB.OPTIMAL:
        row = {
            "instance": instance["name"],
            "experiment": "sensitivity_capacity",
            "status": STATUS_NAMES.get(fixed_model.Status, str(fixed_model.Status)),
        }
        fixed_model.dispose()
        return [row]

    records = []
    for r in instance["vehicles"]:
        for t in instance["days"]:
            name = f"Capacidad_{r}_{t}"
            constr = fixed_model.getConstrByName(name)
            if constr is None:
                continue
            records.append(
                {
                    "instance": instance["name"],
                    "experiment": "sensitivity_capacity",
                    "status": "OPTIMAL_LP_FIXED",
                    "route": r,
                    "day": t,
                    "capacity_rhs": constr.RHS,
                    "slack": constr.Slack,
                    "shadow_price_pi": constr.Pi,
                    "SARHSLow": constr.SARHSLow,
                    "SARHSUp": constr.SARHSUp,
                    "fixed_lp_objective": fixed_model.ObjVal,
                    "threads": fixed_model.Params.Threads,
                    "time_limit_seconds": fixed_model.Params.TimeLimit,
                }
            )
    fixed_model.dispose()
    return records


def calculate_gap(results):
    """Brecha LP/MILP usando el incumbente entero disponible."""
    baseline = next((row for row in results if row.get("experiment") == "base"), None)
    relaxation = next(
        (row for row in results if row.get("experiment") == "relajado"), None
    )
    if baseline is None or relaxation is None:
        return None

    lp_obj, milp_incumbent = relaxation.get("objective"), baseline.get("objective")
    gap = None
    if (
        relaxation.get("status") == "OPTIMAL"
        and lp_obj is not None
        and milp_incumbent is not None
        and milp_incumbent > 0
    ):
        gap = (milp_incumbent - lp_obj) / milp_incumbent * 100
    baseline["integrality_gap_pct"] = gap
    relaxation["integrality_gap_pct"] = gap
    return gap


def run_experiments(instance, build_model_fn=build_model, run_model_fn=run_model):
    return run_experiments_with_size_check(
        instance, build_model_fn, run_model_fn, allow_large=False
    )


def run_experiments_with_size_check(
    instance, build_model_fn, run_model_fn, allow_large=False
):
    """Preflight size before starting a suite that would fail on a restricted license."""
    sizing_model, _ = build_model_fn(instance, params={"OutputFlag": 0}, relax=False)
    num_vars, num_constrs = sizing_model.NumVars, sizing_model.NumConstrs
    sizing_model.dispose()
    if not allow_large and (
        num_vars > RESTRICTED_LICENSE_LIMIT or num_constrs > RESTRICTED_LICENSE_LIMIT
    ):
        return [
            {
                "instance": instance["name"],
                "experiment": "preflight",
                "status": "SKIPPED_RESTRICTED_LICENSE_SIZE",
                "variables": num_vars,
                "constraints": num_constrs,
                "license_limit": RESTRICTED_LICENSE_LIMIT,
                "note": "Use --allow-large with a suitable Gurobi license, or reduce the instance.",
            }
        ]

    results = []
    baseline_model = None

    # Baseline y comparaciones manuales: cada corrida cambia solo el flag nombrado.
    for experiment_name, params in CONFIGURATIONS.items():
        result, model, _ = run_model_fn(
            instance=instance, build_model=build_model_fn, params=params, relax=False
        )
        result["experiment"] = experiment_name
        results.append(result)
        if experiment_name == "base":
            baseline_model = model  # Se conserva para fixed() de sensibilidad.
        else:
            model.dispose()

    baseline = next(row for row in results if row["experiment"] == "base")
    manual_rows = [
        row
        for row in results
        if row["experiment"] in CONFIGURATIONS and row.get("objective") is not None
    ]
    best_manual = min(
        manual_rows,
        key=lambda row: (row["objective"], row.get("runtime_seconds", float("inf"))),
        default=None,
    )

    lp_result, lp_model, _ = run_model_fn(
        instance=instance,
        build_model=build_model_fn,
        params={"OutputFlag": 0},
        relax=True,
    )
    lp_result["experiment"] = "relajado"
    results.append(lp_result)
    lp_model.dispose()
    calculate_gap(results)

    results.append(_run_tuning(instance, build_model_fn, baseline, best_manual))
    sensitivity_rows = sensitivity_capacity(baseline_model, instance)
    results.extend(sensitivity_rows)
    baseline_model.dispose()
    return results


def save_to_csv(results, filename=RESULTS_FILE):
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results)
    if filename.exists() and filename.stat().st_size:
        # Mantiene un CSV válido cuando nuevas métricas agregan columnas.
        previous = pd.read_csv(filename)
        df = pd.concat([previous, df], ignore_index=True, sort=False)
    df.to_csv(filename, index=False, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecutar experimentos con Gurobi.")
    parser.add_argument(
        "--filename",
        type=str,
        default=str(RESULTS_FILE),
        help="Archivo CSV para las métricas de corridas.",
    )
    parser.add_argument(
        "--sensitivity-file",
        type=str,
        default=str(SENSITIVITY_FILE),
        help="Archivo CSV para filas de sensibilidad de capacidad.",
    )
    parser.add_argument(
        "--allow-large",
        action="store_true",
        help="Omitir la prevalidación de tamaño (requiere licencia adecuada).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Mostrar resumen por corrida."
    )
    args = parser.parse_args()

    paths = [INSTANCE_DIR / name for name in INSTANCE_FILES]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Faltan instancias requeridas: " + ", ".join(map(str, missing))
        )

    for path in paths:
        if args.verbose:
            print(f"\nProcesando instancia: {path.name}")

        instance = load_instance(path)
        rows = run_experiments_with_size_check(
            instance, build_model, run_model, allow_large=args.allow_large
        )
        save_to_csv(rows, args.filename)
        sensitivity_rows = [
            row for row in rows if row.get("experiment") == "sensitivity_capacity"
        ]
        if sensitivity_rows:
            save_to_csv(sensitivity_rows, args.sensitivity_file)

        if args.verbose:
            for row in rows:
                print(
                    f"{row.get('experiment')}: status={row.get('status')}, "
                    f"objective={row.get('objective')}, runtime={row.get('runtime_seconds')}"
                )

    print(f"\nResultados guardados en: {Path(args.filename).resolve()}")
    print(f"Sensibilidad guardada en: {Path(args.sensitivity_file).resolve()}")
