# -*- encoding: utf-8 -*-
class ConflictError(KeyError):
    pass

class NotFoundError(KeyError):
    pass

class MalformedError(Exception):
    pass

class ValidationError(Exception):
    pass