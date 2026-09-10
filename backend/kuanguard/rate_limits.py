"""Shared sliding-window limits; memory is only a bounded local-development option."""
from collections import defaultdict, deque
from functools import lru_cache
import hashlib
import math
from threading import Lock
import time
from uuid import uuid4

from fastapi import HTTPException
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from .config import settings
from .security import fail

_rates = defaultdict(deque)
_lock = Lock()
_SCRIPT = """
local clock = redis.call('TIME')
local current = clock[1] * 1000 + math.floor(clock[2] / 1000)
local window = 60000
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', current - window)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return {0, math.max(1, tonumber(oldest[2]) + window - current)}
end
redis.call('ZADD', KEYS[1], current, ARGV[2])
redis.call('PEXPIRE', KEYS[1], window)
return {1, 0}
"""


@lru_cache(maxsize=4)
def redis_client(url):
    return Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1, max_connections=32,
                          retry=Retry(NoBackoff(), 0))


def backend(config):
    if config.rate_limit_backend == "auto":
        return "redis" if config.redis_url else "memory"
    return config.rate_limit_backend


def redis_window(client, key, limit):
    return client.eval(_SCRIPT, 1, key, limit, uuid4().hex)


def health():
    config = settings()
    selected = backend(config)
    if selected == "memory":
        return {"backend": selected, "status": "local_only"}
    try:
        if not config.redis_url or not redis_client(config.redis_url).ping():
            return {"backend": selected, "status": "unavailable"}
    except (RedisError, ValueError):
        return {"backend": selected, "status": "unavailable"}
    return {"backend": selected, "status": "ok"}


def rate_limit(request, category, limit=20):
    config = settings()
    peer = request.client.host if request.client else "unknown"
    key = f"kuanguard:{config.app_env}:rate-limit:v1:{category}:{hashlib.sha256(peer.encode()).hexdigest()}"
    if backend(config) == "redis":
        if not config.redis_url:
            fail(503, "RATE_LIMIT_UNAVAILABLE", "操作保護服務暫時無法使用，請稍後重試。")
        try:
            accepted, retry_ms = redis_window(redis_client(config.redis_url), key, limit)
        except (RedisError, ValueError):
            fail(503, "RATE_LIMIT_UNAVAILABLE", "操作保護服務暫時無法使用，請稍後重試。")
    else:
        if config.app_env not in {"development", "test"}:
            fail(503, "RATE_LIMIT_UNAVAILABLE", "正式環境需要共用操作保護服務。")
        with _lock:
            current = time.monotonic()
            if key not in _rates and len(_rates) >= 4096:
                for expired in [item for item, queue in _rates.items() if not queue or queue[-1] <= current-60]:
                    del _rates[expired]
                if len(_rates) >= 4096:
                    fail(503, "RATE_LIMIT_UNAVAILABLE", "本機操作保護容量已滿，請稍後重試。")
            queue = _rates[key]
            while queue and queue[0] <= current-60:
                queue.popleft()
            accepted = len(queue) < limit
            retry_ms = 0 if accepted else (queue[0]+60-current)*1000
            if accepted:
                queue.append(current)
    if not accepted:
        raise HTTPException(429, {"code": "RATE_LIMITED", "message": "操作過於頻繁，請稍候再試。",
                                  "retry_after_seconds": max(1, math.ceil(retry_ms/1000))})
