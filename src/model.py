import gurobipy as gp
from gurobipy import GRB


# ============================================================
# 1. CONJUNTOS
# ============================================================


def _build_sets(instance):
    """Construye los conjuntos de clientes, días, rutas, nodos y arcos."""

    customers = list(instance["customers"])
    days = list(instance["days"])
    vehicles = list(instance["vehicles"])
    depot = instance["depot"]

    # El JSON no contiene un nodo de retorno separado.
    # Se crea dentro del modelo como nodo ficticio n+1.
    return_node = max(instance["nodes"]) + 1

    if return_node in instance["nodes"]:
        raise ValueError(f"El nodo de retorno {return_node} ya existe en la instancia.")

    nodes = [depot] + customers + [return_node]

    # Arcos dirigidos:
    # - Sin bucles i -> i.
    # - No se sale del nodo de retorno.
    # - No se llega al nodo de salida del depósito.
    # - Se incluye depot -> return_node para representar el descanso.
    arcs = [
        (i, j)
        for i in nodes
        for j in nodes
        if i != j and i != return_node and j != depot
    ]

    # A partir de los datos del cargador, solo los clientes
    # que aparecen en time_windows tienen ventana definida.
    time_window_customers = [i for i in customers if i in instance["time_windows"]]

    active_by_day = {
        t: [i for i in customers if float(instance["nodes"][i]["demand_by_day"][t]) > 0]
        for t in days
    }
    # X solo existe para arcos que pueden pertenecer a un tour ese día.
    # Clientes sin demanda diaria no pueden ser visitados por la ecuación (3).
    arcs_by_day = {
        t: (
            [(depot, return_node)]
            if not active_by_day[t]
            else [
                (i, j)
                for i in [depot] + active_by_day[t]
                for j in active_by_day[t] + [return_node]
                if i != j
            ]
        )
        for t in days
    }

    return {
        "customers": customers,
        "days": days,
        "vehicles": vehicles,
        "depot": depot,
        "return_node": return_node,
        "nodes": nodes,
        "arcs": arcs,
        "active_by_day": active_by_day,
        "arcs_by_day": arcs_by_day,
        "time_window_customers": time_window_customers,
    }


# ============================================================
# 2. PARÁMETROS
# ============================================================


def _build_parameters(instance, sets):
    """Prepara los parámetros utilizados por las restricciones."""

    customers = sets["customers"]
    days = sets["days"]
    arcs = sets["arcs"]
    depot = sets["depot"]
    return_node = sets["return_node"]

    capacity = float(instance["capacity"])
    big_m = float(instance["big_m"])

    depot_open, depot_close = map(
        float,
        instance["depot_window"],
    )

    if capacity <= 0:
        raise ValueError("La capacidad del vehículo debe ser positiva.")

    if big_m <= 0:
        raise ValueError("Big-M debe ser positivo.")

    if depot_open > depot_close:
        raise ValueError("La ventana del depósito es inválida.")

    # Demanda q_it y tiempo de servicio st_it.
    demand = {
        (i, t): float(instance["nodes"][i]["demand_by_day"][t])
        for i in customers
        for t in days
    }

    service_time = {
        (i, t): float(instance["nodes"][i]["service_time_by_day"][t])
        for i in customers
        for t in days
    }

    # Matrices calculadas por instance_loader.py.
    distance_matrix = instance["distance_matrix"]
    travel_time_matrix = instance["travel_time_matrix"]

    distance = {}
    travel_time = {}

    for i, j in arcs:
        if i == depot and j == return_node:
            # Ruta sin operación.
            distance[i, j] = 0.0
            travel_time[i, j] = 0.0

        elif j == return_node:
            # El nodo de retorno representa el depósito.
            distance[i, j] = float(distance_matrix[i, depot])
            travel_time[i, j] = float(travel_time_matrix[i, depot])

        else:
            distance[i, j] = float(distance_matrix[i, j])
            travel_time[i, j] = float(travel_time_matrix[i, j])

    # Ventanas horarias de los clientes que las tienen definidas.
    time_windows = {
        i: tuple(map(float, instance["time_windows"][i]))
        for i in sets["time_window_customers"]
    }

    if any(q < 0 for q in demand.values()):
        raise ValueError("Existen demandas negativas.")

    if any(st < 0 for st in service_time.values()):
        raise ValueError("Existen tiempos de servicio negativos.")

    if any(d < 0 for d in distance.values()):
        raise ValueError("Existen distancias negativas.")

    if any(tt < 0 for tt in travel_time.values()):
        raise ValueError("Existen tiempos de viaje negativos.")

    for i, (a_i, b_i) in time_windows.items():
        if a_i > b_i:
            raise ValueError(f"La ventana horaria del cliente {i} es inválida.")

    return {
        "capacity": capacity,
        "big_m": big_m,
        "depot_open": depot_open,
        "depot_close": depot_close,
        "demand": demand,
        "service_time": service_time,
        "distance": distance,
        "travel_time": travel_time,
        "time_windows": time_windows,
    }


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
# 4. FUNCIÓN OBJETIVO (1)
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

    # (2) Consistencia: cada cliente conserva el mismo vehículo en el horizonte.
    for i in customers:
        model.addConstr(gp.quicksum(Z[i, r] for r in vehicles) == 1, name=f"Asignacion_{i}")

    # (3) Un cliente con demanda se visita exactamente una vez por su vehículo;
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
# 6. CONSERVACIÓN DE FLUJO Y SALIDA DEL DEPÓSITO (4)-(5)
# ============================================================


def _add_flow_constraints(model, variables, sets):
    X = variables["X"]
    customers, days, vehicles = sets["customers"], sets["days"], sets["vehicles"]
    depot = sets["depot"]

    for j in customers:
        for r in vehicles:
            for t in days:
                incoming = gp.quicksum(
                    X[i, j, t, r] for i, jj, tt, rr in X.keys()
                    if jj == j and tt == t and rr == r
                )
                outgoing = gp.quicksum(
                    X[j, k, t, r] for i, k, tt, rr in X.keys()
                    if i == j and tt == t and rr == r
                )
                model.addConstr(incoming == outgoing, name=f"Flujo_{j}_{r}_{t}")

    # (5) Exactamente una salida; depot->return es el tour vacío/descanso.
    for r in vehicles:
        for t in days:
            model.addConstr(
                gp.quicksum(X[i, j, t, r] for i, j, tt, rr in X.keys()
                            if i == depot and tt == t and rr == r) == 1,
                name=f"SalidaDeposito_{r}_{t}",
            )


# ============================================================
# 7. RESTRICCIONES TEMPORALES (7)-(12)
# ============================================================


def _add_time_constraints(model, variables, sets, parameters):
    X, W, dW, rW = variables["X"], variables["W"], variables["dW"], variables["rW"]
    customers, days, vehicles = sets["customers"], sets["days"], sets["vehicles"]
    depot, return_node = sets["depot"], sets["return_node"]
    big_m = parameters["big_m"]
    service_time, travel_time = parameters["service_time"], parameters["travel_time"]
    time_windows = parameters["time_windows"]
    depot_open, depot_close = parameters["depot_open"], parameters["depot_close"]

    # (7), (9), (10): restricciones solo para arcos creados y, por tanto,
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
                dW[r] + travel_time[depot, j]
                <= W[j, t] + big_m * (1 - X[i, j, t, r]),
                name=f"SalidaTiempo_{j}_{t}_{r}",
            )
        elif i in customers and j == return_node:
            model.addConstr(
                W[i, t] + service_time[i, t] + travel_time[i, return_node]
                <= rW[t, r] + big_m * (1 - X[i, j, t, r]),
                name=f"RetornoTiempo_{i}_{t}_{r}",
            )

    # (8) Las ventanas solo se imponen a clientes con ventana definida.
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
# 8. CAPACIDAD DEL VEHÍCULO (14)
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
