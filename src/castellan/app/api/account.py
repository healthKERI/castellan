# -*- encoding: utf-8 -*-
"""
castellan.app.api.account module

REST endpoint handlers for /account - Account management.
"""

import falcon
from keri.help import ogler

from castellan.core.services.custom.custom_errors import ConflictError, NotFoundError

logger = ogler.getLogger()


def _serialize(account):
    """Serialize an Account document to JSON-compatible dict."""
    return {
        "aid": account.aid,
        "username": account.username,
        "email": account.email if account.email else "",
        "first_name": account.first_name if account.first_name else "",
        "last_name": account.last_name if account.last_name else "",
        "role": account.role if account.role else "Owner",
        "key_state": account.key_state if account.key_state else None,
        "created_at": account.created_at.isoformat() if account.created_at else None,
    }


class AccountCollectionEnd:
    """Handles GET /account."""

    def __init__(self, account_service):
        self.service = account_service

    def on_get(self, req, resp):
        """List all accounts.

        Returns:
            200: {"accounts": [Account objects...]}
        """
        try:
            filter_term = req.get_param("filter", default=None)
            role = req.get_param("role", default=None)
            page = req.get_param_as_int("page", default=0)
            page_size = req.get_param_as_int("page_size", default=20)
            order = req.get_param_as_list("order", default=None)

            accounts, total, num_pages = self.service.list_accounts(
                flter=filter_term,
                role=role,
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
                "accounts": [_serialize(a) for a in accounts],
            }

        except Exception as e:
            logger.error(f"GET /account failed: {e}", exc_info=True)
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

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
            if part.name == "data":
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
        username = doc.get("username", "").strip()

        if not aid:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'aid' is required."
            )
        if not username:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'alias' is required."
            )
        if not kel:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'kel' part is required."
            )

        try:
            identifier = self.service.create_account(
                doc=doc, kel=bytes(kel)  # type: ignore
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


class AccountResourceEnd:
    """Handles POST /accounts/{aid} and DELETE /accounts/{aid}."""

    def __init__(self, service):
        self.service = service

    def on_get(self, req, resp, aid):
        """Get an account.

        Path params:
            aid - Account AID to update
        """
        try:
            account = self.service.get_account(aid)
            if account is None:
                raise NotFoundError(f"Account not found: {aid}")

            resp.status = falcon.HTTP_200
            resp.content_type = "application/json"
            resp.media = _serialize(account)

        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except Exception as e:
            logger.error(f"GET /accounts/{aid} failed: {e}", exc_info=True)
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

    def on_post(self, req, resp, aid):
        """Update an account.

        Path params:
            aid - Account AID to update

        Request body (JSON): {
            username?,
            email?,
            first_name?,
            last_name?,
            role?,
            ... other updatable fields
        }

        Note: 'aid' and 'kel' fields are ignored if present in the request.

        Returns:
            200: Updated account
            404: Account not found
            400: Validation error
        """
        try:
            body = req.media
            if not body:
                raise falcon.HTTPBadRequest(
                    title="Bad Request",
                    description="Request body is required.",
                )

            # Filter out aid and kel - these should not be updated via this endpoint
            update_data = {k: v for k, v in body.items() if k not in ("aid", "kel")}

            if not update_data:
                raise falcon.HTTPBadRequest(
                    title="Bad Request",
                    description="No updatable fields provided in request body.",
                )

            logger.info(f"Updating account with aid: {aid}")
            account = self.service.update_account(aid, update_data)

            if account is None:
                # update_account returns None if no changes were made
                # Fetch and return the current account
                account = self.service.get_account(aid)
                if account is None:
                    raise NotFoundError(f"Account not found: {aid}")

            resp.status = falcon.HTTP_200
            resp.content_type = "application/json"
            resp.media = _serialize(account)

        except falcon.HTTPBadRequest:
            raise
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except ValueError as e:
            raise falcon.HTTPBadRequest(title="Bad Request", description=str(e))
        except Exception as e:
            logger.error(f"POST /accounts/{aid} failed: {e}", exc_info=True)
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

    def on_delete(self, req, resp, aid):
        """Delete an account."""
        try:
            self.service.delete_account(aid)
            resp.status = falcon.HTTP_204
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )
