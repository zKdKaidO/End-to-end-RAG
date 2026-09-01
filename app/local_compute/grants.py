"""Trusted platform-grant verification and local durable one-time consumption."""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass

from app.compute_control import ComputeControlError, ComputeControlService

from .errors import LocalComputeError, LocalComputeErrorCode

ALLOWED_OPERATIONS = frozenset({"documents", "jobs", "retrieval", "answer"})


@dataclass(frozen=True)
class VerifiedGrant:
    grant_id: str; user_id: str; device_id: str; credential_epoch: int; endpoint_generation: str; origin: str; browser_nonce: str; operations: frozenset[str]; expires_at: int


class PlatformGrantVerificationKeyProvider:
    def __init__(self, public_key_b64: str): self.public_key_b64=public_key_b64
    def get(self) -> str:
        if not self.public_key_b64: raise LocalComputeError(LocalComputeErrorCode.PLATFORM_VERIFICATION_KEY_UNAVAILABLE)
        return self.public_key_b64


class PlatformGrantVerifier:
    def __init__(self, runtime, key_provider: PlatformGrantVerificationKeyProvider, now=time.time):
        self.runtime,self.key_provider,self.now=runtime,key_provider,now

    def validate(self, grant: str, origin: str, browser_nonce: str) -> VerifiedGrant:
        if self.runtime.state.value in {"REVOKED", "UPDATE_REQUIRED"}: raise LocalComputeError(LocalComputeErrorCode.DEVICE_REVOKED if self.runtime.state.value=="REVOKED" else LocalComputeErrorCode.UPDATE_REQUIRED)
        if origin not in self.runtime.settings.allowed_origins: raise LocalComputeError(LocalComputeErrorCode.ORIGIN_NOT_ALLOWED)
        try: claims=ComputeControlService.verify_grant_signature(grant,self.key_provider.get())
        except ComputeControlError as exc: raise LocalComputeError(LocalComputeErrorCode.GRANT_SIGNATURE_INVALID) from exc
        paired=self.runtime.catalog.get_paired_device_state()
        if not paired: raise LocalComputeError(LocalComputeErrorCode.NOT_PAIRED)
        try:
            operations=frozenset(claims["operations"]); verified=VerifiedGrant(str(claims["grant_id"]),str(claims["user_id"]),str(claims["device_id"]),int(claims["credential_epoch"]),str(claims["endpoint_generation"]),str(claims["origin"]),str(claims["browser_nonce"]),operations,int(claims["exp"]))
        except (KeyError, TypeError, ValueError) as exc: raise LocalComputeError(LocalComputeErrorCode.GRANT_INVALID) from exc
        if verified.device_id != paired["device_id"] or (paired.get("owner_user_id") and verified.user_id != paired["owner_user_id"]): raise LocalComputeError(LocalComputeErrorCode.GRANT_DEVICE_MISMATCH)
        if verified.credential_epoch != int(paired["credential_epoch"]): raise LocalComputeError(LocalComputeErrorCode.GRANT_EPOCH_MISMATCH)
        if verified.endpoint_generation != self.runtime.endpoint_generation: raise LocalComputeError(LocalComputeErrorCode.ENDPOINT_GENERATION_MISMATCH)
        if verified.origin != origin: raise LocalComputeError(LocalComputeErrorCode.ORIGIN_NOT_ALLOWED)
        if not secrets.compare_digest(verified.browser_nonce,browser_nonce): raise LocalComputeError(LocalComputeErrorCode.BROWSER_NONCE_MISMATCH)
        if verified.expires_at <= int(self.now()): raise LocalComputeError(LocalComputeErrorCode.GRANT_EXPIRED)
        if not operations or not operations.issubset(ALLOWED_OPERATIONS): raise LocalComputeError(LocalComputeErrorCode.GRANT_OPERATION_INVALID)
        return verified

    def consume(self, verified: VerifiedGrant) -> None:
        grant_hash=hashlib.sha256(verified.grant_id.encode()).hexdigest()
        if not self.runtime.catalog.consume_local_grant(grant_hash,verified.expires_at,int(self.now())): raise LocalComputeError(LocalComputeErrorCode.GRANT_ALREADY_CONSUMED)
