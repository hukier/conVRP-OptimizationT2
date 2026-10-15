import json
import math
from pathlib import Path


def load_instance(path):
    with Path(path).open(encoding="utf-8") as file:
        data = json.load(file)

    depot = int(data["depot"])
    days = [int(d) for d in data["days"]]
    vehicles = [int(v) for v in data["vehicles"]]

    # Cargar y normalizar nodos
    nodes = {}
    for node_id_str, values in data["nodes"].items():
        node_id = int(node_id_str)

        # Demandas por día: convertir llaves a int
        if "demand_by_day" in values:
            demand_by_day = {
                int(day): float(qty)
                for day, qty in values["demand_by_day"].items()
            }
        else:
            base_demand = float(values.get("demand", 0))
            demand_by_day = {day: base_demand for day in days}

        # Tiempo de servicio por día: convertir llaves a int
        if "service_time_by_day" in values:
            service_time_by_day = {
                int(day): float(st)
                for day, st in values["service_time_by_day"].items()
            }
        else:
            base_st = float(values.get("service_time", 0))
            service_time_by_day = {day: base_st for day in days}

        nodes[node_id] = {
            "x": float(values["x"]),
            "y": float(values["y"]),
            "demand": float(values.get("demand", 0)),
            "demand_by_day": demand_by_day,
            "service_time_by_day": service_time_by_day,
        }

    # Ventanas de tiempo de los clientes y depósito
    windows = {
        int(node_id): (float(window[0]), float(window[1]))
        for node_id, window in data.get("time_windows", {}).items()
    }

    # Ventana de operación del depósito [aW, bW]
    if "depot_window" in data:
        depot_window = (float(data["depot_window"][0]), float(data["depot_window"][1]))
    elif depot in windows:
        depot_window = windows[depot]
    else:
        depot_window = (0.0, 240.0)

    # Clientes (excluyendo el depósito 0)
    customers = sorted(node_id for node_id in nodes if node_id != depot)

    # Matriz de distancias euclidianas td_ij redondeadas a 2 decimales
    distance_matrix = {}
    for i in nodes:
        for j in nodes:
            dist = round(
                math.sqrt(
                    (nodes[i]["x"] - nodes[j]["x"]) ** 2
                    + (nodes[i]["y"] - nodes[j]["y"]) ** 2
                ),
                2,
            )
            distance_matrix[(i, j)] = dist

    # Matriz de tiempos de viaje tt_ij (asumiendo velocidad promedio = 1)
    travel_time_matrix = {
        (i, j): dist for (i, j), dist in distance_matrix.items()
    }

    # Cota Big-M segura: bW + max(tt_ij) + max(st_it)
    bW = depot_window[1]
    max_tt = max(travel_time_matrix.values()) if travel_time_matrix else 0.0
    max_st = max(
        (st for node in nodes.values() for st in node["service_time_by_day"].values()),
        default=0.0,
    )
    big_m = round(bW + max_tt + max_st, 2)

    # Órdenes activas O: tuplas (i, t) con i in customers, t in days y q_{it} > 0
    active_orders = [
        (i, t)
        for i in customers
        for t in days
        if nodes[i]["demand_by_day"].get(t, 0) > 0
    ]

    instance = {
        **data,
        "depot": depot,
        "days": days,
        "vehicles": vehicles,
        "capacity": float(data["capacity"]),
        "depot_window": depot_window,
        "nodes": nodes,
        "time_windows": windows,
        "customers": customers,
        "distance_matrix": distance_matrix,
        "travel_time_matrix": travel_time_matrix,
        "big_m": big_m,
        "active_orders": active_orders,
    }

    validate_instance(instance)
    return instance


def validate_instance(data):
    customers = data["customers"]
    nodes = data["nodes"]
    depot = data["depot"]
    days = data["days"]
    vehicles = data["vehicles"]
    capacity = data["capacity"]

    assert depot in nodes, "El depósito no está definido."
    assert len(customers) >= 15, "Se requieren al menos 15 clientes."
    assert len(days) >= 3, "Se requieren al menos 3 días."
    assert len(vehicles) >= 3, "Se requieren al menos 3 vehículos."
    assert capacity > 0, "La capacidad debe ser positiva."

    depot_window = data.get("depot_window")
    assert depot_window is not None, "El horario del depósito no está definido."
    assert depot_window[0] <= depot_window[1], "La ventana del depósito es inválida."

    for customer in customers:
        assert nodes[customer]["demand"] >= 0, (
            f"Demanda base negativa para cliente {customer}."
        )
        for day in days:
            assert day in nodes[customer]["demand_by_day"], (
                f"Falta demanda para cliente {customer} en el día {day}."
            )
            assert nodes[customer]["demand_by_day"][day] >= 0, (
                f"Demanda negativa para cliente {customer} en día {day}."
            )
            assert day in nodes[customer]["service_time_by_day"], (
                f"Falta tiempo de servicio para cliente {customer} en el día {day}."
            )
            assert nodes[customer]["service_time_by_day"][day] >= 0, (
                f"Tiempo de servicio negativo para cliente {customer} en día {day}."
            )

        assert customer not in data["time_windows"] or (
            data["time_windows"][customer][0] <= data["time_windows"][customer][1]
        ), f"Ventana de tiempo inválida para cliente {customer}."

    assert all(customer in nodes for customer in data["time_windows"]), (
        "Hay ventanas asociadas a nodos inexistentes."
    )

    # Verificación de capacidad total de la flota por día
    total_fleet_capacity = len(vehicles) * capacity
    for day in days:
        total_demand_day = sum(nodes[c]["demand_by_day"][day] for c in customers)
        assert total_demand_day <= total_fleet_capacity, (
            f"La demanda total en el día {day} ({total_demand_day}) supera "
            f"la capacidad de la flota ({total_fleet_capacity})."
        )


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data"

    instance_files = [
        data_dir / "instance_1_c101_15c.json",
        data_dir / "instance_2_rc101_18c.json",
    ]

    print("=" * 70)
    print("VERIFICACIÓN Y CARGA DE INSTANCIAS conVRP")
    print("=" * 70)

    for inst_path in instance_files:
        if not inst_path.exists():
            print(f"ERROR: Archivo no encontrado: {inst_path}")
            continue

        inst = load_instance(inst_path)
        print(f"\n[OK] Instancia cargada y validada exitosamente: {inst['name']}")
        print(f"  - Fuente: {inst.get('source_reference', 'N/A')}")
        print(f"  - Depósito: Nodo {inst['depot']} | Horario: {inst['depot_window']}")
        print(f"  - Clientes: {len(inst['customers'])} clientes")
        print(f"  - Días de planificación: {inst['days']}")
        print(f"  - Flota: {len(inst['vehicles'])} vehículos | Capacidad Q = {inst['capacity']}")
        print(f"  - Capacidad total de la flota por día = {len(inst['vehicles']) * inst['capacity']}")
        print(f"  - Cota Big-M calculada: {inst['big_m']}")
        print(f"  - Total órdenes activas O: {len(inst['active_orders'])}")

        print("  - Detalle por día:")
        for t in inst["days"]:
            day_demand = sum(inst["nodes"][c]["demand_by_day"][t] for c in inst["customers"])
            active_c = [c for c in inst["customers"] if inst["nodes"][c]["demand_by_day"][t] > 0]
            pct_util = (day_demand / (len(inst["vehicles"]) * inst["capacity"])) * 100
            pct_act = (len(active_c) / len(inst["customers"])) * 100
            print(
                f"    * Día {t}: Demanda = {day_demand:5.1f} ({pct_util:5.1f}% flota) | "
                f"Clientes activos = {len(active_c)}/{len(inst['customers'])} ({pct_act:5.1f}%)"
            )
    print("\n" + "=" * 70)

