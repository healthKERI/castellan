# -*- encoding: utf-8 -*-
"""
KERI
hksvc.core.haberying package

"""
from keri.app import habbing


class Hby:
    _hby = {}

    @staticmethod
    def hby(name, base, bran):
        if (name, base, bran) not in Hby._hby:
            hby = habbing.Habery(name=name, base=base, bran=bran)
            Hby._hby[(name, base, bran)] = hby

        return Hby._hby[(name, base, bran)]

