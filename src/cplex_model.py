"""
cplex_model.py
Modelo de ruteo consistente (versión reducida de Campelo et al., 2019) en CPLEX.

Equivalente a la implementación en gurobipy. Misma firma:
    model, variables = build_model(instance, params=None, relax=False)

Requiere: pip install docplex cplex
"""

from docplex.mp.model import Model
from utils import _build_sets, _build_parameters


# Variables
def _add_variables(model, sets, relax=False):
    customers = sets["customers"]
    days = sets["days"]
    vehicles = sets["vehicles"]
    arcs_by_day = sets["arcs_by_day"]

    x_keys = [(i, j, t, r) for t in days for i, j in arcs_by_day[t] for r in vehicles]
    z_keys = [(i, r) for i in customers for r in vehicles]

    if relax:
        X = model.continuous_var_dict(x_keys, lb=0, ub=1, name="X")
        Z = model.continuous_var_dict(z_keys, lb=0, ub=1, name="Z")
    else:
        X = model.binary_var_dict(x_keys, name="X")
        Z = model.binary_var_dict(z_keys, name="Z")

    W = model.continuous_var_dict(
        [(i, t) for i in customers for t in days], lb=0, name="W"
    )
    dW = model.continuous_var_dict(vehicles, lb=0, name="dW")
    rW = model.continuous_var_dict(
        [(t, r) for t in days for r in vehicles], lb=0, name="rW"
    )

    return {"X": X, "Z": Z, "W": W, "dW": dW, "rW": rW}


# objetivo
def _add_objective(model, variables, sets, parameters):
    X = variables["X"]
    distance = parameters["distance"]
    model.minimize(
        model.sum(
            distance[i, j] * X[i, j, t, r]
            for t in sets["days"]
            for i, j in sets["arcs_by_day"][t]
            for r in sets["vehicles"]
        )
    )


# Índices de arcos entrantes / salientes (evita escanear X.keys() cada vez)
def _build_arc_index(X):
    in_arcs, out_arcs = {}, {}
    for i, j, t, r in X.keys():
        in_arcs.setdefault((j, t, r), []).append((i, j, t, r))
        out_arcs.setdefault((i, t, r), []).append((i, j, t, r))
    return in_arcs, out_arcs


# ASIGNACIÓN Y ACOPLAMIENTO
def _add_assignment_constraints(model, variables, sets, parameters, in_arcs):
    X, Z = variables["X"], variables["Z"]
    customers, days, vehicles = sets["customers"], sets["days"], sets["vehicles"]
    demand = parameters["demand"]

    for i in customers:
        model.add_constraint(
            model.sum(Z[i, r] for r in vehicles) == 1, ctname=f"Asignacion_{i}"
        )

    for j in customers:
        for r in vehicles:
            for t in days:
                keys = in_arcs.get((j, t, r), [])
                incoming = model.sum(X[k] for k in keys)
                if demand[j, t] > 0:
                    model.add_constraint(
                        incoming == Z[j, r], ctname=f"Acoplamiento_{j}_{r}_{t}"
                    )
                elif keys:
                    model.add_constraint(
                        incoming == 0, ctname=f"Acoplamiento_{j}_{r}_{t}"
                    )
                # Sin arcos y sin demanda: restricción trivial 0 == 0, se omite.


# FLUJO Y SALIDA DEL DEPÓSITO
def _add_flow_constraints(model, variables, sets, in_arcs, out_arcs):
    X = variables["X"]
    customers, days, vehicles = sets["customers"], sets["days"], sets["vehicles"]
    depot = sets["depot"]

    for j in customers:
        for r in vehicles:
            for t in days:
                ins = in_arcs.get((j, t, r), [])
                outs = out_arcs.get((j, t, r), [])
                if not ins and not outs:
                    continue  # trivial 0 == 0
                model.add_constraint(
                    model.sum(X[k] for k in ins) == model.sum(X[k] for k in outs),
                    ctname=f"Flujo_{j}_{r}_{t}",
                )

    for r in vehicles:
        for t in days:
            model.add_constraint(
                model.sum(X[k] for k in out_arcs.get((depot, t, r), [])) == 1,
                ctname=f"SalidaDeposito_{r}_{t}",
            )


# RESTRICCIONES TEMPORALES
def _add_time_constraints(model, variables, sets, parameters):
    X, W, dW, rW = variables["X"], variables["W"], variables["dW"], variables["rW"]
    customers, days, vehicles = sets["customers"], sets["days"], sets["vehicles"]
    customer_set = set(customers)
    depot, return_node = sets["depot"], sets["return_node"]
    M = parameters["big_m"]
    st, tt = parameters["service_time"], parameters["travel_time"]
    time_windows = parameters["time_windows"]

    for (i, j, t, r), x in X.items():
        if i in customer_set and j in customer_set:
            model.add_constraint(
                W[i, t] + st[i, t] + tt[i, j] <= W[j, t] + M * (1 - x),
                ctname=f"Tiempo_{i}_{j}_{t}_{r}",
            )
        elif i == depot and j in customer_set:
            model.add_constraint(
                dW[r] + tt[depot, j] <= W[j, t] + M * (1 - x),
                ctname=f"SalidaTiempo_{j}_{t}_{r}",
            )
        elif i in customer_set and j == return_node:
            model.add_constraint(
                W[i, t] + st[i, t] + tt[i, return_node] <= rW[t, r] + M * (1 - x),
                ctname=f"RetornoTiempo_{i}_{t}_{r}",
            )

    # Las ventanas solo se imponen a clientes con ventana definida.
    for i, (a_i, b_i) in time_windows.items():
        for t in days:
            model.add_constraint(W[i, t] >= a_i, ctname=f"VentanaInicio_{i}_{t}")
            model.add_constraint(W[i, t] <= b_i, ctname=f"VentanaFin_{i}_{t}")

    for r in vehicles:
        model.add_constraint(
            dW[r] >= parameters["depot_open"], ctname=f"AperturaDeposito_{r}"
        )

    for t in days:
        for r in vehicles:
            model.add_constraint(
                rW[t, r] <= parameters["depot_close"], ctname=f"CierreDeposito_{r}_{t}"
            )


# Capacidad
def _add_capacity_constraints(model, variables, sets, parameters):
    Z = variables["Z"]
    demand, capacity = parameters["demand"], parameters["capacity"]
    for r in sets["vehicles"]:
        for t in sets["days"]:
            model.add_constraint(
                model.sum(demand[i, t] * Z[i, r] for i in sets["customers"])
                <= capacity,
                ctname=f"Capacidad_{r}_{t}",
            )


# Traducción de parámetros estilo Gurobi -> CPLEX
# CPLEX no tiene un "Cuts=0" global: hay que apagar cada familia de cortes (-1 = off).
_CUT_FAMILIES = [
    "bqp",
    "cliques",
    "covers",
    "disjunctive",
    "flowcovers",
    "pathcut",
    "gomory",
    "gubcovers",
    "implied",
    "localimplied",
    "liftproj",
    "mcfcut",
    "mircut",
    "multiplebqp",
    "rlt",
    "zerohalfcut",
]


def _apply_params(model, params):
    """
    Acepta claves estilo Gurobi (case-insensitive) y las traduce:
      cuts=0       -> todas las familias mip.cuts.* = -1
      presolve=0   -> preprocessing.presolve = 0
      mipfocus=1/3 -> emphasis.mip = 1 (factibilidad) / 3 (cota)
      heuristics=0 -> mip.strategy.heuristicfreq = -1
      outputflag   -> se usa en solve(log_output=...)
      threads, timelimit
    Adicionalmente: params["cplex"] = {"mip.strategy.rinsheur": 10, ...}
    """
    p = {k.lower(): v for k, v in params.items()}
    P = model.parameters

    if "cuts" in p and p["cuts"] == 0:
        for fam in _CUT_FAMILIES:
            try:
                getattr(P.mip.cuts, fam).set(-1)
            except AttributeError:
                pass  # la familia no existe en esta versión de CPLEX
    if "presolve" in p and p["presolve"] == 0:
        P.preprocessing.presolve = 0
    if "mipfocus" in p:
        P.emphasis.mip = int(
            p["mipfocus"]
        )  # 0 balance,1 factib.,2 optim.,3 cota,4 ocultas,5 heur.
    if "heuristics" in p and p["heuristics"] == 0:
        P.mip.strategy.heuristicfreq = -1
    if "threads" in p:
        P.threads = int(p["threads"])
    if "timelimit" in p:
        P.timelimit = float(p["timelimit"])

    for path, value in p.get("cplex", {}).items():  # parámetros nativos arbitrarios
        node = P
        for part in path.split("."):
            node = getattr(node, part)
        node.set(value)


# FUNCIÓN PRINCIPAL
def build_cplex_model(instance, params=None, relax=False):
    params = params or {}

    model = Model(name=str(instance["name"]))

    # Parámetros obligatorios de las corridas
    model.parameters.threads = 1
    model.parameters.timelimit = 600
    _apply_params(model, params)
    model.context.solver.log_output = bool(
        params.get("OutputFlag", params.get("outputflag", 1))
    )

    sets = _build_sets(instance)
    parameters = _build_parameters(instance, sets)
    variables = _add_variables(model, sets, relax=relax)
    in_arcs, out_arcs = _build_arc_index(variables["X"])

    _add_objective(model, variables, sets, parameters)
    _add_assignment_constraints(model, variables, sets, parameters, in_arcs)
    _add_flow_constraints(model, variables, sets, in_arcs, out_arcs)
    _add_time_constraints(model, variables, sets, parameters)
    _add_capacity_constraints(model, variables, sets, parameters)

    variables.update(
        {
            "arcs": sets["arcs"],
            "arcs_by_day": sets["arcs_by_day"],
            "customers": sets["customers"],
            "days": sets["days"],
            "vehicles": sets["vehicles"],
            "depot": sets["depot"],
            "return_node": sets["return_node"],
        }
    )
    return model, variables
