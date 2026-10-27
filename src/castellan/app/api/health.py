# -*- encoding: utf-8 -*-
"""
castellan.app.api.health module

Health/liveness/readiness endpoints for the castellan credential server.
"""

import falcon


class HealthEnd:
    """Simple liveness/readiness health check endpoint."""

    async def on_get(self, req, rep):
        """
        GET /health

        Returns 200 with a small JSON payload indicating the service is up.
        """
        rep.status = falcon.HTTP_200
        rep.media = {"status": "ok"}
