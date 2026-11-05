import uuid
from collections.abc import AsyncIterator, Callable

import pytest
from httpx import AsyncClient

from tests.auth_helpers import TokenIssuer

# Every API test here needs the real database.
pytestmark = pytest.mark.database

Headers = dict[str, str]


@pytest.fixture
def new_user(token_issuer: TokenIssuer) -> Callable[[], Headers]:
    """Returns auth headers for a brand-new user each call; tests never share accounts."""
    return lambda: token_issuer.headers_for(uuid.uuid4())


@pytest.fixture
def alice(new_user: Callable[[], Headers]) -> Headers:
    return new_user()


@pytest.fixture
def bob(new_user: Callable[[], Headers]) -> Headers:
    return new_user()


async def create_recipient(
    client: AsyncClient, headers: Headers, **fields: object
) -> dict[str, object]:
    body = {"name": "Mom", "relationship": "parent", "interests": ["gardening"]} | fields
    response = await client.post("/api/v1/recipients", json=body, headers=headers)
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


async def create_chat(client: AsyncClient, headers: Headers, **fields: object) -> dict[str, object]:
    response = await client.post("/api/v1/chats", json=fields, headers=headers)
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


# The gift agent against the sample catalog and rulebook, with a scripted LLM.
from giftai.agent.outputs import GiftPicks, TurnAnalysis  # noqa: E402
from giftai.llm.dependencies import get_chat_model  # noqa: E402
from pipelines.catalog import steps as catalog_steps  # noqa: E402
from pipelines.catalog.config import SelectionRules  # noqa: E402
from pipelines.catalog.neighbors import AlsParameters  # noqa: E402
from pipelines.catalog.workspace import Workspace  # noqa: E402
from pipelines.rulebook import steps as rulebook_steps  # noqa: E402
from tests.api.agent_support import AgentClient, first_turn, pick_coffee  # noqa: E402
from tests.catalog_samples import CATEGORY, write_sample_dataset  # noqa: E402
from tests.conftest import build_test_app, make_settings, open_client  # noqa: E402
from tests.fakes import HashingTextEmbedder, ScriptedChatModel  # noqa: E402
from tests.rulebook_samples import write_rulebook  # noqa: E402


@pytest.fixture(scope="module")
def catalog_and_rules(test_database_url: str, tmp_path_factory: pytest.TempPathFactory) -> None:
    workspace = Workspace(tmp_path_factory.mktemp("catalog"))
    write_sample_dataset(workspace)
    catalog_steps.select(workspace, [CATEGORY], SelectionRules())
    catalog_steps.embed(workspace, HashingTextEmbedder())
    catalog_steps.neighbors(
        workspace, [CATEGORY], AlsParameters(factors=2, iterations=20, neighbors_per_product=4)
    )
    catalog_steps.load(workspace, test_database_url)
    rulebook = write_rulebook(tmp_path_factory.mktemp("rulebook") / "rulebook.yaml")
    rulebook_steps.seed(rulebook, test_database_url)


@pytest.fixture
async def agent(
    catalog_and_rules: None, test_database_url: str, token_issuer: TokenIssuer
) -> AsyncIterator[AgentClient]:
    model = ScriptedChatModel({TurnAnalysis: first_turn, GiftPicks: pick_coffee})
    app = build_test_app(
        make_settings(test_database_url, agent_turns_per_user_per_day=3), token_issuer
    )
    app.dependency_overrides[get_chat_model] = lambda: model
    async with open_client(app) as client:
        yield AgentClient(client, model)


@pytest.fixture
def user(new_user: Callable[[], Headers]) -> Headers:
    return new_user()
