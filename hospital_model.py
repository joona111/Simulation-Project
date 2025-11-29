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



# --- alt. versions, used in dense.ipynb ---
import random
import simpy

# generator starts new patient process according to interval distribution
def patient_generator_mkB(env,conf,resu,facilities):
    while True:
        env.process(patient_mkB(env,conf,resu,facilities))
        yield env.timeout(random.expovariate(1/conf['means'][0]))

# individual patient, keeps track of actual service times for each stage: required time and extra waiting
def patient_mkB(env,conf,resu,facilities):
    # minimum processing times for each stage, using config
    e = random.expovariate
    req_times = [e(1/conf['means'][1]),e(1/conf['means'][2]),e(1/conf['means'][3])]

    flow_times = [env.now, 0, 0, 0, 0] # arrival times at each stage, including release
    resu['patient_flow'].append(flow_times)

    # --- individual patient path through system ---
    # note that patient path logging is also timed, to reduce error in total
    # * if it was logged at the end, active patients would not affect simulation results
    # * some error still remains, from not considering partial process completions at result calculation moment.

    prep = facilities[0].request()
    resu['patient_counts'][0] += 1
    yield prep # wait prep room
    flow_times[1] = env.now # patient taken to a prep room
    resu['patient_counts'][1] += 1

    yield env.timeout(req_times[0])
    op = facilities[1].request()
    resu['util_active'][0] += req_times[0] # prep done, waiting op
    yield op
    facilities[0].release(prep) # op room free, release prep
    resu['patient_counts'][1] -= 1
    resu['patient_counts'][2] += 1
    flow_times[2] = env.now # patient enters operation
    resu['total_active'][0] += flow_times[2] - flow_times[1] # op start - prep start = prep total

    yield env.timeout(req_times[1])
    rec = facilities[2].request()

    resu['util_active'][1] += req_times[1] # op done
    block_start = env.now
    yield rec
    block_end = env.now
    resu["or_time_blocked"]+= block_end - block_start # time waiting for rec bed
    facilities[1].release(op) # op free once rec opens
    resu['patient_counts'][2] -= 1
    resu['patient_counts'][3] += 1
    flow_times[3] = env.now # patient starts recovery
    resu['total_active'][1] += flow_times[3] - flow_times[2] # op total

    yield env.timeout(req_times[2])
    facilities[2].release(rec) # rec done
    resu['patient_counts'][3] -= 1
    resu['patient_counts'][0] -= 1 # reduce total # of patients in system when rec is done
    resu['util_active'][2] += req_times[2] # rec done
    resu['total_active'][2] += req_times[2] # rec does not need to wait, so util% is always 100.
    flow_times[4] = env.now # patient leaves

# result monitor for things the patient doesnt track directly
def monitor_mkB(env,conf,resu,facilities):
    while True:

        snapshot = {
            'time': env.now,
            'patient_counts': resu['patient_counts'].copy(), # totals in system at snapshot time
            'or_queue':len(facilities[1].queue), #length of operating room queue at snapshot time
            #'or_blocked':blocked#1 if or is blocked at snapshot time,otherwise 0
        }
        resu['snapshots'].append(snapshot)
        yield env.timeout(conf['monitor_interval'])

class hospital_model:

    def __init__(self,conf):
        self.env = simpy.Environment()
        self.conf = conf

        # simulation results
        self.results = {
            'patient_flow': [], # all flow times for each patient: arrival/prep/op/rec/leave
            'patient_counts': [0,0,0,0], # patient count in: total/prep/op/rec
            'total_active': [0,0,0], # total time of prep/op/rec
            'util_active': [0,0,0], # active time of prep/op/rec
            'snapshots': [], # simulation situation at snapshot times, created by monitor process
            "or_time_blocked": 0 # total time operating room was blocked waiting for recovery bed
        }

        # seed the rng
        random.seed(a=conf['seed']) # doesnt need to check for None, seed() already does

        # create limited resources
        # + request all slack resources to remove them from the useable pool
        self.facilities = []
        self.slack_requests = []
        for i in range(0,len(conf['total'])):
            self.facilities.append(simpy.Resource(self.env,capacity=conf['total'][i]))
            facility_slack = []
            self.slack_requests.append(facility_slack)

        # create always-on processes
        self.env.process(monitor_mkB(self.env,conf,self.results,self.facilities))
        self.env.process(patient_generator_mkB(self.env,conf,self.results,self.facilities))

    
    # env run for time, also does config check for facilities
    def run_for(self, time):
        # refresh facilities according to config at start of time step:
        for i in range(0,len(self.conf['total'])): # loop each facility type.
            # pop and release previous slack state
            for j in range(0,len(self.slack_requests[i])):
                self.facilities[i].release(self.slack_requests[i].pop())
            # create new slack state
            for j in range(0,self.conf['total'][i] - self.conf['staffed'][i]):
                self.slack_requests[i].append(self.facilities[i].request())
                if (len(self.facilities[i].queue) > 0): # request did not go through immediately, move it to be first in prio
                    self.facilities[i].queue.insert(0,self.facilities[i].queue.pop())
        # continue simulation from current time
        self.env.run(until= self.env.now + time)
