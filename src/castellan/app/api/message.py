# -*- encoding: utf-8 -*-
"""
castellan.app.api.message module

REST endpoint handlers for the castellan intra-enterprise mailbox:

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

from castellan.core.services.custom.custom_errors import NotFoundError

logger = ogler.getLogger()

_CESR_DESTINATION_HEADER = "cesr-destination"


def _serialize(msg) -> dict:
    return {
        "id": msg.id,
        "recipient_aid": msg.recipient_aid,
        "sender_aid": msg.sender_aid,
        "topic": msg.topic,
        "raw": msg.raw.decode("utf-8") if isinstance(msg.raw, (bytes, bytearray)) else msg.raw,
        "read": msg.read,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "multisig_alias": msg.multisig_alias if hasattr(msg, "multisig_alias") else ""
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

        The sender AID is the whisper-uploaded identifier, passed as the `sender` query param.
        The recipient AID is the target group participant, passed as the `recipient` query param
        (or via the CESR-Destination header). One POST per recipient is required.

        Response (201): serialized Message document.
        """
        logger.info("POST /messages: request received")

        # Resolve recipient
        recipient_aid = req.get_param("recipient")

        if not recipient_aid:
            logger.warning(
                "POST /messages 400: no recipient AID provided via header or query param"
            )
            raise falcon.HTTPBadRequest(
                title="Bad Request",
                description=(
                    f"Recipient AID required: supply '{_CESR_DESTINATION_HEADER}' "
                    "header or 'recipient' query param."
                ),
            )

        topic = req.get_param("topic", default="multisig")

        sender_aid = req.get_param("sender")
        if not sender_aid:
            logger.warning("POST /messages 400: missing required 'sender' query param")
            raise falcon.HTTPBadRequest(
                title="Bad Request",
                description="Required query param 'sender' (whisper-uploaded sender AID) is missing.",
            )

        multisig_alias = req.get_param("multisig_alias", default="")

        try:
            raw = req.bounded_stream.read()
            logger.debug(
                f"POST /messages: read {len(raw) if raw else 0} bytes from request body"
            )
        except Exception as e:
            logger.error(f"POST /messages 400: failed to read request body — {e}", exc_info=True)
            raise falcon.HTTPBadRequest(
                title="Read Error",
                description=f"Could not read request body: {e}",
            )

        if not raw:
            logger.warning("POST /messages 400: empty request body")
            raise falcon.HTTPBadRequest(
                title="Bad Request",
                description="Request body must contain CESR-encoded event bytes.",
            )

        logger.info(
            f"POST /messages: posting message — "
            f"sender={sender_aid[:16]}..., recipient={recipient_aid[:16]}..., "
            f"topic={topic}, body_length={len(raw)}"
        )

        try:
            msg = self.service.post_message(
                recipient_aid=recipient_aid,
                sender_aid=sender_aid,
                topic=topic,
                raw=raw,
                multisig_alias=multisig_alias
            )
        except Exception as e:
            logger.error(
                f"POST /messages 500: service.post_message raised {type(e).__name__}: {e}",
                exc_info=True,
            )
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        logger.info(
            f"POST /messages 201: id={msg.id}, topic={topic}, "
            f"sender={sender_aid[:16]}..., recipient={recipient_aid[:16]}..., "
            f"body_length={len(raw)}"
        )
        resp.status = falcon.HTTP_201
        resp.content_type = "application/json"
        resp.media = _serialize(msg)

    def on_get(self, req, resp):
        """
        Poll messages for the given AID.

        Query params:
            aid         — recipient AID (required; the whisper-uploaded identifier prefix)
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
        """
        recipient_aid = req.get_param("aid")
        if not recipient_aid:
            logger.warning("GET /messages: missing required 'aid' query param — returning 400")
            raise falcon.HTTPBadRequest(
                title="Bad Request",
                description="Required query param 'aid' (recipient AID) is missing.",
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
            logger.error(f"GET /messages 500: {e}")
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        logger.info(f"GET /messages 200: aid={recipient_aid[:16]}... count={total}")
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

        logger.info(f"PUT /messages/{id} 200: marked read")
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

        logger.info(f"DELETE /messages/{id} 204")
        resp.status = falcon.HTTP_204