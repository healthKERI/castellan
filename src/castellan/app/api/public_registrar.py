# -*- encoding: utf-8 -*-
"""
hkapi.app.api.registrar module

Falcon endpoints that expose the healthKERI platform as a KERIGuard credential
registrar for SaaS-mode deployments.  All routes are ESSR-protected by the
existing SignatureValidationComponent middleware.

Routes (all mounted under /registrar/ in setup_app):
    GET  /registrar/                        — return the registrar hab's own AID
    PUT  /registrar/                        — accept CESR grant / introduction
    GET  /registrar/credential/{said}       — return CESR stream for a credential
    GET  /registrar/credentials/search      — search credentials by issuer
    GET  /registrar/oobi/{aid}              — return CESR OOBI for a watched AID
"""

import falcon
from castellan.core.services.custom.custom_errors import NotFoundError
from castellan.core.services.registrar_service import (
    RegistrarService,
    KeystateBehindError,
)
from keri.help import ogler

logger = ogler.getLogger()


class RegistrarEnd:
    """GET /registrar/ — return the registrar hab's own AID.
    PUT  /registrar/ — accept CESR grant bytes (IPEX grant or introduction).
    """

    def __init__(self, registrarSvc: RegistrarService):
        self.service = registrarSvc

    def on_get(self, _, resp):
        resp.status = falcon.HTTP_200
        resp.media = self.service.get_identity()


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


class RegistrarCredentialEnd:
    """GET /registrar/credential/{said} — return CESR stream for a credential."""

    def __init__(self, registrarSvc: RegistrarService):
        self.service = registrarSvc

    def on_get(self, req, resp, said):
        registry = req.get_param_as_bool("registry", default=False)
        tel = req.get_param_as_bool("tel", default=False)
        try:
            out = self.service.get_credential_cesr(said, registry=registry, tel=tel)
        except NotFoundError:
            raise falcon.HTTPNotFound(
                title="Not Found",
                description=f"Credential {said} not found",
            )
        except Exception as e:
            logger.error(f"RegistrarCredentialEnd: error fetching {said}: {e}")
            raise falcon.HTTPInternalServerError(
                title="Internal Error",
                description=str(e),
            )
        resp.status = falcon.HTTP_200
        resp.content_type = "application/cesr"
        resp.data = out


class RegistrarCredentialSearchEnd:
    """GET /registrar/credentials/search — search credentials by issuer."""

    def __init__(self, registrarSvc: RegistrarService):
        self.service = registrarSvc

    def on_get(self, req, resp):
        issuer = req.get_param("issuer", required=True)
        issuer_sn = req.get_param_as_int("issuer_sn", required=True)
        try:
            saids = self.service.search_credentials(issuer, issuer_sn)
        except KeystateBehindError as e:
            raise falcon.HTTPPreconditionFailed(
                title="Keystate Behind",
                description=str(e),
            )
        except Exception as e:
            logger.error(f"RegistrarCredentialSearchEnd: error: {e}")
            raise falcon.HTTPInternalServerError(
                title="Internal Error",
                description=str(e),
            )
        resp.status = falcon.HTTP_200
        resp.media = {"credentials": saids}


class RegistrarOOBIEnd:
    """GET /registrar/oobi/{aid} — return CESR OOBI for a watched AID."""

    def __init__(self, registrarSvc: RegistrarService):
        self.service = registrarSvc

    def on_get(self, _req, resp, aid):
        try:
            oobi_bytes = self.service.get_oobi_cesr(aid)
        except NotFoundError:
            raise falcon.HTTPNotFound(
                title="Not Found",
                description=f"AID {aid} not found or has no OOBI",
            )
        except Exception as e:
            logger.error(f"RegistrarOOBIEnd: error fetching OOBI for {aid}: {e}")
            raise falcon.HTTPInternalServerError(
                title="Internal Error",
                description=str(e),
            )
        resp.status = falcon.HTTP_200
        resp.content_type = "application/cesr"
        resp.data = oobi_bytes
