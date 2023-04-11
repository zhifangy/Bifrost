# Bifrost

This package heavily uses [*Simple Slurm*](https://github.com/amq92/simple_slurm) package for reference. The basic usage is mostly the same. In Bifrost, additional parser functions are added to facilitate integration of SLRUM arguement into python script. Also, new methods are added to fine control the array job behavior.  

Basic example:
```python
import datetime

from bifrost import Slurm

slurm = Slurm(
    array=range(3, 12),
    cpus_per_task=15,
    dependency=dict(after=65541, afterok=34987),
    gres=['gpu:kepler:2', 'gpu:tesla:2', 'mps:400'],
    ignore_pbs=True,
    job_name='name',
    output=f'{Slurm.JOB_ARRAY_MASTER_ID}_{Slurm.JOB_ARRAY_ID}.out',
    time=datetime.timedelta(days=1, hours=2, minutes=3, seconds=4),
)
slurm.sbatch(["python demo.py" + slurm.SLURM_ARRAY_TASK_ID])
```
The above snippet is equivalent to submit the following script to SLURM's sbatch command:

```bash
#!/bin/sh

#SBATCH --array               3-11
#SBATCH --cpus-per-task       15
#SBATCH --dependency          after:65541,afterok:34987
#SBATCH --gres                gpu:kepler:2,gpu:tesla:2,mps:400
#SBATCH --ignore-pbs
#SBATCH --job-name            name
#SBATCH --output              %A_%a.out
#SBATCH --time                1-02:03:04

python demo.py $SLURM_ARRAY_TASK_ID
```

## Contents
+ [Introduction](#introduction)
+ [Many syntaxes available](#many-syntaxes-available)
    - [Using configuration files](#using-configuration-files)
    - [Using the command line](#using-the-command-line)
+ [Array job](#array-job)
+ [Parser for python script](#parser-for-python-script)
+ [Job dependencies](#job-dependencies)
+ [Additional features](#additional-features)
    - [Filename Patterns](#filename-patterns)
    - [Output Environment Variables](#output-environment-variables)



## Introduction

The [`sbatch`](https://slurm.schedmd.com/sbatch.html) and [`srun`](https://slurm.schedmd.com/srun.html) commands in [Slurm](https://slurm.schedmd.com/overview.html) allow submitting parallel jobs into a Linux cluster in the form of batch scripts that follow a certain structure.

The goal of this library is to provide a simple wrapper for these functions (`sbatch` and `srun`) so that Python code can be used for constructing and launching the aforementioned batch script.

Indeed, the generated batch script (header) can be shown by printing the `slurm` object:

```python
from bifrost import Slurm

slurm = Slurm(array=range(3, 12), job_name='name')
print(slurm)
```
```bash
>> #!/bin/sh
>>
>> #SBATCH --array               3-11
>> #SBATCH --job-name            name
```

Then, the job can be launched with either command:
```python
slurm.srun(["echo hello!", "echo world!"])
slurm.sbatch(["echo hello!", "echo world!"])
```
Note: the `sbatch` and `srun` accept a list of string as input. Each element in the list represents a single line of command in the script.
```bash
>> Submitted batch job 34987
```

While both commands are quite similar, [`srun`](https://slurm.schedmd.com/srun.html) will wait for the job completion, while [`sbatch`](https://slurm.schedmd.com/sbatch.html) will launch and disconnect from the jobs.
> More information can be found in [Slurm's Quick Start Guide](https://slurm.schedmd.com/quickstart.html) and in [here](https://stackoverflow.com/questions/43767866/slurm-srun-vs-sbatch-and-their-parameters).




## Many syntaxes available

```python
slurm = Slurm('-a', '3-11')
slurm = Slurm('--array', '3-11')
slurm = Slurm('array', '3-11')
slurm = Slurm(array='3-11')
slurm = Slurm(array=range(3, 12))
slurm.add_arguments(array=range(3, 12))
slurm.set_array(range(3, 12))
```

All these arguments are equivalent!
It's up to you to choose the one(s) that best suits you needs.

You can either keep a command-line-like syntax or a more Python-like one

```python
slurm = Slurm()
slurm.set_dependency('after:65541,afterok:34987')
slurm.set_dependency(['after:65541', 'afterok:34987'])
slurm.set_dependency(dict(after=65541, afterok=34987))
```

All the possible arguments have their own setter methods
(ex. `set_array`, `set_dependency`, `set_job_name`).

Please note that hyphenated arguments, such as `--job-name`, need to be underscored
(so to comply with Python syntax and be coherent).

```python
slurm = Slurm('--job_name', 'name')
slurm = Slurm(job_name='name')

# slurm = Slurm('--job-name', 'name')  # NOT VALID
# slurm = Slurm(job-name='name')       # NOT VALID
```

Moreover, boolean arguments such as `--contiguous`, `--ignore_pbs` or `--overcommit`
can be activated with `True` or an empty string.

```python
slurm = Slurm('--contiguous', True)
slurm.add_arguments(ignore_pbs='')
slurm.set_wait(False)
print(slurm)
```
```bash
#!/bin/sh

#SBATCH --contiguous
#SBATCH --ignore-pbs
```




## Array job
The Slurm class provides a method `set_array_info` to help easy indexing a python list using `JOB_ARRAY_ID` environment variable set by SLURM. This is useful if a complex input arguement is needed for the job command.
```python
subject_list = [f"sub-{i:03d}" for i in range(1, 5)]

slurm = Slrum()
slurm.set_array()
slurm.set_array(range(len(subject_list)))
slurm.set_array_info("SUB_ID", subject_list)
slurm.sbatch(["python demo.py --sub_id ${SUB_ID}"])
```
The generated script adds additional lines in the command
```bash
#!/bin/sh

#SBATCH --array               0-3

ARRAY=(sub-001 sub-002 sub-003 sub-004)
SUB_ID=${ARRAY[$SLURM_ARRAY_TASK_ID]}
python demo.py --sub_id ${SUB_ID}"
```




## Parser for python script
Sometimes we want a computation could submit itself. In that case, we could include the parser for SLURM as part of the script and use a special `--submit` argument to control the behavior of the script.  
Here is an example
```python
import argparse
from bifrost import Slurm, add_slurm_argument, select_slurm_arguments

parser = argparse.ArgumentParser(description="Parameters.")
parser.add_argument(
    "--sub_id",
    "--sub-id",
    action="store",
    nargs="*",
    help=(
        "One or more subject identifiers (the sub- prefix should be removed)."
        "If this is omitted, using a pre-defined subject_list."
    ),
)
parser = add_slurm_argument(parser) # adds all SLURM arguments as part of the parser
args = parser.parse_args()

# Select SLURM arguments
# we don't want to pass any user defined, script specific argument to the Slrum class
slurm_args = select_slurm_arguments(args)
slurm_args["job_name"] = "MyTask" # we could also modify arguments in script
# Start SLURM
jobs = Slurm(**slurm_args)
# Submit job and exit script
# the argument --submit could be use to control whether the script should submit itself
# or do the actual computation
if args.submit:
    jobs.sbatch(cmd)
    print(jobs.job_script)
    exit()

# Some fancy computation
answer_to_the_universe = 42
```




## Job dependencies

The `sbatch` call prints a message if successful and returns the corresponding `job_id`

```python
job_id = slurm.sbatch(["python demo.py", slurm.SLURM_ARRAY_TAKSK_ID])
```
or

```python
job_id = slurm.job_id
```

If the job submission was successful, it prints:

```
Submitted batch job 34987
```

And returns the variable `job_id = 34987`, which can be used for setting dependencies on subsequent jobs

```python
slurm_after = Slurm(dependency=dict(afterok=job_id)))
```




## Additional features

For convenience, Filename Patterns and Output Environment Variables are available as attributes of the Slurm class instance.

See [https://slurm.schedmd.com/sbatch.html](https://slurm.schedmd.com/sbatch.html#lbAH) for details on the commands.

```python
from bifrost import Slurm

slurm.set_output(f"{slurm.JOB_ARRAY_MASTER_ID}_{slurm.JOB_ARRAY_ID}.log")
slurm.sbatch(["python demo.py", slurm.SLURM_ARRAY_JOB_ID])
```

This example would result in output files of the form `65541_15.log`.
Here the job submission ID is `65541`, and this output file corresponds to the submission number `15` in the job array. Moreover, this index is passed to the Python code `demo.py` as an argument.




### Filename Patterns

`sbatch` allows for a filename pattern to contain one or more replacement symbols.

They can be accessed with `Slurm.<name>`

name                | value | description
:-------------------|------:|:-----------
JOB_ARRAY_MASTER_ID | %A    |  job array's master job allocation number
JOB_ARRAY_ID        | %a    |  job array id (index) number
JOB_ID_STEP_ID      | %J    |  jobid.stepid of the running job. (e.g. "128.0")
JOB_ID              | %j    |  jobid of the running job
HOSTNAME            | %N    |  short hostname. this will create a separate io file per node
NODE_IDENTIFIER     | %n    |  node identifier relative to current job (e.g. "0" is the first node of the running job) this will create a separate io file per node
STEP_ID             | %s    |  stepid of the running job
TASK_IDENTIFIER     | %t    |  task identifier (rank) relative to current job. this will create a separate io file per task
USER_NAME           | %u    |  user name
JOB_NAME            | %x    |  job name
PERCENTAGE          | %%    |  the character "%"
DO_NOT_PROCESS      | \\\\  |  do not process any of the replacement symbols



### Output Environment Variables

The Slurm controller will set the following variables in the environment of the batch script.

They can be accessed with `Slurm.<name>`.

name                   | description
:----------------------|:-----------
SLURM_ARRAY_TASK_COUNT | total number of tasks in a job array
SLURM_ARRAY_TASK_ID    | job array id (index) number
SLURM_ARRAY_TASK_MAX   | job array's maximum id (index) number
SLURM_ARRAY_TASK_MIN   | job array's minimum id (index) number
SLURM_ARRAY_TASK_STEP  | job array's index step size
SLURM_ARRAY_JOB_ID     | job array's master job id number
...                    | ...

See [https://slurm.schedmd.com/sbatch.html](https://slurm.schedmd.com/sbatch.html#lbAK) for a complete list.
