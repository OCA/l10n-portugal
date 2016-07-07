#!/usr/bin/env python
# -*- coding: utf-8 -*-
##########################################################################
#
# Copyright (C) ThinkOpen Solutions (<http://thinkopen.solutions>).
# All Rights Reserved
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3.0 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.
#
##########################################################################

"""
Extension of the datetime module to suit HRSelf project needs.
"""

import datetime
from datetime import timedelta
import types
import xmlrpclib

DAY = DAYS = timedelta(days=1)

DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
XML_RPC_DATETIME_FORMAT = '%Y%m%dT%H:%M:%S'


def to_date(obj, date_format=None):
    """
    Converts an object representing a date(time) into a date.
    @param obj: an object representing a date(time)
    @param date_format: an optional date format
    @return: a date
    @rtype: datetime.date
    """
    if isinstance(obj, datetime.datetime):
        res = obj.date()
    elif isinstance(obj, datetime.date):
        res = obj
    elif isinstance(obj, xmlrpclib.DateTime):
        res = to_date(obj.value, XML_RPC_DATETIME_FORMAT)
    elif isinstance(obj, types.StringTypes):
        if date_format is not None:
            res = datetime.datetime.strptime(obj, date_format).date()
        else:
            try:
                res = to_date(obj, DATE_FORMAT)
            except ValueError:
                res = to_date(obj, DATETIME_FORMAT)
    else:
        raise TypeError("type object %s is not date/datetime like" % type(obj))
    return res


def to_datetime(obj, datetime_format=None):
    """
    Converts an object representing a date(time) into a datetime.
    @param obj: an object representing a date(time)
    @param datetime_format: an optional datetime format
    @return: a datetime
    @rtype: datetime.datetime
    """
    if isinstance(obj, datetime.datetime):
        res = obj
    elif isinstance(obj, datetime.date):
        res = datetime.datetime(obj.year, obj.month, obj.day)
    elif isinstance(obj, xmlrpclib.DateTime):
        res = to_datetime(obj.value, XML_RPC_DATETIME_FORMAT)
    elif isinstance(obj, types.StringTypes):
        if datetime_format is not None:
            res = datetime.datetime.strptime(obj, datetime_format)
        else:
            try:
                res = to_datetime(obj, DATETIME_FORMAT)
            except ValueError:
                res = to_datetime(obj, DATE_FORMAT)
    else:
        raise TypeError("type object %s is not date/datetime like" % type(obj))
    return res


def to_string(obj, date_format=DATE_FORMAT, datetime_format=DATETIME_FORMAT):
    """
    Converts an object representing a date(time) into a string.
    @param obj: an object representing a date(time)
    @param date_format: an optional date format
    @param datetime_format: an optional datetime format
    @return: a string
    @rtype: str
    """
    if isinstance(obj, datetime.datetime):
        res = obj.strftime(datetime_format)
    elif isinstance(obj, datetime.date):
        res = obj.strftime(date_format)
    elif isinstance(obj, xmlrpclib.DateTime):
        res = obj.value
    elif isinstance(obj, types.StringTypes):
        res = obj
    else:
        raise TypeError("type object %s is not date/datetime like" % type(obj))
    return res


class period(object):

    """Time interval between two dates (inclusive)."""

    def __init__(self, start, end=None):
        self.start = to_date(start)
        self.end = end and to_date(end)

    def __contains__(self, obj):
        date = to_date(obj)
        return self.start <= date and (not self.end or date <= self.end)

if __name__ == '__main__':
    d = datetime.date(2010, 1, 1)
    dt = datetime.datetime(2010, 1, 2, 3, 4, 5)
    assert to_date(d) == d
    assert to_datetime(d) == datetime.datetime(2010, 1, 1, 0, 0, 0)
    assert to_string(d) == "2010-01-01"
    assert to_date(dt) == datetime.date(2010, 1, 2)
    assert to_datetime(dt) == dt
    assert to_string(dt) == "2010-01-02 03:04:05"

    assert to_date("2010-01-01") == datetime.date(2010, 1, 1)
    assert to_date("2010-01-02 08:00:00") == datetime.date(2010, 1, 2)
    assert to_datetime("2010-01-03") == datetime.datetime(2010, 1, 3, 0, 0)
    assert to_datetime("2010-01-04 08:00:00") == \
        datetime.datetime(2010, 01, 4, 8, 0, 0)
    assert to_string("2010-01-05") == "2010-01-05"
    assert to_string("2010-01-06 08:00:00") == "2010-01-06 08:00:00"
