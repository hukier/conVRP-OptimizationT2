"""Experimentos reproducibles del modelo conVRP con CPLEX (docplex + API nativa).

Las corridas MIP y LP usan siempre Threads=1 y TimeLimit=600. El ajuste
automático (tuning) tiene un límite total separado (TUNE_TIME_LIMIT) de 120 s.

Cada ejecución del script genera un run_id con fecha/hora y guarda todo en:

    results/cplex/<run_id>/
        cplex_results_<run_id>.csv        métricas por corrida (todas las instancias)
        cplex_sensitivity_<run_id>.csv    precios sombra / rangos RHS de Capacidad
        cplex_run_<run_id>.json           metadatos (versión CPLEX, args, semillas...)

Además se agrega (append) a results/cplex_results_all.csv y
results/cplex_sensitivity_all.csv, para analizar varias ejecuciones juntas.

Réplicas: --repeats N repite toda la suite con semillas seed_base..seed_base+N-1
(parameters.randomseed). Con Threads=1 cada (instancia, semilla) es reproducible.

Ejemplos:
    python experiments_cplex.py -v
    python experiments_cplex.py --repeats 5 --seed-base 0 --tag final
    python experiments_cplex.py --repeats 3 --skip-tuning --allow-large
"""

import argparse
import json
import math
import os
import platform
import socket
import tempfile
from datetime import datetime
from pathlib import Path
from time import perf_counter

import cplex
import pandas as pd

from instance_loader import load_instance
from cplex_model import build_model

SOLVER = "cplex"

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTANCE_DIR = REPO_ROOT / "data"
RESULTS_DIR = REPO_ROOT / "results"

INSTANCE_FILES = ("instance_1_c101_15c.json", "instance_2_rc101_15c.json")
TIME_LIMIT = 600
TUNE_TIME_LIMIT = 120
THREADS = 1
# CPLEX Community Edition: 1000 variables / 1000 constraints
RESTRICTED_LICENSE_LIMIT = 1000

CONFIGURATIONS = {
    "base": {},
    "cuts_0": {"Cuts": 0},
    "presolve_0": {"Presolve": 0},
    "mipfocus_1": {"MIPFocus": 1},
    "mipfocus_3": {"MIPFocus": 3},
    "heuristics_0": {"Heuristics": 0},
}


# Utilidades


def _clean(x):
    """NaN/inf -> None para que el CSV quede limpio."""
    if x is None:
        return None
    try:
        if math.isnan(x) or math.isinf(x):
            return None
    except TypeError:
        pass
    return x


def _export_lp(model, filename="model.lp"):
    path = os.path.join(tempfile.mkdtemp(), filename)
    model.export_as_lp(path)
    return path


def _base_row(instance, experiment, ctx, relax=False):
    return {
        "solver": SOLVER,
        "run_id": ctx["run_id"],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "replicate": ctx["replicate"],
        "seed": ctx["seed"],
        "instance": instance["name"],
        "experiment": experiment,
        "relaxation": relax,
    }


def _prepare(model, seed, time_limit=TIME_LIMIT):
    """Parámetros fijos de comparación (se aplican DESPUÉS de build_model)."""
    model.parameters.threads = THREADS
    model.parameters.timelimit = time_limit
    model.parameters.randomseed = seed


def _solve_and_measure(model, instance, experiment, ctx, relax=False):
    """Resuelve un modelo docplex y devuelve (fila_de_métricas, solución)."""
    start = perf_counter()
    sol = model.solve()
    wall = perf_counter() - start
    det = model.solve_details

    has_sol = sol is not None
    try:
        best_bound = _clean(det.best_bound)
    except Exception:
        best_bound = None
    try:
        gap = _clean(det.mip_relative_gap)
        gap_pct = gap * 100 if (gap is not None and has_sol) else None
    except Exception:
        gap_pct = None
    try:
        nodes = det.nb_nodes_processed
    except Exception:
        nodes = None

    row = _base_row(instance, experiment, ctx, relax)
    row.update(
        {
            "status": str(det.status),
            "objective": sol.objective_value if has_sol else None,
            "best_bound": best_bound,
            "gap_pct": 0.0 if (has_sol and relax) else gap_pct,
            "runtime_seconds": _clean(det.time),
            "wall_seconds": wall,
            "nodes": nodes,
            "has_solution": has_sol,
            "num_vars": model.number_of_variables,
            "num_constraints": model.number_of_constraints,
            "threads": THREADS,
            "time_limit_seconds": TIME_LIMIT,
        }
    )
    return row, sol


# Tuning (API nativa de CPLEX)
def _run_tuning(model, instance, ctx, baseline, best_manual):
    """Ejecuta tune_problem y re-resuelve con la mejor configuración."""
    c = cplex.Cplex(_export_lp(model))
    for stream in (c.set_log_stream, c.set_results_stream, c.set_warning_stream):
        stream(None)

    c.parameters.threads.set(THREADS)
    c.parameters.randomseed.set(ctx["seed"])
    c.parameters.timelimit.set(TIME_LIMIT)  # límite por corrida de prueba
    c.parameters.tune.timelimit.set(TUNE_TIME_LIMIT)  # límite total del tuning

    start = perf_counter()
    tune_status = c.parameters.tune_problem(
        [(c.parameters.threads.get_id(), THREADS)]  # fijo: no tunear threads
    )
    tuning_wall = perf_counter() - start
    changed = {str(k): v for k, v in c.parameters.get_changed()}

    # Blindar parámetros de comparación tras el tuning
    c.parameters.threads.set(THREADS)
    c.parameters.timelimit.set(TIME_LIMIT)
    c.parameters.randomseed.set(ctx["seed"])

    t0 = perf_counter()
    c.solve()
    wall = perf_counter() - t0

    has_sol = c.solution.is_primal_feasible()
    row = _base_row(instance, "tuned", ctx)
    row.update(
        {
            "status": c.solution.get_status_string(),
            "objective": c.solution.get_objective_value() if has_sol else None,
            "best_bound": _clean(c.solution.MIP.get_best_objective()),
            "gap_pct": 100 * c.solution.MIP.get_mip_relative_gap() if has_sol else None,
            "runtime_seconds": wall,
            "wall_seconds": wall,
            "nodes": c.solution.progress.get_num_nodes_processed(),
            "has_solution": has_sol,
            "threads": THREADS,
            "time_limit_seconds": TIME_LIMIT,
            "tune_status": tune_status,
            "tuning_wall_seconds": tuning_wall,
            "tune_time_limit_seconds": TUNE_TIME_LIMIT,
            "tuned_params": json.dumps(changed, default=str),
            "baseline_objective": baseline["objective"],
            "baseline_runtime_seconds": baseline["runtime_seconds"],
            "baseline_gap_pct": baseline["gap_pct"],
            "best_manual_experiment": best_manual["experiment"]
            if best_manual
            else None,
            "best_manual_objective": best_manual["objective"] if best_manual else None,
            "best_manual_runtime_seconds": best_manual["runtime_seconds"]
            if best_manual
            else None,
            "best_manual_gap_pct": best_manual["gap_pct"] if best_manual else None,
        }
    )

    def _delta(a, b):
        return a - b if a is not None and b is not None else None

    row["delta_vs_baseline"] = _delta(row["objective"], baseline["objective"])
    row["runtime_delta_vs_baseline_seconds"] = _delta(
        row["runtime_seconds"], baseline["runtime_seconds"]
    )
    if best_manual:
        row["delta_vs_best_manual"] = _delta(row["objective"], best_manual["objective"])
        row["runtime_delta_vs_best_manual_seconds"] = _delta(
            row["runtime_seconds"], best_manual["runtime_seconds"]
        )
    c.end()
    return row


# Sensibilidad de capacidad (equivalente a Model.fixed() de Gurobi)


def sensitivity_capacity(model, solution, variables, instance, ctx):
    """Fija X y Z al incumbente, resuelve el LP y extrae Pi, holgura y rangos RHS."""
    if solution is None:
        return [
            {
                **_base_row(instance, "sensitivity_capacity", ctx),
                "status": "NO_INTEGER_SOLUTION",
            }
        ]

    c = cplex.Cplex(_export_lp(model))
    for stream in (c.set_log_stream, c.set_results_stream, c.set_warning_stream):
        stream(None)
    c.parameters.threads.set(THREADS)
    c.parameters.timelimit.set(TIME_LIMIT)

    for dvar in list(variables["X"].values()) + list(variables["Z"].values()):
        v = float(round(solution.get_value(dvar)))
        c.variables.set_lower_bounds(dvar.name, v)
        c.variables.set_upper_bounds(dvar.name, v)

    c.set_problem_type(c.problem_type.LP)
    c.parameters.preprocessing.presolve.set(0)  # base limpia para sensibilidad
    c.solve()

    if c.solution.get_status() not in (1,):  # 1 = CPX_STAT_OPTIMAL
        row = {
            **_base_row(instance, "sensitivity_capacity", ctx),
            "status": c.solution.get_status_string(),
        }
        c.end()
        return [row]

    names = [
        f"Capacidad_{r}_{t}" for r in instance["vehicles"] for t in instance["days"]
    ]
    pairs = [(r, t) for r in instance["vehicles"] for t in instance["days"]]
    rhs = c.linear_constraints.get_rhs(names)
    slack = c.solution.get_linear_slacks(names)
    pi = c.solution.get_dual_values(names)
    ranges = c.solution.sensitivity.rhs(names)
    lp_obj = c.solution.get_objective_value()

    records = []
    for k, (r, t) in enumerate(pairs):
        records.append(
            {
                **_base_row(instance, "sensitivity_capacity", ctx),
                "status": "OPTIMAL_LP_FIXED",
                "route": r,
                "day": t,
                "capacity_rhs": rhs[k],
                "slack": slack[k],
                "shadow_price_pi": pi[k],
                "SARHSLow": ranges[k][0],
                "SARHSUp": ranges[k][1],
                "fixed_lp_objective": lp_obj,
                "threads": THREADS,
                "time_limit_seconds": TIME_LIMIT,
            }
        )
    c.end()
    return records


# Brecha de integralidad
def calculate_gap(results):
    """Brecha LP/MILP usando el incumbente entero del baseline."""
    baseline = next((r for r in results if r.get("experiment") == "base"), None)
    relaxation = next((r for r in results if r.get("experiment") == "relajado"), None)
    if baseline is None or relaxation is None:
        return None

    lp_obj, milp = relaxation.get("objective"), baseline.get("objective")
    gap = None
    if (
        "optimal" in str(relaxation.get("status")).lower()
        and lp_obj is not None
        and milp is not None
        and milp > 0
    ):
        gap = (milp - lp_obj) / milp * 100
    baseline["integrality_gap_pct"] = gap
    relaxation["integrality_gap_pct"] = gap
    return gap


# Suite completa para una instancia y una semilla


def run_experiments(instance, ctx, allow_large=False, skip_tuning=False):
    sizing, _ = build_model(instance, {"OutputFlag": 0}, relax=False)
    n_vars, n_cons = sizing.number_of_variables, sizing.number_of_constraints
    sizing.end()
    if not allow_large and (
        n_vars > RESTRICTED_LICENSE_LIMIT or n_cons > RESTRICTED_LICENSE_LIMIT
    ):
        return [
            {
                **_base_row(instance, "preflight", ctx),
                "status": "SKIPPED_RESTRICTED_LICENSE_SIZE",
                "num_vars": n_vars,
                "num_constraints": n_cons,
                "license_limit": RESTRICTED_LICENSE_LIMIT,
                "note": "Use --allow-large con licencia adecuada o reduzca la instancia.",
            }
        ]

    results = []
    base_model = base_sol = base_vars = None

    for name, params in CONFIGURATIONS.items():
        model, variables = build_model(
            instance, {**params, "OutputFlag": 0}, relax=False
        )
        _prepare(model, ctx["seed"])
        row, sol = _solve_and_measure(model, instance, name, ctx)
        results.append(row)
        if name == "base":
            base_model, base_sol, base_vars = model, sol, variables
        else:
            model.end()

    baseline = next(r for r in results if r["experiment"] == "base")
    manual_rows = [r for r in results if r.get("objective") is not None]
    best_manual = min(
        manual_rows,
        key=lambda r: (r["objective"], r.get("runtime_seconds") or float("inf")),
        default=None,
    )

    lp_model, _ = build_model(instance, {"OutputFlag": 0}, relax=True)
    _prepare(lp_model, ctx["seed"])
    lp_row, _ = _solve_and_measure(lp_model, instance, "relajado", ctx, relax=True)
    results.append(lp_row)
    lp_model.end()
    calculate_gap(results)

    if not skip_tuning:
        results.append(_run_tuning(base_model, instance, ctx, baseline, best_manual))

    results.extend(sensitivity_capacity(base_model, base_sol, base_vars, instance, ctx))
    base_model.end()
    return results


# Guardado


def save_to_csv(results, filename):
    """Append que mantiene un CSV válido cuando aparecen columnas nuevas."""
    if not results:
        return
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results)
    if filename.exists() and filename.stat().st_size:
        df = pd.concat([pd.read_csv(filename), df], ignore_index=True, sort=False)
    df.to_csv(filename, index=False, encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description="Ejecutar experimentos con CPLEX.")
    p.add_argument("--data-dir", default=str(INSTANCE_DIR))
    p.add_argument("--results-dir", default=str(RESULTS_DIR))
    p.add_argument(
        "--instances",
        nargs="+",
        default=list(INSTANCE_FILES),
        help="Nombres de archivo de instancia dentro de --data-dir.",
    )
    p.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Número de réplicas (una semilla distinta por réplica).",
    )
    p.add_argument("--seed-base", type=int, default=0)
    p.add_argument("--tag", default="", help="Etiqueta opcional añadida al run_id.")
    p.add_argument("--skip-tuning", action="store_true")
    p.add_argument(
        "--allow-large",
        action="store_true",
        help="Omitir la prevalidación de tamaño (requiere licencia adecuada).",
    )
    p.add_argument(
        "--no-master",
        action="store_true",
        help="No agregar a los CSV acumulados *_all.csv.",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    paths = [Path(args.data_dir) / n for n in args.instances]
    missing = [x for x in paths if not x.is_file()]
    if missing:
        raise FileNotFoundError("Faltan instancias: " + ", ".join(map(str, missing)))

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + (
        f"_{args.tag}" if args.tag else ""
    )
    run_dir = Path(args.results_dir) / SOLVER / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    results_file = run_dir / f"{SOLVER}_results_{run_id}.csv"
    sens_file = run_dir / f"{SOLVER}_sensitivity_{run_id}.csv"
    master_results = Path(args.results_dir) / f"{SOLVER}_results_all.csv"
    master_sens = Path(args.results_dir) / f"{SOLVER}_sensitivity_all.csv"

    seeds = [args.seed_base + i for i in range(args.repeats)]
    metadata = {
        "run_id": run_id,
        "solver": SOLVER,
        "cplex_version": cplex.Cplex().get_version(),
        "python": platform.python_version(),
        "host": socket.gethostname(),
        "started": datetime.now().isoformat(timespec="seconds"),
        "instances": [x.name for x in paths],
        "seeds": seeds,
        "threads": THREADS,
        "time_limit_seconds": TIME_LIMIT,
        "tune_time_limit_seconds": TUNE_TIME_LIMIT,
        "configurations": CONFIGURATIONS,
        "skip_tuning": args.skip_tuning,
        "args": vars(args),
    }
    (run_dir / f"{SOLVER}_run_{run_id}.json").write_text(
        json.dumps(metadata, indent=2, default=str), encoding="utf-8"
    )

    for rep, seed in enumerate(seeds):
        ctx = {"run_id": run_id, "replicate": rep, "seed": seed}
        for path in paths:
            if args.verbose:
                print(f"\n[{run_id}] réplica {rep} (seed={seed}) - {path.name}")
            instance = load_instance(path)
            rows = run_experiments(
                instance,
                ctx,
                allow_large=args.allow_large,
                skip_tuning=args.skip_tuning,
            )
            sens = [r for r in rows if r.get("experiment") == "sensitivity_capacity"]
            main_rows = [
                r for r in rows if r.get("experiment") != "sensitivity_capacity"
            ]

            # Guardado incremental: una caída no pierde lo ya corrido
            save_to_csv(main_rows, results_file)
            save_to_csv(sens, sens_file)
            if not args.no_master:
                save_to_csv(main_rows, master_results)
                save_to_csv(sens, master_sens)

            if args.verbose:
                for r in main_rows:
                    print(
                        f"  {r.get('experiment')}: status={r.get('status')}, "
                        f"obj={r.get('objective')}, gap%={r.get('gap_pct')}, "
                        f"t={r.get('runtime_seconds')}"
                    )

    print(f"\nResultados:    {results_file.resolve()}")
    print(f"Sensibilidad:  {sens_file.resolve()}")
    print(f"Metadatos:     {(run_dir / f'{SOLVER}_run_{run_id}.json').resolve()}")


if __name__ == "__main__":
    main()
