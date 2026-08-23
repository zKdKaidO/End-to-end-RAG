# Account Deletion V1

`DELETE /api/v1/auth/account` validates the current password and atomically:

1. locks the active user;
2. creates one durable `account_deletion_jobs` intent;
3. snapshots every private document into `account_deletion_document_refs`;
4. changes `ACTIVE -> DELETING`;
5. revokes all auth sessions;
6. commits, attempts RQ enqueue, and returns HTTP 202.

Redis failure does not lose intent. Startup reconciliation and the admin retry endpoint enqueue the same logical RQ job ID. Conditional state transitions ensure a fast worker's `RUNNING/COMPLETED` state cannot be overwritten by the request/reconciler.

The account-deletion worker is repeatable:

```text
PENDING/QUEUED/FAILED -> RUNNING
  -> revoke sessions again
  -> cascade chat/history/snapshots
  -> remove subject's grants
  -> resume durable document refs
       referenced -> RETAINED_REFERENCED
       orphaned   -> DELETED
       failure    -> FAILED (retryable)
  -> delete/finalize user
  -> COMPLETED
```

A simulated crash after grants were removed preserved both durable refs and resumed successfully. Shared/Global documents remain; user-only canonical documents are eventually removed. No synchronous second cleanup path exists in the HTTP request.
