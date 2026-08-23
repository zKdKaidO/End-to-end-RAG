from __future__ import annotations

import hashlib
import math
import secrets
import time
from dataclasses import dataclass

from redis import Redis
from redis.exceptions import RedisError

from app.auth.service import normalize_email
from app.core.config import settings


class SecurityControlUnavailable(RuntimeError):
    """A mandatory distributed security control is unavailable."""


@dataclass(frozen=True)
class LimitDecision:
    allowed: bool
    retry_after_seconds: int = 0
    reason: str | None = None


_DUAL_BUCKET_LUA = """
local now = tonumber(ARGV[1])
local specs = {
  {KEYS[1], tonumber(ARGV[2]), tonumber(ARGV[3])},
  {KEYS[2], tonumber(ARGV[4]), tonumber(ARGV[5])}
}
local states = {}
local max_retry = 0
for i, spec in ipairs(specs) do
  local values = redis.call('HMGET', spec[1], 'tokens', 'updated')
  local tokens = tonumber(values[1]) or spec[3]
  local updated = tonumber(values[2]) or now
  tokens = math.min(spec[3], tokens + math.max(0, now - updated) * spec[2] / 60000)
  states[i] = {tokens, spec[2], spec[3], spec[1]}
  if tokens < 1 then
    local retry = math.ceil((1 - tokens) * 60000 / spec[2])
    if retry > max_retry then max_retry = retry end
  end
end
if max_retry > 0 then return {0, max_retry} end
for _, state in ipairs(states) do
  local remaining = state[1] - 1
  redis.call('HSET', state[4], 'tokens', remaining, 'updated', now)
  redis.call('PEXPIRE', state[4], math.ceil((state[3] / state[2]) * 120000))
end
return {1, 0}
"""


_GENERATION_ACQUIRE_LUA = """
local now = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local burst = tonumber(ARGV[3])
local lease_id = ARGV[4]
local lease_expiry = tonumber(ARGV[5])
local user_limit = tonumber(ARGV[6])
local global_limit = tonumber(ARGV[7])

redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[3], '-inf', now)
local values = redis.call('HMGET', KEYS[1], 'tokens', 'updated')
local tokens = tonumber(values[1]) or burst
local updated = tonumber(values[2]) or now
tokens = math.min(burst, tokens + math.max(0, now - updated) * rate / 60000)
if tokens < 1 then
  return {0, math.ceil((1 - tokens) * 60000 / rate), 1}
end
if redis.call('ZCARD', KEYS[2]) >= user_limit then return {0, 1000, 2} end
if redis.call('ZCARD', KEYS[3]) >= global_limit then return {0, 1000, 3} end

redis.call('HSET', KEYS[1], 'tokens', tokens - 1, 'updated', now)
redis.call('PEXPIRE', KEYS[1], math.ceil((burst / rate) * 120000))
redis.call('ZADD', KEYS[2], lease_expiry, lease_id)
redis.call('ZADD', KEYS[3], lease_expiry, lease_id)
redis.call('PEXPIRE', KEYS[2], math.max(1000, lease_expiry - now + 1000))
redis.call('PEXPIRE', KEYS[3], math.max(1000, lease_expiry - now + 1000))
return {1, 0, 0}
"""


_GENERATION_RELEASE_LUA = """
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
return 1
"""


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _redis() -> Redis:
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


class LoginRateLimiter:
    def __init__(self, redis: Redis | None = None, namespace: str = "security:v1:login"):
        self.redis = redis or _redis()
        self.namespace = namespace

    def consume(self, network_identity: str, account_identifier: str) -> LimitDecision:
        now_ms = int(time.time() * 1000)
        keys = [
            f"{self.namespace}:network:{_digest(network_identity)}",
            f"{self.namespace}:account:{_digest(normalize_email(account_identifier))}",
        ]
        try:
            allowed, retry_ms = self.redis.eval(
                _DUAL_BUCKET_LUA,
                2,
                *keys,
                now_ms,
                settings.AUTH_LOGIN_NETWORK_RATE_PER_MINUTE,
                settings.AUTH_LOGIN_NETWORK_BURST,
                settings.AUTH_LOGIN_RATE_PER_MINUTE,
                settings.AUTH_LOGIN_BURST,
            )
        except RedisError as exc:
            raise SecurityControlUnavailable("Login protection is unavailable") from exc
        return LimitDecision(bool(allowed), max(1, math.ceil(int(retry_ms) / 1000)) if not allowed else 0, "LOGIN_RATE_LIMIT")


@dataclass(frozen=True)
class GenerationLease:
    lease_id: str
    user_key: str
    global_key: str


class GenerationAdmissionController:
    def __init__(self, redis: Redis | None = None, namespace: str = "security:v1:generation"):
        self.redis = redis or _redis()
        self.namespace = namespace

    def acquire(self, user_id: str) -> tuple[LimitDecision, GenerationLease | None]:
        now_ms = int(time.time() * 1000)
        lease_id = secrets.token_urlsafe(24)
        user_digest = _digest(user_id)
        rate_key = f"{self.namespace}:rate:{user_digest}"
        user_key = f"{self.namespace}:active:user:{user_digest}"
        global_key = f"{self.namespace}:active:global"
        expiry = now_ms + settings.CHAT_GENERATION_LEASE_TTL_SECONDS * 1000
        try:
            allowed, retry_ms, reason_code = self.redis.eval(
                _GENERATION_ACQUIRE_LUA,
                3,
                rate_key,
                user_key,
                global_key,
                now_ms,
                settings.CHAT_GENERATION_RATE_PER_MINUTE,
                settings.CHAT_GENERATION_BURST,
                lease_id,
                expiry,
                settings.CHAT_MAX_ACTIVE_GENERATIONS_PER_USER,
                settings.CHAT_MAX_GLOBAL_GENERATIONS,
            )
        except RedisError as exc:
            raise SecurityControlUnavailable("Generation admission control is unavailable") from exc
        reasons = {1: "GENERATION_RATE_LIMIT", 2: "USER_GENERATION_ACTIVE", 3: "GLOBAL_GENERATION_ACTIVE"}
        if not allowed:
            return LimitDecision(False, max(1, math.ceil(int(retry_ms) / 1000)), reasons.get(int(reason_code), "GENERATION_ADMISSION_REJECTED")), None
        return LimitDecision(True), GenerationLease(lease_id, user_key, global_key)

    def release(self, lease: GenerationLease | None) -> None:
        if lease is None:
            return
        try:
            self.redis.eval(_GENERATION_RELEASE_LUA, 2, lease.user_key, lease.global_key, lease.lease_id)
        except RedisError:
            # Lease TTL provides stale recovery if release cannot reach Redis.
            return


login_rate_limiter = LoginRateLimiter()
generation_admission = GenerationAdmissionController()
