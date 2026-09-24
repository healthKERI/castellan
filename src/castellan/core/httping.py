# -*- encoding: utf-8 -*-

"""
KERI
kourier.core.httping package

"""

import falcon
from keri import kering
from keri.app import httping
from keri.app.httping import CESR_DESTINATION_HEADER
from keri.core import coring
from keri.core.parsing import Parser
from keri.help import ogler
from keri.kering import Ilks

from castellan.core.services import IdentifierService, MessageService
from castellan.core.services.custom.custom_errors import NotFoundError

logger = ogler.getLogger()


def load_ends(app, identifier_service: IdentifierService, parser: Parser):
    http = HttpEnd(identifier_service=identifier_service, parser=parser)
    app.add_route("/", http)


class HttpEnd:
    """
    HTTP handler that accepts and KERI events POSTed as the body of a request with all attachments to
    the message as a CESR attachment HTTP header.  KEL Messages are processed and added to the database
    of the provided Habitat.

    This also handles `req`, `exn` and `tel` messages that respond with a KEL replay.
    """

    def __init__(self, identifier_service: IdentifierService, parser: Parser):
        """
        Create the KEL HTTP server from the Habitat with an optional Falcon App to
        register the routes with.

        Parameters
        ----------
        identifier_service: IdentifierService
            The identifier service to use for looking up identifiers
        parser: Parser
            The parser to use for parsing KERI messages
        """
        self.identifier_service = identifier_service
        self.parser = parser

    def on_post(self, req, rep):
        """
        Handles POST for KERI event messages.

        Parameters:
              req (Request) Falcon HTTP request
              rep (Response) Falcon HTTP response

        ---
        summary:  Accept KERI events with attachment headers and parse
        description:  Accept KERI events with attachment headers and parse.
        tags:
           - Events
        requestBody:
           required: true
           content:
             application/json:
               schema:
                 type: object
                 description: KERI event message
        responses:
           200:
              description: Mailbox query response for server sent events
           204:
              description: KEL or EXN event accepted.
        """
        if req.method == "OPTIONS":
            rep.status = falcon.HTTP_200
            return

        if CESR_DESTINATION_HEADER not in req.headers:
            raise falcon.HTTPBadRequest(title="CESR request destination header missing")

        aid = req.headers[CESR_DESTINATION_HEADER]
        try:
            self.identifier_service.get(aid)
        except NotFoundError:
            raise falcon.HTTPNotFound(title=f"unknown destination AID {aid}")

        rep.set_header('Cache-Control', "no-cache")
        rep.set_header('connection', "close")

        cr = httping.parseCesrHttpRequest(req=req)
        sadder = coring.Sadder(ked=cr.payload, kind=kering.Kinds.json)
        msg = bytearray(sadder.raw)
        msg.extend(cr.attachments.encode("utf-8"))

        self.parser.parseOne(ims=msg, local=True)

        if sadder.proto in ("ACDC",):
            rep.set_header('Content-Type', "application/json")
            rep.status = falcon.HTTP_204
        else:
            ilk = sadder.ked["t"]
            if ilk in (Ilks.icp, Ilks.rot, Ilks.ixn, Ilks.dip, Ilks.drt, Ilks.exn, Ilks.rpy):
                rep.set_header('Content-Type', "application/json")
                rep.status = falcon.HTTP_204
            elif ilk in (Ilks.vcp, Ilks.vrt, Ilks.iss, Ilks.rev, Ilks.bis, Ilks.brv):
                rep.set_header('Content-Type', "application/json")
                rep.status = falcon.HTTP_204
            else:
                rep.set_header('Content-Type', "application/json")
                rep.status = falcon.HTTP_204

    def on_put(self, req, rep):
        """
        Handles PUT for KERI mbx event messages.

        Parameters:
              req (Request) Falcon HTTP request
              rep (Response) Falcon HTTP response

        ---
        summary:  Accept KERI events with attachment headers and parse
        description:  Accept KERI events with attachment headers and parse.
        tags:
           - Events
        requestBody:
           required: true
           content:
             application/json:
               schema:
                 type: object
                 description: KERI event message
        responses:
           200:
              description: Mailbox query response for server sent events
           204:
              description: KEL or EXN event accepted.
        """
        if req.method == "OPTIONS":
            rep.status = falcon.HTTP_200
            return

        rep.set_header('Cache-Control', "no-cache")
        rep.set_header('connection', "close")

        if CESR_DESTINATION_HEADER not in req.headers:
            raise falcon.HTTPBadRequest(title="CESR request destination header missing")

        aid = req.headers[CESR_DESTINATION_HEADER]
        try:
            self.identifier_service.get(aid)
        except NotFoundError:
            raise falcon.HTTPNotFound(title=f"unknown destination AID {aid}")

        self.parser.parse(ims=req.bounded_stream.read(), local=True)

        rep.set_header('Content-Type', "application/json")
        rep.status = falcon.HTTP_204


class ForwardHandler:
    """
    Handler for forward `exn` messages used to envelope other KERI messages intended for another recipient.
    This handler acts as a mailbox for other identifiers and stores the messages in a local database.

    on
        {
           "v": "KERI10JSON00011c_",                               // KERI Version String
           "t": "exn",                                             // peer to peer message ilk
           "dt": "2020-08-22T17:50:12.988921+00:00"
           "r": "/fwd",
           "q": {
              "pre": "EEBp64Aw2rsjdJpAR0e2qCq3jX7q7gLld3LjAwZgaLXU",
              "topic": "delegate"
            }
           "a": '{
              "v":"KERI10JSON000154_",
              "t":"dip",
              "d":"Er4bHXd4piEtsQat1mquwsNZXItvuoj_auCUyICmwyXI",
              "i":"Er4bHXd4piEtsQat1mquwsNZXItvuoj_auCUyICmwyXI",
              "s":"0",
              "kt":"1",
              "k":["DuK1x8ydpucu3480Jpd1XBfjnCwb3dZ3x5b1CJmuUphA"],
              "n":"EWWkjZkZDXF74O2bOQ4H5hu4nXDlKg2m4CBEBkUxibiU",
              "bt":"0",
              "b":[],
              "c":[],
              "a":[],
              "di":"Et78eYkh8A3H9w6Q87EC5OcijiVEJT8KyNtEGdpPVWV8"
           }
        }-AABAA1o61PgMhwhi89FES_vwYeSbbWnVuELV_jv7Yv6f5zNiOLnj1ZZa4MW2c6Z_vZDt55QUnLaiaikE-d_ApsFEgCA

    """

    resource = "/fwd"

    def __init__(self, hby, message_service: MessageService, identifier_service: IdentifierService):
        """

        Parameters:
            hby (Habery): database environment
            message_service (MessageService): message storage for store and forward
            identifier_service (IdentifierService): identifier service

        """
        self.hby = hby
        self.message_service = message_service
        self.identifier_service = identifier_service

    def handle(self, serder, attachments=None):
        """  Do route specific processsing of IPEX protocol exn messages

        Parameters:
            serder (Serder): Serder of the IPEX protocol exn message
            attachments (list): list of tuples of root pathers and CESR SAD path attachments to the exn event

        """

        sender_aid = serder.ked.get('i', '')
        embeds = serder.ked['e']
        modifiers = serder.ked['q'] if 'q' in serder.ked else {}

        recipient_aid = modifiers["pre"]
        try:
            multisig = self.identifier_service.get(recipient_aid)
        except NotFoundError:
            logger.error(title=f"unknown destination AID {recipient_aid}")
            return

        if multisig.mailbox is False:
            logger.error(title=f"destination AID {recipient_aid} has not registered this service as a mailbox")
            return

        topic = modifiers["topic"]

        pevt = bytearray()
        for pather, atc in attachments:
            ked = pather.resolve(embeds)
            sadder = coring.Sadder(ked=ked, kind=kering.Kinds.json)
            pevt.extend(sadder.raw)
            pevt.extend(atc)

        if not pevt:
            print("error with message, nothing to forward", serder.ked)
            return

        try:
            self.message_service.post_message(
                recipient_aid=recipient_aid,
                sender_aid=sender_aid,
                topic=topic,
                raw=pevt,
                multisig_alias=multisig.alias,
            )
        except Exception as e:
            logger.error(
                f"POST /messages 500: service.post_message raised {type(e).__name__}: {e}",
                exc_info=True,
            )


