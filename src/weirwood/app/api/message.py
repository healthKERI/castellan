# -*- encoding: utf-8 -*-
"""
weirwood.app.api.message module

REST endpoint handlers for the weirwood intra-enterprise mailbox:

  POST   /messages        — post a CESR-encoded message for a recipient AID
  GET    /messages        — poll messages for the authenticated AID
  PUT    /messages/{id}   — mark a message as read
  DELETE /messages/{id}   — delete a message

Authentication: all routes use the existing ESSR SignatureValidationComponent.
The sender_aid is derived from the authenticated request (req.context.aid).
The recipient_aid for POST is taken from the CESR-Destination header or
the `recipient` query param.

Primary use case: routing /multisig/vcp EXN events between group members
during multisig registry inception.  Other topics (issuance, revocation)
will be added in later steps.
"""
import falcon
from keri.help import ogler

from weirwood.core.services.custom.custom_errors import NotFoundError

logger = ogler.getLogger()

_CESR_DESTINATION_HEADER = "cesr-destination"


def _serialize(msg) -> dict:
    return {
        "id": msg.id,
        "recipient_aid": msg.recipient_aid,
        "sender_aid": msg.sender_aid,
        "topic": msg.topic,
        "raw": msg.raw.decode("latin-1") if isinstance(msg.raw, (bytes, bytearray)) else msg.raw,
        "read": msg.read,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


class MessageCollectionEnd:
    """Handles POST /messages and GET /messages."""

    def __init__(self, msgSvc):
        self.service = msgSvc

    def on_post(self, req, resp):
        """
        Post a CESR-encoded message to a recipient AID.

        The request body contains the raw CESR-encoded event bytes.
        The recipient AID is read from the CESR-Destination header (preferred)
        or the `recipient` query parameter.
        The topic is taken from the `topic` query parameter (default: multisig).

        The sender AID is derived from req.context.aid (set by ESSR middleware).

        Response (201): serialized Message document.
        """
        # Resolve recipient
        recipient_aid = (
            req.get_header(_CESR_DESTINATION_HEADER)
            or req.get_param("recipient")
        )
        if not recipient_aid:
            raise falcon.HTTPBadRequest(
                title="Bad Request",
                description=(
                    f"Recipient AID required: supply '{_CESR_DESTINATION_HEADER}' "
                    "header or 'recipient' query param."
                ),
            )

        topic = req.get_param("topic", default="multisig")

        # Sender from ESSR context
        sender_aid = getattr(req.context, "aid", None)
        if not sender_aid:
            raise falcon.HTTPUnauthorized(
                title="Unauthorized",
                description="Could not determine sender AID from request context.",
            )

        try:
            raw = req.bounded_stream.read()
        except Exception as e:
            raise falcon.HTTPBadRequest(
                title="Read Error",
                description=f"Could not read request body: {e}",
            )

        if not raw:
            raise falcon.HTTPBadRequest(
                title="Bad Request",
                description="Request body must contain CESR-encoded event bytes.",
            )

        try:
            msg = self.service.post_message(
                recipient_aid=recipient_aid,
                sender_aid=sender_aid,
                topic=topic,
                raw=raw,
            )
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        resp.status = falcon.HTTP_201
        resp.content_type = "application/json"
        resp.media = _serialize(msg)

    def on_get(self, req, resp):
        """
        Poll messages for the authenticated AID.

        Query params:
            topic       — filter to a specific topic (e.g. "multisig")
            unread      — if "true", return only unread messages
            page        — zero-indexed page (default 0)
            page_size   — results per page (default 50)

        Response (200):
            {
              "count": N,
              "page": P,
              "num_pages": NP,
              "messages": [...]
            }

        The authenticated AID is read from req.context.aid (ESSR middleware).
        """
        recipient_aid = getattr(req.context, "aid", None)
        if not recipient_aid:
            raise falcon.HTTPUnauthorized(
                title="Unauthorized",
                description="Could not determine recipient AID from request context.",
            )

        topic = req.get_param("topic", default=None)
        unread_only = req.get_param_as_bool("unread", default=False)
        page = req.get_param_as_int("page", default=0)
        page_size = req.get_param_as_int("page_size", default=50)

        try:
            messages, total, num_pages = self.service.get_messages(
                recipient_aid=recipient_aid,
                topic=topic,
                unread_only=unread_only,
                page=page,
                page_size=page_size,
            )
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        resp.status = falcon.HTTP_200
        resp.content_type = "application/json"
        resp.media = {
            "count": total,
            "page": page,
            "num_pages": num_pages,
            "messages": [_serialize(m) for m in messages],
        }


class MessageResourceEnd:
    """Handles PUT /messages/{id} and DELETE /messages/{id}."""

    def __init__(self, msgSvc):
        self.service = msgSvc

    def on_put(self, req, resp, id):
        """Mark a message as read."""
        try:
            msg = self.service.mark_read(id)
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        resp.status = falcon.HTTP_200
        resp.content_type = "application/json"
        resp.media = _serialize(msg)

    def on_delete(self, req, resp, id):
        """Delete a message."""
        try:
            self.service.delete_message(id)
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        resp.status = falcon.HTTP_204