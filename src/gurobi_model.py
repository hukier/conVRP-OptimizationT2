import gurobipy as gp
from gurobipy import GRB
from utils import _build_sets, _build_parameters


# ============================================================
# 1. CONJUNTOS
# ============================================================


# ============================================================
# 3. VARIABLES DE DECISIÓN
# ============================================================


def _add_variables(model, sets, relax=False):
    """Crea X, Z, W, dW y rW."""

    customers = sets["customers"]
    days = sets["days"]
    vehicles = sets["vehicles"]
    arcs_by_day = sets["arcs_by_day"]

    # Para la relajación continua, X y Z pasan a ser continuas [0,1].
    binary_type = GRB.CONTINUOUS if relax else GRB.BINARY

    # X[i,j,t,r] = 1 si la ruta r recorre el arco (i,j) el día t.
    X = model.addVars(
        [(i, j, t, r) for t in days for i, j in arcs_by_day[t] for r in vehicles],
        vtype=binary_type,
        lb=0,
        ub=1,
        name="X",
    )

    # Z[i,r] = 1 si el cliente i queda asignado a la ruta r.
    Z = model.addVars(
        customers,
        vehicles,
        vtype=binary_type,
        lb=0,
        ub=1,
        name="Z",
    )

    # W[i,t]: instante de inicio del servicio al cliente i el día t.
    W = model.addVars(
        customers,
        days,
        vtype=GRB.CONTINUOUS,
        lb=0,
        name="W",
    )

    # dW[r]: horario de salida de la ruta r.
    dW = model.addVars(
        vehicles,
        vtype=GRB.CONTINUOUS,
        lb=0,
        name="dW",
    )

    # rW[t,r]: horario de retorno de la ruta r el día t.
    rW = model.addVars(
        days,
        vehicles,
        vtype=GRB.CONTINUOUS,
        lb=0,
        name="rW",
    )

    return {
        "X": X,
        "Z": Z,
        "W": W,
        "dW": dW,
        "rW": rW,
    }


# ============================================================
# 4. FUNCIÓN OBJETIVO
# ============================================================
def _add_objective(model, variables, sets, parameters):
    """Minimiza la distancia total recorrida."""

    X = variables["X"]

    days = sets["days"]
    vehicles = sets["vehicles"]
    arcs_by_day = sets["arcs_by_day"]

    distance = parameters["distance"]

    model.setObjective(
        gp.quicksum(
            distance[i, j] * X[i, j, t, r]
            for t in days
            for i, j in arcs_by_day[t]
            for r in vehicles
        ),
        GRB.MINIMIZE,
    )


# ============================================================
# 5. RESTRICCIONES DE ASIGNACIÓN Y ACOPLAMIENTO (2)-(3)
# ============================================================
def _add_assignment_constraints(model, variables, sets, parameters):
    X, Z = variables["X"], variables["Z"]
    customers, days, vehicles = sets["customers"], sets["days"], sets["vehicles"]
    depot = sets["depot"]
    demand = parameters["demand"]

    # Consistencia: cada cliente conserva el mismo vehículo en el horizonte.
    for i in customers:
        model.addConstr(
            gp.quicksum(Z[i, r] for r in vehicles) == 1, name=f"Asignacion_{i}"
        )

    # Un cliente con demanda se visita exactamente una vez por su vehículo;
    # sin demanda, no se visita.
    for j in customers:
        for r in vehicles:
            for t in days:
                incoming = gp.quicksum(
                    X[i, j, t, r]
                    for i, jj, tt, rr in X.keys()
                    if jj == j and tt == t and rr == r
                )
                rhs = Z[j, r] if demand[j, t] > 0 else 0
                model.addConstr(incoming == rhs, name=f"Acoplamiento_{j}_{r}_{t}")


# ============================================================
# 6. CONSERVACIÓN DE FLUJO Y SALIDA DEL DEPÓSITO
# ============================================================


def _add_flow_constraints(model, variables, sets):
    X = variables["X"]
    customers, days, vehicles = sets["customers"], sets["days"], sets["vehicles"]
    depot = sets["depot"]

    for j in customers:
        for r in vehicles:
            for t in days:
                incoming = gp.quicksum(
                    X[i, j, t, r]
                    for i, jj, tt, rr in X.keys()
                    if jj == j and tt == t and rr == r
                )
                outgoing = gp.quicksum(
                    X[j, k, t, r]
                    for i, k, tt, rr in X.keys()
                    if i == j and tt == t and rr == r
                )
                model.addConstr(incoming == outgoing, name=f"Flujo_{j}_{r}_{t}")

    # Exactamente una salida: depot->return es el tour vacío/descanso.
    for r in vehicles:
        for t in days:
            model.addConstr(
                gp.quicksum(
                    X[i, j, t, r]
                    for i, j, tt, rr in X.keys()
                    if i == depot and tt == t and rr == r
                )
                == 1,
                name=f"SalidaDeposito_{r}_{t}",
            )


# ============================================================
# 7. RESTRICCIONES TEMPORALES
# ============================================================


def _add_time_constraints(model, variables, sets, parameters):
    X, W, dW, rW = variables["X"], variables["W"], variables["dW"], variables["rW"]
    customers, days, vehicles = sets["customers"], sets["days"], sets["vehicles"]
    depot, return_node = sets["depot"], sets["return_node"]
    big_m = parameters["big_m"]
    service_time, travel_time = parameters["service_time"], parameters["travel_time"]
    time_windows = parameters["time_windows"]
    depot_open, depot_close = parameters["depot_open"], parameters["depot_close"]

    # restricciones solo para arcos creados y, por tanto,
    # potencialmente seleccionables en el día correspondiente.
    for i, j, t, r in X.keys():
        if i in customers and j in customers:
            model.addConstr(
                W[i, t] + service_time[i, t] + travel_time[i, j]
                <= W[j, t] + big_m * (1 - X[i, j, t, r]),
                name=f"Tiempo_{i}_{j}_{t}_{r}",
            )
        elif i == depot and j in customers:
            model.addConstr(
                dW[r] + travel_time[depot, j] <= W[j, t] + big_m * (1 - X[i, j, t, r]),
                name=f"SalidaTiempo_{j}_{t}_{r}",
            )
        elif i in customers and j == return_node:
            model.addConstr(
                W[i, t] + service_time[i, t] + travel_time[i, return_node]
                <= rW[t, r] + big_m * (1 - X[i, j, t, r]),
                name=f"RetornoTiempo_{i}_{t}_{r}",
            )

    # Las ventanas solo se imponen a clientes con ventana definida.
    for i, (a_i, b_i) in time_windows.items():
        for t in days:
            model.addConstr(W[i, t] >= a_i, name=f"VentanaInicio_{i}_{t}")
            model.addConstr(W[i, t] <= b_i, name=f"VentanaFin_{i}_{t}")

    for r in vehicles:
        model.addConstr(dW[r] >= depot_open, name=f"AperturaDeposito_{r}")
    for t in days:
        for r in vehicles:
            model.addConstr(rW[t, r] <= depot_close, name=f"CierreDeposito_{r}_{t}")


# ============================================================
# 8. CAPACIDAD DEL VEHÍCULO
# ============================================================


def _add_capacity_constraints(model, variables, sets, parameters):
    Z = variables["Z"]

    customers = sets["customers"]
    days = sets["days"]
    vehicles = sets["vehicles"]

    demand = parameters["demand"]
    capacity = parameters["capacity"]

    # Capacidad diaria por vehículo.
    for r in vehicles:
        for t in days:
            model.addConstr(
                gp.quicksum(demand[i, t] * Z[i, r] for i in customers) <= capacity,
                name=f"Capacidad_{r}_{t}",
            )


# ============================================================
# 9. FUNCIÓN PRINCIPAL
# ============================================================


def build_model(instance, params=None, relax=False):
    """
    Construye el PLEM de ruteo consistente.

    Parámetros
    ----------
    instance : dict
        Instancia obtenida con load_instance().
    params : dict, opcional
        Parámetros adicionales de Gurobi.
    relax : bool, opcional
        Si es True, X y Z son continuas en [0,1].

    Retorna
    -------
    model : gurobipy.Model
    variables : dict
    """

    params = params or {}

    model = gp.Model(instance["name"])

    # Parámetros obligatorios de las corridas.
    model.Params.Threads = 1
    model.Params.TimeLimit = 600
    model.Params.OutputFlag = params.get(
        "OutputFlag",
        params.get("outputflag", 1),
    )

    # Parámetros adicionales para los experimentos.
    for name, value in params.items():
        if name.lower() != "outputflag":
            model.setParam(name, value)

    # Construcción modular.
    sets = _build_sets(instance)
    parameters = _build_parameters(instance, sets)
    variables = _add_variables(model, sets, relax=relax)

    _add_objective(model, variables, sets, parameters)

    _add_assignment_constraints(model, variables, sets, parameters)
    _add_flow_constraints(model, variables, sets)
    _add_time_constraints(model, variables, sets, parameters)
    _add_capacity_constraints(model, variables, sets, parameters)

    # Guardar información útil para análisis posteriores.
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

    model.update()

    return model, variables
