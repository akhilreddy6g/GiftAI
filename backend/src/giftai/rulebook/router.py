from typing import Annotated

from fastapi import APIRouter, Path, Query

from giftai.rulebook.dependencies import RulebookServiceDep
from giftai.rulebook.schemas import RuleList, RuleRead, RulesQuery
from giftai.rulebook.service import to_rule_read

router = APIRouter(prefix="/rules", tags=["rulebook"])

RuleId = Annotated[str, Path(pattern=r"^R-\d{3,6}$", description="Such as R-012")]


@router.get("", summary="Gifting rules that apply to a situation")
async def list_rules(
    query: Annotated[RulesQuery, Query()], service: RulebookServiceDep
) -> RuleList:
    return RuleList(items=[to_rule_read(rule) for rule in await service.rules_for(query)])


@router.get("/{rule_id}", summary="One gifting rule, with its sources")
async def get_rule(rule_id: RuleId, service: RulebookServiceDep) -> RuleRead:
    return to_rule_read(await service.get(rule_id))
