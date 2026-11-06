from __future__ import annotations

import threading

from pyme_guard.domain.journey import Application


class InMemoryApplicationRepository:
    """Repositorio del prototipo. En producción: PostgreSQL con cifrado y retención definida."""

    def __init__(self) -> None:
        self._items: dict[str, Application] = {}
        self._lock = threading.Lock()

    def save(self, application: Application) -> None:
        with self._lock:
            self._items[application.id] = application

    def get(self, application_id: str) -> Application | None:
        with self._lock:
            return self._items.get(application_id)

    def human_queue(self) -> list[Application]:
        with self._lock:
            pending = [a for a in self._items.values() if a.in_human_queue]
        return sorted(pending, key=lambda a: a.created_at)
