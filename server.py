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


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
