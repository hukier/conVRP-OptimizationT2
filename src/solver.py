import gurobipy as gp
from gurobipy import GRB

def print_status(status):

    match status:
        case GRB.OPTIMAL:
            print("An optimal solution was found.")

        case GRB.INFEASIBLE:
            print("No feasible solution exists for the model. You can diagnose this using model.computeIIS().")

        case GRB.UNBOUNDED:
            print("The model is unbounded (the objective can be improved infinitely).")

        case GRB.INF_OR_UNBD:
             print("The model is either infeasible or unbounded             .")

        case GRB.ITERATION_LIMIT:
            print("The solver stopped because it reached the iteration limit.")

        case GRB.NODE_LIMIT:
            print("The solver stopped because it reached the branch-and-bound node limit.")

        case GRB.TIME_LIMIT:
            print("The solver stopped because it reached the time limit.")

        case GRB.INTERRUPTED:
            print("The optimization was interrupted manually (e.g., via Ctrl-C or model.terminate()).")

        case _:
            print(f"Optimization stopped with status code: {status}")model = gp.Model("prueba")


STATUS_NAMES = {
    GRB.OPTIMAL:     "OPTIMAL",
    GRB.TIME_LIMIT:  "TIME_LIMIT",
    GRB.INFEASIBLE:  "INFEASIBLE",
    GRB.UNBOUNDED:   "UNBOUNDED",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.INTERRUPTED: "INTERRUPTED",
}


def run_model(instance, build_model, params=None, relax=False):
    params = params or {}
 
    # construir modelo con las instancias correspondientes
    model, variables = build_model(
        instance,
        params=params,
        relax=relax
    )

    # limites de procesamiento impuestos.
    model.Params.Threads = 1
    model.Params.TimeLimit = 600

    model.optimize()

    has_solution = model.SolCount > 0

    result = {
        "instance": instance["name"],
        "relaxation": relax,
        "status": STATUS_NAMES.get(
            model.Status, str(model.Status)
        ),
        "objective": model.ObjVal if has_solution else None,
        "best_bound": model.ObjBound,
        "gap_pct": (
            model.MIPGap * 100
            if has_solution and model.IsMIP
            else (0.0 if has_solution else None)
        ),
        "runtime_seconds": model.Runtime,
        "solutions_found": model.SolCount,
    }

    return result, model, variables

if __name__ == __main__:

    print('Prueba Gurobi')
    x = model.addVar(lb=0, name="x")
    model.setObjective(x, GRB.MINIMIZE)
    model.optimize()
    
    print("Estado:", model.Status)
    print("Objetivo:", model.ObjVal)
    print("Variable:", x.X)
