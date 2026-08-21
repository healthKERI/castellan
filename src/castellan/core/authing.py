# -*- encoding: utf-8 -*-
"""
KERI
hksvc.core.authing package

"""

from urllib.parse import quote

import falcon
from keri.help import ogler

from castellan.core.services.account_service import AccountService

logger = ogler.getLogger()


class Authenticater:
    DefaultFields = ["Signify-Resource", "@method", "@path", "Signify-Timestamp"]

    SigningFields = ["Signify-Resource", "Signify-Timestamp"]

    def __init__(self, hab, accountSvc: AccountService, account_aid=None):
        self.hab = hab
        self.accountSvc = accountSvc
        self.account_aid = account_aid

    @staticmethod
    def resource(request):
        headers = request.headers
        if "SIGNIFY-RESOURCE" not in headers:
            raise falcon.HTTPBadRequest(
                title="Missing Header",
                description="The 'SIGNIFY-RESOURCE' header is required.",
            )
        return headers["SIGNIFY-RESOURCE"]

    def signer(self, request):
        if self.account_aid:
            return self.account_aid

        headers = request.headers
        if "ESSR-SENDER" not in headers:
            return None

        return headers["ESSR-SENDER"]


class SignatureValidationComponent:
    """Validate Signature and Signature-Input header signatures"""

    def __init__(self, accountSvc, hab, parser, auth: Authenticater, allowed=None):
        self.accountSvc = accountSvc
        self.hab = hab
        self.resource = self.hab.pre
        self.parser = parser
        self.authn = auth
        self.allowed = allowed if allowed is not None else []

    def process_request(self, req, rep):
        """Process request to ensure has a valid signature from aid

        Parameters:
            req: Http request object
            rep: Http response object
        """
        if req.path.startswith("/static"):
            return

        for path in self.allowed:
            if req.path == path:
                return

        req.path = quote(req.path)
        if (signer := self.authn.signer(req)) is not None:
            if (account := self.accountSvc.get_account(signer)) is not None:
                req.context.account = account
                return

        rep.complete = (
            True  # This short-circuits Falcon, skipping all further processing
        )
        rep.status = falcon.HTTP_401
        return
