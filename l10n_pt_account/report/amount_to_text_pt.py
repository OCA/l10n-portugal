# -*- coding: utf-8 -*-
# Copyright 2010-2016 ThinkOpen Solutions
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)./

###########
# ENGLISH #
###########

from openerp.tools.translate import _

import logging

to_19 = ('Zero',  'Um', 'Dois', 'Três', 'Quatro', 'Cinco', 'Seis',
         'Sete', 'Oito', 'Nove', 'Dez', 'Onze', 'Doze', 'Treze',
         'Catorze', 'Quinze', 'Dezasseies', 'Dezassete', 'Dezoito', 'Dezanove')
tens = ('Vinte', 'Trinta', 'Quarenta', 'Cinquenta',
        'Sessenta', 'Setenta', 'Oitenta', 'Noventa')
denom = ('',
         'Mil', 'Milhão', 'Milhar de Milhão', 'Bilião', 'Milhar de Bilião',
         'Trilião', 'Milhar de Trilião', 'Quatrilião', 'Milhar de Quatrilião',
         'Quintilião', 'Milhar de Quintilião', 'Sextilião',
         'Milhar de Sextilião')
to_900 = ('', 'Cento', 'Duzentos', 'Trezentos',
          'Quatrocentos', 'Quinhentos', 'Seiscentos',
          'Setecentos', 'Oitocentos', 'Novecentos')

# convert a value < 100 to English.


def _convert_nn(val):
    if val < 20:
        return to_19[val]
    for (dcap, dval) in ((k, 20 + (10 * v)) for (v, k) in enumerate(tens)):
        if dval + 10 > val:
            if val % 10:
                return dcap + '' + ' e ' + '' + to_19[val % 10]
            return dcap

# convert a value < 1000 to english, special cased because it is the
# level that kicks off the < 100 special case.  The rest are more general.
# This also allows you to get strings in the form of 'forty-five hundred'
# if called directly.


def _convert_nnn(val):
    word = ''
    (mod, rem) = (val % 100, val // 100)
    if rem > 0:
        word = to_900[rem]
        if val == 100:
            word = 'Cem'
        if mod > 0:
            word = word + ' e '
    if mod > 0:
        word = word + _convert_nn(mod)
    return word


def english_number(val):
    if val < 100:
        return _convert_nn(val)
    if val < 1000:
        return _convert_nnn(val)
    for (didx, dval) in ((v - 1, 1000 ** v) for v in range(len(denom))):
        if dval > val:
            mod = 1000 ** didx
            l = val // mod
            r = val - (l * mod)
            ret = _convert_nnn(l) + ' ' + denom[didx]
            if mod == 1000 and l == 1:
                ret = 'Mil'
            if r > 0:
                ret = ret + ', ' + english_number(r)
            return ret


def amount_to_text(number, currency):
    number = '%.2f' % number
    units_name = 'Euros'
    list = str(number).split('.')
    start_word = english_number(int(list[0]))
    end_word = english_number(int(list[1]))
    cents_number = int(list[1])
    cents_name = (cents_number > 1 or cents_number ==
                  0) and 'Cêntimos' or 'Cêntimo'
    final_result = start_word + ' ' + units_name + \
        ' e ' + end_word + ' ' + cents_name
    return final_result


#####################
# Generic functions #
#####################

_translate_funcs = {'pt': amount_to_text}

# TODO: we should use the country AND language (ex: septante VS soixante dix)
# TODO: we should use en by default, but the translation func is yet to be
# implemented


def amount_to_text(nbr, lang='pt', currency='euro'):
    """
    Converts an integer to its textual representation,
    using the language set in the context if any.
    Example:
        1654: thousands six cent cinquante-quatre.
    """
    if lang not in _translate_funcs:
        logging.getLogger('translate').warning(
            _("no translation function found for lang: '%s'" % lang))
        # TODO: (default should be en) same as above
        lang = 'pt'
    return _translate_funcs[lang](abs(nbr), currency)