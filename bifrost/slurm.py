#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations
from typing import Union
import os
from pathlib import Path
import subprocess
import argparse
import time

from .utils import read_config_file, format_key, format_value, IGNORE_BOOLEAN


class Slurm:
    """Simple Slurm class for running sbatch commands.

    See https://slurm.schedmd.com/sbatch.html for a complete list of arguments
    accepted by the sbatch command (ex. -a, --array).

    Validation of arguments is handled by the argparse module.

    Multiple syntaxes are allowed for defining the arguments.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the parser with the given arguments."""

        __pkg_path = Path(__file__).parent
        self.namespace = Namespace()
        self.log_dir = os.getcwd()

        # Create SLURM argument parser
        arguments = read_config_file(__pkg_path.joinpath("config", "arguments.txt"))
        self.parser = argparse.ArgumentParser()
        for arg in arguments:
            self.parser.add_argument(*(format_key(a) for a in arg[0:2] if a != ""), help=arg[3])

        # Add filename patterns as static variables
        for pattern in read_config_file(__pkg_path.joinpath("config", "filename_patterns.txt")):
            setattr(self, *pattern)

        # Add output environment variables as static variables
        for (var,) in read_config_file(__pkg_path.joinpath("config", "output_env_vars.txt")):
            setattr(self, var, "$" + var)

        # Create setter methods for each argument
        for arg in read_config_file(__pkg_path.joinpath("config", "arguments.txt")):
            self._create_setter_method(arg[0])

        # Add provided arguments in constructor
        self.add_arguments(*args, **kwargs)

        # Set default values for common arguments (if not provided)
        self._set_defaults()

    def __str__(self) -> str:
        """Prints the generated sbatch script."""
        return self.format_arguments()

    def __repr__(self) -> str:
        """Prints the argparse namespace."""
        return repr(vars(self.namespace))

    def add_arguments(self, *args, **kwargs):
        """Parses the given key-value pairs.

        Both syntaxes *args and **kwargs are allowed, ex:
            add_arguments('arg1', val1, 'arg2', val2, arg3=val3, arg4=val4)
        """

        for key, value in zip(args[0::2], args[1::2]):
            self._parse_argument(key, value)
        for key, value in kwargs.items():
            self._parse_argument(key, value)

        return self

    def set_log_dir(self, log_dir: Union[Path, str]):
        """Set log file directory."""

        self.log_dir = Path(log_dir).as_posix()
        # also reset output argument
        self.namespace.output = (
            Path(self.log_dir).joinpath(f"{self.JOB_NAME}_{self.JOB_ID}.log").as_posix()
        )

    def set_array_info(self, array_variable: str, array_list: list[Union[str, int, float]]):
        """Set useful information for array job."""

        self.additional_array_info = True
        self.array_variable = array_variable  # could be used in command as variable
        self.array_list = f"{' '.join(array_list)}"
        self.array_command = [
            f"ARRAY=({self.array_list})",
            f"{self.array_variable}=${{ARRAY[{self.SLURM_ARRAY_TASK_ID}]}}",
        ]

    def format_arguments(self, shell: str = "/bin/sh", script_mode: bool = True) -> str:
        """Formats Slrum arguments for script or commandline usage."""
        if script_mode:
            args = [
                f"#SBATCH --{self._valid_key(k):<19} {v}"
                for k, v in vars(self.namespace).items()
                if v is not None
            ]
            args = "\n".join([f"#!{shell}", ""] + args)
        else:
            args = []
            for k, v in vars(self.namespace).items():
                if v is not None:
                    if v != "":
                        args.append(f"--{self._valid_key(k)}={v}")
                    else:
                        args.append(f"--{self._valid_key(k)}")
            args = " ".join(args)

        return args

    def wrap_command_to_script(
        self, command: Union[str, list[str]], shell: str = "/bin/sh"
    ) -> str:
        """Wraps command into a script string for sbatch."""

        command = self._preprocess_command(command, convert=False)
        if self.additional_array_info:
            command = self.array_command + command
        self._modify_log_filename()
        script = [self.format_arguments(shell=shell)] + [""] + command
        script = "\n".join(script)

        return script

    def wrap_command_to_argument(
        self, command: Union[str, list[str]], convert: bool = True
    ) -> str:
        """Wraps command into a script string for sbatch."""

        command = self._preprocess_command(command, convert=convert)
        if self.additional_array_info:
            command = self._preprocess_command(self.array_command, convert=convert) + command
        command = "; ".join(command)
        command = [f'--wrap="{command}"']
        self._modify_log_filename()
        script = [self.format_arguments(script_mode=False)] + command
        script = " ".join(script)

        return script

    def sbatch(
        self, command: Union[str, list[str]], shell: str = "/bin/sh", verbose: bool = True
    ) -> str:
        """Submits commands to SLURM through sbatch."""

        # Submit job
        script = self.wrap_command_to_script(command=command, shell=shell)
        self.job_script = script
        proc = subprocess.run(
            ["sbatch"], input=script, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        # Check job submission
        success_msg = "Submitted batch job"
        if not success_msg in proc.stdout:
            print(proc.stdout)
            raise RuntimeError("SLURM job submission failed.")
        if verbose:
            print(proc.stdout)
        # Record job id
        job_id = proc.stdout.split(" ")[3].replace("\n", "")
        self.job_id = job_id

        return job_id

    def srun(self, command: Union[str, list[str]]) -> int:
        """Runs commands through SLURM srun."""

        args = self.format_arguments(script_mode=False)
        command = self._preprocess_command(command, convert=False)
        command = "; ".join(command)
        command = f"sh -c '({command})'"
        srun_cmd = "srun " + args + " " + command
        print(srun_cmd)
        # Run command
        proc = subprocess.run(
            srun_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )

        return proc.returncode

    def write_command_to_file(
        self, command: Union[str, list[str]], out_file: Union[Path, str], shell: str = "/bin/sh"
    ):
        """Writes command to a sbatch ready file."""

        command = self._preprocess_command(command, convert=False)
        if self.additional_array_info:
            command = self.array_command + command
        script = [self.format_arguments(shell=shell)] + [""] + command
        script = "\n".join(script)
        with open(out_file, "w") as f:
            f.write(script)

    def get_status(self):
        """Gets submitted job status."""
        return print(get_status(self.job_id))

    def get_job_info(
        self,
        output_format: str = "default",
        no_header: bool = False,
        allocations: bool = True,
        extra_args: list[str] = [],
    ):
        """Gets submitted job information."""
        return print(
            get_job_info(
                self.job_id,
                output_format=output_format,
                no_header=no_header,
                allocations=allocations,
                extra_args=extra_args,
            )
        )

    def wait_completion(self) -> dict[str, str]:
        """Waits until the submitted job finished."""
        return wait_completion(self.job_id)

    def _parse_argument(self, key: str, value: str):
        """Parses the given key-value pair."""
        key, value = format_key(key), format_value(value)
        if value is not IGNORE_BOOLEAN:
            self.parser.parse_args([key, value], namespace=self.namespace)

    def _create_setter_method(self, key: str):
        """Creates the setter method for the given 'key'."""

        # function needs to be bound to the Slrum instance
        def set_key(value):
            return self.add_arguments(key, value)

        set_key.__name__ = f"set_{key}"
        set_key.__doc__ = f'Setter method for the argument "{key}"'
        setattr(self, set_key.__name__, set_key)

    def _set_defaults(self):
        """Sets default values for arguments (if not provided)."""
        if (self.namespace.account is None) and (os.getenv("SLURM_ACCOUNT") is not None):
            self.namespace.account = os.getenv("SLURM_ACCOUNT")
        if (self.namespace.partition is None) and (os.getenv("SLURM_PARTITION") is not None):
            self.namespace.partition = os.getenv("SLURM_PARTITION")
        if (self.namespace.mail_user is None) and (os.getenv("SLURM_NOTIFY_EMAIL") is not None):
            self.namespace.mail_user = os.getenv("SLURM_NOTIFY_EMAIL")
        if self.namespace.nodes is None:
            self.nodes = 1
        if self.namespace.cpus_per_task is None:
            self.namespace.cpus_per_task = 2
        if self.namespace.mem is None:
            self.namespace.mem = "8GB"
        if self.namespace.time is None:
            self.namespace.time = "3-00:00:00"
        if self.namespace.job_name is None:
            self.namespace.job_name = "Job"
        # job log file
        if self.namespace.output is None:
            if os.getenv("LOG_DIR") is not None:
                self.log_dir = os.getenv("LOG_DIR")
            self.namespace.output = (
                Path(self.log_dir).joinpath(f"{self.JOB_NAME}_{self.JOB_ID}.log").as_posix()
            )
            self.custom_output = False
        else:
            self.custom_output = True
        self.additional_array_info = False

    def _modify_log_filename(self):
        """Modify output log filename to contain array information."""

        if (self.namespace.array is not None) and (not self.custom_output):
            self.namespace.output = Path(self.log_dir).joinpath(
                f"{self.JOB_NAME}_{self.JOB_ARRAY_MASTER_ID}_{self.JOB_ARRAY_ID}.log"
            )

    @staticmethod
    def _valid_key(key: str) -> str:
        """Long arguments (for slurm) constructed with '-' have been internally
        represented with '_' (for Python). Correct for this in the output.
        """
        return key.replace("_", "-")

    @staticmethod
    def _preprocess_command(command: Union[str, list[str]], convert: bool = False) -> list[str]:
        """Preprocess command for later use."""

        if not isinstance(command, (list, str)):
            raise TypeError("Argument command needs to be a string or a list of string.")
        if isinstance(command, str):
            command = [command]
        # escape $ symbol if needed
        command = [i.replace("$", "\\$") if convert else i for i in command]

        return command


class Namespace:
    """Dummy class required for accessing the arguments in argparse."""

    pass


def get_queue(
    user_id: str = None,
    account_id: str = None,
    no_header: bool = False,
    extra_args: list[str] = [],
) -> str:
    """Gets SLURM queue information."""

    cmd = ["squeue"] + extra_args
    cmd += ["--user", user_id] if user_id else []
    cmd += ["--account", account_id] if account_id else []
    cmd += ["--noheader"] if no_header else []
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    return proc.stdout


def get_job_info(
    job_id: Union[int, str],
    output_format: str = "default",
    no_header: bool = False,
    allocations: bool = True,
    extra_args: list[str] = [],
) -> str:
    """Gets SLURM job information."""
    cmd = ["sacct", "-j", job_id] + extra_args
    cmd += ["-n"] if no_header else []
    cmd += ["-X"] if allocations else []
    if output_format == "default":
        cmd += [
            "--format",
            ",".join(
                [
                    "JobID%20",
                    "JobName%25",
                    "State",
                    "Partition",
                    "Elapsed",
                    "AllocCPUS",
                    "AllocNodes",
                ]
            ),
        ]
    else:
        cmd += ["--format", output_format]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    return proc.stdout


def get_status(job_id: Union[int, str]) -> dict:
    """Gets a SLRUM job status."""
    job_info = get_job_info(
        job_id,
        output_format="JobID,State",
        no_header=True,
        extra_args=["--parsable2"],
    ).split("\n")

    status = dict()
    for line in job_info:
        if not line == "":
            status[line.split("|")[0]] = line.split("|")[1]

    return status


def wait_completion(job_id: Union[int, str, list[Union[int, str]]]) -> dict[str, str]:
    """Waits until a SLRUM job finished."""

    print(f"Waiting job: {job_id} to finish...")
    while True:
        job_status = get_status(job_id)
        if len(job_status) > 0:
            # All jobs are successfully finished
            if _all_status(job_status, "COMPLETED"):
                print("All jobs have successfully finished.")
                break
            # Any job is not in RUNNING or PENDING state
            elif (not _any_status(job_status, "RUNNING")) and (
                not _any_status(job_status, "PENDING")
            ):
                error_job_id = [
                    i for i, j in job_status.items() if j not in ["RUNNING", "PENDING"]
                ]
                print("Failed jobs:\n")
                get_queue(extra_args=["-j", error_job_id])
                break
            # Special case for PENDING due to "ReqNodeNotAvail, Reserved for maintenance"
            if _any_status(job_status, "PENDING"):
                pending_job_id = [i for i, j in job_status.items() if j == "PENDING"]
                queue_info = get_queue(extra_args=["-j", pending_job_id]).split("\n")
                print("Failed jobs:\n")
                print(queue_info[0])
                for i in [i for i in queue_info if "ReqNodeNotAvail" in i]:
                    print(i)
                break
        time.sleep(10)
    return job_status


def _any_status(job_status: dict[str, str], status: str):
    return any([i == status for i in job_status.values()])


def _all_status(job_status: dict[str, str], status: str):
    return all([i == status for i in job_status.values()])
