import gurobipy as gp
from gurobipy import GRB


def build_model(instance, params=None, relax=False):
    params = params or {}

    model = gp.model(instance["name"])

    # parámetros obligatorios para las corridas comparativas.
    model.params.threads = 1
    model.params.timelimit = 600
    model.params.outputflag = params.get("outputflag", 1)

    # permite aplicar configuraciones adicionales del solver.
    for name, value in params.items():
        if name not in {"outputflag"}:
            model.setparam(name, value)

    customers = instance["customers"]
    days = instance["days"]
    vehicles = instance["vehicles"]

    # los conjuntos y variables definitivos se agregan aquí,
    # una vez confirmadas sus dimensiones en el modelo matemático.
    variables = {}

    # TODO: definir x, z, w, dw y rw.
    # TODO: definir la función objetivo (1).
    # TODO: agregar las restricciones (2)-(5), (7)-(12), (14) y (16).
    # TODO: comprobar que los índices coincidan con la formulación.

    return model, variables
