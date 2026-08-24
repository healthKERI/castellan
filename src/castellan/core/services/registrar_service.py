# -*- encoding: utf-8 -*-
"""
hksvc.core.services.registrar_service module

RegistrarService: exposes the healthKERI platform as a KERIGuard credential registrar
for SaaS-mode deployments.  Mirrors the open-source registrar's HTTP API so that the
sentinel's CredentialLoader and the admin plugin's push path work without modification.
"""

from castellan.core.services import IssuedCredentialService
from castellan.core.services.custom.custom_errors import NotFoundError, ValidationError
from castellan.core.services.issued_credential_service import TELEvent
from keri import kering
from keri.core import parsing
from keri.core.serdering import SerderKERI
from keri.help import ogler
from keri.vdr import verifying

logger = ogler.getLogger()


class KeystateBehindError(Exception):
    """Raised when the platform's adjudication SN is behind the requested issuer SN."""


class RegistrarService:
    """
    Exposes the healthKERI platform as a KERIGuard registrar.

    Provides parse_grant, get_credential_cesr, search_credentials, and
    get_oobi_cesr — the four operations the sentinel needs in SaaS mode.
    """

    def __init__(
        self,
        hby,
        hab,
        rgy,
        tvy,
        credential_service: IssuedCredentialService,
        key_event_log_service,
    ):
        self.hby = hby
        self.hab = hab
        self.rgy = rgy
        self.tvy = tvy
        self.credential_service = credential_service
        self.key_event_log_service = key_event_log_service

        self.verifier = verifying.Verifier(hby=hby, reger=rgy.reger)

        # Parser for ACDC/TEL/KEL (credential data)
        self.credential_psr = parsing.Parser(
            kvy=hby.kvy, tvy=rgy.tvy, vry=self.verifier
        )

    def get_identity(self) -> dict:
        """Return the registrar hab's own AID.

        Lets clients resolve this AID's KEL (via get_oobi_cesr) before trusting
        replies signed by it — e.g. the /end/role/add attestations embedded in
        get_oobi_cesr's own output for *other* AIDs. Without this, those
        attestations verify against an unknown signer and escrow forever.
        """
        return {"aid": self.hab.pre}

    def get_credential_cesr(
        self, said: str, registry: bool = False, tel: bool = False
    ) -> bytes:
        """
        Return a CESR stream for a credential.

        Mirrors registrar's output_cred(): optional registry TEL prefix,
        optional credential TEL, then the signed ACDC.

        Raises NotFoundError if the credential is unknown.
        """

        try:
            out = self.credential_service.get_credential_stream(said)
        except Exception as e:
            logger.error(f"Error getting credential {said}: {e}")
            import traceback

            traceback.print_exc()
            raise NotFoundError(f"Credential {said} not found")

        return bytes(out)

    def search_credentials(self, issuer_aid: str, issuer_sn: int) -> list:
        """
        Return SAIDs of credentials issued by issuer_aid.

        Raises KeystateBehindError if the platform's latest adjudication SN
        for the issuer is behind issuer_sn.
        """
        state = self.key_event_log_service.get_keystate(issuer_aid)
        state_sn = int(state.s, 16)
        if state_sn == issuer_sn:
            return []

        if state_sn < issuer_sn:
            raise KeystateBehindError(
                f"Platform at sn={state_sn}, need sn={issuer_sn} for {issuer_aid}"
            )

        events = TELEvent.objects(anc__sn__gt=issuer_sn, anc__prefix=issuer_aid)
        return [event.sad["i"] for event in events] if events else []

    def get_oobi_cesr(self, aid: str) -> bytes:
        """
        Return CESR-encoded OOBI reply bytes for a watched AID.

        Mirrors registrar's get_oobi(): uses hab.replyToOobi.
        Raises NotFoundError if the AID is unknown or has no witness OOBI.
        """
        if aid not in self.hby.kevers:
            raise NotFoundError(f"AID {aid} not found")

        msgs = self.hab.replyToOobi(aid=aid, role=kering.Roles.witness)
        if not msgs:
            raise NotFoundError(f"No OOBI available for {aid}")

        return bytes(msgs)

    def parse_revocation(self, tel: bytes, kel: bytes, doc: dict):
        """Parse revocation TEL event with anchring KEL event"""

        # Try IPEX exchange path (introduction + grant via exchanger)
        issuer = doc.get("issuer")
        if not issuer:
            raise ValidationError("Missing required field: issuer")

        # Refresh keystate from Mongodb to ensure we have the latest KEL
        self.key_event_log_service.get_keystate(issuer)

        tel_event = SerderKERI(raw=tel)
        if tel_event.ilk != kering.Ilks.rev:
            raise ValidationError(f"Invalid TEL ilk: {tel_event.ilk}")

        credential_said = tel_event.sad["i"]
        credential = self.credential_service.get_credential(credential_said)

        if not credential:
            raise ValidationError(f"Invalid credential said: {credential_said}")

        if credential.issuer != issuer:
            raise ValidationError(f"Invalid issuer AID: {credential.issuer}")

        regk = tel_event.sad["ri"]

        kel_event = SerderKERI(raw=kel)
        seals = kel_event.seals
        match = next(
            (
                seal
                for seal in seals
                if seal.get("i") == credential_said
                and seal.get("d") == tel_event.sad["d"]
                and seal.get("s") == tel_event.sad["s"]
            ),
            None,
        )

        if not match:
            raise ValidationError("Invalid KEL seal")

        self.credential_psr.parseOne(kel)
        self.hab.kvy.processEscrows()
        self.credential_psr.parseOne(tel)
        self.tvy.processEscrows()

        self.credential_service.capture_tel_events(issuer, regk, credential_said)

    @staticmethod
    def search_tel_events(issuer, issuer_sn):
        return []
