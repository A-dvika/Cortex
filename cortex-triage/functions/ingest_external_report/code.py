#input_type_name: IngestExternalReportInput
#output_type_name: IngestExternalReportResult
#function_name: ingest_external_report

"""Normalize external work items into Cortex's issue intake table.

This function is intentionally conservative: it records the incoming Jira,
Slack, email, GitHub, or manual item as a pending issue and deduplicates by
source + external_id. The triage workflow can then process the normalized
title/body/source/url/reporter/external_id shape without caring where it came
from.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


SOURCES = {"github", "jira", "slack", "email", "manual"}


class IngestExternalReportInput(BaseModel):
    source: str = "manual"
    external_id: str = ""
    repo: str = ""
    title: str = ""
    body: str = ""
    url: str = ""
    reporter: str = ""
    payload: Dict[str, Any] = {}


class IngestExternalReportResult(BaseModel):
    ok: bool
    issue_id: Optional[str] = None
    created: bool = False
    duplicate: bool = False
    triage_ready: bool = False
    detail: str = ""


def _row_id(record) -> Optional[str]:
    if record is None:
        return None
    if isinstance(record, dict):
        return record.get("id")
    return getattr(record, "id", None)


def _first(*values: Any) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _normalize(data: IngestExternalReportInput) -> Dict[str, str]:
    payload = data.payload or {}
    source = (data.source or payload.get("source") or "manual").strip().lower()
    if source not in SOURCES:
        source = "manual"

    fields = payload.get("fields") or {}
    slack_user = payload.get("user") or {}
    email_from = payload.get("from") or {}

    title = _first(
        data.title,
        payload.get("title"),
        payload.get("summary"),
        fields.get("summary"),
        payload.get("subject"),
        payload.get("text"),
    )
    body = _first(
        data.body,
        payload.get("body"),
        payload.get("description"),
        fields.get("description"),
        payload.get("text"),
        payload.get("snippet"),
    )
    external_id = _first(
        data.external_id,
        payload.get("external_id"),
        payload.get("id"),
        payload.get("key"),
        payload.get("ts"),
        payload.get("message_id"),
    )
    url = _first(
        data.url,
        payload.get("url"),
        payload.get("self"),
        payload.get("permalink"),
        payload.get("web_url"),
    )
    reporter = _first(
        data.reporter,
        payload.get("reporter"),
        fields.get("reporter", {}).get("displayName") if isinstance(fields.get("reporter"), dict) else "",
        slack_user.get("name") if isinstance(slack_user, dict) else "",
        email_from.get("email") if isinstance(email_from, dict) else "",
        payload.get("author"),
    )

    return {
        "source": source,
        "external_id": external_id[:120],
        "title": (title or "Untitled external report")[:300],
        "body": body,
        "url": url[:600],
        "reporter": reporter[:200],
    }


async def ingest_external_report(ctx: FunctionContext, data: IngestExternalReportInput) -> IngestExternalReportResult:
    pod = Pod.from_env()
    item = _normalize(data)

    repo = (data.repo or "").strip()

    if item["external_id"]:
        try:
            filters = [
                {"field": "source", "op": "eq", "value": item["source"]},
                {"field": "external_id", "op": "eq", "value": item["external_id"]},
            ]
            if repo:
                filters.append({"field": "repo", "op": "eq", "value": repo})
            existing = pod.records.list("issues", limit=1, filter=filters).to_dict()["items"]
            if existing:
                return IngestExternalReportResult(
                    ok=True,
                    issue_id=existing[0].get("id"),
                    duplicate=True,
                    triage_ready=True,
                    detail="already ingested " + item["source"] + " item " + item["external_id"],
                )
        except Exception:
            pass

    try:
        record = pod.table("issues").create({
            "source": item["source"],
            "external_id": item["external_id"],
            "repo": repo,
            "title": item["title"],
            "body": item["body"],
            "url": item["url"],
            "reporter": item["reporter"],
            "triage_status": "pending",
        })
    except Exception as e:
        return IngestExternalReportResult(ok=False, detail="issue create failed: " + str(e)[:140])

    return IngestExternalReportResult(
        ok=True,
        issue_id=_row_id(record),
        created=True,
        triage_ready=True,
        detail="ingested " + item["source"] + " report",
    )
