#!/usr/bin/env python
# -*- coding: utf-8 -*-
import numpy as np

''' This method returns the index of `time_series` that is closest to `time_point`
    s.t. time_series[index] <= time_point (price is right rules).
'''
def timeToTick(time_series, time_point):
    # Add an offset of a single nanosecond so that if the supplied time_point is at a value that is
    # in the timeseries, then we'll get that tick back, rather than the tick prior
    # A single nanosecond is used under the assumption that we won't ever have a time_series that
    # has a delta t in the nanosecond range.
    res = (np.array(time_series) - (time_point + 1e-9) < 0).nonzero()[0]
    # This will only be the case if time_point is less than time_series[0]
    if len(res) == 0:
        return 0

    return res[-1]

''' This method returns the index of `time_series` that is closest to `time_point` '''
def timeToNearestTick(time_series, time_point):
    return np.argmin(np.abs(np.array(time_series) - time_point))
