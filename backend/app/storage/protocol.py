"""Repository protocol implemented by both storage backends."""

from __future__ import annotations

from typing import Protocol

from backend.app.models import AqiContext, Document, Profile, User


class Repository(Protocol):
    """Persistence port for users, profiles, AQI context and documents."""

    def ensure_schema(self) -> None:
        """Create or migrate the storage schema."""
        ...

    def create_user(self, email: str, password_hash: str) -> User:
        """Insert a user and return it with a generated id."""
        ...

    def get_user_by_email(self, email: str) -> User | None:
        """Return the user with ``email``, or None."""
        ...

    def get_user_by_id(self, user_id: str) -> User | None:
        """Return the user with ``user_id``, or None."""
        ...

    def update_user_password_hash(self, user_id: str, password_hash: str) -> None:
        """Replace the password hash for ``user_id`` when the user exists."""
        ...

    def save_profile(self, profile: Profile) -> Profile:
        """Insert or update the profile for ``profile.user_id``."""
        ...

    def get_profile(self, user_id: str) -> Profile | None:
        """Return the profile for ``user_id``, or None."""
        ...

    def save_aqi_context(self, ctx: AqiContext) -> AqiContext:
        """Insert or update the AQI context for ``ctx.user_id``."""
        ...

    def get_aqi_context(self, user_id: str) -> AqiContext | None:
        """Return the AQI context for ``user_id``, or None."""
        ...

    def create_document(self, doc: Document) -> Document:
        """Insert a document and return it with a generated id."""
        ...

    def list_documents(self, owner_id: str) -> list[Document]:
        """Return every document owned by ``owner_id``."""
        ...

    def get_document(self, doc_id: str) -> Document | None:
        """Return the document with ``doc_id``, or None."""
        ...

    def delete_document(self, doc_id: str, owner_id: str) -> bool:
        """Delete ``doc_id`` when owned by ``owner_id``."""
        ...

    def count_documents(self, owner_id: str) -> int:
        """Return the number of documents owned by ``owner_id``."""
        ...

    def count_users(self) -> int:
        """Return the total number of users."""
        ...

    def count_profiles(self) -> int:
        """Return the total number of profiles."""
        ...

    def count_all_documents(self) -> int:
        """Return the total number of documents across owners."""
        ...

    def close(self) -> None:
        """Release any resources held by the repository."""
        ...
