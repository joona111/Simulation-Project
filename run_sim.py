import simpy

from config import CONFIG, seed_all
from hospital_model import patient_generator, monitor


def run_sim(config=CONFIG):
    seed_all(config["random_seed"])
    env = simpy.Environment()

    hospital = {
        "prep": simpy.Resource(env, capacity=config["prep_units"]),
        "op": simpy.Resource(env, capacity=config["op_units"]),
        "recovery": simpy.Resource(env, capacity=config["recovery_units"]),
        "metrics": {
            "completed": 0,
            "patient_times": [],
            "prep_q": [],
            "or_q": [],
            "rec_q": [],
            "or_util": [],
        }
    }

    env.process(patient_generator(env, hospital, config))
    env.process(monitor(env, hospital, config["monitor_interval"]))

    env.run(until=config["sim_duration"])
    return hospital