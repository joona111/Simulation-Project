from config import expovariate


def patient_generator(env, hospital, config):
    i = 0
    while True:
        i += 1

        patient = {
            "id": i,
            "created_at": env.now,
            "prep_time": expovariate(config["prep_mean"]),
            "op_time": expovariate(config["op_mean"]),
            "rec_time": expovariate(config["recovery_mean"]),
        }

        env.process(patient_flow(env, patient, hospital, config))

        ia = expovariate(config["interarrival_mean"])
        yield env.timeout(ia)


def patient_flow(env, patient, hospital, config):
    prep_res = hospital["prep"]
    or_res = hospital["op"]
    rec_res = hospital["recovery"]
    metrics = hospital["metrics"]

    with prep_res.request() as req:
        arrival_to_prep_q = env.now
        yield req
        start_prep = env.now
        yield env.timeout(patient["prep_time"])
        end_prep = env.now

    if config.get("block_or_until_recovery", True):
        with or_res.request() as or_req:
            arrival_to_or_q = env.now
            yield or_req
            start_op = env.now
            # do operation
            yield env.timeout(patient["op_time"])
            end_op = env.now

            with rec_res.request() as rec_req:
                arrival_to_rec_q = env.now
                yield rec_req
                start_rec = env.now
                yield env.timeout(patient["rec_time"])
                end_rec = env.now

    else:
        with or_res.request() as or_req:
            arrival_to_or_q = env.now
            yield or_req
            start_op = env.now
            yield env.timeout(patient["op_time"])
            end_op = env.now

        with rec_res.request() as rec_req:
            arrival_to_rec_q = env.now
            yield rec_req
            start_rec = env.now
            yield env.timeout(patient["rec_time"])
            end_rec = env.now

    metrics["completed"] += 1
    metrics["patient_times"].append({
        "id": patient["id"],
        "arrival": patient["created_at"],
        "end": end_rec,
        "total_time": end_rec - patient["created_at"],
        "prep_wait": start_prep - arrival_to_prep_q,
        "or_wait": start_op - arrival_to_or_q,
        "rec_wait": start_rec - arrival_to_rec_q,
    })


def monitor(env, hospital, interval):
    prep_res = hospital["prep"]
    or_res = hospital["op"]
    rec_res = hospital["recovery"]
    metrics = hospital["metrics"]

    while True:
        t = env.now
        prep_q_len = len(prep_res.queue)
        or_q_len = len(or_res.queue)
        rec_q_len = len(rec_res.queue)
        or_util = or_res.count / or_res.capacity

        metrics["prep_q"].append((t, prep_q_len))
        metrics["or_q"].append((t, or_q_len))
        metrics["rec_q"].append((t, rec_q_len))
        metrics["or_util"].append((t, or_util))
        yield env.timeout(interval)