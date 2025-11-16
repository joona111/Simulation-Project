import random

# Main configuration dictionary used by the rest of the code.
# All time-related values are in **minutes**.
CONFIG = {
    # Total length of the simulation in minutes.
    # 24 * 60 = 1440 minutes = 24 hours.
    "sim_duration": 24 * 60,

    # Random seed for reproducibility of the results.
    "random_seed": 42,

    # Mean time between arrivals of patients (in minutes).
    # The actual arrivals follow an exponential distribution with this mean.
    "interarrival_mean": 25,

    # ---------------------------------------------------------------------
    # Resource capacities
    # ---------------------------------------------------------------------
    # Number of parallel "slots" (beds/rooms) in each stage of the system.
    "prep_units": 3,      # monitored preparation beds
    "op_units": 1,        # operating rooms
    "recovery_units": 3,  # recovery beds

    # ---------------------------------------------------------------------
    # Service-time means (in minutes)
    # ---------------------------------------------------------------------
    # Each stage duration is sampled from an exponential distribution with
    # the corresponding mean below.
    "prep_mean": 40,       # average time spent in preparation
    "op_mean": 20,         # average surgery duration
    "recovery_mean": 40,   # average recovery duration

    # ---------------------------------------------------------------------
    # Monitoring
    # ---------------------------------------------------------------------
    # How often (in minutes) we sample queue lengths and OR utilization.
    "monitor_interval": 5,

    # ---------------------------------------------------------------------
    # Flow logic
    # ---------------------------------------------------------------------
    # If True:
    #   - The OR stays OCCUPIED (blocked) until a recovery bed is acquired.
    #   - This models a system where the patient cannot leave the OR unless
    #     a recovery slot is immediately available.
    #
    # If False:
    #   - The OR is freed as soon as the operation completes.
    #   - The patient then waits in the recovery queue while the OR can
    #     start treating another patient.
    "block_or_until_recovery": True,
}


def expovariate(mean: float) -> float:
    """
    Return a sample from an exponential distribution with a given mean.

    SimPy does not care about the units, so as long as we consistently
    treat these values as "minutes" across the config and the model,
    the simulation remains coherent.
    """
    # random.expovariate expects the rate λ (lambda = 1 / mean)
    return random.expovariate(1.0 / mean)


def seed_all(seed_value: int | None = None) -> None:
    """
    Set the global random seed for reproducibility.

    Parameters
    ----------
    seed_value : int or None
        If provided, this value is passed to random.seed().
        If None, no seeding is applied (randomness is not reproducible).
    """
    if seed_value is not None:
        random.seed(seed_value)
