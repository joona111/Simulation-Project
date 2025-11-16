import simpy

from config import CONFIG, seed_all
from hospital_model import patient_generator, monitor


def run_sim(config: dict = CONFIG) -> dict:
    """
    Run a complete simulation and return the hospital state with metrics.

    Parameters
    ----------
    config : dict, optional
        Configuration dictionary. Defaults to CONFIG from config.py.
        You can pass a modified copy of CONFIG if you want to experiment
        with different parameters.

    Returns
    -------
    dict
        The `hospital` dictionary containing:
            - "prep", "op", "recovery": SimPy Resource objects
            - "metrics": dict with:
                - "completed": number of patients that finished recovery
                - "patient_times": per-patient timing metrics
                - "prep_q", "or_q", "rec_q": queue length time series
                - "or_util": OR utilization time series
    """
    seed_all(config["random_seed"])
    env = simpy.Environment()

    hospital = {
        # SimPy Resources for each stage.
        "prep": simpy.Resource(env, capacity=config["prep_units"]),
        "op": simpy.Resource(env, capacity=config["op_units"]),
        "recovery": simpy.Resource(env, capacity=config["recovery_units"]),

        # Dictionary for storing metrics during the simulation.
        "metrics": {
            "completed": 0,     # number of patients fully processed
            "patient_times": [],  # list of per-patient timing info dicts
            "prep_q": [],       # list of (time, queue_length) for prep
            "or_q": [],         # list of (time, queue_length) for OR
            "rec_q": [],        # list of (time, queue_length) for recovery
            "or_util": [],      # list of (time, utilization) for OR
        },
    }

    # Start the two main processes:
    # 1) patient_generator: creates patient flows
    env.process(patient_generator(env, hospital, config))

    # 2) monitor: periodically samples queue lengths and OR utilization
    env.process(monitor(env, hospital, config["monitor_interval"]))

    # Run the simulation up to the configured end time (in minutes).
    env.run(until=config["sim_duration"])

    # Return the full state so callers can inspect resources and metrics.
    return hospital