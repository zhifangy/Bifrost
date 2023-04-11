#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Generic utility functions."""

# Author: Zhifang Ye
# Email: zhifang.ye.fghm@gmail.com
# Notes:

from __future__ import annotations
from typing import Iterable, Optional, Union
from pathlib import Path
import math
import datetime


IGNORE_BOOLEAN = "IGNORE_BOOLEAN"


def read_config_file(filename: Union[Path, str]) -> list:
    """Reads SLURM arguments/variables text file."""

    with open(filename) as f:
        lines = f.readlines()
    lines = [[i.strip() for i in line.split(",")] for line in lines]

    return lines


def format_key(key: str) -> str:
    """Formats key in argument form."""
    key = str(key).strip()
    if "-" not in key:
        key = f"--{key}" if len(key) > 1 else f"-{key}"
    return key


def format_value(value) -> str:
    """Maintain correct formatting for values in key-value pairs
    This function handles some special cases for the type of value:
        1) A 'range' object:
            Converts range(3, 15) into '3-14'.
            Useful for defining job arrays using a Python syntax.
            Note the correct form of handling the last element.
        2) A 'dict' object:
            Converts dict(after=65541, afterok=34987)
            into 'after:65541,afterok:34987'.
            Useful for arguments that have multiple 'sub-arguments',
            such as when declaring dependencies.
        3) A `datetime.timedelta` object:
            Converts timedelta(days=1, hours=2, minutes=3, seconds=4)
            into '1-02:03:04'.
            Useful for arguments involving time durations.
        4) An `iterable` object:
            Will recursively format each item
            Useful for defining lists of parameters
    """
    if isinstance(value, str):
        pass

    elif isinstance(value, range):
        start, stop, step = value.start, value.stop - 1, value.step
        value = f"{start}-{stop}" + ("" if value.step == 1 else f":{step}")

    elif isinstance(value, dict):
        value = ",".join((f"{k}:{format_value(v)}" for k, v in value.items()))

    elif isinstance(value, datetime.timedelta):
        time_format = "{days}-{hours2}:{minutes2}:{seconds2}"
        value = format_timedelta(value, time_format=time_format)

    elif isinstance(value, Iterable):
        value = ",".join((format_value(item) for item in value))

    elif isinstance(value, bool):
        value = "" if value else IGNORE_BOOLEAN

    return str(value).strip()


def format_timedelta(value: datetime.timedelta, time_format: str):
    """Format a datetime.timedelta (https://stackoverflow.com/a/30339105)"""
    if hasattr(value, "seconds"):
        seconds = value.seconds + value.days * 24 * 3600
    else:
        seconds = int(value)

    seconds_total = seconds

    minutes = int(math.floor(seconds / 60))
    minutes_total = minutes
    seconds -= minutes * 60

    hours = int(math.floor(minutes / 60))
    hours_total = hours
    minutes -= hours * 60

    days = int(math.floor(hours / 24))
    days_total = days
    hours -= days * 24

    years = int(math.floor(days / 365))
    years_total = years
    days -= years * 365

    return time_format.format(
        **{
            "seconds": seconds,
            "seconds2": str(seconds).zfill(2),
            "minutes": minutes,
            "minutes2": str(minutes).zfill(2),
            "hours": hours,
            "hours2": str(hours).zfill(2),
            "days": days,
            "years": years,
            "seconds_total": seconds_total,
            "minutes_total": minutes_total,
            "hours_total": hours_total,
            "days_total": days_total,
            "years_total": years_total,
        }
    )


def convert_to_gb(value: str) -> str:
    """
    Convert memory capacity string to a uniform representation in GB.

    From https://github.com/nipreps/fmriprep/blob/4bb8a61cde27575865cdd2b7df5afcb5d6860523/fmriprep/cli/parser.py#L40
    """

    scale = {"G": 1, "T": 10**3, "M": 1e-3, "K": 1e-6, "B": 1e-9}
    digits = "".join([c for c in value if c.isdigit()])
    units = value[len(digits) :] or "M"

    return int(digits) * scale[units[0]]
