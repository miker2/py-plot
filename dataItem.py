# -*- coding: utf-8 -*-


class dataItem(object):
    '''
        Data structure for storing data items in the list widget
    '''
    def __init__(self, var_name, data):
        self._var_name = var_name
        self._data = data
        self._time = None

    @property
    def var_name(self):
        return self._var_name

    @property
    def data(self):
        return self._data

    @property
    def time(self):
        return self._time

    def __repr__(self):
        return self._var_name
