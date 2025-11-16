# -- file that contains process function definitions --

from config import expovariate

def patient_generator(env, hospital, config):
    """
    Continuously create patients according to an interarrival distribution.

    For each new patient:
    - Assign a unique id and creation time.
    - Sample individual service times (prep, op, recovery).
    - Start a separate SimPy process (patient_flow) to simulate that patient.
    - Wait for the next arrival based on the exponential interarrival time.

    Parameters
    ----------
    env : simpy.Environment
        The SimPy environment driving the simulation clock.
    hospital : dict
        Dictionary holding resources and metrics.
    config : dict
        Configuration dictionary (see CONFIG in config.py).
    """
    i = 0  # patient counter

    while True:
        i += 1

        # Create a new "patient" record containing the id, the arrival time,
        # and the individual service times sampled from exponential distributions.
        patient = {
            "id": i,
            "created_at": env.now,  # current simulation time at arrival
            # Each patient gets their own service times right at creation.
            "prep_time": expovariate(config["prep_mean"]),
            "op_time": expovariate(config["op_mean"]),
            "rec_time": expovariate(config["recovery_mean"]),
        }

        # Launch an independent process to simulate this patient's journey.
        env.process(patient_flow(env, patient, hospital, config))

        # Schedule the next patient's arrival.
        ia = expovariate(config["interarrival_mean"])
        yield env.timeout(ia)


def patient_flow(env, patient, hospital, config):
    """
    Simulate the full journey of a single patient:
        Preparation → Operating Room (OR) → Recovery.

    Flow behavior is controlled by:
        config["block_or_until_recovery"]

    If True:
        - The OR remains blocked (occupied) until the recovery resource
          is acquired. This models a system with no intermediate buffer:
          the patient cannot leave OR without a free recovery bed.

    If False:
        - The OR is released immediately after surgery.
        - The patient then waits in the recovery queue; this models
          a system where there is some kind of buffer or staging area
          between OR and recovery.

    Throughout the journey, we record:
        - Waiting times before each stage (prep, OR, recovery)
        - Total time in the system (arrival → end of recovery)

    Parameters
    ----------
    env : simpy.Environment
    patient : dict
        Contains "id", "created_at", and individual service times.
    hospital : dict
        Contains SimPy resources and metrics.
    config : dict
        Simulation configuration.
    """
    # Shortcut references to resources and metrics for readability.
    prep_res = hospital["prep"]
    or_res = hospital["op"]
    rec_res = hospital["recovery"]
    metrics = hospital["metrics"]

    # 1) PREPARATION STAGE
    # Request a preparation bed: if none are available, the patient waits
    # in the queue associated with this resource.
    with prep_res.request() as req:
        arrival_to_prep_q = env.now  # time when patient first joins prep queue
        yield req                     # wait until a prep unit becomes available
        start_prep = env.now          # time when prep actually starts

        # Simulate the preparation duration.
        yield env.timeout(patient["prep_time"])
        end_prep = env.now            # time when prep is completed

    # 2) OPERATING ROOM & 3) RECOVERY STAGE
    if config["block_or_until_recovery"]:
        # MODE 1: Block OR until recovery is available.
        # The patient holds onto the OR until a recovery bed is acquired.
        # This can create a bottleneck if recovery beds are scarce, but
        # prevents patients from being "parked" in an in-between buffer.
        with or_res.request() as or_req:
            arrival_to_or_q = env.now
            yield or_req            # wait for OR
            start_op = env.now

            # Perform the operation.
            yield env.timeout(patient["op_time"])
            end_op = env.now

            # BEFORE releasing the OR, we must ensure a recovery bed is acquired.
            # If no recovery bed is immediately free, this will block the OR.
            with rec_res.request() as rec_req:
                arrival_to_rec_q = env.now
                yield rec_req           # wait for a recovery bed
                start_rec = env.now

                # Now we can release the OR (leaving this 'with or_res.request()'
                # context). The patient is now in recovery.
                yield env.timeout(patient["rec_time"])
                end_rec = env.now

    else:
        # MODE 2: Release OR immediately after surgery.
        # The patient first uses the OR, then releases it and joins the
        # recovery queue. This allows the OR to serve the next patient
        # while this patient is still waiting for recovery.
        with or_res.request() as or_req:
            arrival_to_or_q = env.now
            yield or_req             # wait for OR
            start_op = env.now

            # Operation duration.
            yield env.timeout(patient["op_time"])
            end_op = env.now         # OR is freed when this 'with' block exits

        # After leaving OR, we now request a recovery bed.
        with rec_res.request() as rec_req:
            arrival_to_rec_q = env.now
            yield rec_req            # wait for recovery
            start_rec = env.now

            # Recovery duration.
            yield env.timeout(patient["rec_time"])
            end_rec = env.now

    # 4) RECORD PER-PATIENT METRICS
    metrics["completed"] += 1

    metrics["patient_times"].append(
        {
            "id": patient["id"],
            "arrival": patient["created_at"],
            "end": end_rec,
            # Total time the patient spent in the system.
            "total_time": end_rec - patient["created_at"],
            # Waiting times before each major stage.
            "prep_wait": start_prep - arrival_to_prep_q,
            "or_wait": start_op - arrival_to_or_q,
            "rec_wait": start_rec - arrival_to_rec_q,
        }
    )


def monitor(env, hospital, interval: float):
    """
    Periodically sample queue lengths and OR utilization.

    This function is run as a background SimPy process and simply
    takes "snapshots" of the system state every `interval` minutes.

    Parameters
    ----------
    env : simpy.Environment
        The SimPy environment.
    hospital : dict
        Contains the resources and the 'metrics' dict.
    interval : float
        Time between snapshots (in minutes).
    """
    prep_res = hospital["prep"]
    or_res = hospital["op"]
    rec_res = hospital["recovery"]
    metrics = hospital["metrics"]

    while True:
        t = env.now

        # Current queue lengths for each resource.
        prep_q_len = len(prep_res.queue)
        or_q_len = len(or_res.queue)
        rec_q_len = len(rec_res.queue)

        # OR utilization: how much of its capacity is currently in use.
        # For a Resource, 'count' is the number of users; 'capacity' is
        # the maximum number of concurrent users.
        or_util = or_res.count / or_res.capacity

        # Store tuples (time, value) so we can later plot or analyze
        # the evolution over time.
        metrics["prep_q"].append((t, prep_q_len))
        metrics["or_q"].append((t, or_q_len))
        metrics["rec_q"].append((t, rec_q_len))
        metrics["or_util"].append((t, or_util))

        # Wait until the next snapshot.
        yield env.timeout(interval)


# -- alternative versions --

# generator starts new patient process according to interval distribution
def patient_generator_mkB(env, resources):
    while True:
        env.process(patient_mkB(env, resources))
        yield env.timeout(random.expovariate(1/timeavgs[0])) # avg. interarrival 25, exponential distr.


# individual patient, keeps track of actual service times for each stage: required time and extra waiting
def patient_mkB(env, resources):
    e = random.expovariate
    required = [e(1/timeavgs[1]), e(1/timeavgs[2]), e(1/timeavgs[3])] # required times
    waited = [0,0,0]   # extra waits before each stage
    
    results['wait'].append(waited) # mutable, edited below
    results['req'].append(required)
    
    mydata[0] = env.now # arrival time

    # individual patient path through system
    prep = resources[0].request()
    yield prep # wait prep room
    yield env.timeout(random.expovariate(1/timeavgs[1])) # prep duration
    op = resources[1].request()
    yield op
    resources[0].release(prep) # op room free, release prep
    mydata[1] = env.now # record time ended in prep room
    yield env.timeout(random.expovariate(1/timeavgs[2])) # op duration
    rec = resources[2].request()
    mydata[2] = env.now # *required* time in op room
    yield rec
    resources[1].release(op) # op free once rec opens
    mydata[3] = env.now # *total* time in op room
    yield env.timeout(random.expovariate(1/timeavgs[3])) # op duration
    resources[2].release(rec) # rec done
    mydata[4] = env.now
    
    # calculate times spent instead of simulation times:
    mydata[4] -= mydata[3]
    mydata[3] -= mydata[2]
    mydata[2] -= mydata[1]
    mydata[1] -= mydata[0]