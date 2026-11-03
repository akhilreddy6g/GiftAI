"""Imports every ORM model so that ``Base.metadata`` knows the full schema.

Alembic imports this module before comparing models with the database. Each feature that
stores data adds its ``models`` module here.
"""

from giftai.chats.models import Chat, Message
from giftai.recipients.models import Recipient
from giftai.users.models import User

__all__ = ["Chat", "Message", "Recipient", "User"]
