import time
from redis import Redis

def transient_always_fail(job_key):
    r = Redis(host='redis', port=6379, decode_responses=True)
    r.rpush(f"test_exec_timestamps:{job_key}", str(time.time()))
    raise Exception("Always fail")

def transient_fail_once_then_success(job_key):
    r = Redis(host='redis', port=6379, decode_responses=True)
    r.rpush(f"test_exec_timestamps:{job_key}", str(time.time()))
    count = r.llen(f"test_exec_timestamps:{job_key}")
    if count == 1:
        raise Exception("Fail on first attempt")
    return "Success"
