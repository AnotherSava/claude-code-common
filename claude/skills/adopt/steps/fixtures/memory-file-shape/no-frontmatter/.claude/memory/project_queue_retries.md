# Queue retries

The worker retries three times with a jittered backoff and then parks the job. A parked
job raises nothing and is invisible until someone reads the parked table, which is why
the nightly summary counts parked jobs rather than failures.
