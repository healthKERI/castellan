# -*- encoding: utf-8 -*-
"""
castellan.app.api.schema_field_tracking module

REST endpoint handlers for /schemas/{said}/fields.
"""

import falcon
from keri.help import ogler

from castellan.core.services.custom.custom_errors import NotFoundError

logger = ogler.getLogger()


def _serialize_field(field):
    """Serialize a TrackedField to dict."""
    return {"type": field.type, "label": field.label}


class SchemaFieldTrackingEnd:
    """Handles GET /schemas/{said}/fields and DELETE /schemas/{said}/fields."""

    def __init__(self, trackingSvc):
        self.service = trackingSvc

    def on_get(self, req, resp, said):
        """Get all tracked field type/label pairs for a schema.

        Path params:
            said - Schema SAID

        Returns:
            200: {"schema_said": str, "fields": [{type, label}, ...]}
            (empty list if no fields tracked)
        """
        try:
            fields = self.service.get_tracked_fields(said)

            resp.status = falcon.HTTP_200
            resp.content_type = "application/json"
            resp.media = {
                "schema_said": said,
                "fields": [_serialize_field(f) for f in fields],
            }

        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )

    def on_delete(self, req, resp, said):
        """Delete a specific field type/label pair from tracking.

        Path params:
            said - Schema SAID

        Query params:
            type  - Field type (required)
            label - Field label (required)

        Returns:
            204: No content (success)
            400: Missing required parameters
            404: Schema tracking or field not found
        """
        try:
            field_type = req.get_param("type")
            field_label = req.get_param("label")

            if not field_type or not field_label:
                raise falcon.HTTPBadRequest(
                    title="Bad Request",
                    description="Query parameters 'type' and 'label' are required",
                )

            self.service.delete_tracked_field(said, field_type, field_label)

            resp.status = falcon.HTTP_204

        except falcon.HTTPBadRequest:
            raise
        except NotFoundError as e:
            raise falcon.HTTPNotFound(title="Not Found", description=str(e))
        except Exception as e:
            raise falcon.HTTPInternalServerError(
                title="Internal Server Error",
                description=f"An unexpected error occurred: {e}",
            )
