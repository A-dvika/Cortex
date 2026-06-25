#input_type_name: GithubPingInput
#output_type_name: GithubPingResult
#function_name: github_ping

"""One-call probe to confirm the function sandbox allows outbound HTTP to GitHub."""

import requests
from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class GithubPingInput(BaseModel):
    url: str = "https://api.github.com/rate_limit"


class GithubPingResult(BaseModel):
    ok: bool
    status: int
    detail: str = ""


async def github_ping(ctx: FunctionContext, data: GithubPingInput) -> GithubPingResult:
    try:
        r = requests.get(
            data.url,
            timeout=15,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "cortex-triage"},
        )
        return GithubPingResult(ok=(r.status_code < 500), status=r.status_code, detail=str(r.text)[:200])
    except Exception as e:  # noqa: BLE001 — probe: report any failure as detail
        return GithubPingResult(ok=False, status=0, detail=("ERR: " + str(e))[:200])
