from pathlib import Path

from instance_loader import load_instance
from model import build_model
from solver import run_model


def main():
    repo_root = Path(__file__).resolve().parent.parent
    instance_path = repo_root / "data" / "instance_1_c101_15c.json"

    instance = load_instance(instance_path)

    # PLEM
    result, model, variables = run_model(
        instance=instance,
        build_model=build_model,
        params={},
        relax=False,
    )

    print("\nResultado del PLEM:")
    print(result)

    model.dispose()

    # Relajación continua
    result_lp, model_lp, variables_lp = run_model(
        instance=instance,
        build_model=build_model,
        params={},
        relax=True,
    )

    print("\nResultado de la relajación:")
    print(result_lp)

    model_lp.dispose()


if __name__ == "__main__":
    main()
