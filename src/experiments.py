CONFIGURATIONS = {
    "baseline": {},
    "cuts_0": {"Cuts": 0},
    "presolve_0": {"Presolve": 0},
    "mipfocus_1": {"MIPFocus": 1},
    "mipfocus_3": {"MIPFocus": 3},
    "heuristics_0": {"Heuristics": 0},
}


def run_experiments(instance, build_model, run_model):
    results = []

    for experiment_name, params in CONFIGURATIONS.items():
        result, model, variables = run_model(
            instance=instance,
            build_model=build_model,
            params=params,
            relax=False,
        )

        result["experiment"] = experiment_name
        results.append(result)

        model.dispose()

    return results
