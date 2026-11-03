from enum import StrEnum

from pydantic import BaseModel


class CheckStatus(StrEnum):
    OK = "ok"
    FAILING = "failing"


class LivenessReport(BaseModel):
    status: CheckStatus


class ReadinessReport(BaseModel):
    status: CheckStatus
    database: CheckStatus
    vector_extension: CheckStatus
