import random

CONFIG = {
    "sim_duration": 24 * 60,
    "random_seed": 42,
    "interarrival_mean": 25,
    "prep_units": 3,
    "op_units": 1,
    "recovery_units": 3,
    "prep_mean": 40,
    "op_mean": 20,
    "recovery_mean": 40,
    "monitor_interval": 5,
    "block_or_until_recovery": True,
}


def expovariate(mean):
    return random.expovariate(1.0 / mean)


def seed_all(seed_value=None):
    if seed_value is not None:
        random.seed(seed_value)
