#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agents_shipgate.core.human_authorization import human_authorization_signature_payload
from agents_shipgate.schemas.human_authorization import (
    HumanAuthorizationPrincipalV1,
    HumanAuthorizationProofV1,
    HumanAuthorizationRequestV1,
    HumanAuthorizationStatementV1,
    TrustedEd25519KeyV1,
    build_human_authorization,
    build_human_authorization_trust_policy,
    ed25519_key_id,
)


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def load_or_create_key(path: Path) -> Ed25519PrivateKey:
    if path.exists():
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise SystemExit("stored key is not Ed25519")
        return key
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    path.chmod(0o600)
    return key


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", type=Path, required=True)
    ap.add_argument("--grant", type=Path, required=True)
    ap.add_argument("--policy", type=Path, required=True)
    ap.add_argument("--key", type=Path, required=True)
    ap.add_argument("--mode", choices=("valid", "expired"), required=True)
    args = ap.parse_args()

    request = HumanAuthorizationRequestV1.model_validate_json(args.request.read_text())
    key = load_or_create_key(args.key)
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    key_id = ed25519_key_id(public)
    principal = "github:user:stage008b-reviewer"
    now = datetime.now(UTC)

    trusted = TrustedEd25519KeyV1(
        key_id=key_id,
        public_key=b64url(public),
        provider="github",
        principal=principal,
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
    )
    policy = build_human_authorization_trust_policy(
        repository_ids=[request.repository_id],
        keys=[trusted],
        max_ttl_seconds=12 * 60 * 60,
        clock_skew_seconds=30,
    )
    args.policy.parent.mkdir(parents=True, exist_ok=True)
    args.policy.write_text(policy.model_dump_json(indent=2) + "\n", encoding="utf-8")
    args.policy.chmod(0o600)

    if args.mode == "valid":
        issued = now - timedelta(seconds=5)
        not_before = now - timedelta(seconds=5)
        expires = now + timedelta(hours=2)
    else:
        issued = now - timedelta(hours=3)
        not_before = now - timedelta(hours=3)
        expires = now - timedelta(hours=1)

    statement = HumanAuthorizationStatementV1(
        request=request,
        principal=HumanAuthorizationPrincipalV1(provider="github", subject=principal),
        reason=f"Stage008B externally signed {args.mode} exact-operation grant.",
        issued_at=issued,
        not_before=not_before,
        expires_at=expires,
        nonce=b64url((f"stage008b-{args.mode}-{request.authorization_request_id}").encode()[:48]),
    )
    proof = HumanAuthorizationProofV1(
        key_id=key_id,
        signature=b64url(key.sign(human_authorization_signature_payload(statement))),
    )
    grant = build_human_authorization(statement=statement, proof=proof)
    args.grant.parent.mkdir(parents=True, exist_ok=True)
    args.grant.write_text(
        json.dumps(grant.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.grant.chmod(0o600)

    print(json.dumps({
        "authorization_id": grant.authorization_id,
        "authorization_request_id": request.authorization_request_id,
        "mode": args.mode,
        "repository_id": request.repository_id,
        "source_commit_sha": request.source_head_commit_sha,
        "destination_ref": request.operation.destination_ref,
        "expected_lease_oid": request.operation.expected_lease_oid,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
