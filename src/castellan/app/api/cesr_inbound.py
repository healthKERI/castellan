# -*- encoding: utf-8 -*-

import falcon
from hio.base import doing
from hio.help import decking
from keri.app import forwarding
from keri.core import coring, parsing, serdering
from keri.help import helping, ogler
from keri.peer import exchanging
from keri.vc import protocoling

logger = ogler.getLogger()

class CastellanIpexGrantHandler:
    """
    Handles /ipex/grant EXN messages received at the castellan CESR endpoint.

    On receipt of a QVI grant:
      1. Verifies the grant is an /ipex/grant routed to castellan's own AID.
      2. Parses the embedded ACDC/iss/anc event streams.
      3. Saves the credential to ReceivedCredentialService.
      4. Enqueues an admit cue for QviAdmitDoer to process asynchronously.
    """
    resource = "/ipex/grant"

    def __init__(self, hby, hab, rgy, verifier, tvy, received_svc, admit_cues):
        self.hby = hby
        self.hab = hab
        self.rgy = rgy
        self.verifier = verifier
        self.tvy = tvy
        self.received_svc = received_svc
        self.admit_cues = admit_cues  # decking.Deck() shared with QviAdmitDoer

    def verify(self, serder, attachments=None):
        return True  # KEL validated by Exchanger before handle() is called

    def handle(self, serder, attachments=None):
        sender = serder.ked.get("i", "")
        embeds = serder.ked.get("e", {})
        acdc_ked = embeds.get("acdc")
        if acdc_ked is None:
            logger.warning("ipex/grant missing acdc embed, ignoring")
            return

        said = acdc_ked.get("d", "")
        logger.info(f"Received /ipex/grant for credential said={said} from {sender}")

        # Parse embedded events so verifier/reger have them.
        # cloneMessage retrieves the stored grant and its path-indexed attachments.
        grant_serder, pathed = exchanging.cloneMessage(self.hby, serder.said)
        if grant_serder is None:
            logger.error(f"Could not clone grant serder said={serder.said}")
            return

        psr = parsing.Parser(kvy=None, tvy=self.tvy, vry=self.verifier)
        for label in ("anc", "iss", "acdc"):
            ked = embeds.get(label)
            if ked is None:
                continue
            sadder = coring.Sadder(ked=ked)
            attach = pathed.get(label, b"")
            ims = bytearray(sadder.raw) + bytearray(attach)
            try:
                psr.parseOne(ims=ims)
            except Exception as e:
                logger.warning(f"Could not parse embed {label} for said={said}: {e}")

        # Persist via ReceivedCredentialService (mirrors existing save_credential pattern).
        try:
            if not self.rgy.reger.saved.get(keys=said):
                logger.warning(f"Credential {said} not in reger.saved after parsing; will retry in admit doer")
            else:
                holder = self.hab.pre
                self.received_svc.save_credential(
                    doc={"said": said, "holder": holder, "schema": {}},
                    acdc=bytes(coring.Sadder(ked=acdc_ked).raw),
                )
        except Exception as e:
            logger.warning(f"Could not save received credential {said}: {e}")

            # Enqueue admit regardless of save outcome; QviAdmitDoer will retry persistence.
        self.admit_cues.append({"grant_said": serder.said, "sender": sender})
        logger.info(f"Enqueued admit cue for grant_said={serder.said}")


class CastellanForwardHandler:
    """
    Handles /fwd EXN envelopes arriving at the castellan CESR endpoint.

    IPEX embeds (topic /ipex/grant etc.) are re-dispatched through the parser
    so CastellanIpexGrantHandler can process them.  Multisig embeds are stored
    in the message service for intra-enterprise coordination.

    parser and exc are set post-construction (after exc is created) to break
    the circular dependency: exc needs this handler, this handler needs exc.
    """
    resource = "/fwd"

    def __init__(self, hby, message_service):
        self.hby = hby
        self.message_service = message_service
        self.parser = None  # set by resting.py after exc is created
        self.exc = None     # set by resting.py after exc is created

    def verify(self, serder, attachments=None):
        return True  # Exchanger validates sender KEL before calling handle()

    def handle(self, serder, attachments=None):
        modifiers = serder.ked.get("q", {})
        recipient = modifiers.get("pre", "")
        topic = modifiers.get("topic", "/ipex/grant")

        embeds = serder.ked.get("e", {})
        for label, embed in embeds.items():
            if label == "d":
                continue

            # Reconstruct inner event bytes
            try:
                sadder = coring.Sadder(ked=embed)
                inner_raw = bytearray(sadder.raw)
            except Exception as e:
                logger.warning(f"Could not reconstruct embed '{label}' in /fwd: {e}")
                continue

            # Append only the path-indexed attachment bytes for this embed label
            if attachments:
                label_pather = coring.Pather(path=[label])
                for np, pattach in attachments:
                    if np.startswith(label_pather):
                        inner_raw.extend(pattach)

            # Dispatch IPEX embeds to the parser so /ipex/grant handler fires.
            inner_route = embed.get("r", "")
            if inner_route.startswith("/ipex") and self.parser is not None and self.exc is not None:
                try:
                    self.parser.parse(ims=bytearray(inner_raw), exc=self.exc, local=False)
                except Exception as e:
                    logger.warning(f"Could not re-dispatch /fwd embed '{label}': {e}")
            else:
                # Multisig and other intra-enterprise topics → message service
                multisig_alias = modifiers.get("alias", "")
                try:
                    self.message_service.post_message(
                        recipient_aid=recipient,
                        sender_aid=serder.ked.get("i", ""),
                        topic=topic.lstrip("/"),
                        raw=bytes(inner_raw),
                        multisig_alias=multisig_alias,
                    )
                except Exception as e:
                    logger.warning(f"Could not store /fwd message for '{label}': {e}")


class QviAdmitDoer(doing.DoDoer):
    """
    Async doer that processes QVI admit cues enqueued by CastellanIpexGrantHandler.

    For each cue it builds an /ipex/admit EXN signed by castellan's hab and
    delivers it back to the grant sender via StreamPoster.
    """

    def __init__(self, hby, hab, admit_cues, exc):
        self.hby = hby
        self.hab = hab
        self.admit_cues = admit_cues
        self.exc = exc
        super().__init__(doers=[doing.doify(self.admitDo)])

    def admitDo(self, tymth, tock=0.5, **kwa):
        self.wind(tymth)
        self.tock = tock
        _ = (yield self.tock)

        while True:
            while self.admit_cues:
                cue = self.admit_cues.popleft()
                grant_said = cue.get("grant_said")
                sender = cue.get("sender")

                grant_serder, _ = exchanging.cloneMessage(self.hby, grant_said)
                if grant_serder is None:
                    logger.error(f"QviAdmitDoer: grant {grant_said} not found in DB, skipping")
                    yield self.tock
                    continue

                try:
                    exn, atc = protocoling.ipexAdmitExn(
                        hab=self.hab,
                        message="",
                        grant=grant_serder,
                        dt=helping.nowIso8601(),
                    )
                    admit_msg = bytearray(exn.raw)
                    admit_msg.extend(atc)

                    # Register admit locally so erpy table is updated
                    parsing.Parser().parseOne(ims=bytes(admit_msg), exc=self.exc)

                    # Deliver back to grant sender (mock-GLEIF)
                    postman = forwarding.StreamPoster(
                        hby=self.hby,
                        hab=self.hab,
                        recp=sender,
                        topic="credential",
                    )
                    admit_atc = exchanging.serializeMessage(self.hby, exn.said)
                    del admit_atc[:exn.size]
                    postman.send(serder=exn, attachment=admit_atc)

                    deliver_doer = doing.DoDoer(doers=postman.deliver())
                    self.extend([deliver_doer])

                    while not deliver_doer.done:
                        yield self.tock

                    self.remove([deliver_doer])
                    logger.info(f"QviAdmitDoer: sent admit for grant_said={grant_said} to {sender}")

                except Exception as e:
                    logger.error(f"QviAdmitDoer: failed to send admit for {grant_said}: {e}")

            yield self.tock


class CesrInboundEnd:
    def __init__(self, exc, kvy, rvy, tvy):
        self.exc = exc
        self.kvy = kvy
        self.rvy = rvy
        self.tvy = tvy

    def _parse(self, req, rep):
        body = req.bounded_stream.read()
        parsing.Parser().parse(
            ims=bytearray(body),
            kvy=self.kvy,
            rvy=self.rvy,
            tvy=self.tvy,
            exc=self.exc,
            local=False,
        )
        rep.status = falcon.HTTP_204

    def on_put(self, req, rep):
        # StreamPoster (HTTPStreamMessenger) sends PUT to path "/" — same parsing logic
        self._parse(req, rep)