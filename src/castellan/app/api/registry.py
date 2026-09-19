# -*- encoding: utf-8 -*-
"""
castellan.app.api.registry module

REST endpoint handlers for credential registries:

  GET    /registries              — list all registries with pagination/filter
  POST   /registries              — create a new registry
  GET    /registries/{registry_pre} — get a single registry
  POST   /registries/{registry_pre} — update a registry
  DELETE /registries/{registry_pre} — delete a registry
"""

import falcon
from keri.help import ogler

from castellan.core.services.custom.custom_errors import ConflictError, NotFoundError

logger = ogler.getLogger()


def _serialize(registry) -> dict:
    """Serialize a Registry document to a dictionary."""
    return {
        "registry_pre": registry.registry_pre,
        "registry_said": registry.registry_said,
        "registry_name": registry.registry_name,
        "issuer_aid": registry.issuer_aid,
        "created_at": registry.created_at.isoformat() if registry.created_at else None,
    }


class RegistryCollectionEnd:
    """Handles GET /registries and POST /registries."""

    def __init__(self, registry_svc):
        self.service = registry_svc

    def on_get(self, req, resp):
        """
        List registries with pagination, filtering, and sorting.

        Query params:
            page       - zero-indexed page (default 0)
            page_size  - results per page (default 20)
            filter     - free-text search against registry_name/registry_pre/registry_said
            order      - sort field(s), e.g. -created_at (repeatable)
            issuer_aid - filter by issuer AID (optional)

        Response (200):
            {
              "count": N,
              "page": page,
              "num_pages": num_pages,
              "registries": [...]
            }
        """
        page = req.get_param_as_int("page", default=0)
        page_size = req.get_param_as_int("page_size", default=20)
        filter_term = req.get_param("filter", default=None)
        order = req.get_param_as_list("order", default=None)
        issuer_aid = req.get_param("issuer_aid", default=None)

        try:
            registries, total, num_pages = self.service.list_registries(
                page=page,
                page_size=page_size,
                filter_term=filter_term,
                order=order,
                issuer_aid=issuer_aid,
            )
            serialized = [_serialize(r) for r in registries]
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
            "registries": serialized,
        }

    def on_post(self, req, resp):
        """
        Create a new registry.

        Request body (application/json):
            {
              "registry_pre": "...",
              "registry_said": "...",
              "registry_name": "...",
              "issuer_aid": "..."
            }

        Response (201): serialized Registry document.
        Response (400): if required fields are missing.
        Response (409): if registry with same pre or said already exists.
        """
        body = req.media or {}

        registry_pre = (
            body.get("registry_pre", "").strip() if body.get("registry_pre") else ""
        )
        registry_said = (
            body.get("registry_said", "").strip() if body.get("registry_said") else ""
        )
        registry_name = (
            body.get("registry_name", "").strip() if body.get("registry_name") else ""
        )
        issuer_aid = (
            body.get("issuer_aid", "").strip() if body.get("issuer_aid") else ""
        )

        if not registry_pre:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'registry_pre' is required."
            )
        if not registry_said:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'registry_said' is required."
            )
        if not registry_name:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'registry_name' is required."
            )
        if not issuer_aid:
            raise falcon.HTTPBadRequest(
                title="Bad Request", description="'issuer_aid' is required."
            )

        try:
            registry = self.service.create_registry(
                registry_pre=registry_pre,
                registry_said=registry_said,
                registry_name=registry_name,
                issuer_aid=issuer_aid,
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
        resp.media = _serialize(registry)


class RegistryResourceEnd:
    """Handles GET, POST, DELETE /registries/{registry_pre}."""

    def __init__(self, registry_svc):
        self.service = registry_svc

    def on_get(self, req, resp, registry_pre):
        """
        Get a single registry by its prefix.

        Response (200): serialized Registry document.
        Response (404): if registry not found.
        """
        try:
            registry = self.service.get_registry(registry_pre)
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        resp.status = falcon.HTTP_200
        resp.content_type = "application/json"
        resp.media = _serialize(registry)

    def on_post(self, req, resp, registry_pre):
        """
        Update a registry.

        Request body (application/json):
            {
              "registry_name": "Updated Name"
            }

        Note: registry_pre, registry_said, and issuer_aid cannot be updated.

        Response (200): updated Registry document.
        Response (400): if attempting to update immutable fields or invalid data.
        Response (404): if registry not found.
        """
        body = req.media or {}

        try:
            registry = self.service.update_registry(registry_pre, body)
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
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
        resp.media = _serialize(registry)

    def on_delete(self, req, resp, registry_pre):
        """
        Delete a registry.

        Response (204): no content.
        Response (404): if registry not found.
        """
        try:
            self.service.delete_registry(registry_pre)
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

        resp.status = falcon.HTTP_204
