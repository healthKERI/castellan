# -*- encoding: utf-8 -*-
"""
castellan.app.api.identifier module

REST endpoint handlers for castellan-uploaded identifiers:

  POST   /identifiers       — upload a whisper identifier (aid, alias, oobi)
  GET    /identifiers       — list all uploaded identifiers
  DELETE /identifiers/{aid} — remove an uploaded identifier

Authentication: all routes require ESSR via SignatureValidationComponent.
The uploading AID is derived from req.context.aid (set by middleware).
Alias uniqueness is enforced server-side; duplicate alias → 409 Conflict.
"""

import base64
import json

from requests_toolbelt import MultipartEncoder

import falcon
from keri.help import ogler

from castellan.core.services.custom.custom_errors import ConflictError, NotFoundError

logger = ogler.getLogger()


def _serialize(identifier) -> dict:
    return {
        "aid": identifier.aid,
        "alias": identifier.alias,
        "oobi": identifier.oobi or "",
        "created_at": (
            identifier.created_at.isoformat() if identifier.created_at else None
        ),
    }


class IdentifierCollectionEnd:
    """Handles POST /identifiers and GET /identifiers."""

    def __init__(self, identifierSvc):
        self.service = identifierSvc

    def on_post(self, req, resp):
        """
        Upload a whisper identifier to castellan.

        Request body (multipart/form-data):
            doc  — JSON part: {"aid": "...", "alias": "...", "oobi": "..."}
            kel  — binary part: raw CESR-encoded KEL bytes

        The uploading AID must match req.context.aid (ESSR-authenticated caller).
        Alias must be unique across castellan; returns 409 on conflict.

        Response (201): serialized UploadedIdentifier document.
        """
        form = req.get_media()

        doc = {}
        kel = None
        for part in form:
            if part.name == "doc":
                if part.content_type.startswith("application/json"):
                    json_data = part.get_media()
                    if isinstance(json_data, dict):
                        doc.update(json_data)
                    else:
                        raise falcon.HTTPBadRequest(
                            title="Bad Request",
                            description="The 'doc' part must be a JSON object.",
                        )
                else:
                    raise falcon.HTTPBadRequest(
                        title="Bad Request",
                        description="The 'doc' part must have content-type application/json.",
                    )
            elif part.name == "kel":
                kel = part.get_data()
            else:
                raise falcon.HTTPBadRequest(
                    title="Bad Request",
                    description=f"Unexpected form part '{part.name}'.",
                )

        aid = doc.get("aid", "").strip()
        alias = doc.get("alias", "").strip()
        oobi = doc.get("oobi", "").strip()

        if not aid:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'aid' is required."
            )
        if not alias:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'alias' is required."
            )
        if not kel:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'kel' part is required."
            )

        try:
            identifier = self.service.upload(
                aid=aid, alias=alias, kel=bytes(kel), oobi=oobi  # type: ignore
            )
        except ConflictError as e:
            raise falcon.HTTPConflict(
                title="Conflict",
                description=str(e),
            )
        except ValueError as e:
            raise falcon.HTTPBadRequest(
                title="Bad Request",
                description=str(e),
            )
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        resp.status = falcon.HTTP_201
        resp.content_type = "application/json"
        resp.media = _serialize(identifier)

    def on_get(self, req, resp):
        """
        List all identifiers uploaded to castellan.

        Response (200):
            {
              "count": N,
              "identifiers": [...]
            }
        """
        try:
            identifiers = self.service.list_all()
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        resp.status = falcon.HTTP_200
        resp.content_type = "application/json"
        resp.media = {
            "count": len(identifiers),
            "identifiers": [_serialize(i) for i in identifiers],
        }


class IdentifierKelEnd:
    """Handles GET /identifiers/{aid}/kel — returns CESR KEL stream as base64 JSON."""

    def __init__(self, identifierSvc):
        self.service = identifierSvc

    def on_get(self, req, resp, aid):
        """
        Return the CESR-encoded KEL for an uploaded identifier.

        Response (200):
            {"kel": "<base64-encoded CESR bytes>"}

        Response (404): if AID is not a known uploaded identifier.
        Response (200) with {"kel": ""}: if identifier exists but KEL not yet captured.
        """
        try:
            kel_bytes = self.service.get_kel_stream(aid)
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        resp.status = falcon.HTTP_200
        resp.content_type = "application/json"
        resp.media = {"kel": base64.b64encode(kel_bytes).decode("ascii")}


class IdentifierResourceEnd:
    """Handles DELETE /identifiers/{aid}."""

    def __init__(self, identifier_svc, key_event_log_service):
        self.service = identifier_svc
        self.key_event_log_service = key_event_log_service

    def on_get(self, req, resp, aid):
        """Identifier get endpoint

        Parameters:
            req (Request): Falcon HTTP request object
            resp (Response): Falcon HTTP response object
            aid (str): The aid of the Identifier requested
        """
        kel = req.get_param_as_bool("kel", default=False)

        try:
            identifier = self.service.get_identifier_with_key_state(aid)

            ims = None
            if kel:
                ims = self.key_event_log_service.get_kel_stream(aid)
                ims.extend(self.key_event_log_service.get_rpy_stream(aid))

        except ConflictError as e:
            raise falcon.HTTPConflict(
                title="Conflict", description=f"A conflict error occurred: {e}"
            )
        except NotFoundError as e:
            raise falcon.HTTPNotFound(
                title="Not Found", description=f"Identifier not found with error: {e}"
            )
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        if ims is not None:
            multipart_data = MultipartEncoder(
                fields={
                    "doc": ("doc", json.dumps(identifier), "application/json"),
                    "cesr": ("cesr", ims.decode("utf-8"), "application/cesr"),
                }
            )

            resp.status = falcon.HTTP_201
            resp.content_type = multipart_data.content_type
            resp.data = multipart_data.to_string()

        else:
            resp.status = falcon.HTTP_200
            resp.content_type = "application/json"
            resp.media = identifier

    def on_delete(self, req, resp, aid):
        """Delete an uploaded identifier by AID."""
        try:
            self.service.delete(aid)
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        resp.status = falcon.HTTP_204
