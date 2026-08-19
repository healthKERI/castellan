# -*- encoding: utf-8 -*-
"""
castellan.core.services.message_service module

Service and MongoDB document model for intra-enterprise CESR messages.

Castellan acts as a simple relay/mailbox for CESR-encoded events between
castellan instances and whisper clients (e.g., /multisig/vcp EXN coordination).
Messages are stored per-recipient and polled via HTTP GET (no SSE for MVP).
"""

import math
import uuid
from datetime import datetime

from keri.help import ogler
from mongoengine import BinaryField, BooleanField, DateTimeField, Document, StringField

from castellan.core.services.custom.custom_errors import NotFoundError

logger = ogler.getLogger()

# Well-known topics
TOPIC_MULTISIG = "multisig"
TOPIC_ISSUANCE = "issuance"
TOPIC_REVOCATION = "revocation"


class Message(Document):
    """A CESR-encoded message relayed through the castellan mailbox."""

    id = StringField(required=True, primary_key=True)
    recipient_aid = StringField(required=True)  # target AID
    sender_aid = StringField(required=True)  # authenticated sender (from ESSR)
    topic = StringField(required=True)  # multisig | issuance | revocation
    raw = BinaryField(required=True)  # raw CESR-encoded event bytes
    read = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now)
    multisig_alias = StringField(default="")

    meta = {
        "indexes": [
            "recipient_aid",
            ("recipient_aid", "topic"),
            ("recipient_aid", "read"),
        ],
        "ordering": ["created_at"],
    }


class MessageService:
    """Service for storing and retrieving intra-enterprise CESR messages."""

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def post_message(
        self,
        recipient_aid: str,
        sender_aid: str,
        topic: str,
        raw: bytes,
        multisig_alias: str = "",
    ) -> "Message":
        """
        Store a CESR-encoded message for a recipient AID.

        Args:
            recipient_aid: Target AID (who should receive this message).
            sender_aid:    Authenticated sender AID (from ESSR signature).
            topic:         Logical channel (multisig / issuance / revocation).
            raw:           Raw CESR-encoded event bytes.

        Returns:
            The created Message document.
        """
        msg = Message(
            id=str(uuid.uuid4()),
            recipient_aid=recipient_aid,
            sender_aid=sender_aid,
            topic=topic,
            raw=raw,
            multisig_alias=multisig_alias,
            read=False,
        )
        msg.save()
        logger.info(
            f"Stored message id={msg.id} topic={topic} "
            f"recipient={recipient_aid} sender={sender_aid}"
        )
        return msg

    # ------------------------------------------------------------------
    # Read / Poll
    # ------------------------------------------------------------------

    def get_messages(
        self,
        recipient_aid: str,
        topic: str | None = None,
        unread_only: bool = False,
        page: int = 0,
        page_size: int = 50,
    ) -> tuple[list["Message"], int, int]:
        """
        Poll messages for an AID with optional topic/read filters and pagination.

        Args:
            recipient_aid: AID whose messages to retrieve.
            topic:         If set, filter to this topic.
            unread_only:   If True, return only unread messages.
            page:          Zero-indexed page number.
            page_size:     Results per page (default 50).

        Returns:
            (messages, total_count, num_pages)
        """
        qs = Message.objects(recipient_aid=recipient_aid)
        if topic is not None:
            qs = qs.filter(topic=topic)
        if unread_only:
            qs = qs.filter(read=False)

        qs = qs.order_by("created_at")
        total = qs.count()
        num_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        messages = list(qs.skip(page * page_size).limit(page_size))
        return messages, total, num_pages

    def get_message(self, message_id: str) -> "Message":
        """Fetch a single Message by ID. Raises NotFoundError if missing."""
        try:
            return Message.objects.get(id=message_id)
        except Message.DoesNotExist:
            raise NotFoundError(f"Message not found: {message_id}")

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def mark_read(self, message_id: str) -> "Message":
        """Mark a message as read. Raises NotFoundError if missing."""
        msg = self.get_message(message_id)
        msg.read = True
        msg.save()
        return msg

    def delete_message(self, message_id: str) -> None:
        """Delete a message. Raises NotFoundError if missing."""
        msg = self.get_message(message_id)
        msg.delete()
        logger.info(f"Deleted message id={message_id}")
