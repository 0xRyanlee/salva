"""
Party Events Adapter.

Maps UnifiedResult → Party Supabase `events` table schema.
This is the ONLY file that knows about Party's DB column names.
The rest of Salva is completely unaware of Supabase.

Column mapping (live DB, verified):
    UnifiedResult.title           → events.title
    UnifiedResult.description     → events.description
    UnifiedResult.source_name     → events.source
    UnifiedResult.source_url      → events.source_url
    UnifiedResult.external_id     → events.external_id
    UnifiedResult.starts_at       → events.start_time
    UnifiedResult.ends_at         → events.end_time
    UnifiedResult.location_name   → events.location_name
    UnifiedResult.location_address→ events.address
    UnifiedResult.city            → events.city
    UnifiedResult.latitude        → events.latitude
    UnifiedResult.longitude       → events.longitude
    UnifiedResult.capacity        → events.capacity
    UnifiedResult.price_amount    → events.price
    UnifiedResult.cover_image_url → events.cover_image
    UnifiedResult.organizer_name  → events.organizer_name
    UnifiedResult.ai_summary      → events.ai_summary
    UnifiedResult.ai_type         → events.ai_type
    UnifiedResult.ai_tags         → events.ai_tags

Dedup key: (source, source_url) unique pair.
"""
from __future__ import annotations

import logging
import os

from adapters.base import BaseAdapter
from core.controller import RunSummary
from core.types import UnifiedResult
from enrichment import omlx

logger = logging.getLogger("salva.adapters.party")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


class PartyAdapter(BaseAdapter):
    domain = "events"

    def __init__(
        self,
        supabase_url: str = SUPABASE_URL,
        service_key: str = SUPABASE_SERVICE_KEY,
        enrich: bool = True,
    ):
        if not supabase_url or not service_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        self._url = supabase_url.rstrip("/")
        self._key = service_key
        self._enrich = enrich
        self._client = self._make_client()

    def persist(self, results: list[UnifiedResult]) -> dict:
        inserted = updated = skipped = 0

        for r in results:
            if self._enrich and not r.ai_summary:
                self._try_enrich(r)

            row = self._to_row(r)
            outcome = self._upsert(row, r.source_name, r.source_url)
            if outcome == "new":
                inserted += 1
            elif outcome == "updated":
                updated += 1
            else:
                skipped += 1

        logger.info(
            "Party persist: +%d updated=%d skipped=%d",
            inserted, updated, skipped
        )
        return {"inserted": inserted, "updated": updated, "skipped": skipped}

    def on_run_complete(self, summary: RunSummary) -> None:
        logger.info(
            "Party run done: %d qualified in %.1fs",
            summary.total_qualified, summary.elapsed_seconds
        )

    # ------------------------------------------------------------------

    def _try_enrich(self, r: UnifiedResult) -> None:
        fields = self.enrich_fields(r)
        enriched = omlx.enrich("events", fields)
        if enriched:
            r.ai_type = enriched.get("type")
            r.ai_summary = enriched.get("summary")
            r.ai_tags = enriched.get("tags", [])
            r.ai_language = enriched.get("language")
            r.ai_target_audience = enriched.get("target_audience")
            if enriched.get("city") and not r.city:
                r.city = enriched["city"]

    def _to_row(self, r: UnifiedResult) -> dict:
        return {
            "source": r.source_name,
            "source_url": r.source_url,
            "external_id": r.external_id,
            "title": r.title,
            "description": r.description,
            "type": r.ai_type or "event",
            "tags": r.tags or r.ai_tags,
            "start_time": r.starts_at.isoformat() if r.starts_at else None,
            "end_time": r.ends_at.isoformat() if r.ends_at else None,
            "location_name": r.location_name,
            "address": r.location_address,
            "city": r.city,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "capacity": r.capacity,
            "price": r.price_amount,
            "cover_image": r.cover_image_url,
            "organizer_name": r.organizer_name,
            "ai_summary": r.ai_summary,
            "ai_type": r.ai_type,
            "ai_tags": r.ai_tags,
            "is_public": True,
            "status": "published",
            "enrichment_status": "done" if r.ai_summary else "pending",
        }

    def _upsert(self, row: dict, source: str, source_url: str) -> str:
        existing = (
            self._client.table("events")
            .select("id")
            .eq("source", source)
            .eq("source_url", source_url)
            .execute()
        )
        if existing.data:
            self._client.table("events").update(row).eq("id", existing.data[0]["id"]).execute()
            return "updated"
        if not row.get("title") or len(row["title"]) < 3:
            return "skipped"
        self._client.table("events").insert(row).execute()
        return "new"

    def _make_client(self):
        try:
            from supabase import create_client
            return create_client(self._url, self._key)
        except ImportError:
            raise ImportError("pip install supabase")
