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

        self._user_email_to_uuid: Optional[dict[str, str]] = None

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

    def list_organization_users(self, team_uuid: Optional[str] = None) -> dict:
        """List users in the organization.

        Args:
            team_uuid: Optional team UUID to filter by.

        Returns:
            Dict with 'data' list of user objects (uuid, email, firstName, lastName, ...).
        """
        params = {}
        if team_uuid:
            params["teamUUID"] = team_uuid
        response = self.client.get("/organizations/users", params=params)
        response.raise_for_status()
        return response.json()

    def resolve_user_uuid(self, email: str) -> str:
        """Resolve an organization user's email to their UUID.

        Caches the full user list on first call. Raises ValueError if not found.
        """
        if self._user_email_to_uuid is None:
            users = self.list_organization_users().get("data", [])
            self._user_email_to_uuid = {
                (u.get("email") or "").lower(): u.get("uuid")
                for u in users
                if u.get("email") and u.get("uuid")
            }
        uuid = self._user_email_to_uuid.get(email.lower())
        if not uuid:
            raise ValueError(f"No organization user found with email: {email}")
        return uuid

    def list_scorecards(self) -> dict:
        """List all scorecards configured for the organization.

        Returns:
            Raw API response. Scorecards typically live under 'data' with nested items.
        """
        response = self.client.get("/scorecards")
        response.raise_for_status()
        return response.json()

    def get_scorecards_summary(
        self,
        scorecard_id: str,
        from_date: str,
        to_date: str,
        owner_email: Optional[str] = None,
        user_uuids: Optional[list[str]] = None,
        team_uuids: Optional[list[str]] = None,
        scorecard_item_ids: Optional[list[str]] = None,
    ) -> dict:
        """Fetch per-criterion averages for a scorecard over a date range.

        Args:
            scorecard_id: Scorecard UUID.
            from_date: Start date in YYYY-MM-DD format.
            to_date: End date in YYYY-MM-DD format.
            owner_email: Optional org user email. Resolved to user UUID and merged into user_uuids.
            user_uuids: Optional explicit user UUID filter.
            team_uuids: Optional team UUID filter.
            scorecard_item_ids: Optional filter to specific criterion UUIDs.

        Returns:
            Dict with 'data' array of per-user/team summary items.
        """
        resolved_users = list(user_uuids or [])
        if owner_email:
            resolved_users.append(self.resolve_user_uuid(owner_email))

        body = {
            "scorecardUUID": scorecard_id,
            "fromDateTime": f"{from_date}T00:00:00Z",
            "toDateTime": f"{to_date}T23:59:59Z",
            "teamUUIDs": team_uuids or [],
            "userUUIDs": resolved_users,
            "scorecardsItemsUUIDs": scorecard_item_ids or [],
        }
        response = self.client.post("/scorecards/summary", json=body)
        response.raise_for_status()
        return response.json()

    def create_scorecard_result(
        self,
        scorecard_id: str,
        items: list[dict],
        summary: str,
        conversation_id: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> dict:
        """Create a scorecard result (written coaching feedback) on a conversation.

        Args:
            scorecard_id: Scorecard UUID (from list_scorecards).
            items: List of per-criterion results. Each item should contain:
                - scorecard_item_uuid (str, required): the criterion UUID
                - description (str, required): written notes for this criterion
                - numeric_result (int, optional): numeric score
            summary: Overall notes across all criteria.
            conversation_id: Conversation UUID the scorecard is scored against.
            chat_id: Alternative target (Attention chat UUID); one of conversation_id/chat_id required.

        Returns:
            API response: {"success": bool}.
        """
        if not conversation_id and not chat_id:
            raise ValueError("create_scorecard_result requires conversation_id or chat_id")

        body: dict = {
            "scorecard_uuid": scorecard_id,
            "summary": summary,
            "items": items,
        }
        if conversation_id:
            body["conversation_uuid"] = conversation_id
        if chat_id:
            body["chat_uuid"] = chat_id

        response = self.client.post("/createScorecardResult", json=body)
        response.raise_for_status()
        return response.json()

    def ask_attention(
        self,
        prompt: str,
        conversation_ids: Optional[list[str]] = None,
        deal_id: Optional[str] = None,
        include_timestamps: bool = False,
    ) -> list[dict]:
        """Run Attention's AI analysis (v2) against a prompt.

        Args:
            prompt: The analysis question.
            conversation_ids: Conversation UUIDs to analyze. Docs mark this required; we
                default to an empty list if not supplied and let the API surface any error.
            deal_id: Deal identifier. Docs mark this required; we pass "" if not supplied.
            include_timestamps: If True, returns timestamped transcript segments per conversation.

        Returns:
            Array of {output, conversation_id, error, segments?} objects.
        """
        conv_ids = conversation_ids or []
        deal = deal_id if deal_id is not None else ""
        if not conv_ids and not deal:
            raise ValueError(
                "ask_attention requires at least one of conversation_ids or deal_id; "
                "API returns 500 ('at least one of deal_id or conversations_ids is required') otherwise."
            )

        body = {
            "conversations_ids": conv_ids,
            "deal_id": deal,
            "prompt": prompt,
        }
        params = {}
        if include_timestamps:
            params["include_timestamps"] = "true"

        response = self.client.post("/ask_attention/v2", json=body, params=params)
        response.raise_for_status()
        return response.json()

    def list_gi_history(
        self,
        user_email: Optional[str] = None,
        user_uuid: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        without_enhancing_results: bool = False,
    ) -> dict:
        """List general-intelligence (GI) insight history for a user.

        Args:
            user_email: Organization user email (resolved to UUID). Provide this OR user_uuid.
            user_uuid: User UUID (skip email lookup).
            limit: Max entries (default 20).
            offset: Pagination offset (default 0).
            without_enhancing_results: Return raw insight data without post-processing.

        Returns:
            Dict with 'data' array of GIHistory objects and 'meta' pagination.
        """
        if not user_uuid:
            if not user_email:
                raise ValueError("list_gi_history requires user_email or user_uuid")
            user_uuid = self.resolve_user_uuid(user_email)

        params = {
            "user_uuid": user_uuid,
            "limit": limit,
            "offset": offset,
        }
        if without_enhancing_results:
            params["withoutEnhancingResults"] = "true"

        response = self.client.get("/gi/history", params=params)
        response.raise_for_status()
        return response.json()

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
