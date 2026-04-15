#!/usr/bin/env python3
"""
Attention MCP Server

Exposes Attention API for call transcript search and retrieval via MCP protocol.
Documentation: https://docs.attention.com/api-authentication
"""

import json
import logging
from datetime import datetime
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from attention_client import AttentionClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
server = Server("attention")

# Global client instance (initialized on first use)
_client: Optional[AttentionClient] = None


def get_client() -> AttentionClient:
    """Get or create the Attention client."""
    global _client
    if _client is None:
        _client = AttentionClient()
    return _client


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="search_conversations",
            description="Search Attention for call recordings and transcripts. Use for sales calls, customer calls, and demos.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term for conversation title (case-insensitive partial match)",
                    },
                    "from_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format",
                    },
                    "to_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format",
                    },
                    "participant_email": {
                        "type": "string",
                        "description": "Filter by participant email address",
                    },
                    "owner_email": {
                        "type": "string",
                        "description": "Filter by call owner email address",
                    },
                    "size": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 20)",
                        "default": 20,
                    },
                },
            },
        ),
        Tool(
            name="get_conversation",
            description="Get full details and transcript for a specific Attention conversation by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "string",
                        "description": "The conversation UUID",
                    },
                    "detailed_transcript": {
                        "type": "boolean",
                        "description": "Include detailed transcript with speaker labels (default: true)",
                        "default": True,
                    },
                },
                "required": ["conversation_id"],
            },
        ),
        Tool(
            name="list_recent_conversations",
            description="List recent Attention conversations from the past N days.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 7)",
                        "default": 7,
                    },
                    "size": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 20)",
                        "default": 20,
                    },
                },
            },
        ),
        Tool(
            name="list_scorecards",
            description="List all scorecards configured for the organization (id, name, criteria). Call this first to pick a scorecard_id and criterion ids for create_scorecard_result.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_scorecards_summary",
            description="Get per-criterion averages for a scorecard over a date range. Feeds weekly manager rollup.",
            inputSchema={
                "type": "object",
                "properties": {
                    "scorecard_id": {
                        "type": "string",
                        "description": "Scorecard UUID (from list_scorecards)",
                    },
                    "from_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format",
                    },
                    "to_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format",
                    },
                    "owner_email": {
                        "type": "string",
                        "description": "Optional: filter to a specific AE by email (translated to user UUID internally)",
                    },
                    "user_uuids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: explicit user UUIDs to filter by",
                    },
                    "team_uuids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: team UUIDs to filter by",
                    },
                    "scorecard_item_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: restrict to specific criterion UUIDs",
                    },
                },
                "required": ["scorecard_id", "from_date", "to_date"],
            },
        ),
        Tool(
            name="create_scorecard_result",
            description="Create a scorecard result (written coaching feedback) on a conversation. Writes directly into Attention so managers don't need to transcribe feedback manually.",
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "string",
                        "description": "Conversation UUID the scorecard is scored against",
                    },
                    "scorecard_id": {
                        "type": "string",
                        "description": "Scorecard UUID (from list_scorecards)",
                    },
                    "items": {
                        "type": "array",
                        "description": "Per-criterion results. Each object: {scorecard_item_uuid, description, numeric_result?}",
                        "items": {
                            "type": "object",
                            "properties": {
                                "scorecard_item_uuid": {
                                    "type": "string",
                                    "description": "The criterion UUID (from a scorecard's items)",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Written notes for this criterion",
                                },
                                "numeric_result": {
                                    "type": "integer",
                                    "description": "Optional numeric score for this criterion",
                                },
                            },
                            "required": ["scorecard_item_uuid", "description"],
                        },
                    },
                    "summary": {
                        "type": "string",
                        "description": "Overall notes across all criteria",
                    },
                    "chat_id": {
                        "type": "string",
                        "description": "Alternative target: Attention chat UUID (use instead of conversation_id)",
                    },
                },
                "required": ["scorecard_id", "items", "summary"],
            },
        ),
        Tool(
            name="ask_attention",
            description="Run Attention's AI analysis (v2) against a prompt over one or more conversations. Returns per-conversation outputs; useful as a second-opinion signal alongside Sales Bible logic.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The analysis question",
                    },
                    "conversation_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Conversation UUIDs to analyze",
                    },
                    "deal_id": {
                        "type": "string",
                        "description": "Deal identifier (docs mark this required; empty string accepted when not scoped to a deal)",
                    },
                    "include_timestamps": {
                        "type": "boolean",
                        "description": "If true, returns timestamped transcript segments per conversation (default: false)",
                        "default": False,
                    },
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="list_gi_history",
            description="List an org user's generalized-insights (GI) history. Feeds rep-profile updates.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_email": {
                        "type": "string",
                        "description": "Org user email (translated to UUID internally). Provide this OR user_uuid.",
                    },
                    "user_uuid": {
                        "type": "string",
                        "description": "User UUID (skip email lookup)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max entries (default: 20)",
                        "default": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset (default: 0)",
                        "default": 0,
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        client = get_client()

        if name == "search_conversations":
            result = client.search_conversations(
                query=arguments.get("query"),
                from_date=arguments.get("from_date"),
                to_date=arguments.get("to_date"),
                participant_email=arguments.get("participant_email"),
                owner_email=arguments.get("owner_email"),
                size=arguments.get("size", 20),
            )
            return [TextContent(type="text", text=format_search_results(result))]

        elif name == "get_conversation":
            result = client.get_conversation(
                conversation_id=arguments["conversation_id"],
                detailed_transcript=arguments.get("detailed_transcript", True),
            )
            return [TextContent(type="text", text=format_conversation(result))]

        elif name == "list_recent_conversations":
            result = client.list_recent_conversations(
                days_back=arguments.get("days_back", 7),
                size=arguments.get("size", 20),
            )
            return [TextContent(type="text", text=format_search_results(result))]

        elif name == "list_scorecards":
            result = client.list_scorecards()
            return [TextContent(type="text", text=format_scorecards(result))]

        elif name == "get_scorecards_summary":
            result = client.get_scorecards_summary(
                scorecard_id=arguments["scorecard_id"],
                from_date=arguments["from_date"],
                to_date=arguments["to_date"],
                owner_email=arguments.get("owner_email"),
                user_uuids=arguments.get("user_uuids"),
                team_uuids=arguments.get("team_uuids"),
                scorecard_item_ids=arguments.get("scorecard_item_ids"),
            )
            return [TextContent(type="text", text=format_scorecards_summary(result))]

        elif name == "create_scorecard_result":
            result = client.create_scorecard_result(
                scorecard_id=arguments["scorecard_id"],
                items=arguments["items"],
                summary=arguments["summary"],
                conversation_id=arguments.get("conversation_id"),
                chat_id=arguments.get("chat_id"),
            )
            return [TextContent(type="text", text=format_scorecard_result(result, arguments))]

        elif name == "ask_attention":
            result = client.ask_attention(
                prompt=arguments["prompt"],
                conversation_ids=arguments.get("conversation_ids"),
                deal_id=arguments.get("deal_id"),
                include_timestamps=arguments.get("include_timestamps", False),
            )
            return [TextContent(type="text", text=format_ask_attention(result))]

        elif name == "list_gi_history":
            result = client.list_gi_history(
                user_email=arguments.get("user_email"),
                user_uuid=arguments.get("user_uuid"),
                limit=arguments.get("limit", 20),
                offset=arguments.get("offset", 0),
            )
            return [TextContent(type="text", text=format_gi_history(result))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.exception(f"Error calling tool {name}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


def format_search_results(result: dict) -> str:
    """Format search results for display."""
    data = result.get("data", [])
    meta = result.get("meta", {})

    if not data:
        return "No conversations found."

    lines = [f"Found {meta.get('totalRecords', len(data))} conversations:\n"]

    for conv in data:
        attrs = conv.get("attributes", {})
        conv_id = conv.get("id", attrs.get("uuid", "unknown"))
        title = attrs.get("title", "Untitled")
        created = attrs.get("createdAt", "")

        # Format date
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                created = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pass

        # Get participants
        participants = attrs.get("participants", [])
        participant_names = [p.get("name") or p.get("email", "Unknown") for p in participants[:3]]
        participant_str = ", ".join(participant_names)
        if len(participants) > 3:
            participant_str += f" (+{len(participants) - 3} more)"

        lines.append(f"- **{title}**")
        lines.append(f"  ID: {conv_id}")
        lines.append(f"  Date: {created}")
        lines.append(f"  Participants: {participant_str}")
        lines.append("")

    # Pagination info
    if meta.get("pageCount", 1) > 1:
        lines.append(f"\nPage {meta.get('pageNumber', 1)} of {meta.get('pageCount')}")

    return "\n".join(lines)


def format_conversation(result: dict) -> str:
    """Format a single conversation with transcript."""
    # API returns attributes directly, not nested under "data"
    attrs = result.get("attributes", {})
    if not attrs:
        # Fallback for potential nested structure
        data = result.get("data", {})
        attrs = data.get("attributes", {})

    conv_id = attrs.get("uuid", result.get("id", "unknown"))
    title = attrs.get("title", "Untitled")
    created = attrs.get("createdAt", "")

    # Format date
    if created:
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            created = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            pass

    # Get participants
    participants = attrs.get("participants", [])
    participant_lines = []
    for p in participants:
        name = p.get("name") or p.get("email", "Unknown")
        email = p.get("email", "")
        if email and name != email:
            participant_lines.append(f"  - {name} ({email})")
        else:
            participant_lines.append(f"  - {name}")

    # Get transcript
    transcript = attrs.get("transcript", {})
    transcript_text = format_transcript(transcript)

    # Get extracted intelligence (AI summaries)
    # Use confirmedExtractedIntelligence first, fall back to extractedIntelligence
    intelligence = attrs.get("confirmedExtractedIntelligence", {}) or attrs.get("extractedIntelligence", {})
    intel_lines = []
    if intelligence:
        for key, item in intelligence.items():
            if isinstance(item, dict):
                intel_title = item.get("title", key)
                intel_value = item.get("value", "")
                if intel_value:
                    intel_lines.append(f"### {intel_title}")
                    intel_lines.append(intel_value)
                    intel_lines.append("")
            elif item:
                intel_lines.append(f"  - {key}: {item}")

    # Build output
    lines = [
        f"# {title}",
        f"",
        f"**ID:** {conv_id}",
        f"**Date:** {created}",
        f"**Video Status:** {attrs.get('videoStatus', 'Unknown')}",
        f"",
        f"## Participants",
    ]
    lines.extend(participant_lines)

    if intel_lines:
        lines.append("")
        lines.append("## Extracted Intelligence")
        lines.extend(intel_lines)

    lines.append("")
    lines.append("## Transcript")
    lines.append("")
    lines.append(transcript_text)

    return "\n".join(lines)


def format_transcript(transcript) -> str:
    """Format transcript data."""
    if not transcript:
        return "*No transcript available*"

    # Handle different transcript formats
    if isinstance(transcript, str):
        return transcript

    # Attention API returns a list of segments with speaker and words
    if isinstance(transcript, list):
        lines = []
        current_speaker = None
        current_text = []

        for segment in transcript:
            speaker_info = segment.get("speaker", {})
            speaker_name = speaker_info.get("name") or speaker_info.get("email", "Unknown")

            # Combine words into text
            words = segment.get("words", [])
            segment_text = "".join(w.get("text", "") for w in words).strip()

            if not segment_text:
                continue

            # Group consecutive segments by speaker
            if speaker_name == current_speaker:
                current_text.append(segment_text)
            else:
                # Output previous speaker's text
                if current_speaker and current_text:
                    lines.append(f"**{current_speaker}:** {' '.join(current_text)}")
                current_speaker = speaker_name
                current_text = [segment_text]

        # Don't forget the last speaker
        if current_speaker and current_text:
            lines.append(f"**{current_speaker}:** {' '.join(current_text)}")

        return "\n\n".join(lines) if lines else "*No transcript available*"

    if isinstance(transcript, dict):
        # Check for common transcript formats
        if "text" in transcript:
            return transcript["text"]
        if "segments" in transcript:
            segments = transcript["segments"]
            lines = []
            for seg in segments:
                speaker = seg.get("speaker", "Unknown")
                text = seg.get("text", "")
                lines.append(f"**{speaker}:** {text}")
            return "\n\n".join(lines)

        # Fallback: pretty print the dict
        return json.dumps(transcript, indent=2)

    return str(transcript)


def _extract_scorecards(result) -> list[dict]:
    """Pull scorecards out of the API response, which may be a bare list or wrapped."""
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("data", "scorecards", "results"):
            val = result.get(key)
            if isinstance(val, list):
                return val
    return []


def _scorecard_items(sc: dict) -> list[dict]:
    """Pull criterion items out of a scorecard, which may be nested under attributes."""
    attrs = sc.get("attributes", sc) if isinstance(sc.get("attributes"), dict) else sc
    for key in ("items", "scorecardItems", "criteria"):
        val = attrs.get(key)
        if isinstance(val, list):
            return val
    return []


def format_scorecards(result) -> str:
    """Format list of scorecards with their criteria."""
    scorecards = _extract_scorecards(result)
    if not scorecards:
        return "No scorecards configured.\n\nRaw response:\n" + json.dumps(result, indent=2)[:2000]

    lines = [f"Found {len(scorecards)} scorecard(s):\n"]
    for sc in scorecards:
        attrs = sc.get("attributes", sc) if isinstance(sc.get("attributes"), dict) else sc
        sc_id = sc.get("uuid") or attrs.get("uuid") or sc.get("id", "unknown")
        sc_name = attrs.get("name") or attrs.get("title", "Untitled")
        lines.append(f"## {sc_name}")
        lines.append(f"  ID: {sc_id}")

        items = _scorecard_items(sc)
        if items:
            lines.append("  Criteria:")
            for item in items:
                iattrs = item.get("attributes", item) if isinstance(item.get("attributes"), dict) else item
                item_id = item.get("uuid") or iattrs.get("uuid") or item.get("id", "unknown")
                item_title = iattrs.get("title") or iattrs.get("name", "Untitled")
                lines.append(f"    - {item_title} ({item_id})")
        lines.append("")
    return "\n".join(lines)


def format_scorecards_summary(result: dict) -> str:
    """Format a scorecards summary (per-criterion averages)."""
    data = result.get("data", [])
    if not data:
        return "No summary data for the given filters."

    lines = [f"Scorecard summary — {len(data)} row(s):\n"]
    for row in data:
        user = row.get("userName") or "(unassigned)"
        team = row.get("teamName") or ""
        overall = row.get("overallScoreTotals")
        metrics_count = row.get("metricsCount")

        header = f"### {user}" + (f" — {team}" if team else "")
        lines.append(header)
        if overall is not None:
            lines.append(f"  Overall: {overall} across {metrics_count} call(s)")
        if row.get("min") is not None or row.get("max") is not None:
            lines.append(f"  Min / Max: {row.get('min')} / {row.get('max')}")

        for item in row.get("itemAverageTotals", []) or []:
            title = item.get("title", "Untitled")
            avg = item.get("average")
            lines.append(f"  - {title}: {avg}")
        lines.append("")
    return "\n".join(lines)


def format_scorecard_result(result: dict, sent_args: dict) -> str:
    """Format the response from create_scorecard_result."""
    success = result.get("success", False)
    lines = []
    if success:
        lines.append("Scorecard result created successfully.")
    else:
        lines.append("Scorecard result creation did not report success.")
    target = sent_args.get("conversation_id") or sent_args.get("chat_id") or "(unknown)"
    lines.append(f"Target: {target}")
    lines.append(f"Scorecard: {sent_args.get('scorecard_id')}")
    lines.append(f"Items scored: {len(sent_args.get('items') or [])}")
    lines.append("")
    lines.append("Raw response:")
    lines.append(json.dumps(result, indent=2))
    return "\n".join(lines)


def format_ask_attention(result) -> str:
    """Format the response from ask_attention v2."""
    if not isinstance(result, list):
        return "Unexpected response shape:\n" + json.dumps(result, indent=2)[:2000]
    if not result:
        return "No output returned from Attention."

    lines = [f"Attention returned {len(result)} result(s):\n"]
    for entry in result:
        conv_id = entry.get("conversation_id", "(no conversation)")
        output = entry.get("output", "")
        error = entry.get("error", "")
        segments = entry.get("segments") or []

        lines.append(f"### {conv_id}")
        if error:
            lines.append(f"  Error: {error}")
        if output:
            lines.append(output)
        for seg in segments:
            start = seg.get("start_sec")
            end = seg.get("end_sec")
            text = seg.get("text", "")
            lines.append(f"  [{start}s – {end}s] {text}")
        lines.append("")
    return "\n".join(lines)


def format_gi_history(result: dict) -> str:
    """Format GI history list."""
    data = result.get("data", [])
    if not data:
        return "No GI history entries for this user."

    meta = result.get("meta", {})
    lines = [f"GI history — {len(data)} entry(ies):\n"]
    for entry in data:
        title = entry.get("title", "Untitled")
        entry_id = entry.get("uuid", "unknown")
        results = entry.get("results") or []
        lines.append(f"## {title}")
        lines.append(f"  ID: {entry_id}")
        lines.append(f"  Results: {len(results)}")
        for r in results[:3]:
            prompt = (r.get("prompt") or "")[:120]
            synthesis = (r.get("synthesis") or "")[:200]
            if prompt:
                lines.append(f"    - Prompt: {prompt}")
            if synthesis:
                lines.append(f"      Synthesis: {synthesis}")
        lines.append("")

    if meta:
        lines.append(f"Page {meta.get('pageNumber', '?')} of {meta.get('pageCount', '?')} "
                     f"— {meta.get('totalRecords', '?')} total")
    return "\n".join(lines)


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
