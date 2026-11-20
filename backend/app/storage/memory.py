"""In-memory repository used by tests and the offline demo."""

from __future__ import annotations

import threading
import uuid
from dataclasses import replace
from datetime import UTC, datetime

from backend.app.models import AqiContext, Document, Profile, User


def _now() -> str:
    """Return the current UTC timestamp in ISO-8601."""
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    """Return a fresh hex identifier."""
    return uuid.uuid4().hex


class InMemoryRepo:
    """A thread-safe in-memory implementation of the Repository protocol."""

    def __init__(self) -> None:
        """Initialise the empty stores and the lock."""
        self._users: dict[str, User] = {}
        self._users_by_email: dict[str, str] = {}
        self._profiles: dict[str, Profile] = {}
        self._contexts: dict[str, AqiContext] = {}
        self._documents: dict[str, Document] = {}
        self._lock = threading.RLock()

    def ensure_schema(self) -> None:
        """No-op: the in-memory store needs no schema."""

    def create_user(self, email: str, password_hash: str) -> User:
        """Insert a user, rejecting a duplicate email.

        Raises:
            ValueError: When ``email`` is already registered.
        """
        with self._lock:
            if email in self._users_by_email:
                raise ValueError("email already registered")
            user = User(_new_id(), email, password_hash, _now())
            self._users[user.id] = user
            self._users_by_email[user.email] = user.id
        return user

    def get_user_by_email(self, email: str) -> User | None:
        """Return the user with ``email``, or None."""
        with self._lock:
            user_id = self._users_by_email.get(email)
            return self._users.get(user_id) if user_id else None

    def get_user_by_id(self, user_id: str) -> User | None:
        """Return the user with ``user_id``, or None."""
        with self._lock:
            return self._users.get(user_id)

    def update_user_password_hash(self, user_id: str, password_hash: str) -> None:
        """Replace the password hash for ``user_id`` when it exists."""
        with self._lock:
            user = self._users.get(user_id)
            if user is not None:
                self._users[user_id] = replace(user, password_hash=password_hash)

    def save_profile(self, profile: Profile) -> Profile:
        """Insert or update the profile for ``profile.user_id``."""
        with self._lock:
            self._profiles[profile.user_id] = profile
        return profile

    def get_profile(self, user_id: str) -> Profile | None:
        """Return the profile for ``user_id``, or None."""
        with self._lock:
            return self._profiles.get(user_id)

    def save_aqi_context(self, ctx: AqiContext) -> AqiContext:
        """Insert or update the AQI context for ``ctx.user_id``."""
        with self._lock:
            self._contexts[ctx.user_id] = ctx
        return ctx

    def get_aqi_context(self, user_id: str) -> AqiContext | None:
        """Return the AQI context for ``user_id``, or None."""
        with self._lock:
            return self._contexts.get(user_id)

    def create_document(self, doc: Document) -> Document:
        """Insert a document and return it with a generated id."""
        stored = replace(
            doc,
            id=doc.id or _new_id(),
            created_at=doc.created_at or _now(),
        )
        with self._lock:
            self._documents[stored.id] = stored
        return stored

    def list_documents(self, owner_id: str) -> list[Document]:
        """Return every document owned by ``owner_id``."""
        with self._lock:
            return [
                doc for doc in self._documents.values() if doc.owner_id == owner_id
            ]

    def get_document(self, doc_id: str) -> Document | None:
        """Return the document with ``doc_id``, or None."""
        with self._lock:
            return self._documents.get(doc_id)

    def delete_document(self, doc_id: str, owner_id: str) -> bool:
        """Delete ``doc_id`` when owned by ``owner_id``."""
        with self._lock:
            doc = self._documents.get(doc_id)
            if doc is None or doc.owner_id != owner_id:
                return False
            del self._documents[doc_id]
            return True

    def count_documents(self, owner_id: str) -> int:
        """Return the number of documents owned by ``owner_id``."""
        with self._lock:
            return sum(
                1 for doc in self._documents.values() if doc.owner_id == owner_id
            )

    def count_users(self) -> int:
        """Return the total number of users."""
        with self._lock:
            return len(self._users)

    def count_profiles(self) -> int:
        """Return the total number of profiles."""
        with self._lock:
            return len(self._profiles)

    def count_all_documents(self) -> int:
        """Return the total number of documents across owners."""
        with self._lock:
            return len(self._documents)

    def close(self) -> None:
        """No-op: nothing to release."""
