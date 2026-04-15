# Attention MCP Server

An MCP (Model Context Protocol) server that provides access to [Attention](https://attention.tech) call recordings and transcripts. Enables AI assistants like Claude to search, retrieve, and analyze sales calls, customer calls, and demos.

## Features

- **Search conversations** - Find calls by title, date range, participant, or owner
- **Get full transcripts** - Retrieve complete call transcripts with speaker labels
- **AI summaries** - Access Attention's extracted intelligence (call sentiment, summaries, action items)
- **List recent calls** - Quick access to conversations from the past N days
- **Scorecards** - List scorecards, fetch per-criterion rollups, and post written coaching feedback back into Attention
- **Ask Attention v2** - Run Attention's AI analysis across one or more conversations as a second-opinion signal
- **GI history** - Pull a rep's generalized-insights history for profile updates

## Installation

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Attention API key ([get one here](https://app.attention.tech) → Settings → Organization → API Keys)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/highgravitas/attention-mcp.git
   cd attention-mcp
   ```

2. **Create virtual environment and install dependencies**
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -r requirements.txt
   ```

3. **Set your API key**

   Option A: Environment variable (recommended)
   ```bash
   export ATTENTION_API_KEY="your-api-key-here"
   ```

   Option B: Create a `.env` file
   ```bash
   echo 'ATTENTION_API_KEY=your-api-key-here' > .env
   ```

## Configuration

### Claude Code / Claude Desktop

Add to your MCP configuration file:

**Claude Code** (`~/.claude/settings.json` or project `.mcp.json`):
```json
{
  "mcpServers": {
    "attention": {
      "type": "stdio",
      "command": "/path/to/attention-mcp/.venv/bin/python",
      "args": ["/path/to/attention-mcp/server.py"],
      "env": {
        "ATTENTION_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):
```json
{
  "mcpServers": {
    "attention": {
      "command": "/path/to/attention-mcp/.venv/bin/python",
      "args": ["/path/to/attention-mcp/server.py"],
      "env": {
        "ATTENTION_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

After adding the configuration, restart Claude Code/Desktop to load the server.

## Available Tools

### `search_conversations`

Search for calls by various criteria.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search term for conversation title (case-insensitive partial match) |
| `from_date` | string | Start date in YYYY-MM-DD format |
| `to_date` | string | End date in YYYY-MM-DD format |
| `participant_email` | string | Filter by participant email address |
| `owner_email` | string | Filter by call owner email address |
| `size` | integer | Maximum number of results (default: 20) |

**Example:**
```
Search Attention for calls with Acme Corp from last month
```

### `get_conversation`

Get full details and transcript for a specific conversation.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `conversation_id` | string | The conversation UUID (required) |
| `detailed_transcript` | boolean | Include detailed transcript with speaker labels (default: true) |

**Returns:**
- Call metadata (title, date, participants, video status)
- AI-generated insights (call sentiment, summary, action items)
- Full transcript with speaker labels

**Example:**
```
Get the transcript for conversation abc-123-def
```

### `list_recent_conversations`

List recent conversations from the past N days.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `days_back` | integer | Number of days to look back (default: 7) |
| `size` | integer | Maximum number of results (default: 20) |

**Example:**
```
Show me calls from the last 2 weeks
```

### `list_scorecards`

List all scorecards configured for the org, including each scorecard's criteria. Call this first so you know which `scorecard_id` and criterion UUIDs to pass to `create_scorecard_result` or `get_scorecards_summary`.

**Parameters:** none.

**Example:**
```
List all Attention scorecards
```

### `get_scorecards_summary`

Per-criterion averages for a scorecard across a date range. Feeds weekly manager rollups.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `scorecard_id` | string | Scorecard UUID from `list_scorecards` (required) |
| `from_date` | string | Start date YYYY-MM-DD (required, converted to ISO 8601 internally) |
| `to_date` | string | End date YYYY-MM-DD (required) |
| `owner_email` | string | Optional — filters to a specific AE. Email is resolved to a user UUID via `/organizations/users`. |
| `user_uuids` | array | Optional — explicit user UUIDs (merged with any resolved `owner_email`) |
| `team_uuids` | array | Optional — team UUIDs |
| `scorecard_item_ids` | array | Optional — restrict to specific criterion UUIDs |

**Example:**
```
Get last month's scorecard summary for owner@company.com on the AM scorecard
```

### `create_scorecard_result`

Create a scorecard result (structured coaching feedback) on a conversation. This writes directly into Attention's UI so managers don't have to transcribe feedback manually.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `scorecard_id` | string | Scorecard UUID (required) |
| `items` | array | Per-criterion results (required). Each object: `{scorecard_item_uuid, description, numeric_result?}` |
| `summary` | string | Overall notes across all criteria (required) |
| `conversation_id` | string | Target conversation UUID (one of conversation_id/chat_id required) |
| `chat_id` | string | Alternative target: Attention chat UUID |

**Notes:**
- Idempotency is not documented by the Attention API; re-posting the same `scorecard_id + conversation_id` may create duplicate results. De-duplicate on the caller side if needed.
- Requires an API key with write scope on scorecards.

**Example:**
```
Post a scorecard result for conversation X on the AM scorecard with these notes per criterion...
```

### `ask_attention`

Run Attention's AI analysis (v2) across one or more conversations. Returns an array of per-conversation outputs — useful as a second-opinion signal alongside the Sales Bible.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | string | The analysis question (required) |
| `conversation_ids` | array | Conversation UUIDs to analyze |
| `deal_id` | string | Deal identifier (empty string accepted when not scoped to a deal) |
| `include_timestamps` | boolean | If true, returns timestamped transcript segments per conversation |

**Notes:**
- The API requires at least one of `conversation_ids` or `deal_id`. The client validates this and raises a `ValueError` before making the network call.
- Per-conversation errors (e.g. `"conversation transcript is empty"`) surface in the `error` field of each result object, not as HTTP errors.

**Example:**
```
Use ask_attention to summarize the decision-maker objections across these 3 calls
```

### `list_gi_history`

List an org user's generalized-insights (GI) history. Feeds rep-profile updates.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `user_email` | string | Org user email (resolved to UUID internally). Provide this OR `user_uuid`. |
| `user_uuid` | string | User UUID (skip email lookup) |
| `limit` | integer | Max entries (default: 20) |
| `offset` | integer | Pagination offset (default: 0) |

**Notes:**
- The underlying `/gi/history` endpoint does not accept date range filters.
- If the user has no GI history, the API returns `{"data": null}` rather than an empty array.

**Example:**
```
Show GI history for ae@company.com
```

## Output Format

### Conversation Details

When retrieving a conversation, the output includes:

```markdown
# Call Title

**ID:** conversation-uuid
**Date:** 2025-01-14 10:30
**Video Status:** READY

## Participants
  - John Smith (john@company.com)
  - Jane Doe (jane@customer.com)

## Extracted Intelligence
### Call Sentiment
Positive - The customer expressed strong interest...

### Last Call Summary
Key points discussed:
- Feature requirements
- Timeline expectations
- Next steps

## Transcript

**John Smith:** Welcome to the call...

**Jane Doe:** Thanks for having me...
```

## API Reference

This server wraps the [Attention API v2](https://docs.attention.com/api-reference).

### Authentication

The server uses Bearer token authentication. Get your API key from:
1. Log into https://app.attention.tech
2. Navigate to Settings → Organization → API Keys
3. Click "+ Create API Key"
4. Copy the key (only shown once)

### Rate Limits

Attention API rate limits apply. See [Attention documentation](https://docs.attention.com) for current limits.

## Development

### Project Structure

```
attention-mcp/
├── server.py              # MCP server implementation
├── attention_client.py    # Attention API client wrapper
├── scripts/
│   └── smoke_test.py      # End-to-end smoke test against the real API
├── requirements.txt       # Python dependencies
├── .gitignore
└── README.md
```

### Smoke Test

`scripts/smoke_test.py` exercises every client method against the real Attention API:

```bash
# Dry-run (default) — validates every call except the destructive POST /createScorecardResult
ATTENTION_API_KEY=... .venv/bin/python scripts/smoke_test.py

# Opt-in actual write of a scorecard result (creates visible data in the Attention UI)
ATTENTION_API_KEY=... .venv/bin/python scripts/smoke_test.py --write
```

### Running Locally

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the server (for testing)
python server.py
```

### Testing the Client

```python
from attention_client import AttentionClient

client = AttentionClient()

# Search for conversations
results = client.search_conversations(query="Acme", from_date="2025-01-01")

# Get a specific conversation
conv = client.get_conversation("conversation-uuid", detailed_transcript=True)
```

## Troubleshooting

### "ATTENTION_API_KEY must be set"

Ensure the API key is set either:
- In your environment: `export ATTENTION_API_KEY="..."`
- In the MCP server config's `env` section
- In a `.env` file in the project directory

### Empty transcripts

If transcripts appear empty:
1. Check that the call has finished processing in Attention
2. Verify your API key has permission to access transcripts
3. Some calls may not have transcripts if recording failed

### Connection errors

- Verify your API key hasn't been revoked
- Check network connectivity to `api.attention.tech`
- Ensure you're not hitting rate limits

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Related

- [Attention](https://attention.tech) - AI-powered conversation intelligence
- [MCP Protocol](https://modelcontextprotocol.io) - Model Context Protocol specification
- [Claude Code](https://claude.ai/code) - Anthropic's CLI for Claude
