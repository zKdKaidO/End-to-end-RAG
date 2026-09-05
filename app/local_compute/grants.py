"""Trusted platform-grant verification and local durable one-time consumption."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .errors import LocalComputeError, LocalComputeErrorCode


ALLOWED_OPERATIONS = frozenset(
    {
        "documents",
        "jobs",
        "retrieval",
        "answer",
    }
)


@dataclass(frozen=True)
class VerifiedGrant:
    grant_id: str
    user_id: str
    device_id: str
    credential_epoch: int
    endpoint_generation: str
    origin: str
    browser_nonce: str
    operations: frozenset[str]
    expires_at: int


class PlatformGrantVerificationKeyProvider:
    def __init__(self, public_key_b64: str):
        self.public_key_b64 = public_key_b64

    def get(self) -> str:
        if not self.public_key_b64:
            raise LocalComputeError(
                LocalComputeErrorCode.PLATFORM_VERIFICATION_KEY_UNAVAILABLE
            )

        return self.public_key_b64


def _decode_urlsafe_base64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)

    return base64.urlsafe_b64decode(
        value + padding
    )


def _verify_grant_signature(
    grant: str,
    public_key_b64: str,
) -> dict:
    """
    Verify the platform-issued local-session grant without importing
    platform database/control-plane code.

    Wire format is intentionally identical to ComputeControlService:
        base64url(json claims).base64url(ed25519 signature)
    """

    try:
        encoded_claims, encoded_signature = grant.split(
            ".",
            1,
        )

        if not encoded_claims or not encoded_signature:
            raise ValueError(
                "Malformed grant."
            )

        signature = _decode_urlsafe_base64(
            encoded_signature
        )

        public_key_bytes = base64.b64decode(
            public_key_b64,
            validate=True,
        )

        public_key = Ed25519PublicKey.from_public_bytes(
            public_key_bytes
        )

        public_key.verify(
            signature,
            encoded_claims.encode("ascii"),
        )

        claims_bytes = _decode_urlsafe_base64(
            encoded_claims
        )

        claims = json.loads(
            claims_bytes.decode("utf-8")
        )

        if not isinstance(claims, dict):
            raise ValueError(
                "Grant claims must be an object."
            )

        return claims

    except (
        ValueError,
        TypeError,
        UnicodeDecodeError,
        binascii.Error,
        InvalidSignature,
        json.JSONDecodeError,
    ) as exc:
        raise LocalComputeError(
            LocalComputeErrorCode.GRANT_SIGNATURE_INVALID
        ) from exc


class PlatformGrantVerifier:
    def __init__(
        self,
        runtime,
        key_provider: PlatformGrantVerificationKeyProvider,
        now=time.time,
    ):
        self.runtime = runtime
        self.key_provider = key_provider
        self.now = now

    def validate(
        self,
        grant: str,
        origin: str,
        browser_nonce: str,
    ) -> VerifiedGrant:
        if self.runtime.state.value in {
            "REVOKED",
            "UPDATE_REQUIRED",
        }:
            if self.runtime.state.value == "REVOKED":
                raise LocalComputeError(
                    LocalComputeErrorCode.DEVICE_REVOKED
                )

            raise LocalComputeError(
                LocalComputeErrorCode.UPDATE_REQUIRED
            )

        if origin not in self.runtime.settings.allowed_origins:
            raise LocalComputeError(
                LocalComputeErrorCode.ORIGIN_NOT_ALLOWED
            )

        claims = _verify_grant_signature(
            grant,
            self.key_provider.get(),
        )

        paired = (
            self.runtime.catalog
            .get_paired_device_state()
        )

        if not paired:
            raise LocalComputeError(
                LocalComputeErrorCode.NOT_PAIRED
            )

        try:
            operations = frozenset(
                claims["operations"]
            )

            verified = VerifiedGrant(
                grant_id=str(
                    claims["grant_id"]
                ),
                user_id=str(
                    claims["user_id"]
                ),
                device_id=str(
                    claims["device_id"]
                ),
                credential_epoch=int(
                    claims["credential_epoch"]
                ),
                endpoint_generation=str(
                    claims["endpoint_generation"]
                ),
                origin=str(
                    claims["origin"]
                ),
                browser_nonce=str(
                    claims["browser_nonce"]
                ),
                operations=operations,
                expires_at=int(
                    claims["exp"]
                ),
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise LocalComputeError(
                LocalComputeErrorCode.GRANT_INVALID
            ) from exc

        if (
            verified.device_id
            != paired["device_id"]
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.GRANT_DEVICE_MISMATCH
            )

        owner_user_id = paired.get(
            "owner_user_id"
        )

        if (
            owner_user_id
            and verified.user_id != owner_user_id
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.GRANT_DEVICE_MISMATCH
            )

        if (
            verified.credential_epoch
            != int(
                paired["credential_epoch"]
            )
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.GRANT_EPOCH_MISMATCH
            )

        if (
            verified.endpoint_generation
            != self.runtime.endpoint_generation
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.ENDPOINT_GENERATION_MISMATCH
            )

        if verified.origin != origin:
            raise LocalComputeError(
                LocalComputeErrorCode.ORIGIN_NOT_ALLOWED
            )

        if not secrets.compare_digest(
            verified.browser_nonce,
            browser_nonce,
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.BROWSER_NONCE_MISMATCH
            )

        if verified.expires_at <= int(
            self.now()
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.GRANT_EXPIRED
            )

        if (
            not operations
            or not operations.issubset(
                ALLOWED_OPERATIONS
            )
        ):
            raise LocalComputeError(
                LocalComputeErrorCode.GRANT_OPERATION_INVALID
            )

        return verified

    def consume(
        self,
        verified: VerifiedGrant,
    ) -> None:
        grant_hash = hashlib.sha256(
            verified.grant_id.encode("utf-8")
        ).hexdigest()

        consumed = (
            self.runtime.catalog
            .consume_local_grant(
                grant_hash,
                verified.expires_at,
                int(
                    self.now()
                ),
            )
        )

        if not consumed:
            raise LocalComputeError(
                LocalComputeErrorCode.GRANT_ALREADY_CONSUMED
            )