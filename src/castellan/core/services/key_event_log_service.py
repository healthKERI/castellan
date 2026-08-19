# -*- encoding: utf-8 -*-
from dataclasses import asdict

from keri import kering, core
from keri.app.habbing import Habery
from keri.core import coring, serdering, parsing, eventing, Counter, Codens
from keri.core.coring import NonTransDex
from keri.core.parsing import Parser
from keri.db import dbing
from keri.help import helping, ogler
from mongoengine import Document, StringField, DictField, ListField, IntField, EmbeddedDocumentField, EmbeddedDocument

logger = ogler.getLogger()

class Aid(Document):
    aid = StringField(required=True, primary_key=True)
    key_state = DictField(required=True)


class Event(Document):
    said = StringField(required=True, primary_key=True)
    sad = DictField(required=True)
    sn = IntField(required=True)
    sigs = ListField(required=False, default=[])
    wigs = ListField(required=False, default=[])
    aes = DictField(default=None)
    vrcs = ListField(required=False, default=[])
    rcts = ListField(required=False, default=[])
    dts = StringField(required=True)


class Tsgs(EmbeddedDocument):
    prefix = StringField(required=True)
    seq = StringField(required=True)
    dig = StringField(required=True)
    sigs = ListField(required=False, default=[])

class Scgs(EmbeddedDocument):
    verfer = StringField(required=True)
    cigar = StringField(required=True)


class Reply(Document):
    said = StringField(required=True, primary_key=True)
    aid = StringField(required=True)
    sad = DictField(required=True)
    cigs = ListField(EmbeddedDocumentField(Scgs))
    tsgs = ListField(EmbeddedDocumentField(Tsgs))


class KeyEventLogService:
    """ Key event log service for managing and retrieving key event logs and identifier state"""

    def __init__(self, hby: Habery | None):
        self.hby = hby

    def add_kel(self, aid: str, ims: bytes):
        parser = Parser(kvy=self.hby.kvy, local=False)

        parser.parse(ims=ims)
        self.hby.kvy.processEscrows()

        if aid not in self.hby.kevers:
            raise ValueError("unable to add key event log, incomplete or unverifiable KEL passed in")

        self.capture_kel(aid)

    @staticmethod
    def get_aid(aid):
        return Aid.objects.get(aid=aid)

    def capture_kel(self, aid):

        if aid not in self.hby.kevers:
            raise ValueError(f"unable to capture KEL for unknown aid {aid}")

        key_state = asdict(self.hby.kvy.kevers[aid].state())
        ident = dict(aid=aid, key_state=key_state)
        Aid(**ident).save()

        if hasattr(aid, 'encode'):
            aid = aid.encode("utf-8")

        for _, fn, dig in self.hby.db.getFelItemPreIter(aid, fn=0):
            self.serialize_event(aid, fn, dig)

    def capture_rpys(self, aid):
        for (_, erole, eid), end in self.hby.db.ends.getItemIter(keys=(aid,)):
            keys = (eid,)
            for (_), saider in self.hby.db.lans.getItemIter(keys=keys):
                serder = self.hby.db.rpys.get(keys=(saider.qb64,))
                cigars = self.hby.db.scgs.get(keys=(saider.qb64,))
                if len(cigars) == 1:
                    (verfer, cigar) = cigars[0]
                    cigar.verfer = verfer
                    cigars = [cigar]
                else:
                    cigars = []

                tsgs = eventing.fetchTsgs(db=self.hby.db.ssgs, saider=saider)
                self.serialize_reply(aid, serder, cigars=cigars, tsgs=tsgs)

            if end and (end.enabled or end.allowed):
                saider = self.hby.db.eans.get(keys=(aid, erole, eid))
                serder = self.hby.db.rpys.get(keys=(saider.qb64,))
                cigars = self.hby.db.scgs.get(keys=(saider.qb64,))
                if len(cigars) == 1:
                    (verfer, cigar) = cigars[0]
                    cigar.verfer = verfer
                    cigars = [cigar]
                else:
                    cigars = []

                tsgs = eventing.fetchTsgs(db=self.hby.db.ssgs, saider=saider)
                self.serialize_reply(aid, serder, cigars=cigars, tsgs=tsgs)

    @staticmethod
    def serialize_reply(aid, serder, cigars=None, tsgs=None):
        reply = dict()
        reply["aid"] = aid
        reply["sad"] = serder.ked
        reply["said"] = serder.said

        cigars = cigars or []
        tsgs = tsgs or []

        if (rpy := Reply.objects(said=serder.said).first()) is not None:
            return rpy

        # add indexed signatures to attachments
        reply["cigs"] = []
        for cig in cigars:
            reply["cigs"].append(Scgs(verfer=cig.verfer.qb64, cigar=cig.qb64))

        # add indexed witness signatures to attachments
        reply["tsgs"] = []
        for (prefixer, seqner, diger, sigers) in tsgs:
            reply["tsgs"].append(Tsgs(prefix=prefixer.qb64, seq=seqner.qb64, dig=diger.qb64, sigs=[siger.qb64 for siger in sigers]))


        reply = Reply(**reply)
        reply.save()

        return reply

    def update_kel(self, aid):
        ident = Aid.objects(aid=aid).first()
        if not ident:
            raise ValueError(f"unable to update KEL for unknown identifier {aid}")

        kever = self.hby.kevers[aid]
        said = ident.key_state["d"]
        if said == kever.serder.said:
            return False

        snh = ident.key_state['s']
        sn = int(snh, 16)

        for dig in self.hby.db.getKelIter(aid, sn=sn+1):
            self.serialize_event(aid, 0, bytes(dig))

        Aid(**{
            'aid': aid,
            'key_state': asdict(self.hby.kvy.kevers[aid].state())
        }).save()
        return True

    def serialize_event(self, aid, fn, dig):
        event = dict()
        dgkey = dbing.dgKey(aid, dig)  # get message
        if not (raw := self.hby.db.getEvt(key=dgkey)):
            raise kering.MissingEntryError("Missing event for dig={}.".format(dig))

        serder = serdering.SerderKERI(raw=bytes(raw))
        event["sad"] = serder.ked
        event["said"] = serder.said
        event["sn"] =  serder.sn

        if (evt := Event.objects(said=serder.said).first()) is not None:
            return evt

        # add indexed signatures to attachments
        event["sigs"] = []
        if not (sigs := self.hby.db.getSigs(key=dgkey)):
            raise kering.MissingEntryError("Missing sigs for dig={}.".format(dig))
        for sig in sigs:
            event["sigs"].append(core.Siger(qb64b=bytes(sig)).qb64)

        # add indexed witness signatures to attachments
        event["wigs"] = []
        if wigs := self.hby.db.getWigs(key=dgkey):
            for wig in wigs:
                event["wigs"].append(core.Siger(qb64b=bytes(wig)).qb64)

        # add authorizer (delegator/issuer) source seal event couple to attachments
        couple = self.hby.db.getAes(dgkey)
        if couple is not None:
            couple = bytearray(couple)
            seqner = coring.Seqner(qb64b=couple, strip=True)
            saider = coring.Saider(qb64b=couple)
            event["aes"] = dict(snh=seqner.snh, said=saider.qb64)

        # add trans endorsement quadruples to attachments not controller
        # may have been originally key event attachments or receipted endorsements
        event["vrcs"] = []
        if quads := self.hby.db.getVrcs(key=dgkey):
            for quad in quads:
                quad = bytearray(quad)
                prefixer = coring.Prefixer(qb64b=quad, strip=True)
                seqner = coring.Seqner(qb64b=quad, strip=True)
                saider = coring.Saider(qb64b=quad, strip=True)
                siger = core.Siger(qb64b=quad, strip=True)
                event["vrcs"].append(dict(pre=prefixer.qb64, snh=seqner.snh, said=saider.qb64, sig=siger.qb64))

        # add nontrans endorsement couples to attachments not witnesses
        # may have been originally key event attachments or receipted endorsements
        event["rcts"] = []
        if coups := self.hby.db.getRcts(key=dgkey):
            for coup in coups:
                coup = bytearray(coup)
                verfer = coring.Verfer(qb64b=coup, strip=True)
                cigar = coring.Cigar(qb64b=coup)
                event["rcts"].append(dict(verfer=verfer.qb64, cig=cigar.qb64))

        # add first seen replay couple to attachments
        if not (dts := self.hby.db.getDts(key=dgkey)):
            raise kering.MissingEntryError("Missing datetime for dig={}.".format(dig))
        event["dts"] = helping.toIso8601(coring.Dater(dts=bytes(dts)).datetime)

        event = Event(**event)
        event.save()

        return event

    def get_full_stream(self, aid, fn=0):
        ims = bytearray()
        ims.extend(self.get_kel_stream(aid, fn))
        ims.extend(self.get_rpy_stream(aid))
        return ims



    @staticmethod
    def get_kel(aid):
        return Event.objects(sad__i=aid).order_by("sn")

    def get_kel_stream(self, aid, fn=0):
        events = self.get_kel(aid)

        ims = bytearray()
        for event in events:
            atc = bytearray()  # attachments
            sn = event.sad['s']
            serder = serdering.SerderKERI(sad=event.sad)
            ims.extend(serder.raw)

            sigs = event.sigs
            atc.extend(core.Counter(code=core.Codens.ControllerIdxSigs,
                                    count=len(sigs), gvrsn=kering.Vrsn_1_0).qb64b)
            for sig in sigs:
                atc.extend(core.Siger(qb64=sig).qb64b)

            wigs = event.wigs
            if wigs:
                atc.extend(core.Counter(code=core.Codens.WitnessIdxSigs,
                                        count=len(wigs), gvrsn=kering.Vrsn_1_0).qb64b)
                for wig in wigs:
                    atc.extend(core.Siger(qb64=wig).qb64b)

            if event.aes:
                couple = event.aes
                seqner = coring.Seqner(snh=couple["snh"])
                saider = coring.Saider(qb64=couple["said"])

                atc.extend(core.Counter(code=core.Codens.SealSourceCouples,
                                        count=1, gvrsn=kering.Vrsn_1_0).qb64b)
                atc.extend(seqner.qb64b)
                atc.extend(saider.qb64b)

            # add trans endorsement quadruples to attachments not controller
            # may have been originally key event attachments or receipted endorsements
            quads = event.vrcs
            if quads:
                atc.extend(core.Counter(code=core.Codens.TransReceiptQuadruples,
                                        count=len(quads), gvrsn=kering.Vrsn_1_0).qb64b)
                for quad in quads:
                    prefixer = coring.Prefixer(qb64=quad["pre"])
                    seqner = coring.Seqner(snh=quad["snh"])
                    saider = coring.Saider(qb64=quad["said"])
                    siger = core.Siger(qb64=quad["sig"])

                    atc.extend(prefixer.qb64b)
                    atc.extend(seqner.qb64b)
                    atc.extend(saider.qb64b)
                    atc.extend(siger.qb64b)

            # add nontrans endorsement couples to attachments not witnesses
            # may have been originally key event attachments or receipted endorsements
            coups = event.rcts
            if coups:
                atc.extend(core.Counter(code=core.Codens.NonTransReceiptCouples,
                                        count=len(coups), gvrsn=kering.Vrsn_1_0).qb64b)
                for coup in coups:
                    verfer = coring.Verfer(qb64=coup["verver"])
                    cigar = coring.Cigar(qb64=coup["cig"])

                    atc.extend(verfer.qb64b)
                    atc.extend(cigar.qb64b)

            # add first seen replay couple to attachments
            dts = coring.Dater(dts=event.dts)
            atc.extend(core.Counter(code=core.Codens.FirstSeenReplayCouples,
                                    count=1, gvrsn=kering.Vrsn_1_0).qb64b)
            atc.extend(core.Number(num=fn, code=core.NumDex.Huge).qb64b)  # may not need to be Huge
            atc.extend(dts.qb64b)

            # prepend pipelining counter to attachments
            if len(atc) % 4:
                raise ValueError("Invalid attachments size={}, nonintegral"
                                 " quadlets.".format(len(atc)))
            pcnt = core.Counter(code=core.Codens.AttachmentGroup,
                                count=(len(atc) // 4), gvrsn=kering.Vrsn_1_0).qb64b
            ims.extend(pcnt)
            ims.extend(atc)

        return ims

    @staticmethod
    def get_rpys(aid):
        return Reply.objects(aid=aid)

    def get_rpy_stream(self, aid):
        ims = bytearray()

        rpys = self.get_rpys(aid)
        for rpy in rpys:
            atc = bytearray()  # attachments
            serder = serdering.SerderKERI(sad=rpy.sad)
            ims.extend(serder.raw)

            if rpy.cigs:
                atc.extend(Counter(Codens.NonTransReceiptCouples, count=len(rpy.cigs),
                                   gvrsn=kering.Vrsn_1_0).qb64b)
                for scgs in rpy.cigs:
                    verfer = coring.Verfer(qb64=scgs.verfer)
                    cigar = coring.Cigar(qb64=scgs.cigar, verfer=verfer)
                    if cigar.verfer.code not in NonTransDex:
                        raise ValueError("Attempt to use tranferable prefix={} for "
                                         "receipt.".format(cigar.verfer.qb64))
                    atc.extend(cigar.verfer.qb64b)
                    atc.extend(cigar.qb64b)

            if rpy.tsgs:
                for tsg in rpy.tsgs:
                    prefixer = coring.Prefixer(qb64=tsg.prefix)
                    seqner = coring.Seqner(qb64=tsg.seq)
                    diger = coring.Diger(qb64=tsg.dig)

                    atc.extend(Counter(Codens.TransIdxSigGroups, count=1,
                                       gvrsn=kering.Vrsn_1_0).qb64b)
                    atc.extend(prefixer.qb64b)
                    atc.extend(seqner.qb64b)
                    atc.extend(diger.qb64b)
                    atc.extend(Counter(Codens.ControllerIdxSigs, count=len(tsg.sigs),
                                       gvrsn=kering.Vrsn_1_0).qb64b)
                    for sig in tsg.sigs:
                        siger = core.Siger(qb64=sig)
                        atc.extend(siger.qb64b)

            if len(atc) % 4:
                raise ValueError("Invalid attachments size={}, nonintegral"
                                 " quadlets.".format(len(atc)))
            ims.extend(Counter(Codens.AttachmentGroup,
                               count=(len(atc) // 4), gvrsn=kering.Vrsn_1_0).qb64b)
            ims.extend(atc)

        return ims

    def get_keystate(self, aid):
        """Get the key state of the given aid from the key event log, parse KEL from mongodb if not up to date."""
        aid_obj = Aid.objects(aid=aid).first()
        if aid not in self.hby.kevers or aid_obj.key_state.get("s") != self.hby.kevers[aid].serder.snh:
            ims = self.get_kel_stream(aid)
            parsing.Parser().parse(bytes(ims), kvy=self.hby.kvy)
            self.hby.kvy.processEscrows()

            if aid not in self.hby.kevers:
                raise ValueError("unable to add key event log, incomplete or unverifiable KEL passed in")

        return self.hby.kevers[aid].state()

    def scan_for_delegates(self, delegator):
        """
        Scan for delegate identifiers in the key event log of a delegator.

        Processes all the events in the delegator's key event log and extracts any
        referenced delegate identifiers from event seals.

        Parameters:
            delegator (str): The identifier prefix of the delegator to scan

        Returns:
            list: List of discovered delegate identifier prefixes found in the scan

        Side Effects:
            - Captures key event logs for discovered valid delegates
            - Logs info messages when delegate KELs are captured
        """
        cloner = self.hby.db.clonePreIter(pre=delegator, fn=0)  # create iterator at 0

        delegates = []
        for msg in cloner:
            srdr = serdering.SerderKERI(raw=msg)
            delegates.extend(self.process_delegator_event_seals(srdr))

        return delegates

    def process_delegator_event_seals(self, srdr):
        """ Process seals from a delegator's event to find and validate delegate identifiers

        Takes a serialized KERI event and checks its seals for valid delegate anchors.
        A valid delegate must meet the following criteria:
        - The seal must contain an inception event anchor ('i', 's', 'd' fields)
        - The sequence number must be 0 (inception event)
        - The seal digest must match the delegate identifier
        - The delegate's KEL must show proper delegation from this delegator
        - The delegate must have valid non-transferable signing keys (ndigers)

        Parameters:
            srdr (Serder): The serialized event to process for delegate anchors

        Returns:
            list: List of discovered and validated delegate identifier prefixes

        Side Effects:
            - Captures KELs for discovered valid delegates to the key event log database
            - Logs delegate KEL capture events at info level
        """

        delegator = srdr.pre
        delegates = []
        for anchor in srdr.seals:
            if 'i' not in anchor and 's' not in anchor and 'd' not in anchor:  # Event seal anchor
                continue

            delegate = anchor['i']
            if anchor['s'] != '0' or delegate != anchor['d']:  # Ensure this is an inception anchor
                continue

            if delegate not in self.hby.kevers:
                continue

            delegateKever = self.hby.kevers[delegate]

            # Check for accidental registration of non-delegate or for a delegate that was neutered.
            if delegateKever.delpre != delegator or not delegateKever.ndigers:
                continue

            self.capture_kel(delegate)
            delegates.append(delegate)

            logger.info(f"Delegate {delegate} KEL captured for delegator {delegator}")

        return delegates
