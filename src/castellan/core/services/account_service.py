# -*- encoding: utf-8 -*-
import datetime
from dataclasses import asdict

from keri.help import ogler
from mongoengine import Document, StringField, IntField, DictField

from castellan.core.services.custom.custom_errors import ConflictError, NotFoundError

logger = ogler.getLogger()


class Account(Document):
    """ Represents an Account with basic personal information. """

    aid = StringField(required=True, primary_key=True)
    username = StringField(required=True, unique=True)
    email = StringField(required=False)
    first_name = StringField(required=False)
    last_name = StringField(required=False)
    key_state = DictField()
    kel = StringField()
    lastModified = IntField()


class AccountService:
    def __init__(self, parser, kvy):
        self.parser = parser
        self.kvy = kvy

        # No need to create collections with mongoengine as it's handled automatically

    @staticmethod
    def account_exists(aid):
        """Check if an account with the given AID exists
        
        Parameters:
            aid (str): The account ID to check
            
        Returns:
            bool: True if the account exists, False otherwise
        """
        try:
            return Account.objects(aid=aid).count() > 0
        except Exception as e:
            raise RuntimeError(f"An error occurred while querying account: {e}")

    def create_account(self, doc, kel):
        """ Creates a new account and stores it in the Account collection."""
        # Create a new Account document
        account = Account(**doc)
        account.lastModified = int(datetime.datetime.now().timestamp())
        aid = doc['aid']

        if self.account_exists(account.aid):
            raise ConflictError(f"accounts with aid {account.aid} already exists")

        try:
            self.parser.parse(ims=bytearray(kel), kvy=self.kvy, local=True)
        except Exception as e:
            raise RuntimeError(f'An error occurred parsing kel into Kevery: {e}')

        if aid not in self.kvy.kevers:
            raise RuntimeError(f'An error occurred parsing kel into Kevery for aid={aid}')

        account.kel = kel.decode("utf-8")
        account.key_state = asdict(self.kvy.kevers[aid].state())

        try:
            # Save the account using mongoengine
            account.save()
        except Exception as e:
            raise RuntimeError(f'An error occurred saving account: {e}')

        return account

    @staticmethod
    def get_account(key):
        """Get an account by its ID
        
        Parameters:
            key (str): The account ID
            
        Returns:
            Account: The account document or None if not found
        """
        try:
            return Account.objects(aid=key).first()
        except Exception:
            return None

    def get_account_by_aid(self, aid):
        """Get an account by its AID
        
        Parameters:
            aid (str): The account AID
            
        Returns:
            Account: The account document or None if not found
        """
        try:
            return Account.objects(aid=aid).first()
        except Exception:
            return None

    @staticmethod
    def get_account_by_username(username):
        """ Retrieves an Account by its username."""
        try:
            accounts = list(Account.objects(username=username))
            count = len(accounts)
            
            if count > 1:
                raise ConflictError('More than one Account returned for the given username: ' + username)
            elif count == 0:
                return None
                
            return accounts[0]
        except Exception as e:
            raise RuntimeError(f'An error occurred querying account: {e}')

    @staticmethod
    def get_account_by_email(email):
        """ Retrieves an Account by its email."""
        try:
            accounts = list(Account.objects(email=email))
            count = len(accounts)
            
            if count > 1:
                raise ConflictError('More than one Account returned for the given email: ' + email)
            elif count == 0:
                return None
                
            return accounts[0]
        except Exception as e:
            raise RuntimeError(f'An error occurred querying account: {e}')

    @staticmethod
    def list_accounts():
        """ Returns all Accounts in the system."""
        try:
            return list(Account.objects.all())
        except Exception as e:
            raise RuntimeError(f'An error occurred querying accounts: {e}')

    @staticmethod
    def count_accounts():
        """ Returns the number of Accounts in the system."""
        try:
            return Account.objects.count()
        except Exception as e:
            raise RuntimeError(f'An error occurred querying accounts: {e}')

    @staticmethod
    def async_list_accounts(date):
        """List accounts modified after a specific date
        
        Note: This is a synchronous implementation since mongoengine doesn't support
        async queries directly. For true async, you would need to use motor or another
        async MongoDB driver.
        
        Parameters:
            date (int): Timestamp to filter accounts by lastModified
            
        Returns:
            list: List of accounts modified after the given date
        """
        try:
            return list(Account.objects(lastModified__gt=date))
        except Exception as e:
            raise RuntimeError(f'An error occurred querying accounts: {e}')

    def update_account(self, aid, doc, kel=None):
        """Update an account
        
        Parameters:
            aid (str): The account ID to update
            doc (dict): Dictionary of fields to update
            kel (bytes, optional): Key event log to update
            
        Raises:
            NotFoundError: If the account is not found
            RuntimeError: If there's an error updating the account
        """
        account = self.get_account(aid)
        if account is None:
            raise NotFoundError('Account not found: ' + aid)

        # Set lastModified timestamp
        account.lastModified = int(datetime.datetime.now().timestamp())
        update = False

        # Update fields from the input doc
        for field_name in doc:
            if field_name == 'aid':
                continue
                
            if hasattr(account, field_name):
                update = True
                setattr(account, field_name, doc[field_name])

        # Process KEL if provided
        if kel is not None:
            aid = account.aid
            sn = self.kvy.kevers[aid].serder.sn
            try:
                self.parser.parse(ims=bytearray(kel), kvy=self.kvy, local=True)
            except Exception as e:
                raise RuntimeError(f'An error occurred parsing kel into Kevery: {e}')
    
            if self.kvy.kevers[aid].serder.sn > sn:
                update = True
                account.key_state = self.kvy.kevers[aid].state().dict()
                account.kel = kel.decode("utf-8")

        if not update:
            return

        try:
            account.save()
            return account
        except Exception as e:
            raise RuntimeError(f'Error {e} updating account {account.aid}')

    def delete_account(self, account_id):
        """Delete an account
        
        Parameters:
            account_id (str): The account ID to delete
        """
        Account.objects(aid=account_id).delete()
