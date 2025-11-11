import simpy

from config import CONFIG, seed_all


def run_sim(config=CONFIG):
    seed_all(config["random_seed"])
    env = simpy.Environment()