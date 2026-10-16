from pydantic import BaseModel, ConfigDict, Field


class LocalEventRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    place: str | None = None
    event_city: str | None = None
    date: str | None = None
    source: str | None = None
    url: str | None = None
    image: str | None = None
    image_original: str | None = None
    venue: str | None = None
    official_site: str | None = None
    audience: str | None = None
    provider_place: str | None = None
    provider_categories: str | None = None
    provider_category_list: list[str] | None = None
    lat: float | None = None
    lon: float | None = None
    location_confidence: str | None = None
    is_real: bool | None = None
    category: str | None = None
    category_label: str | None = None
    priority: int | None = None
    weather_sensitivity: str | None = None


class LocalEventDetailResponse(BaseModel):
    source: str
    url: str
    description: str | None = None
    event_city: str | None = None
    place: str | None = None
    venue: str | None = None
    address: str | None = None
    maps_url: str | None = None
    lat: float | None = None
    lon: float | None = None
    location_confidence: str | None = None


class LocalEventsCache(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    generated_at: str | None = None
    age_seconds: int | None = Field(default=None, ge=0)
    storage: str | None = None
    source_counts: dict[str, int] | None = None
    completed_sources: list[str] | None = None
    pending_sources: list[str] | None = None


class LocalEventsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str
    events: list[LocalEventRecord]
    events_scope: str
    source: str | None = None
    sources: list[str]
    is_real: bool
    cache: LocalEventsCache
