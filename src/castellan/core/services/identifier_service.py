# -*- encoding: utf-8 -*-
"""
castellan.core.services.identifier_service module

Service and MongoDB document model for castellan-uploaded identifiers.

Each whisper user uploads exactly one non-group identifier during initialization.
Castellan stores these so that all whisper instances can discover peers and
exchange OOBIs before constructing a group multisig.
"""

import math
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional, Tuple

from bson import ObjectId
from keri import kering
from keri.app import habbing
from keri.core.serdering import SerderKERI
from keri.help import ogler
from mongoengine import (
    DateTimeField,
    Document,
    StringField,
    DoesNotExist,
    Q,
    ListField,
    EmbeddedDocument,
    IntField,
    EmbeddedDocumentField,
    DictField,
    BooleanField,
)

from castellan.core.services.custom.custom_errors import ConflictError, NotFoundError
from castellan.core.services.key_event_log_service import Aid

logger = ogler.getLogger()


class UploadedIdentifier(Document):
    """A single non-group KERI identifier uploaded by a whisper instance."""

    sn = IntField(required=False)
    said = StringField(required=False)
    aid = StringField(unique=True, required=False)  # KERI AID prefix
    alias = StringField(
        required=True, unique=True
    )  # human-readable alias (unique across castellan)
    oobi = StringField(default="")  # OOBI URL for peer resolution
    created_at = DateTimeField(default=datetime.now)
    key_state = DictField(required=False)
    mailbox = BooleanField(default=False)
    registrar = BooleanField(default=False)

    meta = {
        "indexes": ["alias", "aid"],
        "ordering": ["created_at"],
        "collection": "uploaded_identifier",
        "allow_inheritance": True,
    }


class Registry(EmbeddedDocument):
    """Credential registry document."""

    registry_pre = StringField(required=True)  # Registry prefix/identifier
    registry_said = StringField(required=True)
    registry_name = StringField(required=True)  # Human-readable name
    created_at = DateTimeField(default=datetime.now)


class MultisigMember(EmbeddedDocument):
    account_username = StringField(required=True)
    account_aid = StringField(required=True)
    member_aid = StringField(required=False)
    signing_threshold = StringField(required=False)
    rotation_threshold = StringField(required=False)
    public_key = StringField(required=False)
    current_signature = StringField(required=False)
    current_lead = BooleanField(default=False)


class Witness(EmbeddedDocument):
    witness_aid = StringField(required=True)
    witness_alias = StringField(required=True)
    witness_oobi = StringField(required=True)


class Witnesses(EmbeddedDocument):
    adds = ListField(EmbeddedDocumentField(Witness), required=False)
    cuts = ListField(StringField(), required=False)
    threshold = IntField(required=False)


class MultisigIdentifier(UploadedIdentifier):
    """A single multisig KERI identifier uploaded by a whisper instance."""

    members = ListField(EmbeddedDocumentField(MultisigMember))
    signing_threshold = IntField(required=False)
    rotation_threshold = IntField(required=False)
    current_event = DictField(required=False)
    current_metadata = DictField(required=False)
    vcp = DictField(required=False)  # Registry inception event
    mbx = DictField(required=False)
    rgr = DictField(required=False)
    registry = EmbeddedDocumentField(Registry, required=False)
    witness_rotate = EmbeddedDocumentField(Witnesses, required=False)
    witnesses = ListField(EmbeddedDocumentField(Witness), required=False)


class IdentifierService:
    """Service for storing and retrieving castellan-uploaded identifiers."""

    def __init__(
            self,
            account_service,
            kelSvc=None,
            parser=None,
            kvy=None,
            hby=None,
            castellan_hab=None,
    ):
        self.account_service = account_service
        self.kelSvc = kelSvc
        self.parser = parser
        self.kvy = kvy
        self.hby = hby
        self.castellan_hab = castellan_hab

    def upload(
            self, aid: str, alias: str, kel: bytes, oobi: str = ""
    ) -> "UploadedIdentifier":
        """
        Store an identifier uploaded by a whisper instance.

        Args:
            aid:   KERI AID prefix (primary key).
            alias: Human-readable alias — must be unique across castellan.
            kel:   Raw CESR-encoded KEL bytes for the identifier.
            oobi:  OOBI URL for peer resolution (optional).

        Returns:
            The created UploadedIdentifier document.

        Raises:
            ConflictError: If the alias is already in use.
            ValueError: If the KEL cannot be parsed or verified.
        """
        if not aid:
            raise ValueError("aid is required")
        if not alias:
            raise ValueError("alias is required")
        if not kel:
            raise ValueError("kel is required")

        if self.parser is None or self.kvy is None:
            raise RuntimeError(
                "IdentifierService requires parser and kvy to process KEL"
            )

        try:
            self.parser.parse(ims=bytearray(kel), kvy=self.kvy, local=False)
        except Exception as e:
            raise RuntimeError(f"An error occurred parsing KEL into Kevery: {e}")

        if aid not in self.kvy.kevers:
            raise ValueError(
                f"KEL parsed but AID {aid} not found in kevers — KEL may be incomplete or unverifiable"
            )

        if self.kelSvc is not None:
            try:
                self.kelSvc.capture_kel(aid)
                self.kelSvc.scan_for_delegates(aid)
                self.kelSvc.capture_rpys(aid)

                logger.info(f"KEL captured for aid={aid}")
                if self.hby is not None and self.castellan_hab is not None:
                    group_hab = self.hby.habs.get(aid)
                    if group_hab is not None and isinstance(
                            group_hab, habbing.GroupHab
                    ):
                        role_msgs = group_hab.makeEndRole(
                            eid=self.castellan_hab.pre, role=kering.Roles.mailbox
                        )
                        self.parser.parse(ims=bytearray(role_msgs))
                        logger.info(
                            f"Registered castellan as mailbox for group AID={aid}"
                        )
            except Exception as e:
                raise RuntimeError(f"KEL capture failed for aid={aid}: {e}")

        if (identifier := UploadedIdentifier.objects(alias=alias).first()) is None:
            identifier = UploadedIdentifier(aid=aid, alias=alias, oobi=oobi)

        identifier.key_state = asdict(self.hby.kvy.kevers[aid].state())
        identifier.save()

        logger.info(f"Uploaded identifier aid={aid} alias={alias}")

        return identifier

    def list_identifiers(
            self,
            page: int = 0,
            page_size: int = 20,
            filter_term: str | None = None,
            order: list[str] | None = None,
    ) -> tuple[list["UploadedIdentifier"], int, int]:
        """
        List uploaded identifiers with pagination/filter/sort, mirroring
        SchemaService.list_schemas / IssuedCredentialService.list_credentials.

        Args:
            page: Zero-indexed page number (default 0).
            page_size: Results per page (default 20).
            filter_term: Case-insensitive substring match against alias or aid.
            order: Sort field(s), e.g. ["-created_at"] (default ["-created_at"]).

        Returns:
            (identifiers, total_count, num_pages)
        """
        qs = UploadedIdentifier.objects()

        if filter_term:
            qs = qs.filter(
                Q(alias__icontains=filter_term) | Q(aid__icontains=filter_term)
            )

        if order:
            qs = qs.order_by(*order)
        else:
            qs = qs.order_by("-created_at")

        total = qs.count()
        num_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        items = list(qs.skip(page * page_size).limit(page_size))
        return items, total, num_pages

    def get_key_state_summary(self, aid: str) -> dict | None:
        """
        Best-effort remote key state for aid, same shape as returned by
        get_identifier_with_key_state's "key_state" field. Returns None if
        unavailable (no kelSvc, or state lookup fails) rather than raising —
        callers use this to enrich a list response and a single bad AID
        should not fail the whole page.
        """
        if self.kelSvc is None:
            return None
        try:
            return asdict(self.kelSvc.get_keystate(aid))
        except Exception as e:
            logger.debug(f"Could not get key state for aid={aid}: {e}")
            return None

    def get(self, aid: str) -> "UploadedIdentifier":
        """Fetch a single identifier by AID. Raises NotFoundError if missing."""
        try:
            return UploadedIdentifier.objects.get(aid=aid)
        except DoesNotExist:
            raise NotFoundError(f"Identifier not found: {aid}")

    def get_kel_stream(self, aid: str) -> bytes:
        """
        Return the CESR-encoded KEL stream for the given AID.

        Raises NotFoundError if no identifier exists for aid.
        Returns empty bytes if the KEL has not been captured yet.
        """
        Aid.objects.with_id(aid)  # raises NotFoundError if unknown
        if self.kelSvc is None:
            return b""
        try:
            return self.kelSvc.get_full_stream(aid)
        except Exception as e:
            logger.warning(f"KEL stream retrieval failed for aid={aid}: {e}")
            return b""

    def delete(self, aid: str) -> None:
        """Delete an uploaded identifier. Raises NotFoundError if missing."""
        identifier = self.get(aid)
        identifier.delete()
        logger.info(f"Deleted identifier aid={aid}")

    def get_identifier_with_key_state(self, aid):
        """Retrieves an Identifier by its aid."""
        try:
            identifier = UploadedIdentifier.objects.get(aid=aid)
            key_state = asdict(self.kelSvc.get_keystate(identifier.aid))

            return {
                "alias": identifier.alias,
                "aid": identifier.aid,
                "key_state": key_state,
            }
        except DoesNotExist:
            raise NotFoundError(f"Identifier not found: {aid}")

        except Exception as e:
            if isinstance(e, (ConflictError, NotFoundError)):
                raise
            raise RuntimeError(
                f"An error occurred while querying identifier: {type(e)}"
            )

    @staticmethod
    def list_multisig_identifiers(
            page: int = 0,
            page_size: int = 20,
            filter_term: str | None = None,
            order: list[str] | None = None,
    ) -> tuple[list["MultisigIdentifier"], int, int]:
        """
        List multisig identifiers with pagination/filter/sort.

        Args:
            page: Zero-indexed page number (default 0).
            page_size: Results per page (default 20).
            filter_term: Case-insensitive substring match against alias or aid.
            order: Sort field(s), e.g. ["-created_at"] (default ["-created_at"]).

        Returns:
            (identifiers, total_count, num_pages)
        """
        qs = MultisigIdentifier.objects()

        if filter_term:
            qs = qs.filter(
                Q(alias__icontains=filter_term) | Q(aid__icontains=filter_term)
            )

        if order:
            qs = qs.order_by(*order)
        else:
            qs = qs.order_by("-created_at")

        total = qs.count()
        num_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        items = list(qs.skip(page * page_size).limit(page_size))
        return items, total, num_pages

    def create_multisig_identifier(
            self,
            alias: str,
            accounts: List[Tuple[str, str, str]],
            aid: str,
            kel: bytes,
            signing_threshold: Optional[int] = None,
            rotation_threshold: Optional[int] = None,
    ) -> MultisigIdentifier:
        """Creates a new multisig identifier."""

        members = list()
        for (
                account_aid,
                member_signing_threshold,
                member_rotation_threshold,
        ) in accounts:
            account = self.account_service.get_account(account_aid)
            if account is None:
                raise NotFoundError(f"Account not found: {account_aid}")

            members.append(
                MultisigMember(
                    account_aid=account_aid,
                    account_username=account.username,
                    signing_threshold=member_signing_threshold,
                    rotation_threshold=member_rotation_threshold,
                )
            )

        multisig_identifier = MultisigIdentifier(
            alias=alias,
            members=members,
            signing_threshold=signing_threshold,
            rotation_threshold=rotation_threshold,
        )
        try:
            self.parser.parse(ims=bytearray(kel), kvy=self.kvy, local=False)
        except Exception as e:
            raise RuntimeError(f"An error occurred parsing KEL into Kevery: {e}")

        if aid not in self.kvy.kevers:
            raise ValueError(
                f"KEL parsed but AID {aid} not found in kevers — KEL may be incomplete or unverifiable"
            )

        # After capturing the KEL of the new local member AID, set the member AID
        multisig_identifier.members[0].member_aid = aid

        if self.kelSvc is not None:
            try:
                self.kelSvc.capture_kel(aid)
                self.kelSvc.scan_for_delegates(aid)
                self.kelSvc.capture_rpys(aid)

                logger.info(f"KEL captured for aid={aid}")
                if self.hby is not None and self.castellan_hab is not None:
                    group_hab = self.hby.habs.get(aid)
                    if group_hab is not None and isinstance(
                            group_hab, habbing.GroupHab
                    ):
                        role_msgs = group_hab.makeEndRole(
                            eid=self.castellan_hab.pre, role=kering.Roles.mailbox
                        )
                        self.parser.parse(ims=bytearray(role_msgs))
                        logger.info(
                            f"Registered castellan as mailbox for group AID={aid}"
                        )
            except Exception as e:
                raise RuntimeError(f"KEL capture failed for aid={aid}: {e}")

        multisig_identifier.save()

        return multisig_identifier

    def join_multisig(
            self, multisig_id: str, account_aid: str, member_aid: str, kel: bytes
    ) -> MultisigIdentifier:
        """
        Allow a member to join a multisig identifier by providing their member AID and KEL.

        Args:
            multisig_id: The AID of the multisig identifier to join.
            account_aid: The AID of the account attempting to join.
            member_aid: The member's KERI AID prefix.
            kel: Raw CESR-encoded KEL bytes for the member's identifier.

        Returns:
            The updated MultisigIdentifier document.

        Raises:
            NotFoundError: If the multisig identifier is not found.
            PermissionError: If the account is not authorized to join (not in members list).
            ValueError: If the KEL cannot be parsed or the member_aid is invalid.
        """
        if not multisig_id:
            raise ValueError("multisig_id is required")
        if not account_aid:
            raise ValueError("account_aid is required")
        if not member_aid:
            raise ValueError("member_aid is required")
        if not kel:
            raise ValueError("kel is required")

        # Load the multisig identifier
        try:
            multisig = UploadedIdentifier.objects(id=ObjectId(multisig_id)).first()
        except DoesNotExist:
            raise NotFoundError(f"Multisig identifier not found: {multisig_id}")

        # Find the member by account_aid
        member_found = False
        member_index = -1
        for idx, member in enumerate(multisig.members):
            if member.account_aid == account_aid:
                member_found = True
                member_index = idx
                break

        if not member_found:
            raise PermissionError(
                f"Account {account_aid} is not authorized to join this multisig"
            )

        # Validate the KEL
        if self.parser is None or self.kvy is None:
            raise RuntimeError(
                "IdentifierService requires parser and kvy to process KEL"
            )

        try:
            self.parser.parse(ims=bytearray(kel), kvy=self.kvy, local=False)
        except Exception as e:
            raise ValueError(f"An error occurred parsing KEL into Kevery: {e}")

        if member_aid not in self.kvy.kevers:
            raise ValueError(
                f"KEL parsed but AID {member_aid} not found in kevers — KEL may be incomplete or unverifiable"
            )

        # Capture the KEL if kelSvc is available
        if self.kelSvc is not None:
            try:
                self.kelSvc.capture_kel(member_aid)
                self.kelSvc.scan_for_delegates(member_aid)
                self.kelSvc.capture_rpys(member_aid)
                logger.info(f"KEL captured for member_aid={member_aid}")
            except Exception as e:
                raise RuntimeError(
                    f"KEL capture failed for member_aid={member_aid}: {e}"
                )

        # Update the member_aid in the members list
        multisig.members[member_index].member_aid = member_aid
        multisig.save()

        logger.info(
            f"Member {account_aid} joined multisig {multisig_id} with member_aid={member_aid}"
        )

        return multisig

    def submit_multisig_inception(
            self, multisig_id: str, account_aid: str, data: dict, icp: bytes
    ) -> MultisigIdentifier:
        """
        Record that a member has submitted their signature for a multisig identifier.

        Args:
            multisig_id: The AID of the multisig identifier.
            account_aid: The AID of the account submitting their signature.
            data: The data associated with the multisig signature.
            icp: Raw CESR-encoded ICP (inception event) bytes.

        Returns:
            The updated MultisigIdentifier document.

        Raises:
            NotFoundError: If the multisig identifier is not found.
            PermissionError: If the account is not authorized (not in members list).
            ValueError: If the ICP cannot be parsed.
        """
        if not multisig_id:
            raise ValueError("multisig_id is required")
        if not account_aid:
            raise ValueError("account_aid is required")
        if not icp:
            raise ValueError("icp is required")
        if "aid" not in data:
            raise ValueError("data must contain 'aid' key")

        multisig_aid = data["aid"]

        # Load the multisig identifier
        try:
            multisig = MultisigIdentifier.objects.get(id=ObjectId(multisig_id))
        except DoesNotExist:
            raise NotFoundError(f"Multisig identifier not found: {multisig_id}")

        # Find the member by account_aid
        member_found = False
        member_index = -1
        for idx, member in enumerate(multisig.members):
            if member.account_aid == account_aid:
                member_found = True
                member_index = idx
                break

        if not member_found:
            raise PermissionError(
                f"Account {account_aid} is not authorized to sign this multisig"
            )

        inception_event = SerderKERI(raw=bytes(icp))
        if multisig_aid != inception_event.pre:
            raise ValueError("supplied aid does not match inception event pre")

        if multisig.aid is not None:
            if multisig.aid != inception_event.pre:
                raise ValueError("aid does not match inception event pre")
        else:
            multisig.aid = inception_event.pre

        already_complete = multisig_aid in self.kvy.kevers
        try:
            self.parser.parse(ims=bytearray(icp), kvy=self.kvy, local=True)
            self.kvy.processEscrows()
        except Exception as e:
            raise ValueError(f"An error occurred parsing ICP into Kevery: {e}")

        if already_complete:
            return multisig

        # This was the deciding signature and the event is now committed.
        if (
                multisig_aid in self.kvy.kevers
                and inception_event.sner.sn == self.kvy.kevers[multisig_aid].sner.num
        ):
            multisig.key_state = asdict(self.hby.kvy.kevers[multisig_aid].state())
            multisig.current_event = None
            for member in multisig.members:
                member.public_key = None

            multisig.save()

            self.kelSvc.capture_kel(multisig_aid)
            self.kelSvc.scan_for_delegates(multisig_aid)
            self.kelSvc.capture_rpys(multisig_aid)

            return multisig

        multisig.current_event = inception_event.ked

        # Set the public_key flag for this member
        multisig.members[member_index].public_key = inception_event.verfers[
            member_index
        ].qb64
        multisig.save()

        return multisig

    def create_registry(
            self, multisig_id: str, account_aid: str,
            vcp: bytes, ixn: bytes, mailbox: bytes, registrar: bytes,
            body: dict
    ) -> MultisigIdentifier:
        """
        Create a credential registry for a multisig identifier.

        Args:
            multisig_id: The ID of the multisig identifier.
            account_aid: The AID of the account creating the registry.
            vcp: Raw CESR-encoded registry inception event bytes.
            ixn: Raw CESR-encoded interaction event bytes.
            mailbox: Raw CESR-encoded mailbox event bytes.
            registrar: Raw CESR-encoded registrar event bytes.
            body: Additional metadata (optional).

        Returns:
            The updated MultisigIdentifier document with vcp and current_event set.

        Raises:
            ValueError: If required parameters are missing or events cannot be parsed.
            NotFoundError: If the multisig identifier is not found.
            PermissionError: If the account is not authorized (not in members list).
        """
        if not multisig_id:
            raise ValueError("multisig_id is required")
        if not account_aid:
            raise ValueError("account_aid is required")
        if not vcp:
            raise ValueError("vcp is required")
        if not ixn:
            raise ValueError("ixn is required")
        if not mailbox:
            raise ValueError("mailbox is required")
        if not registrar:
            raise ValueError("registrar is required")
        if "name" not in body:
            raise ValueError("registry name is require")

        registry_name = body["name"]

        # Load the multisig identifier
        try:
            multisig = MultisigIdentifier.objects.get(id=ObjectId(multisig_id))
        except DoesNotExist:
            raise NotFoundError(f"Multisig identifier not found: {multisig_id}")

        # Verify account_aid is in the members list
        member_idx = -1
        for idx, member in enumerate(multisig.members):
            if member.account_aid == account_aid:
                member_idx = idx
                break

        if member_idx == -1:
            raise PermissionError(
                f"Account {account_aid} is not authorized to create registry for this multisig"
            )

        # Parse the all the events
        try:
            vcp_event = SerderKERI(raw=bytes(vcp))
        except Exception as e:
            raise ValueError(f"Failed to parse vcp event: {e}")

        try:
            ixn_event = SerderKERI(raw=bytes(ixn))
        except Exception as e:
            raise ValueError(f"Failed to parse ixn event: {e}")
        try:
            mailbox_event = SerderKERI(raw=bytes(mailbox))
        except Exception as e:
            raise ValueError(f"Failed to parse mailbox event: {e}")

        try:
            registrar_event = SerderKERI(raw=bytes(registrar))
        except Exception as e:
            raise ValueError(f"Failed to parse registrar event: {e}")

        # Determine if 1 signature is enough and if so complete the event.
        member_aid = multisig.members[member_idx].member_aid
        tholder = self.hby.kevers[member_aid].tholder
        if tholder.satisfy([member_idx]):
            # Validate the KEL
            if self.parser is None or self.kvy is None:
                raise RuntimeError(
                    "IdentifierService requires parser and kvy to process KEL"
                )

            try:
                self.parser.parse(ims=bytearray(ixn), kvy=self.kvy, local=True)
                self.parser.parse(ims=bytearray(vcp), kvy=self.kvy, local=True)
                self.parser.parse(ims=bytearray(mailbox), kvy=self.kvy, local=True)
                self.parser.parse(ims=bytearray(registrar), kvy=self.kvy, local=True)

            except Exception as e:
                raise ValueError(f"An error occurred parsing KEL into Kevery: {e}")

            multisig.key_state = asdict(self.hby.kvy.kevers[multisig.aid].state())
            multisig.current_event = None
            for member in multisig.members:
                member.public_key = None
                member.current_signature = None
                member.current_lead = False

            multisig.registry = Registry(
                registry_pre=vcp_event.pre,
                registry_said=vcp_event.said,
                registry_name=registry_name,
            )
            multisig.mailbox = True
            multisig.registrar = True

            multisig.save()

            self.kelSvc.capture_kel(multisig.aid)
            self.kelSvc.scan_for_delegates(multisig.aid)
            self.kelSvc.capture_rpys(multisig.aid)

        else:
            # Update the multisig with the registry events
            multisig.current_event = ixn_event.ked
            multisig.members[member_idx].current_signature = ixn[
                ixn_event.size:
            ].decode("utf-8")
            multisig.members[member_idx].current_lead = True
            multisig.current_metadata = dict(registry_name=registry_name)
            multisig.vcp = vcp_event.ked
            multisig.mbx = mailbox_event.ked
            multisig.rgr = registrar_event.ked
            multisig.save()

            logger.info(
                f"Created registry for multisig {multisig_id} by account {account_aid}"
            )

        return multisig

    @staticmethod
    def set_witness_rotate(
            multisig_id: str,
            adds: list[dict],
            cuts: list[str],
            witness_threshold: int,
    ) -> MultisigIdentifier:
        """
        Set the witness rotation configuration for a multisig identifier.

        Args:
            multisig_id: The ID of the multisig identifier.
            adds: List of witness dicts with keys: witness_aid, witness_alias, witness_oobi
            cuts: List of witness AIDs to remove.
            witness_threshold: The new witness threshold.

        Returns:
            The updated MultisigIdentifier document.

        Raises:
            NotFoundError: If the multisig identifier is not found.
            ValueError: If current_event is not empty (operation in progress).
        """
        try:
            multisig = MultisigIdentifier.objects.get(id=ObjectId(multisig_id))
        except DoesNotExist:
            raise NotFoundError(f"Multisig identifier not found: {multisig_id}")

        if multisig.current_event:
            raise ValueError(
                "Cannot set witness rotate while an operation is in progress"
            )

        witness_adds = [
            Witness(
                witness_aid=w["aid"],
                witness_alias=w["alias"],
                witness_oobi=w["oobi"],
            )
            for w in adds
        ]

        witnesses = Witnesses(
            adds=witness_adds,
            cuts=cuts,
            threshold=witness_threshold,
        )

        multisig.witness_rotate = witnesses
        multisig.save()

        logger.info(f"Set witness rotate for multisig {multisig_id}")

        return multisig

    def complete_witness_rotate(
            self, multisig_id, rot: bytes, witness_data: list[dict]
    ):
        try:
            multisig = MultisigIdentifier.objects.get(id=ObjectId(multisig_id))
        except DoesNotExist:
            raise NotFoundError(f"Multisig identifier not found: {multisig_id}")

        if self.parser is None or self.kvy is None:
            raise RuntimeError(
                "IdentifierService requires parser and kvy to process KEL"
            )

        serder = SerderKERI(raw=bytes(rot))
        sn = serder.sn

        try:
            self.parser.parse(ims=bytearray(rot), kvy=self.kvy, local=True)
            self.kvy.processEscrows()

            if int(self.kvy.kevers[multisig.aid].state().s, 16) != sn:
                raise ValueError(
                    f"Invalid witness rotate event for multisig {multisig_id}"
                )

            self.kelSvc.capture_kel(multisig.aid)
            self.kelSvc.scan_for_delegates(multisig.aid)

        except Exception as e:
            raise ValueError(f"An error occurred parsing KEL into Kevery: {e}")

        multisig.key_state = asdict(self.hby.kvy.kevers[multisig.aid].state())
        multisig.current_event = None
        multisig.witness_rotate = None

        for member in multisig.members:
            member.public_key = None
            member.current_signature = None
            member.current_lead = False

        multisig.witnesses = [
            Witness(
                witness_aid=w["aid"],
                witness_alias=w["alias"],
                witness_oobi=w["oobi"],
            )
            for w in witness_data
        ]

        multisig.save()

        return multisig
