import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from giftai.core.validation import Interests, Name, Notes, PartialUpdate
from giftai.gifting import Relationship


class RecipientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    relationship: Relationship
    interests: Interests = []
    notes: Notes | None = None


class RecipientUpdate(PartialUpdate):
    required_when_present = frozenset({"name", "relationship", "interests"})

    name: Name | None = None
    relationship: Relationship | None = None
    interests: Interests | None = None
    notes: Notes | None = None


class RecipientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    relationship: Relationship
    interests: list[str]
    notes: str | None
    created_at: datetime
    updated_at: datetime
