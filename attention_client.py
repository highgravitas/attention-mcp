"""
Attention API Client

Wrapper for the Attention REST API (https://api.attention.tech/v2/)
Documentation: https://docs.attention.com/api-authentication
"""

import os
from datetime import datetime, timedelta
from typing import Optional
import httpx


class AttentionClient:
    """Client for interacting with the Attention API."""

    BASE_URL = "https://api.attention.tech/v2"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Attention client.

        Args:
            api_key: Attention API key. If not provided, reads from ATTENTION_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("ATTENTION_API_KEY")
        if not self.api_key:
            raise ValueError("ATTENTION_API_KEY must be set")

        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def search_conversations(
        self,
        query: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        participant_email: Optional[str] = None,
        owner_email: Optional[str] = None,
        page: int = 1,
        size: int = 20,
        detailed_transcript: bool = False,
    ) -> dict:
        """
        Search for conversations.

        Args:
            query: Search term for title (case-insensitive partial match)
            from_date: Start date (ISO 8601 format, e.g., "2024-01-01")
            to_date: End date (ISO 8601 format)
            participant_email: Filter by participant email
            owner_email: Filter by owner email
            page: Page number (starts from 1)
            size: Items per page
            detailed_transcript: Include detailed transcript info

        Returns:
            Dict with 'data' (list of conversations) and 'meta' (pagination info)
        """
        params = {
            "page": page,
            "size": size,
            "detailedTranscript": str(detailed_transcript).lower(),
        }

        if query:
            params["filter[title]"] = query
        if from_date:
            params["fromDateTime"] = f"{from_date}T00:00:00Z"
        if to_date:
            params["toDateTime"] = f"{to_date}T23:59:59Z"
        if participant_email:
            params["filter[participants.email]"] = participant_email
        if owner_email:
            params["filter[owner.email]"] = owner_email

        response = self.client.get("/conversations", params=params)
        response.raise_for_status()
        return response.json()

    def get_conversation(
        self,
        conversation_id: str,
        detailed_transcript: bool = True,
        include_internal_participants: bool = False,
    ) -> dict:
        """
        Get a single conversation by ID.

        Args:
            conversation_id: The conversation UUID
            detailed_transcript: Include detailed transcript info
            include_internal_participants: Include internal participants

        Returns:
            Conversation data with transcript
        """
        params = {
            "detailedTranscript": str(detailed_transcript).lower(),
            "filter[include_internal_participants]": str(include_internal_participants).lower(),
        }

        response = self.client.get(f"/conversations/{conversation_id}", params=params)
        response.raise_for_status()
        return response.json()

    def list_recent_conversations(
        self,
        days_back: int = 7,
        size: int = 20,
    ) -> dict:
        """
        List recent conversations from the past N days.

        Args:
            days_back: Number of days to look back
            size: Maximum number of results

        Returns:
            Dict with 'data' (list of conversations) and 'meta' (pagination info)
        """
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")

        return self.search_conversations(
            from_date=from_date,
            to_date=to_date,
            size=size,
        )

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
