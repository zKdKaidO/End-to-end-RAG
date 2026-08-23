# Account Deletion Residual Audit V1

A controlled real-queue test created Alice with sessions, grants, chat sessions/turns, one uniquely owned document/object, and access to a shared document also granted to Bob. Deletion completed through the real API, RQ worker, PostgreSQL and MinIO.

After completion, Alice's user, sessions, grants, chat rows, unique document descendants, and unique MinIO object were absent. The shared document/object and Bob's grant remained. The RQ finished-job record persisted only for the configured finite result-retention window and contained identifiers/state rather than the deleted source or chat body; the controlled probe then cleaned it.

Application logs and infrastructure backups have independent operational retention and are not synchronously erased by product account deletion. This is a documented residual requiring a deployment retention/backup policy, not a live authorization leak.
