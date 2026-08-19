# -*- encoding: utf-8 -*-
"""
castellan.app.api.registrar module

REST endpoint handlers for the castellan TEL registrar role:

  POST   /registrar/tel-events          — receive a TEL event, sign, store
  GET    /registrar/tel-events/{regk}   — list events for a registry
  GET    /registrar/tel-events/{regk}/{vcid}  — list events for a credential
  GET    /oobi/{cid}/registrar          — standard KERI registrar OOBI

The /oobi endpoint serves castellan's registrar endpoint information as a
CESR-encoded KERI reply stream so clients can resolve castellan via keripy's
standard OOBI resolution mechanism.
"""

import base64

import falcon
from keri import kering
from keri.help import ogler

from castellan.core.services.custom.custom_errors import ConflictError

logger = ogler.getLogger()


def _serialize_event(event) -> dict:
    return {
        "said": event.said,
        "regk": event.regk,
        "vcid": event.vcid,
        "sn": event.sn,
        "event_type": event.event_type,
        "receipt": event.receipt,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


class RegistrarTelCollectionEnd:
    """
    POST /registrar/tel-events

    Accepts a raw CESR-encoded TEL event body, parses it, signs it with the
    castellan registrar hab, and stores it.  Returns the event metadata plus
    castellan's cigar receipt signature.
    """

    def __init__(self, telSvc):
        self.service = telSvc

    def on_post(self, req, resp):
        """
        Receive a TEL event from an issuer.

        Request body: raw CESR-encoded TEL event bytes
        Content-Type: application/cesr or application/octet-stream

        Response (201):
            {
              "said": "<event SAID>",
              "regk": "<registry prefix>",
              "vcid": "<credential SAID or null>",
              "sn":   <sequence number>,
              "event_type": "vcp|vrt|iss|bis|rev|brv",
              "receipt": "<castellan cigar signature qb64>"
            }
        """
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
                description="Request body must contain CESR-encoded TEL event bytes.",
            )

        try:
            event, receipt_qb64 = self.service.receive_event(raw)
        except ValueError as e:
            raise falcon.HTTPBadRequest(title="Invalid TEL Event", description=str(e))
        except ConflictError as e:
            raise falcon.HTTPConflict(title="Conflict", description=str(e))
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        resp.status = falcon.HTTP_201
        resp.content_type = "application/json"
        resp.media = _serialize_event(event)


class RegistrarTelResourceEnd:
    """
    GET /registrar/tel-events/{regk}
    GET /registrar/tel-events/{regk}/{vcid}

    Retrieve stored TEL events for a registry or a specific credential.
    """

    def __init__(self, telSvc):
        self.service = telSvc

    def on_get(self, req, resp, regk, vcid=None):
        """
        List TEL events.

        Path params:
            regk  — registry prefix (AID)
            vcid  — credential SAID (optional; when present, filter to that credential)

        Response (200):
            { "regk": ..., "vcid": ..., "count": N, "events": [...] }
        """
        try:
            if vcid:
                events = self.service.get_events_for_credential(regk, vcid)
            else:
                events = self.service.get_events_for_registry(regk)
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        resp.status = falcon.HTTP_200
        resp.content_type = "application/json"
        resp.media = {
            "regk": regk,
            "vcid": vcid,
            "count": len(events),
            "events": [_serialize_event(e) for e in events],
        }


class RegistrarBackerEnd:
    """
    GET /registrar/backer

    Returns the AID and base64-encoded KEL of castellan's non-transferable
    backer identifier.  Whisper instances call this during setup to learn
    which AID to include in registry ``baks`` lists and to resolve the
    backer's key state locally.

    Response (200):
        {
          "aid":     "<non-transferable backer prefix>",
          "kel_b64": "<base64-encoded CESR KEL bytes>"
        }
    """

    def __init__(self, hby, hab):
        self.hby = hby
        self.hab = hab  # non-transferable backer hab

    def on_get(self, req, resp):
        kel_bytes = b"".join(self.hby.db.clonePreIter(pre=self.hab.pre, fn=0))
        resp.status = falcon.HTTP_200
        resp.content_type = "application/json"
        resp.media = {
            "aid": self.hab.pre,
            "kel_b64": base64.b64encode(kel_bytes).decode(),
        }


class RegistrarOobiEnd:
    """
    GET /oobi/{cid}/registrar

    Serves castellan's registrar OOBI as a CESR-encoded KERI reply stream.

    This is a standard KERI OOBI endpoint — `registrar` is defined in
    kering.Roles alongside `witness`, `mailbox`, etc.  Clients resolve this
    OOBI using keripy's standard oobiing mechanism so they can verify
    castellan's AID and reach its TEL endpoints.

    Path params:
        cid — the controller AID whose registrar OOBI is requested
              (typically castellan's own AID)
    """

    def __init__(self, hab):
        self.hab = hab

    def on_get(self, req, resp, cid):
        try:
            msgs = self.hab.replyToOobi(aid=cid, role=kering.Roles.registrar)
        except Exception as e:
            logger.error(f"Error building registrar OOBI for {cid}: {e}")
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"Could not build registrar OOBI: {e}",
            )

        if not msgs:
            raise falcon.HTTPNotFound(
                title="Not Found",
                description=f"No registrar OOBI registered for {cid}.",
            )

        resp.status = falcon.HTTP_200
        resp.content_type = "application/json+cesr"
        resp.data = bytes(msgs)


class MailboxOobiEnd:
    """
    GET /oobi/{cid}/mailbox/{eid}

    Serves castellan's mailbox OOBI as a CESR-encoded KERI reply stream so
    that callers (e.g. mock-gleif) can resolve castellan's mailbox endpoint
    without going through witnesses.
    """

    def __init__(self, hab):
        self.hab = hab

    def on_get(self, req, resp, cid, eid=None):
        try:
            msgs = self.hab.replyToOobi(aid=cid, role=kering.Roles.mailbox)
        except Exception as e:
            logger.error(f"Error building mailbox OOBI for {cid}: {e}")
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"Could not build mailbox OOBI: {e}",
            )

        if not msgs:
            raise falcon.HTTPNotFound(
                title="Not Found",
                description=f"No mailbox OOBI registered for {cid}.",
            )

        resp.status = falcon.HTTP_200
        resp.content_type = "application/json+cesr"
        resp.data = bytes(msgs)
