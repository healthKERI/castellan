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
from castellan.core.services.identifier_service import MultisigIdentifier

logger = ogler.getLogger()


def _serialize(identifier) -> dict:
    if isinstance(identifier, MultisigIdentifier):
        return _serialize_multisig(identifier)
    return _serialize_identifier(identifier)


def _serialize_identifier(identifier) -> dict:
    data = {
        "id": str(identifier.id),
        "aid": identifier.aid,
        "alias": identifier.alias,
        "oobi": identifier.oobi or "",
        "created_at": (
            identifier.created_at.isoformat() if identifier.created_at else None
        ),
    }
    return data


def _serialize_multisig(identifier) -> dict:
    """Serialize a MultisigIdentifier with its multisig-specific fields."""
    data = _serialize_identifier(identifier)
    data["members"] = (
        [_serialize_member(member) for member in identifier.members]
        if hasattr(identifier, "members")
        else []
    )
    data["signing_threshold"] = (
        identifier.signing_threshold
        if hasattr(identifier, "signing_threshold")
        else None
    )
    data["rotation_threshold"] = (
        identifier.rotation_threshold
        if hasattr(identifier, "rotation_threshold")
        else None
    )
    data["key_state"] = identifier.key_state if hasattr(identifier, "key_state") else {}
    data["current_event"] = (
        identifier.current_event if hasattr(identifier, "current_event") else {}
    )
    data["vcp"] = identifier.vcp if hasattr(identifier, "vcp") else {}

    return data


def _serialize_member(member):
    data = {
        "account_username": member.account_username,
        "account_aid": member.account_aid,
        "member_aid": member.member_aid,
        "signing_threshold": member.signing_threshold,
        "rotation_threshold": member.rotation_threshold,
        "public_key": member.public_key if hasattr(member, "public_key") else None,
    }

    return data


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
        List identifiers uploaded to castellan, with pagination/filter/sort.

        Query params:
            page              - zero-indexed page (default 0)
            page_size         - results per page (default 20)
            filter            - free-text search against alias/aid
            order             - sort field(s), e.g. -created_at or alias (repeatable)
            include_key_state - if true, includes each identifier's current
                                 remote key state (default false). Opt-in and
                                 bounded to page_size because computing it can
                                 trigger a full KEL re-verify per identifier
                                 when the in-memory kever is stale — callers
                                 that need the full unpaginated set (e.g. peer
                                 discovery polling) should leave this off.

        Response (200):
            {
              "count": N,
              "page": page,
              "num_pages": num_pages,
              "identifiers": [...]
            }
        """
        page = req.get_param_as_int("page", default=0)
        page_size = req.get_param_as_int("page_size", default=20)
        filter_term = req.get_param("filter", default=None)
        order = req.get_param_as_list("order", default=None)

        try:
            identifiers, total, num_pages = self.service.list_identifiers(
                page=page,
                page_size=page_size,
                filter_term=filter_term,
                order=order,
            )
            serialized = [_serialize(i) for i in identifiers]
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
            "identifiers": serialized,
        }


class MultisigIdentifierCollectionEnd:
    """Handles POST /multisig/identifiers and GET /multisig/identifiers."""

    def __init__(self, identifier_service):
        self.identifier_service = identifier_service

    def on_post(self, req, resp):
        """
        Upload a multisig identifier to castellan.

        Request body (application/json):
            doc  — JSON part: {"alias": "...", "members": [...], "threshold": N}
            kel  — binary part: raw CESR-encoded KEL bytes

        Response (201): serialized MultisigIdentifier document.
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

        alias = doc.get("alias", "").strip()
        aid = doc.get("local_member_aid", "")
        members = doc.get("members", [])
        signing_threshold = doc.get("signing_threshold")
        rotation_threshold = doc.get("rotation_threshold")

        if not alias:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'alias' is required."
            )
        if not isinstance(members, list) or len(members) == 0:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'members' must be a non-empty list."
            )
        if signing_threshold is not None:
            if not isinstance(signing_threshold, int) or signing_threshold < 1:
                raise falcon.HTTPBadRequest(
                    title="Bad Request",
                    description="'signing threshold' must be a positive integer if provided.",
                )

        if rotation_threshold is not None:
            if not isinstance(rotation_threshold, int) or rotation_threshold < 1:
                raise falcon.HTTPBadRequest(
                    title="Bad Request",
                    description="'rotation threshold' must be a positive integer if provided.",
                )

        try:
            multisig_identifier = self.identifier_service.create_multisig_identifier(
                alias=alias,
                accounts=members,
                aid=aid,
                kel=kel,
                signing_threshold=signing_threshold,
                rotation_threshold=rotation_threshold,
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
        resp.media = _serialize_multisig(multisig_identifier)

    def on_get(self, req, resp):
        """
        List multisig identifiers uploaded to castellan, with pagination/filter/sort.

        Query params:
            page              - zero-indexed page (default 0)
            page_size         - results per page (default 20)
            filter            - free-text search against alias/aid
            order             - sort field(s), e.g. -created_at or alias (repeatable)
            include_key_state - if true, includes each identifier's current
                                 remote key state (default false)

        Response (200):
            {
              "count": N,
              "page": page,
              "num_pages": num_pages,
              "identifiers": [...]
            }
        """
        page = req.get_param_as_int("page", default=0)
        page_size = req.get_param_as_int("page_size", default=20)
        filter_term = req.get_param("filter", default=None)
        order = req.get_param_as_list("order", default=None)

        try:
            identifiers, total, num_pages = (
                self.identifier_service.list_multisig_identifiers(
                    page=page,
                    page_size=page_size,
                    filter_term=filter_term,
                    order=order,
                )
            )
            serialized = [_serialize_multisig(i) for i in identifiers]
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
            "identifiers": serialized,
        }


class MultisigIdentifierResourceEnd:
    """Handles PUT /multisig/identifiers/{id} — allows a member to join a multisig."""

    def __init__(self, identifierSvc):
        self.service = identifierSvc

    def on_put(self, req, resp, multisig_id):
        """
        Allow a member to join a multisig identifier by providing their member AID and KEL.

        Path parameters:
            id — The multisig identifier AID

        Request body (multipart/form-data):
            doc  — JSON part: {"member_aid": "..."}
            kel  — binary part: raw CESR-encoded KEL bytes

        The account_aid is derived from req.context.aid (authenticated caller).

        Response (200): updated MultisigIdentifier document.
        Response (401): if the account is not authorized to join this multisig.
        Response (404): if the multisig identifier is not found.
        """
        # Get the account_aid from the authenticated context
        # Following the pattern in the file comments about ESSR authentication
        account = getattr(req.context, "account", None)
        if not account:
            raise falcon.HTTPUnauthorized(
                title="Unauthorized",
                description="Authentication required. Account not found in request context.",
            )

        account_aid = account.aid

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

        member_aid = doc.get("member_aid", "").strip()

        if not member_aid:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'member_aid' is required."
            )
        if not kel:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'kel' part is required."
            )

        try:
            multisig = self.service.join_multisig(
                multisig_id=multisig_id,
                account_aid=account_aid,
                member_aid=member_aid,
                kel=bytes(kel),  # type: ignore
            )
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except PermissionError as e:
            import traceback

            logger.error(traceback.format_exc())
            raise falcon.HTTPUnauthorized(
                title="Unauthorized",
                description=str(e),
            )
        except ValueError as e:
            import traceback

            logger.error(traceback.format_exc())
            raise falcon.HTTPBadRequest(
                title="Bad Request",
                description=str(e),
            )
        except Exception as e:
            import traceback

            logger.error(traceback.format_exc())
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        resp.status = falcon.HTTP_200
        resp.content_type = "application/json"
        resp.media = _serialize_multisig(multisig)


class MultisigIdentifierSignatureCollectionEnd:
    """Handles POST /multisig/identifiers/{id}/signatures — record member signature submission."""

    def __init__(self, identifierSvc):
        self.service = identifierSvc

    def on_post(self, req, resp, multisig_id):
        """
        Record that a member has submitted their signature for a multisig identifier.

        Path parameters:
            id — The multisig identifier AID

        Request body (multipart/form-data):
            doc  — JSON part: additional metadata (optional)
            icp  — binary part: raw CESR-encoded ICP bytes

        The account_aid is derived from req.context.aid (authenticated caller).

        Response (200): updated MultisigIdentifier document with signature_received flag set.
        Response (401): if the account is not authorized to sign this multisig.
        Response (404): if the multisig identifier is not found.
        """
        # Get the account_aid from the authenticated context
        account = getattr(req.context, "account", None)
        if not account:
            raise falcon.HTTPUnauthorized(
                title="Unauthorized",
                description="Authentication required. Account AID not found in request context.",
            )
        account_aid = account.aid

        form = req.get_media()

        doc = {}
        icp = None
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
            elif part.name == "icp":
                icp = part.get_data()
            else:
                raise falcon.HTTPBadRequest(
                    title="Bad Request",
                    description=f"Unexpected form part '{part.name}'.",
                )

        if not icp:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'icp' part is required."
            )

        try:
            multisig = self.service.submit_multisig_inception(
                multisig_id=multisig_id,
                account_aid=account_aid,
                data=doc,
                icp=bytes(icp),  # type: ignore
            )
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except PermissionError as e:
            raise falcon.HTTPUnauthorized(
                title="Unauthorized",
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

        resp.status = falcon.HTTP_200
        resp.content_type = "application/json"
        resp.media = _serialize_multisig(multisig)


class MultisigIdentifierRegistryCollectionEnd:
    """Handles POST /multisig/identifiers/{multisig_id}/registry — create a credential registry."""

    def __init__(self, identifierSvc):
        self.service = identifierSvc

    def on_post(self, req, resp, multisig_id):
        """
        Create a credential registry for a multisig identifier.

        Path parameters:
            multisig_id — The multisig identifier ID

        Request body (multipart/form-data):
            vcp  — binary part: raw CESR-encoded registry inception event bytes
            ixn  — binary part: raw CESR-encoded interaction event bytes
            body — JSON part: additional metadata (optional)

        The account_aid is derived from req.context.account (authenticated caller).

        Response (201): updated MultisigIdentifier document with vcp and current_event.
        Response (400): if required parts are missing or parse failure.
        Response (401): if the account is not authorized (not in members list).
        Response (404): if the multisig identifier is not found.
        """
        # Get the account from the authenticated context
        account = getattr(req.context, "account", None)
        if not account:
            raise falcon.HTTPUnauthorized(
                title="Unauthorized",
                description="Authentication required. Account not found in request context.",
            )
        account_aid = account.aid

        form = req.get_media()

        body = {}
        vcp: bytes | None = None
        ixn: bytes | None = None
        for part in form:
            if part.name == "body":
                if part.content_type.startswith("application/json"):
                    json_data = part.get_media()
                    if isinstance(json_data, dict):
                        body.update(json_data)
                    else:
                        raise falcon.HTTPBadRequest(
                            title="Bad Request",
                            description="The 'body' part must be a JSON object.",
                        )
                else:
                    raise falcon.HTTPBadRequest(
                        title="Bad Request",
                        description="The 'body' part must have content-type application/json.",
                    )
            elif part.name == "vcp":
                vcp = part.get_data()
            elif part.name == "ixn":
                ixn = part.get_data()
            else:
                raise falcon.HTTPBadRequest(
                    title="Bad Request",
                    description=f"Unexpected form part '{part.name}'.",
                )

        if not vcp:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'vcp' part is required."
            )
        if not ixn:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'ixn' part is required."
            )

        try:
            multisig = self.service.create_registry(
                multisig_id=multisig_id,
                account_aid=account_aid,
                vcp=bytes(vcp),
                ixn=bytes(ixn),
                body=body,
            )
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except PermissionError as e:
            raise falcon.HTTPUnauthorized(
                title="Unauthorized",
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
        resp.media = _serialize_multisig(multisig)


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
