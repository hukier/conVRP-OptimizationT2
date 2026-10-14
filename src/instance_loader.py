import json
from pathlib import Path


def load_instance(path):
    with Path(path).open(encoding="utf-8") as file:
        data = json.load(file)

    nodes = {int(node_id): values for node_id, values in data["nodes"].items()}

    windows = {
        int(node_id): tuple(window) for node_id, window in data["time_windows"].items()
    }

    instance = {
        **data,
        "depot": int(data["depot"]),
        "days": list(data["days"]),
        "vehicles": list(data["vehicles"]),
        "nodes": nodes,
        "time_windows": windows,
        "customers": sorted(
            node_id for node_id in nodes if node_id != int(data["depot"])
        ),
    }

    validate_instance(instance)
    return instance


def validate_instance(data):
    customers = data["customers"]
    nodes = data["nodes"]
    depot = data["depot"]

    assert depot in nodes, "El depósito no está definido."
    assert len(customers) >= 15, "Se requieren al menos 15 clientes."
    assert len(data["days"]) >= 3, "Se requieren al menos 3 días."
    assert len(data["vehicles"]) >= 3, "Se requieren al menos 3 vehículos."
    assert data["capacity"] > 0, "La capacidad debe ser positiva."

    for customer in customers:
        assert nodes[customer]["demand"] >= 0
        assert customer not in data["time_windows"] or (
            data["time_windows"][customer][0] <= data["time_windows"][customer][1]
        )

    assert all(customer in nodes for customer in data["time_windows"]), (
        "Hay ventanas asociadas a nodos inexistentes."
    )
