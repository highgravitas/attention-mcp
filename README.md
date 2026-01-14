# Attention MCP Server

An MCP (Model Context Protocol) server that provides access to [Attention](https://attention.tech) call recordings and transcripts. Enables AI assistants like Claude to search, retrieve, and analyze sales calls, customer calls, and demos.

## Features

- **Search conversations** - Find calls by title, date range, participant, or owner
- **Get full transcripts** - Retrieve complete call transcripts with speaker labels
- **AI summaries** - Access Attention's extracted intelligence (call sentiment, summaries, action items)
- **List recent calls** - Quick access to conversations from the past N days

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
├── server.py           # MCP server implementation
├── attention_client.py # Attention API client wrapper
├── requirements.txt    # Python dependencies
├── .gitignore
└── README.md
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
