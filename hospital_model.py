# -- file that contains process function definitions --

import random
import simpy
import copy

# generator starts new patient process according to interval distribution
def patient_generator_mkB(env,conf,resu,facilities):
    while True:
        env.process(patient_mkB(env,conf,resu,facilities))
        t_out = random.expovariate(1/conf['means'][0])
        if (conf['unif'][0] != None):
            t_out = random.uniform(conf['unif'][0][0],conf['unif'][0][1])
        yield env.timeout(t_out)

# individual patient, keeps track of actual service times for each stage: required time and extra waiting
def patient_mkB(env,conf,resu,facilities):
    # minimum processing times for each stage, using config
    e = random.expovariate
    req_times = [e(1/conf['means'][1]),e(1/conf['means'][2]),e(1/conf['means'][3])]
    
    if (conf['unif'][1] != None):
        req_times[0] = random.uniform(conf['unif'][1][0],conf['unif'][1][1])
    if (conf['unif'][2] != None):
        req_times[1] = random.uniform(conf['unif'][2][0],conf['unif'][2][1])
    if (conf['unif'][3] != None):
        req_times[2] = random.uniform(conf['unif'][3][0],conf['unif'][3][1])

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
            'patient_counts': copy.deepcopy(resu['patient_counts']), # totals in system at snapshot time
            'queues': [len(facilities[0].queue), len(facilities[1].queue), len(facilities[2].queue)] # queues of each stage.
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
            'or_time_blocked': 0
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
        # continue simulation from current time:
        self.env.run(until= self.env.now + time)
