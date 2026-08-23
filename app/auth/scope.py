from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UserRetrievalScope:
    user_id: UUID


@dataclass(frozen=True)
class InternalRetrievalScope:
    reason: str


RetrievalAccessScope = UserRetrievalScope | InternalRetrievalScope
