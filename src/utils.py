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
