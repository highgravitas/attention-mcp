#!/usr/bin/env python3
"""Smoke test for the new attention-mcp tools (HIG-287).

Hits each of the 5 new client methods against the real Attention API. The one
destructive call (create_scorecard_result) is gated behind --write; the default
dry-run mode prints the exact payload the smoke test would POST without
actually writing to the org's Attention workspace.

Usage:
    ATTENTION_API_KEY=... python scripts/smoke_test.py
    ATTENTION_API_KEY=... python scripts/smoke_test.py --write
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

# Make the project root importable when run from anywhere
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

import httpx

from attention_client import AttentionClient


def banner(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def test_list_scorecards(client: AttentionClient) -> dict | None:
    banner("1. list_scorecards")
    try:
        result = client.list_scorecards()
    except httpx.HTTPStatusError as e:
        check("GET /scorecards", False, f"{e.response.status_code} {e.response.text[:200]}")
        return None

    print(json.dumps(result, indent=2)[:1500])
    # Heuristic: the endpoint docs mark response as opaque; accept any JSON.
    check("returned JSON", True, f"top-level keys={list(result.keys()) if isinstance(result, dict) else type(result).__name__}")
    return result


def pick_first_scorecard(scorecards_response) -> tuple[str | None, list[dict]]:
    """Return (scorecard_uuid, items) for the first scorecard found, or (None, [])."""
    candidates: list = []
    if isinstance(scorecards_response, list):
        candidates = scorecards_response
    elif isinstance(scorecards_response, dict):
        for key in ("data", "scorecards", "results"):
            lst = scorecards_response.get(key)
            if isinstance(lst, list):
                candidates = lst
                break
    if not candidates:
        return None, []

    sc = candidates[0]
    attrs = sc.get("attributes", sc) if isinstance(sc.get("attributes"), dict) else sc
    uuid = sc.get("uuid") or attrs.get("uuid") or sc.get("id")
    items_list = None
    for ikey in ("items", "scorecardItems", "criteria"):
        maybe = attrs.get(ikey)
        if isinstance(maybe, list):
            items_list = maybe
            break
    return uuid, (items_list or [])


def test_get_scorecards_summary(client: AttentionClient, scorecard_id: str | None) -> None:
    banner("2. get_scorecards_summary")
    if not scorecard_id:
        check("skipped — no scorecard_id available", False)
        return

    now = datetime.now(timezone.utc)
    to_date = now.strftime("%Y-%m-%d")
    from_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    try:
        result = client.get_scorecards_summary(
            scorecard_id=scorecard_id,
            from_date=from_date,
            to_date=to_date,
        )
    except httpx.HTTPStatusError as e:
        check(
            "POST /scorecards/summary",
            False,
            f"{e.response.status_code} {e.response.text[:300]}",
        )
        return

    print(json.dumps(result, indent=2)[:1500])
    check("returned dict", isinstance(result, dict))
    check("has 'data' array", isinstance(result.get("data"), list))


def test_create_scorecard_result(
    client: AttentionClient,
    scorecard_id: str | None,
    items: list[dict],
    write: bool,
) -> None:
    banner("3. create_scorecard_result (dry-run)" if not write else "3. create_scorecard_result (WRITE)")

    if not scorecard_id or not items:
        check("skipped — need a scorecard with at least one criterion", False)
        return

    # Find a recent conversation to attach to.
    try:
        recent = client.list_recent_conversations(days_back=30, size=1)
    except httpx.HTTPStatusError as e:
        check("lookup recent conversation", False, f"{e.response.status_code}")
        return
    conv_list = recent.get("data") or []
    if not conv_list:
        check("skipped — no recent conversations to attach to", False)
        return
    conv = conv_list[0]
    conv_attrs = conv.get("attributes", {}) if isinstance(conv.get("attributes"), dict) else conv
    conv_uuid = conv.get("id") or conv_attrs.get("uuid")

    # Build a payload targeting the first criterion only.
    first_item = items[0]
    iattrs = first_item.get("attributes", first_item) if isinstance(first_item.get("attributes"), dict) else first_item
    item_uuid = first_item.get("uuid") or iattrs.get("uuid") or first_item.get("id")

    payload = {
        "scorecard_id": scorecard_id,
        "conversation_id": conv_uuid,
        "items": [
            {
                "scorecard_item_uuid": item_uuid,
                "description": "[smoke-test] automated validation — ignore",
                "numeric_result": 3,
            }
        ],
        "summary": "[smoke-test] automated validation — ignore",
    }

    print("Would POST to /createScorecardResult with payload:")
    print(json.dumps(payload, indent=2))

    if not write:
        check("dry-run — no request sent", True, "pass --write to actually POST")
        return

    try:
        result = client.create_scorecard_result(**payload)
    except httpx.HTTPStatusError as e:
        check(
            "POST /createScorecardResult",
            False,
            f"{e.response.status_code} {e.response.text[:300]}",
        )
        return

    print("Response:")
    print(json.dumps(result, indent=2))
    check("reported success", bool(result.get("success")))


def test_ask_attention(client: AttentionClient) -> None:
    banner("4. ask_attention (v2)")

    # Fall back through progressively looser payloads until one works,
    # so we can discover what the API actually requires.
    try:
        recent = client.list_recent_conversations(days_back=30, size=1)
    except httpx.HTTPStatusError as e:
        check("lookup recent conversation", False, f"{e.response.status_code}")
        recent = {"data": []}
    conv_list = recent.get("data") or []
    conv_ids: list[str] = []
    if conv_list:
        conv = conv_list[0]
        conv_attrs = conv.get("attributes", {}) if isinstance(conv.get("attributes"), dict) else conv
        conv_uuid = conv.get("id") or conv_attrs.get("uuid")
        if conv_uuid:
            conv_ids = [conv_uuid]

    attempts = [
        ("empty deal_id + empty conversations", {"prompt": "What topics came up?", "conversation_ids": [], "deal_id": ""}),
        ("empty deal_id + one conversation", {"prompt": "Summarize the call in one sentence.", "conversation_ids": conv_ids, "deal_id": ""}),
    ]

    for label, kwargs in attempts:
        try:
            result = client.ask_attention(**kwargs)
        except ValueError as e:
            # Client-side validation caught a bad combination before the API was hit.
            check(label, True, f"client-side guard worked: {e}")
            continue
        except httpx.HTTPStatusError as e:
            check(label, False, f"{e.response.status_code} {e.response.text[:200]}")
            continue
        print(f"Attempt: {label}")
        print(json.dumps(result, indent=2)[:1500])
        check(label, True)
        return

    check("all attempts failed", False)


def test_list_gi_history(client: AttentionClient) -> None:
    banner("5. list_gi_history")

    try:
        users = client.list_organization_users().get("data") or []
    except httpx.HTTPStatusError as e:
        check("GET /organizations/users", False, f"{e.response.status_code} {e.response.text[:200]}")
        return

    if not users:
        check("skipped — no users returned", False)
        return

    user = users[0]
    user_uuid = user.get("uuid")
    user_email = user.get("email")
    print(f"Using user {user_email} ({user_uuid})")

    try:
        result = client.list_gi_history(user_uuid=user_uuid, limit=5)
    except httpx.HTTPStatusError as e:
        check("GET /gi/history", False, f"{e.response.status_code} {e.response.text[:200]}")
        return

    print(json.dumps(result, indent=2)[:1500])
    check("returned dict", isinstance(result, dict))
    data = result.get("data")
    check(
        "'data' present (list or null)",
        isinstance(data, list) or data is None,
        f"null = no GI history for this user" if data is None else f"{len(data)} entry(ies)",
    )


def test_existing_unchanged(client: AttentionClient) -> None:
    banner("Regression: existing tools still work")

    try:
        recent = client.list_recent_conversations(days_back=7, size=3)
    except httpx.HTTPStatusError as e:
        check("list_recent_conversations", False, f"{e.response.status_code}")
        return

    check("list_recent_conversations", isinstance(recent, dict) and "data" in recent,
          f"{len(recent.get('data', []))} conversations")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually POST create_scorecard_result (default: dry-run, no writes).",
    )
    args = parser.parse_args()

    print(f"Smoke test — write mode: {args.write}")
    with AttentionClient() as client:
        scorecards = test_list_scorecards(client)
        scorecard_id, items = pick_first_scorecard(scorecards or {})
        test_get_scorecards_summary(client, scorecard_id)
        test_create_scorecard_result(client, scorecard_id, items, write=args.write)
        test_ask_attention(client)
        test_list_gi_history(client)
        test_existing_unchanged(client)

    banner("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
