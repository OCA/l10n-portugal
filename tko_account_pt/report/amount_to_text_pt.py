# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.report.int_to_text import int_to_text
from openerp.tools.translate import _
import logging

to_19 = ('Zero',  'Um', 'Dois', 'Três', 'Quatro', 'Cinco', 'Seis', 'Sete',
         'Oito', 'Nove', 'Dez', 'Onze', 'Doze', 'Treze', 'Catorze', 'Quinze',
         'Dezasseies', 'Dezassete', 'Dezoito', 'Dezanove')
tens = ('Vinte', 'Trinta', 'Quarenta', 'Cinquenta', 'Sessenta', 'Setenta',
        'Oitenta', 'Noventa')
denom = ('',
         'Mil', 'Milhão', 'Milhar de Milhão', 'Bilião', 'Milhar de Bilião',
         'Trilião', 'Milhar de Trilião', 'Quatrilião', 'Milhar de Quatrilião',
         'Quintilião', 'Milhar de Quintilião', 'Sextilião',
         'Milhar de Sextilião')
to_900 = ('', 'Cento', 'Duzentos', 'Trezentos', 'Quatrocentos', 'Quinhentos',
          'Seiscentos', 'Setecentos', 'Oitocentos', 'Novecentos')


# convert a value < 100 to Portuguese.
def _convert_nn(val):
    if val < 20:
        return to_19[val]
    for (dcap, dval) in ((k, 20 + (10 * v)) for (v, k) in enumerate(tens)):
        if dval + 10 > val:
            if val % 10:
                return dcap + u' e ' + to_19[val % 10]
            return dcap


# convert a value < 1000 to Portuguese, special cased because it is the level
# that kicks off the < 100 special case.  The rest are more general.  This also
# allows you to get strings in the form of 'forty-five hundred' if called
# directly.
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


def portuguese_number(val):
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
                ret = ret + ', ' + portuguese_number(r)
            return ret


def amount_to_text(number, currency):
    number = '%.2f' % number
    units_name = u'Euros'
    list = str(number).split('.')
    start_word = portuguese_number(int(list[0]))
    end_word = portuguese_number(int(list[1]))
    cents_number = int(list[1])
    cents_name = u'Cêntimo' if cents_number == 1 else u'Cêntimos'
    template = u'{0} {1} e {2} {3}'
    final_result = template.format(
        start_word, units_name, end_word, cents_name)
    return final_result


# -------------------------------------------------------------
# Generic functions
# -------------------------------------------------------------

_translate_funcs = {'pt': amount_to_text}


# TODO: we should use the country AND language (ex: septante VS soixante dix)
# TODO: we should use en by default, but the translation func is yet to be
#  implemented
def amount_to_text(nbr, lang='pt', currency='euro'):
    """
    Converts an integer to its textual representation, using the language
    set in the context if any.
    Example:
        1654: thousands six cent cinquante-quatre.
    """
    if lang not in _translate_funcs:
        msg = _("no translation function found for lang: '%s'") % lang
        logging.getLogger('translate').warning(msg)
        # TODO: (default should be en) same as above
        lang = 'pt'
    return _translate_funcs[lang](abs(nbr), currency)

if __name__ == '__main__':
    from sys import argv

    lang = 'pt'
    if len(argv) < 2:
        for i in range(1, 200):
            logging.info("%s >> %s", i, int_to_text(i, lang))
        for i in range(200, 999999, 139):
            logging.info("%s >> %s", i, int_to_text(i, lang))
    else:
        print int_to_text(int(argv[1]), lang)
