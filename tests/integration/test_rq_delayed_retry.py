import pytest
import uuid
import time
import subprocess
import os
from redis import Redis
from rq import Queue, Retry
from rq.job import Job

@pytest.fixture(scope="module")
def raw_redis():
    return Redis(host='redis', port=6379, decode_responses=True)

@pytest.fixture
def queue_name():
    return f"document-indexing-runtime-test-{uuid.uuid4()}"

@pytest.fixture
def real_worker(queue_name):
    env = os.environ.copy()
    env["PYTHONPATH"] = "/app"
    
    # Start the actual worker externally
    # worker.work(with_scheduler=True) or 
# q worker --with-scheduler
    process = subprocess.Popen(
        ["rq", "worker", queue_name, "--url", "redis://redis:6379/0", "--with-scheduler"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    time.sleep(2) # Wait for worker to boot
    
    yield process
    
    process.terminate()
    process.wait(timeout=5)

def test_transient_exhaustion(raw_redis, queue_name, real_worker):
    q = Queue(queue_name, connection=Redis(host='redis', port=6379))
    job_key = str(uuid.uuid4())
    raw_redis.delete(f"test_exec_timestamps:{job_key}")
    
    job = q.enqueue(
        "tests.rq_runtime_jobs.transient_always_fail",
        args=(job_key,),
        job_id=job_key,
        retry=Retry(max=2, interval=[2, 5])
    )
    
    # Wait for execution to finish (initial + 2s + 5s = ~7s) + some buffer
    time.sleep(12)
    
    timestamps = raw_redis.lrange(f"test_exec_timestamps:{job_key}", 0, -1)
    assert len(timestamps) == 3, f"Expected 3 executions, got {len(timestamps)}"
    
    t0 = float(timestamps[0])
    t1 = float(timestamps[1])
    t2 = float(timestamps[2])
    
    delta1 = t1 - t0
    delta2 = t2 - t1
    
    assert 1.0 <= delta1 <= 4.0, f"delta1 out of bounds: {delta1}"
    assert 4.0 <= delta2 <= 8.0, f"delta2 out of bounds: {delta2}"
    
    updated_job = Job.fetch(job_key, connection=Redis(host='redis', port=6379))
    assert updated_job.get_status() == "failed"
    assert updated_job.retries_left == 0

def test_transient_recovery(raw_redis, queue_name, real_worker):
    q = Queue(queue_name, connection=Redis(host='redis', port=6379))
    job_key = str(uuid.uuid4())
    raw_redis.delete(f"test_exec_timestamps:{job_key}")
    
    job = q.enqueue(
        "tests.rq_runtime_jobs.transient_fail_once_then_success",
        args=(job_key,),
        job_id=job_key,
        retry=Retry(max=2, interval=[2, 5])
    )
    
    # Wait for execution (initial + 2s = ~2s) + buffer
    time.sleep(5)
    
    timestamps = raw_redis.lrange(f"test_exec_timestamps:{job_key}", 0, -1)
    assert len(timestamps) == 2, f"Expected 2 executions, got {len(timestamps)}"
    
    t0 = float(timestamps[0])
    t1 = float(timestamps[1])
    
    delta = t1 - t0
    assert 1.0 <= delta <= 4.0, f"delta out of bounds: {delta}"
    
    updated_job = Job.fetch(job_key, connection=Redis(host='redis', port=6379))
    assert updated_job.get_status() == "finished"
