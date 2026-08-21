# -*- encoding: utf-8 -*-
"""
castellan.app.api.json_schema module

REST endpoint handlers for /schemas - JSON Schema document management.
"""

import falcon
from keri.help import ogler

from castellan.core.services.custom.custom_errors import NotFoundError, ValidationError

logger = ogler.getLogger()


def _serialize(schema):
    """Serialize a Schema document to JSON-compatible dict."""
    return {
        "said": schema.said,
        "schema": schema.sed,  # The actual schema dict
        "created_at": schema.created_at.isoformat() if schema.created_at else None,
    }


class JsonSchemaCollectionEnd:
    """Handles GET /schemas and POST /schemas."""

    def __init__(self, schemaSvc):
        self.service = schemaSvc

    def on_get(self, req, resp):
        """List all schemas with pagination.

        Query params:
            page        - zero-indexed page (default 0)
            page_size   - results per page (default 20)
            order       - sort field(s), e.g. +created_at or -said (repeatable)
        """
        page = req.get_param_as_int("page", default=0)
        page_size = req.get_param_as_int("page_size", default=20)
        order = req.get_param_as_list("order", default=None)

        try:
            schemas, total, num_pages = self.service.list_schemas(
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
                "schemas": [_serialize(s) for s in schemas],
            }

        except Exception as e:
            logger.error(f"GET /schemas failed: {e}", exc_info=True)
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

    def on_post(self, req, resp):
        """Upload a JSON Schema document.

        Expects multipart/form-data with:
            schema - application/json: the JSON Schema document

        The schema must have a valid $id field. SAID is derived from the schema.
        """
        try:
            form = req.get_media()
            schema_dict = None

            for part in form:
                if part.name == "schema":
                    if part.content_type and part.content_type.startswith(
                        "application/json"
                    ):
                        schema_dict = part.get_media()
                    else:
                        raise falcon.HTTPBadRequest(
                            title="Bad Request",
                            description="'schema' part must have content-type application/json",
                        )
                else:
                    raise falcon.HTTPBadRequest(
                        title="Bad Request",
                        description=f"Unexpected form part: {part.name}. Expected 'schema'.",
                    )

            if schema_dict is None:
                raise falcon.HTTPBadRequest(
                    title="Bad Request",
                    description="Missing required 'schema' part in multipart form.",
                )

            if not isinstance(schema_dict, dict):
                raise falcon.HTTPBadRequest(
                    title="Bad Request",
                    description="Schema must be a JSON object.",
                )

            # Validate that schema has $id field
            if "$id" not in schema_dict:
                raise ValidationError("Schema must have a '$id' field")

            schema = self.service.save_schema(schema_dict)

            logger.info(f"Uploaded schema: {schema.said}")
            resp.status = falcon.HTTP_201
            resp.media = _serialize(schema)

        except (falcon.HTTPBadRequest, falcon.HTTPConflict):
            raise
        except ValidationError as e:
            raise falcon.HTTPBadRequest(
                title="Validation Error",
                description=str(e),
            )
        except Exception as e:
            logger.error(f"POST /schemas failed: {e}", exc_info=True)
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )


class JsonSchemaResourceEnd:
    """Handles GET /schemas/{said} and DELETE /schemas/{said}."""

    def __init__(self, schemaSvc):
        self.service = schemaSvc

    def on_get(self, req, resp, said):
        """Retrieve a single JSON Schema by SAID.

        Path params:
            said - The schema SAID (Self-Addressing Identifier)

        Query params:
            stream - if true, return raw schema bytes (application/schema+json)
        """
        stream = req.get_param_as_bool("stream", default=False)

        try:
            schema = self.service.get_schema(said)

            if stream:
                # Return raw schema bytes
                resp.status = falcon.HTTP_200
                resp.content_type = "application/schema+json"
                resp.data = bytes(schema.raw)
            else:
                # Return JSON-serialized response
                resp.status = falcon.HTTP_200
                resp.media = _serialize(schema)

        except NotFoundError as e:
            raise falcon.HTTPNotFound(
                title="Not Found",
                description=str(e),
            )
        except Exception as e:
            logger.error(f"GET /schemas/{said} failed: {e}", exc_info=True)
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

    def on_delete(self, req, resp, said):
        """Delete a JSON Schema by SAID.

        Path params:
            said - The schema SAID (Self-Addressing Identifier)
        """
        try:
            self.service.delete_schema(said)

            logger.info(f"Deleted schema: {said}")
            resp.status = falcon.HTTP_204  # No content

        except NotFoundError as e:
            raise falcon.HTTPNotFound(
                title="Not Found",
                description=str(e),
            )
        except Exception as e:
            logger.error(f"DELETE /schemas/{said} failed: {e}", exc_info=True)
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )
