#!/usr/bin/env python3
from __future__ import annotations

import os
from redis import Redis
from rq import Worker, Queue, Connection


def main():
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    listen = [os.environ.get("RQ_QUEUE", "default")]
    conn = Redis.from_url(redis_url)
    with Connection(conn):
        worker = Worker(list(map(Queue, listen)))
        worker.work()


if __name__ == "__main__":
    main()

