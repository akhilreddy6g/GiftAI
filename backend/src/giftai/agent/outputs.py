"""The structured answers the agent asks the LLM for. Kept flat and simple, because
providers constrain output to these schemas and small models handle simple ones best.
"""

from pydantic import BaseModel, Field

from giftai.gifting import Occasion, Relationship


class TurnAnalysis(BaseModel):
    recipient_name: str | None = Field(description="The recipient's name, if given.")
    relationship: Relationship | None = Field(description="How the user knows them.")
    occasion: Occasion | None = Field(description="What the gift is for.")
    occasion_date: str | None = Field(
        description="When the gift is needed, as YYYY-MM-DD, if a date can be worked out."
    )
    budget_min_usd: int | None = Field(description="Lowest amount to spend, in whole dollars.")
    budget_max_usd: int | None = Field(description="Highest amount to spend, in whole dollars.")
    interests: list[str] = Field(description="Their interests and hobbies, a few words each.")
    personality: str | None = Field(description="One sentence on what they are like.")
    avoid: list[str] = Field(description="Things to stay away from, a few words each.")
    wants_suggestions_now: bool = Field(
        description="True if the user asks for gift ideas now, or for different ones."
    )
    search_queries: list[str] = Field(
        description="2 to 4 short product searches for an online store that would find "
        "great gifts for this person, such as 'pour-over coffee kit'."
    )
    next_question: str | None = Field(
        description="One short, friendly question about the most important missing detail."
    )


class PickedGift(BaseModel):
    asin: str = Field(description="The product id exactly as listed.")
    why: str = Field(description="One or two sentences on why it suits this person.")
    rule_ids: list[str] = Field(description="Ids of the gifting rules this pick follows.")


class GiftPicks(BaseModel):
    intro: str = Field(description="One or two warm sentences introducing the picks.")
    picks: list[PickedGift] = Field(description="5 or 6 gifts, best first, all different kinds.")
