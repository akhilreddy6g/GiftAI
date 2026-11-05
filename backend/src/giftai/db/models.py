"""Imports every ORM model so that ``Base.metadata`` knows the full schema.

Alembic imports this module before comparing models with the database. Each feature that
stores data adds its ``models`` module here.
"""

from giftai.agent.models import AgentUsage, Recommendation
from giftai.catalog.models import Product, ProductNeighbor
from giftai.chats.models import Chat, Message
from giftai.recipients.models import Recipient
from giftai.rulebook.models import GiftingRule, KnowledgeSource, RuleSource
from giftai.users.models import User

__all__ = [
    "AgentUsage",
    "Chat",
    "GiftingRule",
    "KnowledgeSource",
    "Message",
    "Product",
    "ProductNeighbor",
    "Recipient",
    "Recommendation",
    "RuleSource",
    "User",
]
