"""Runs one agent turn for a chat message and stores the result.

The user's message and the reply are saved together only once the agent has answered,
so a failed turn (the LLMs busy) leaves nothing half-done and the user simply resends.
"""

import logging
import uuid
from datetime import UTC, datetime, time, timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from giftai.agent.graph import (
    AgentDependencies,
    Pick,
    TurnState,
    build_agent,
    order_by_date,
)
from giftai.agent.models import Recommendation
from giftai.agent.profile import GiftProfile
from giftai.agent.repository import AgentUsageRepository, RecommendationRepository
from giftai.agent.schemas import ChatTurn, CitedRule, RecommendationList, RecommendationRead
from giftai.catalog.links import add_to_cart_url
from giftai.catalog.repository import ProductRepository
from giftai.catalog.schemas import ProductRead
from giftai.chats.models import Chat, Message, MessageRole
from giftai.chats.repository import MessageRepository
from giftai.chats.schemas import ChatRead, MessageCreate, MessageRead
from giftai.chats.service import MAX_MESSAGES_PER_CHAT, ChatService
from giftai.chats.titles import describe_chat
from giftai.core.errors import LimitReachedError, RateLimitedError, ServiceUnavailableError
from giftai.embeddings.base import TextEmbedder
from giftai.llm.base import ChatModel, LlmMessage, LlmUnavailableError
from giftai.recipients.models import Recipient
from giftai.rulebook.models import GiftingRule
from giftai.rulebook.repository import RulebookRepository
from giftai.users.models import User

logger = logging.getLogger(__name__)

# How much of the conversation the agent reads each turn.
CONVERSATION_WINDOW = 30
AGENT_OFF_REPLY = (
    "The gift assistant is switched off on this server right now, so I can't suggest "
    "gifts yet. Your message is saved."
)


class GiftAgentService:
    def __init__(
        self,
        session: AsyncSession,
        model: ChatModel | None,
        embedder: TextEmbedder,
        turns_per_day: int,
    ) -> None:
        self._session = session
        self._model = model
        self._embedder = embedder
        self._turns_per_day = turns_per_day
        self._chats = ChatService(session)
        self._messages = MessageRepository(session)
        self._recommendations = RecommendationRepository(session)
        self._usage = AgentUsageRepository(session)
        self._rules = RulebookRepository(session)

    async def reply(self, user: User, chat_id: uuid.UUID, data: MessageCreate) -> ChatTurn:
        chat = await self._chats.get(user, chat_id)
        # Two rows per turn: the message and the reply.
        if await self._messages.count_for_chat(chat.id) >= MAX_MESSAGES_PER_CHAT - 1:
            raise LimitReachedError("This chat is full. Start a new chat to keep going.")

        now = datetime.now(UTC)
        if self._model is None:
            return await self._save_turn(chat, data.content, AGENT_OFF_REPLY, [], [], now)

        today = now.date()
        if await self._usage.turns_on(user.id, today) >= self._turns_per_day:
            tomorrow = datetime.combine(today + timedelta(days=1), time(), UTC)
            raise RateLimitedError(
                int((tomorrow - now).total_seconds()) + 1,
                f"You've used today's {self._turns_per_day} assistant replies. "
                "They reset at midnight UTC.",
            )

        history = await self._messages.recent_for_chat(chat.id, CONVERSATION_WINDOW - 1)
        conversation = [
            LlmMessage("assistant" if m.role is MessageRole.ASSISTANT else "user", m.content)
            for m in history
        ] + [LlmMessage("user", data.content)]
        recipient = await self._recipient(chat)
        state: TurnState = {
            "conversation": conversation,
            "profile": profile_for(chat, recipient),
            "questions_asked": chat.agent_questions_asked,
            "already_shown": await self._recommendations.shown_in_chat(chat.id),
            "today": today,
        }
        # Nothing is held open while the LLM thinks.
        await self._session.commit()

        agent = build_agent(
            AgentDependencies(
                self._model, ProductRepository(self._session), self._embedder, self._rules
            )
        )
        try:
            result = cast(TurnState, await agent.ainvoke(state))
        except LlmUnavailableError as error:
            logger.warning("Agent turn failed: %s", error)
            raise ServiceUnavailableError(
                "The gift assistant is busy right now. Please send your message again in a minute."
            ) from error

        apply_profile(chat, result["profile"], recipient)
        chat.agent_questions_asked = result.get("questions_asked", chat.agent_questions_asked)
        await self._usage.record_turn(user.id, today)
        return await self._save_turn(
            chat,
            data.content,
            result["reply"],
            result.get("picks", []),
            result.get("rules", []),
            now,
        )

    async def latest_recommendations(self, user: User, chat_id: uuid.UUID) -> RecommendationList:
        chat = await self._chats.get(user, chat_id)
        recommendations = await self._recommendations.latest_for_chat(chat.id)
        rule_ids = {rule_id for r in recommendations for rule_id in r.rule_ids}
        rules = list(
            await self._session.scalars(select(GiftingRule).where(GiftingRule.id.in_(rule_ids)))
        )
        items = [_read(r, {rule.id: rule for rule in rules}) for r in recommendations]
        return RecommendationList(items=items, add_all_to_cart_url=_cart_url(items))

    async def _recipient(self, chat: Chat) -> Recipient | None:
        if chat.recipient_id is None:
            return None
        return await self._session.get(Recipient, chat.recipient_id)

    async def _save_turn(
        self,
        chat: Chat,
        content: str,
        reply_text: str,
        picks: list[Pick],
        rules: list[GiftingRule],
        now: datetime,
    ) -> ChatTurn:
        message = Message(chat_id=chat.id, role=MessageRole.USER, content=content, created_at=now)
        # A microsecond later, so the pair always reads back in order.
        reply = Message(
            chat_id=chat.id,
            role=MessageRole.ASSISTANT,
            content=reply_text,
            created_at=now + timedelta(microseconds=1),
        )
        self._messages.add(message)
        self._messages.add(reply)
        await self._session.flush()

        recommendations = [
            Recommendation(
                chat_id=chat.id,
                message_id=reply.id,
                product_asin=pick.candidate.product.asin,
                rank=rank,
                reason=pick.reason,
                rule_ids=pick.rule_ids,
                score=round(pick.candidate.score, 4),
                product=pick.candidate.product,
            )
            for rank, pick in enumerate(picks, 1)
        ]
        for recommendation in recommendations:
            self._recommendations.add(recommendation)
        chat.updated_at = now
        await self._session.commit()

        rules_by_id = {rule.id: rule for rule in rules}
        items = [_read(r, rules_by_id) for r in recommendations]
        return ChatTurn(
            message=MessageRead.model_validate(message),
            reply=MessageRead.model_validate(reply),
            recommendations=items,
            add_all_to_cart_url=_cart_url(items),
            order_by=order_by_date(chat.occasion_date, now.date()),
            chat=ChatRead.model_validate(chat),
        )


def profile_for(chat: Chat, recipient: Recipient | None) -> GiftProfile:
    """The agent's notes, overlaid with what the chat and saved person say for certain."""
    profile = GiftProfile.model_validate(chat.agent_profile or {})
    update: dict[str, object] = {
        "occasion": chat.occasion or profile.occasion,
        "occasion_date": chat.occasion_date or profile.occasion_date,
        "budget_min_usd": chat.budget_min_usd
        if chat.budget_min_usd is not None
        else profile.budget_min_usd,
        "budget_max_usd": chat.budget_max_usd
        if chat.budget_max_usd is not None
        else profile.budget_max_usd,
    }
    if recipient is not None:
        update["recipient_name"] = recipient.name
        update["relationship"] = recipient.relationship
        update["interests"] = list(dict.fromkeys([*recipient.interests, *profile.interests]))[:20]
        if recipient.notes and not profile.personality:
            update["personality"] = recipient.notes[:300]
    return profile.model_copy(update=update)


def apply_profile(chat: Chat, profile: GiftProfile, recipient: Recipient | None) -> None:
    """Writes what the agent learned back to the chat, retitling it if the title is
    still automatic."""
    chat.agent_profile = profile.model_dump(mode="json", exclude_none=True)
    chat.occasion = profile.occasion
    chat.occasion_date = profile.occasion_date
    low, high = profile.budget_range()
    chat.budget_min_usd, chat.budget_max_usd = low, high
    if not chat.title_is_custom:
        name = recipient.name if recipient is not None else profile.recipient_name
        chat.title = describe_chat(name, chat.occasion, chat.occasion_date)


def _read(recommendation: Recommendation, rules: dict[str, GiftingRule]) -> RecommendationRead:
    return RecommendationRead(
        id=recommendation.id,
        rank=recommendation.rank,
        product=ProductRead.model_validate(recommendation.product),
        reason=recommendation.reason,
        rules=[
            CitedRule(id=rule.id, kind=rule.kind, rule=rule.rule)
            for rule_id in recommendation.rule_ids
            if (rule := rules.get(rule_id)) is not None
        ],
        add_to_cart_url=add_to_cart_url([recommendation.product_asin]),
    )


def _cart_url(items: list[RecommendationRead]) -> str | None:
    return add_to_cart_url([item.product.asin for item in items]) if items else None
