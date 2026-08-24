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

import falcon
from castellan.core.services.registrar_service import (
    RegistrarService,
    KeystateBehindError,
)
from keri import kering
from keri.help import ogler

logger = ogler.getLogger()


class RegistrarTELEnd:
    """GET /registrar/ — return the registrar hab's own AID.
    PUT  /registrar/ — accept CESR grant bytes (IPEX grant or introduction).
    """

    def __init__(self, registrarSvc: RegistrarService):
        self.service = registrarSvc

    def on_get(self, req, resp):
        issuer = req.get_param("issuer", required=True)
        issuer_sn = req.get_param_as_int("issuer_sn", required=True)
        try:
            saids = self.service.search_tel_events(issuer, issuer_sn)
        except KeystateBehindError as e:
            raise falcon.HTTPPreconditionFailed(
                title="Keystate Behind",
                description=str(e),
            )
        except Exception as e:
            logger.error(f"RegistrarTELEnd: error: {e}")
            raise falcon.HTTPInternalServerError(
                title="Internal Error",
                description=str(e),
            )
        resp.status = falcon.HTTP_200
        resp.media = {"events": saids}

    def on_post(self, req, resp):
        """Accept CESR grant with optional metadata.

        Supports two content types:
        1. multipart/form-data with "data" (CESR bytes) and "doc" (JSON) parts
        2. application/cesr or other for backward compatibility (raw CESR bytes)
        """
        # Check if multipart
        if req.content_type and req.content_type.startswith("multipart/form-data"):
            # Parse multipart form data
            form = req.get_media()
            doc: dict = {}
            tel: bytes = b""
            kel: bytes = b""

            for part in form:
                logger.info(
                    f"RegistrarEnd: parsing tel with {part.name } - {part.content_type}"
                )
                if part.name == "doc":
                    if part.content_type.startswith("application/json"):
                        json_data = part.get_media()
                        if isinstance(json_data, dict):
                            doc.update(json_data)
                        else:
                            raise falcon.HTTPBadRequest(
                                title="Invalid JSON",
                                description="The doc part is not a valid JSON dictionary",
                            )
                elif part.name == "tel":
                    tel = part.get_data()
                elif part.name == "kel":
                    kel = part.get_data()
                else:
                    raise falcon.HTTPBadRequest(
                        title="Bad Request",
                        description=f"Unexpected form part `{part.name}`",
                    )

            if not tel or not kel:
                raise falcon.HTTPBadRequest(
                    title="Missing Field", description="tel and kel parts are required"
                )

            if not doc:
                raise falcon.HTTPBadRequest(
                    title="Missing Field", description="doc part is required"
                )

            try:
                self.service.parse_revocation(tel=tel, kel=kel, doc=doc)
                logger.info("RegistrarEnd: parsed tel")
            except Exception as e:
                logger.error(f"RegistrarEnd: error parsing tel: {e}")
                raise falcon.HTTPInternalServerError(
                    title="Parse Error",
                    description=f"Failed to parse tel: {e}",
                )
        else:
            raise falcon.HTTPBadRequest(
                title="Unsupported Content Type", description="Unsupported Content Type"
            )

        resp.status = falcon.HTTP_204


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
