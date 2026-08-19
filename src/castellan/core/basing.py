# -*- encoding: utf-8 -*-
"""
KERI
castellan.core.basing package

"""

from mongoengine import connect

def databaseInit(host, name, username=None, password=None):
    # Initialize the MongoDB client
    kwa = dict()

    if username:
        kwa["username"] = username

    if password:
        kwa["password"] = password

    connect(db=name, host=host, **kwa)
