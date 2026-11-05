from typing import Annotated

from fastapi import Depends, Request

from giftai.agent.service import GiftAgentService
from giftai.db.session import SessionDep
from giftai.embeddings.dependencies import TextEmbedderDep
from giftai.llm.dependencies import ChatModelDep


def get_gift_agent_service(
    request: Request, session: SessionDep, model: ChatModelDep, embedder: TextEmbedderDep
) -> GiftAgentService:
    turns_per_day: int = request.app.state.agent_turns_per_day
    return GiftAgentService(session, model, embedder, turns_per_day)


GiftAgentServiceDep = Annotated[GiftAgentService, Depends(get_gift_agent_service)]
