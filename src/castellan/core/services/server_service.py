# -*- encoding: utf-8 -*-
import datetime
from dataclasses import asdict

from castellan.core.services.custom.custom_errors import ConflictError
from castellan.core.services.key_event_log_service import KeyEventLogService
from keri.help import ogler
from mongoengine import Document, StringField, IntField

logger = ogler.getLogger()


class Server(Document):
    """Represents an Server with basic personal information."""

    aid = StringField(required=True, primary_key=True)
    ipaddress = StringField(required=True)
    port = IntField(required=True)
    kel = StringField()
    lastModified = IntField()


class ServerService:
    def __init__(self, parser, kvy, kel_service: KeyEventLogService):
        self.parser = parser
        self.kvy = kvy
        self.kel_service = kel_service

        # No need to create collections with mongoengine as it's handled automatically

    @staticmethod
    def server_exists(aid):
        """Check if an server with the given AID exists

        Parameters:
            aid (str): The server ID to check

        Returns:
            bool: True if the server exists, False otherwise
        """
        try:
            return Server.objects(aid=aid).count() > 0
        except Exception as e:
            raise RuntimeError(f"An error occurred while querying server: {e}")

    def create_server(self, doc, kel):
        """Creates a new server and stores it in the Server collection."""
        # Create a new Server document
        server = Server(**doc)
        server.lastModified = int(datetime.datetime.now().timestamp())
        aid = doc["aid"]

        if self.server_exists(server.aid):
            raise ConflictError(f"servers with aid {server.aid} already exists")

        try:
            self.parser.parse(ims=bytearray(kel), kvy=self.kvy, local=True)
        except Exception as e:
            raise RuntimeError(f"An error occurred parsing kel into Kevery: {e}")

        if aid not in self.kvy.kevers:
            raise RuntimeError(
                f"An error occurred parsing kel into Kevery for aid={aid}"
            )

        server.kel = kel.decode("utf-8")
        server.key_state = asdict(self.kvy.kevers[aid].state())

        try:
            # Save the server using mongoengine
            server.save()
            self.kel_service.capture_kel(aid)
            self.kel_service.capture_rpys(aid)

        except Exception as e:
            raise RuntimeError(f"An error occurred saving server: {e}")

        return server

    @staticmethod
    def get_server(key):
        """Get an server by its ID

        Parameters:
            key (str): The server ID

        Returns:
            Server: The server document or None if not found
        """
        try:
            return Server.objects(aid=key).first()
        except Exception:
            return None

    def get_server_by_aid(self, aid):
        """Get an server by its AID

        Parameters:
            aid (str): The server AID

        Returns:
            Server: The server document or None if not found
        """
        try:
            return Server.objects(aid=aid).first()
        except Exception:
            return None

    @staticmethod
    def get_server_by_username(username):
        """Retrieves an Server by its username."""
        try:
            servers = list(Server.objects(username=username))
            count = len(servers)

            if count > 1:
                raise ConflictError(
                    "More than one Server returned for the given username: " + username
                )
            elif count == 0:
                return None

            return servers[0]
        except ConflictError as e:
            raise e
        except Exception as e:
            raise RuntimeError(f"An error occurred querying server: {e}")

    @staticmethod
    def get_server_by_email(email):
        """Retrieves an Server by its email."""
        try:
            servers = list(Server.objects(email=email))
            count = len(servers)

            if count > 1:
                raise ConflictError(
                    "More than one Server returned for the given email: " + email
                )
            elif count == 0:
                return None

            return servers[0]
        except ConflictError as e:
            raise e
        except Exception as e:
            raise RuntimeError(f"An error occurred querying server: {e}")

    @staticmethod
    def list_servers():
        """Returns all Servers in the system."""
        try:
            return list(Server.objects.all())
        except Exception as e:
            raise RuntimeError(f"An error occurred querying servers: {e}")

    @staticmethod
    def count_servers():
        """Returns the number of Servers in the system."""
        try:
            return Server.objects.count()
        except Exception as e:
            raise RuntimeError(f"An error occurred querying servers: {e}")

    @staticmethod
    def async_list_servers(date):
        """List servers modified after a specific date

        Note: This is a synchronous implementation since mongoengine doesn't support
        async queries directly. For true async, you would need to use motor or another
        async MongoDB driver.

        Parameters:
            date (int): Timestamp to filter servers by lastModified

        Returns:
            list: List of servers modified after the given date
        """
        try:
            return list(Server.objects(lastModified__gt=date))
        except Exception as e:
            raise RuntimeError(f"An error occurred querying servers: {e}")

    def delete_server(self, server_id):
        """Delete an server

        Parameters:
            server_id (str): The server ID to delete
        """
        Server.objects(aid=server_id).delete()
