#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Cli parser accepts Slrum arguments."""

# Author: Zhifang Ye
# Email: zhifang.ye.fghm@gmail.com
# Notes:

from __future__ import annotations
from typing import Optional, Union
import os
from pathlib import Path
import argparse

from .utils import read_config_file, format_key


def make_parser_from_file(
    argument_file: Union[Path, str], parser: Optional[argparse.ArgumentParser] = None
) -> argparse.ArgumentParser:
    """Creates/Adds SLURM arguments parser from a text file."""

    if parser is None:
        parser = argparse.ArgumentParser()
    # read arguments from text file
    arguments = read_config_file(argument_file)
    for arg in arguments:
        parser.add_argument(
            *(format_key(a) for a in arg[0:2] if a != ""),
            action=None if arg[2] != "" else "store_true",
            help=arg[3],
        )

    return parser


def add_slurm_argument(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Adds SLURM arguments to existing parser."""

    parser = make_parser_from_file(
        Path(__file__).parent.joinpath("config", "arguments.txt"), parser=parser
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        default=False,
        help="Submit job to SLURM.",
    )

    return parser


def select_slurm_arguments(arguments: argparse.Namespace) -> dict:
    """Selects arguments passes to SLRUM."""

    # read arguments from text file
    valid_args = read_config_file(Path(__file__).parent.joinpath("config", "arguments.txt"))
    valid_args = [arg[0] for arg in valid_args]
    # find SLURM arguments from input
    slurm_args = {}
    for k, v in vars(arguments).items():
        if (k in valid_args) and (v is not None) and (v != False):
            slurm_args[k] = v

    return slurm_args


# def add_slurm_argument(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
#     """Add Slurm arguments onto existed parser."""

#     # yapf: disable
#     slurm = parser.add_argument_group("Options for Slurm")
#     slurm.add_argument(
#         "--submit",
#         action="store_true",
#         default=False,
#         help="Submit job to SLURM.",
#     )
#     slurm.add_argument(
#         "-A",
#         "--account",
#         action="store",
#         default=os.getenv("SLURM_ACCOUNT"),
#         type=str,
#         help="charge job to specified account"
#     )
#     slurm.add_argument(
#         "-p",
#         "--partition",
#         action="store",
#         default=os.getenv("SLURM_PARTITION"),
#         type=str,
#         help="partition requested"
#     )
#     slurm.add_argument(
#         "-N",
#         "--nodes",
#         action="store",
#         default=1,
#         type=int,
#         help="number of nodes on which to run (N = min[-max])"
#     )
#     slurm.add_argument(
#         "-c",
#         # "--n_cpus",
#         "--cpus-per-task",
#         action="store",
#         default=2,
#         type=int,
#         help="number of cpus required per task"
#     )
#     slurm.add_argument(
#         "--mem",
#         action="store",
#         default="8GB",
#         type=str,
#         help="minimum amount of real memory"
#     )
#     slurm.add_argument(
#         "-t",
#         "--time",
#         action="store",
#         default="1-00:00:00",
#         type=str,
#         help="time limit"
#     )
#     slurm.add_argument(
#         "-J",
#         "--job-name",
#         action="store",
#         default="Job",
#         type=str,
#         help="name of job"
#     )
#     slurm.add_argument(
#         "-o",
#         "--output",
#         action="store",
#         default=None,
#         type=str,
#         help="file for batch script's standard output"
#     )
#     slurm.add_argument(
#         "-w",
#         "--nodelist",
#         action="store",
#         default=None,
#         type=str,
#         help="request a specific list of hosts"
#     )
#     slurm.add_argument(
#         "--extra_args",
#         action="store",
#         default=None,
#         nargs="*",
#         help="extra arguments need to forward to SLURM"
#     )
#     # yapf: enable

#     return parser
