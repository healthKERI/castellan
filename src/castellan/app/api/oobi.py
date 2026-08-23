# -*- encoding: utf-8 -*-
"""
castellan.app.api.oobi module

Unauthenticated OOBI-resolution endpoints, serving schema, key state,
credential, and castellan's own server AID straight out of MongoDB:

  GET /oobi/{said}            — AID key-state or schema OOBI dispatcher
  GET /oobi/{said}/credential — credential OOBI
  GET /oobi/server            — castellan server AID OOBI

/oobi/{said} matches keripy's own DOOBI_RE bare-segment shape (end/ending.py)
used for both AID and schema OOBIs, disambiguated here by which store the id
matches rather than by URL shape — the same behavior as keripy's own
witness-side OOBIEnd. Content-Type is what a standard keripy Oobiery client
dispatches on (application/json+cesr vs application/schema+json), so any
compliant client resolves either resource correctly through hab.resolve().
"""

import falcon
from castellan.core.services.custom.custom_errors import NotFoundError
from castellan.core.services.key_event_log_service import KeyEventLogService
from keri.help import ogler
from mongoengine import DoesNotExist

logger = ogler.getLogger()

OOBI_AID_HEADER = "KERI-AID"


class OobiDispatchEnd:
    """
    GET /oobi/{said}

    Resolves an AID's key state (+ any captured replies) if `said` matches a
    known Aid, else a schema's raw JSON if `said` matches a known Schema
    SAID, else 404.

    Path field is named `said` (not `id`) to match keripy's own DOOBI_RE
    group name (end/ending.py) — Falcon also requires sibling variable
    routes at the same path level to share a field name, and this dispatcher
    sits next to /oobi/{said}/credential.
    """

    def __init__(self, kel_svc, schema_svc, issued_svc, received_svc):
        self.kel_svc = kel_svc
        self.schema_svc = schema_svc
        self.issued_svc = issued_svc
        self.received_svc = received_svc

    def on_get(self, _, resp, said):
        try:
            KeyEventLogService.get_aid(said)
            ims = self.kel_svc.get_full_stream(said)
            resp.status = falcon.HTTP_200
            resp.content_type = "application/json+cesr"
            resp.set_header(OOBI_AID_HEADER, said)
            resp.data = bytes(ims)
            return

        except DoesNotExist:
            pass

        try:
            ims = self.issued_svc.get_credential_stream(said)
            resp.status = falcon.HTTP_200
            resp.content_type = "application/json+cesr"
            resp.data = bytes(ims)
            return

        except NotFoundError:
            pass

        try:
            ims = self.received_svc.get_credential_stream(said)
            resp.status = falcon.HTTP_200
            resp.content_type = "application/json+cesr"
            resp.data = bytes(ims)
            return

        except NotFoundError:
            pass

        try:
            schema = self.schema_svc.get_schema(said)
            resp.status = falcon.HTTP_200
            resp.content_type = "application/schema+json"
            resp.data = bytes(schema.raw)
            return

        except NotFoundError:
            raise falcon.HTTPNotFound(
                title="Not Found",
                description=f"No AID, credential or schema SAID found for {said}.",
            )


class ServerOobiEnd:
    """
    GET /oobi/server

    Resolves the key state of castellan's currently-registered server AID —
    the identity clients must resolve before they can ESSR-encrypt requests
    to castellan (see CryptSigner.encode() in kept).
    """

    def __init__(self, server_svc, kel_svc):
        self.server_svc = server_svc
        self.kel_svc = kel_svc

    def on_get(self, _, resp):
        server = self.server_svc.get_active_server()
        if server is None:
            raise falcon.HTTPNotFound(
                title="Not Found",
                description="No castellan server AID registered. Run `castellan up` first.",
            )

        ims = self.kel_svc.get_full_stream(server.aid)
        if not ims:
            raise falcon.HTTPNotFound(
                title="Not Found",
                description=f"No key event log captured for server AID {server.aid}.",
            )

        resp.status = falcon.HTTP_200
        resp.content_type = "application/json+cesr"
        resp.set_header(OOBI_AID_HEADER, server.aid)
        resp.data = bytes(ims)
