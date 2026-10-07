from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any
from uuid import UUID

from qdrant_client import models

from aria.modules.native_web_llm.contracts import NativeWebCitation, NativeWebResult
from aria.modules.qdrant_gateway.client import create_async_qdrant_client


def evidence_point_id(question: str) -> str:
    digest = hashlib.sha256(" ".join(str(question or "").lower().split()).encode("utf-8")).hexdigest()
    return str(UUID(digest[:32]))


def _parse_time(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None


class PublicWebEvidenceStore:
    def __init__(
        self,
        *,
        qdrant_url: str,
        qdrant_api_key: str,
        collection: str,
        read_timeout_ms: int = 200,
        ttl_hours: int = 24,
        client: Any | None = None,
    ) -> None:
        self.collection = str(collection or "aria_web_evidence").strip()
        self.read_timeout_ms = max(10, min(int(read_timeout_ms or 200), 2000))
        self.ttl_hours = max(1, min(int(ttl_hours or 24), 720))
        self.client = client or create_async_qdrant_client(
            url=qdrant_url,
            api_key=qdrant_api_key or None,
            timeout=max(1.0, self.read_timeout_ms / 1000),
        )
        self._tasks: set[asyncio.Task[Any]] = set()

    async def lookup(self, question: str) -> tuple[NativeWebCitation, ...]:
        try:
            rows = await asyncio.wait_for(
                self.client.retrieve(
                    collection_name=self.collection,
                    ids=[evidence_point_id(question)],
                    with_payload=True,
                    with_vectors=False,
                ),
                timeout=self.read_timeout_ms / 1000,
            )
        except Exception:
            return ()
        if not rows:
            return ()
        payload = getattr(rows[0], "payload", None)
        if not isinstance(payload, dict):
            return ()
        expires_at = _parse_time(payload.get("expires_at"))
        if expires_at is None or expires_at <= datetime.now(timezone.utc):
            return ()
        citations: list[NativeWebCitation] = []
        for row in list(payload.get("citations") or [])[:6]:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url", "") or "").strip()
            if not url:
                continue
            citations.append(
                NativeWebCitation(
                    url=url,
                    title=str(row.get("title", "") or "").strip(),
                    source="qdrant.public_web_evidence",
                )
            )
        return tuple(citations)

    def schedule_update(self, question: str, result: NativeWebResult) -> bool:
        if not result.passed or not result.citations:
            return False
        task = asyncio.create_task(self._update(question, result), name="native-web-evidence-update")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return True

    async def _ensure_collection(self) -> None:
        try:
            await self.client.get_collection(self.collection)
            return
        except Exception:
            pass
        await self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(size=1, distance=models.Distance.COSINE),
        )

    async def _update(self, question: str, result: NativeWebResult) -> None:
        try:
            await self._ensure_collection()
            now = datetime.now(timezone.utc)
            payload = {
                "contract": "public_web_evidence_v1",
                "query_fingerprint": hashlib.sha256(
                    " ".join(str(question or "").lower().split()).encode("utf-8")
                ).hexdigest(),
                "provider": result.provider_shape,
                "model": result.model,
                "updated_at": now.isoformat(),
                "expires_at": (now + timedelta(hours=self.ttl_hours)).isoformat(),
                "citations": [
                    {"url": citation.url, "title": citation.title}
                    for citation in result.citations[:6]
                ],
            }
            await self.client.upsert(
                collection_name=self.collection,
                points=[
                    models.PointStruct(
                        id=evidence_point_id(question),
                        vector=[0.0],
                        payload=payload,
                    )
                ],
            )
        except Exception:
            return
