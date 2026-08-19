# -*- encoding: utf-8 -*-
"""
castellan.app.api.received_credential module

REST endpoint handlers for /received-credentials.
"""
import falcon
from keri.help import ogler

from castellan.core.services.custom.custom_errors import (
    ConflictError, NotFoundError, ValidationError
)

logger = ogler.getLogger()


def _serialize(cred):
    return {
        "said": cred.said,
        "sad": cred.sad,
        "issuer": cred.issuer,
        "schema": cred.schema,
        "holder": cred.holder,
        "status": cred.status,
        "created_at": cred.created_at.isoformat() if cred.created_at else None,
        "updated_at": cred.updated_at.isoformat() if cred.updated_at else None,
    }


class ReceivedCredentialCollectionEnd:
    """Handles GET /received-credentials and POST /received-credentials."""

    def __init__(self, receivedCredentialSvc):
        self.service = receivedCredentialSvc

    def on_get(self, req, resp):
        """List received credentials with optional filtering and pagination.

        Query params:
            filter    - free-text search across all fields and sad dict values
            issuer    - exact match on issuer AID
            holder    - exact match on holder AID
            status    - exact match on status string
            page      - zero-indexed page (default 0)
            page_size - results per page (default 20)
            order     - sort field(s), e.g. +created_at or -said (repeatable)
        """
        filter_term = req.get_param("filter", default=None)
        issuer = req.get_param("issuer", default=None)
        holder = req.get_param("holder", default=None)
        status = req.get_param("status", default=None)
        page = req.get_param_as_int("page", default=0)
        page_size = req.get_param_as_int("page_size", default=20)
        order = req.get_param_as_list("order", default=None)

        try:
            credentials, total, num_pages = self.service.list_credentials(
                filter=filter_term,
                issuer=issuer,
                holder=holder,
                status=status,
                page=page,
                page_size=page_size,
                order=order,
            )

            resp.status = falcon.HTTP_200
            resp.content_type = "application/json"
            resp.media = {
                "count": total,
                "page": page,
                "num_pages": num_pages,
                "credentials": [_serialize(c) for c in credentials],
            }

        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

    def on_post(self, req, resp):
        """Upload a received credential.

        Expects multipart/form-data with:
            doc  - application/json: { said, issuer, holder, schema }
            acdc - raw ACDC bytes
        """
        try:
            form = req.get_media()
            doc = {}
            acdc = None

            for part in form:
                if part.name == "doc":
                    if part.content_type.startswith("application/json"):
                        json_data = part.get_media()
                        if isinstance(json_data, dict):
                            doc.update(json_data)
                        else:
                            raise falcon.HTTPBadRequest(
                                title="Invalid JSON",
                                description="The doc part must be a valid JSON object.",
                            )
                elif part.name == "acdc":
                    acdc = part.get_data()
                else:
                    raise falcon.HTTPBadRequest(
                        title="Bad Request",
                        description=f"Unexpected form part: {part.name}",
                    )

            if not acdc:
                raise falcon.HTTPBadRequest(
                    title="Bad Request",
                    description='Missing required form field: "acdc"',
                )

            for field in ("said", "holder", "schema"):
                if field not in doc:
                    raise falcon.HTTPBadRequest(
                        title="Bad Request",
                        description=f'Missing required field in doc: "{field}"',
                    )

            credential = self.service.save_credential(doc, acdc)

            resp.status = falcon.HTTP_201
            resp.content_type = "application/json"
            resp.media = _serialize(credential)

        except (falcon.HTTPBadRequest, falcon.HTTPConflict, falcon.HTTPNotFound):
            raise
        except ConflictError as e:
            raise falcon.HTTPConflict(title="Conflict", description=str(e))
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except ValidationError as e:
            raise falcon.HTTPBadRequest(title="Invalid Request", description=str(e))
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )


class ReceivedCredentialResourceEnd:
    """Handles GET/PUT/DELETE /received-credentials/{said}."""

    def __init__(self, receivedCredentialSvc):
        self.service = receivedCredentialSvc

    def on_get(self, req, resp, said):
        """Retrieve a single received credential.

        Query params:
            stream - if true, return raw ACDC bytes (application/cesr+json)
        """
        stream = req.get_param_as_bool("stream", default=False)

        try:
            if stream:
                ims = self.service.get_credential_stream(said)
                resp.status = falcon.HTTP_200
                resp.content_type = "application/cesr+json"
                resp.data = bytes(ims)
            else:
                credential = self.service.get_credential(said)
                resp.status = falcon.HTTP_200
                resp.content_type = "application/json"
                resp.media = _serialize(credential)

        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

    def on_put(self, req, resp, said):
        """Update a received credential.

        Request body (JSON): { status?, holder? }
        """
        try:
            body = req.media
            if not body:
                raise falcon.HTTPBadRequest(
                    title="Bad Request",
                    description="Request body is required.",
                )

            credential = self.service.update_credential(said, body)

            resp.status = falcon.HTTP_200
            resp.content_type = "application/json"
            resp.media = _serialize(credential)

        except falcon.HTTPBadRequest:
            raise
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

    def on_delete(self, req, resp, said):
        """Delete a received credential."""
        try:
            self.service.delete_credential(said)
            resp.status = falcon.HTTP_204
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )