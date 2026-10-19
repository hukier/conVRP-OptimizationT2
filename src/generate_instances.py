import json
from pathlib import Path


PLANNING_DAYS = [1, 2, 3]
VEHICLES = [1, 2, 3]
DEPOT_WINDOW = [0, 240]


def _build_instance(name, source_reference, capacity, nodes, time_windows):
    return {
        "name": name,
        "source_reference": source_reference,
        "depot": 0,
        "days": PLANNING_DAYS.copy(),
        "vehicles": VEHICLES.copy(),
        "capacity": capacity,
        "depot_window": DEPOT_WINDOW.copy(),
        "nodes": {str(node_id): values for node_id, values in nodes.items()},
        "time_windows": {
            str(node_id): window for node_id, window in time_windows.items()
        },
    }


def generate_c101_instance():
    # Nodos 0 (depósito) y 1-15 (clientes agrupados) de Solomon C101
    # Coordenadas reales C101, demandas base y ventanas calibradas
    nodes_raw = {
        0: {
            "x": 40.0,
            "y": 50.0,
            "demand": 0,
            "demand_by_day": {"1": 0, "2": 0, "3": 0},
            "service_time_by_day": {"1": 0, "2": 0, "3": 0},
        },
        1: {
            "x": 45.0,
            "y": 68.0,
            "demand": 10,
            "demand_by_day": {"1": 10, "2": 15, "3": 10},
            "service_time_by_day": {"1": 10, "2": 10, "3": 10},
        },
        2: {
            "x": 45.0,
            "y": 70.0,
            "demand": 30,
            "demand_by_day": {"1": 25, "2": 0, "3": 25},
            "service_time_by_day": {"1": 10, "2": 0, "3": 10},
        },
        3: {
            "x": 42.0,
            "y": 66.0,
            "demand": 10,
            "demand_by_day": {"1": 10, "2": 15, "3": 0},
            "service_time_by_day": {"1": 10, "2": 10, "3": 0},
        },
        4: {
            "x": 42.0,
            "y": 68.0,
            "demand": 10,
            "demand_by_day": {"1": 0, "2": 10, "3": 15},
            "service_time_by_day": {"1": 0, "2": 10, "3": 10},
        },
        5: {
            "x": 42.0,
            "y": 65.0,
            "demand": 10,
            "demand_by_day": {"1": 10, "2": 10, "3": 10},
            "service_time_by_day": {"1": 10, "2": 10, "3": 10},
        },
        6: {
            "x": 40.0,
            "y": 69.0,
            "demand": 20,
            "demand_by_day": {"1": 20, "2": 20, "3": 20},
            "service_time_by_day": {"1": 10, "2": 10, "3": 10},
        },
        7: {
            "x": 40.0,
            "y": 66.0,
            "demand": 20,
            "demand_by_day": {"1": 20, "2": 0, "3": 20},
            "service_time_by_day": {"1": 10, "2": 0, "3": 10},
        },
        8: {
            "x": 38.0,
            "y": 68.0,
            "demand": 20,
            "demand_by_day": {"1": 20, "2": 20, "3": 0},
            "service_time_by_day": {"1": 10, "2": 10, "3": 0},
        },
        9: {
            "x": 38.0,
            "y": 70.0,
            "demand": 10,
            "demand_by_day": {"1": 0, "2": 15, "3": 10},
            "service_time_by_day": {"1": 0, "2": 10, "3": 10},
        },
        10: {
            "x": 35.0,
            "y": 66.0,
            "demand": 10,
            "demand_by_day": {"1": 15, "2": 10, "3": 10},
            "service_time_by_day": {"1": 10, "2": 10, "3": 10},
        },
        11: {
            "x": 35.0,
            "y": 69.0,
            "demand": 10,
            "demand_by_day": {"1": 10, "2": 15, "3": 15},
            "service_time_by_day": {"1": 10, "2": 10, "3": 10},
        },
        12: {
            "x": 25.0,
            "y": 85.0,
            "demand": 20,
            "demand_by_day": {"1": 20, "2": 0, "3": 25},
            "service_time_by_day": {"1": 10, "2": 0, "3": 10},
        },
        13: {
            "x": 22.0,
            "y": 75.0,
            "demand": 30,
            "demand_by_day": {"1": 30, "2": 30, "3": 30},
            "service_time_by_day": {"1": 10, "2": 10, "3": 10},
        },
        14: {
            "x": 22.0,
            "y": 85.0,
            "demand": 10,
            "demand_by_day": {"1": 0, "2": 15, "3": 15},
            "service_time_by_day": {"1": 0, "2": 10, "3": 10},
        },
        15: {
            "x": 20.0,
            "y": 80.0,
            "demand": 40,
            "demand_by_day": {"1": 25, "2": 40, "3": 0},
            "service_time_by_day": {"1": 10, "2": 10, "3": 0},
        },
    }

    # Ventanas de tiempo [a_i, b_i] para los nodos
    time_windows = {
        0: [0, 240],
        1: [30, 90],
        2: [150, 210],
        3: [20, 80],
        4: [140, 200],
        5: [10, 65],
        6: [120, 180],
        7: [40, 100],
        8: [50, 110],
        9: [110, 170],
        10: [70, 130],
        11: [90, 150],
        12: [130, 190],
        13: [25, 85],
        14: [100, 160],
        15: [80, 140],
    }

    return _build_instance(
        "instance_1_c101_15c",
        "Adapted from CVRPLIB Solomon C101",
        85,
        nodes_raw,
        time_windows,
    )


def generate_rc101_instance():
    # Nodos 0 (depósito) y 1-15 (mixtos random-clustered) de Solomon RC101
    nodes_raw = {
        0: {
            "x": 40.0,
            "y": 50.0,
            "demand": 0,
            "demand_by_day": {"1": 0, "2": 0, "3": 0},
            "service_time_by_day": {"1": 0, "2": 0, "3": 0},
        },
        1: {
            "x": 25.0,
            "y": 85.0,
            "demand": 20,
            "demand_by_day": {"1": 20, "2": 20, "3": 0},
            "service_time_by_day": {"1": 10, "2": 10, "3": 0},
        },
        2: {
            "x": 22.0,
            "y": 75.0,
            "demand": 30,
            "demand_by_day": {"1": 30, "2": 0, "3": 25},
            "service_time_by_day": {"1": 10, "2": 0, "3": 10},
        },
        3: {
            "x": 22.0,
            "y": 85.0,
            "demand": 10,
            "demand_by_day": {"1": 10, "2": 15, "3": 15},
            "service_time_by_day": {"1": 10, "2": 10, "3": 10},
        },
        4: {
            "x": 20.0,
            "y": 80.0,
            "demand": 40,
            "demand_by_day": {"1": 0, "2": 25, "3": 30},
            "service_time_by_day": {"1": 0, "2": 10, "3": 10},
        },
        5: {
            "x": 20.0,
            "y": 85.0,
            "demand": 20,
            "demand_by_day": {"1": 20, "2": 20, "3": 20},
            "service_time_by_day": {"1": 10, "2": 10, "3": 10},
        },
        6: {
            "x": 18.0,
            "y": 75.0,
            "demand": 20,
            "demand_by_day": {"1": 20, "2": 20, "3": 20},
            "service_time_by_day": {"1": 10, "2": 10, "3": 10},
        },
        7: {
            "x": 15.0,
            "y": 75.0,
            "demand": 20,
            "demand_by_day": {"1": 20, "2": 0, "3": 20},
            "service_time_by_day": {"1": 10, "2": 0, "3": 10},
        },
        8: {
            "x": 15.0,
            "y": 80.0,
            "demand": 10,
            "demand_by_day": {"1": 10, "2": 15, "3": 0},
            "service_time_by_day": {"1": 10, "2": 10, "3": 0},
        },
        9: {
            "x": 10.0,
            "y": 35.0,
            "demand": 20,
            "demand_by_day": {"1": 0, "2": 20, "3": 20},
            "service_time_by_day": {"1": 0, "2": 10, "3": 10},
        },
        10: {
            "x": 10.0,
            "y": 40.0,
            "demand": 30,
            "demand_by_day": {"1": 20, "2": 20, "3": 0},
            "service_time_by_day": {"1": 10, "2": 10, "3": 0},
        },
        11: {
            "x": 8.0,
            "y": 40.0,
            "demand": 40,
            "demand_by_day": {"1": 35, "2": 25, "3": 25},
            "service_time_by_day": {"1": 10, "2": 10, "3": 10},
        },
        12: {
            "x": 8.0,
            "y": 45.0,
            "demand": 20,
            "demand_by_day": {"1": 0, "2": 20, "3": 20},
            "service_time_by_day": {"1": 0, "2": 10, "3": 10},
        },
        13: {
            "x": 5.0,
            "y": 35.0,
            "demand": 10,
            "demand_by_day": {"1": 15, "2": 0, "3": 10},
            "service_time_by_day": {"1": 10, "2": 0, "3": 10},
        },
        14: {
            "x": 5.0,
            "y": 45.0,
            "demand": 10,
            "demand_by_day": {"1": 10, "2": 15, "3": 10},
            "service_time_by_day": {"1": 10, "2": 10, "3": 10},
        },
        15: {
            "x": 2.0,
            "y": 40.0,
            "demand": 20,
            "demand_by_day": {"1": 20, "2": 20, "3": 20},
            "service_time_by_day": {"1": 10, "2": 10, "3": 10},
        },
    }

    # Ventanas de tiempo [a_i, b_i] de Solomon RC101
    time_windows = {
        0: [0, 240],
        1: [145, 175],
        2: [50, 80],
        3: [109, 139],
        4: [141, 171],
        5: [41, 71],
        6: [95, 125],
        7: [79, 109],
        8: [91, 121],
        9: [91, 121],
        10: [119, 149],
        11: [59, 89],
        12: [64, 94],
        13: [142, 172],
        14: [35, 65],
        15: [58, 88],
    }

    return _build_instance(
        "instance_2_rc101_15c",
        "Adapted from CVRPLIB Solomon RC101",
        90,
        nodes_raw,
        time_windows,
    )


def save_instance(instance_data, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(instance_data, f, indent=2, ensure_ascii=False)
    print(f"Instancia guardada exitosamente en: {path}")


def main():
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data"

    instances = (
        (generate_c101_instance(), "instance_1_c101_15c.json"),
        (generate_rc101_instance(), "instance_2_rc101_15c.json"),
    )
    for instance, filename in instances:
        save_instance(instance, data_dir / filename)


if __name__ == "__main__":
    main()
