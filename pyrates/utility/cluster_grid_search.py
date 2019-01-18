
# -*- coding: utf-8 -*-
#
#
# PyRates software framework for flexible implementation of neural
# network models and simulations. See also:
# https://github.com/pyrates-neuroscience/PyRates
#
# Copyright (C) 2017-2018 the original authors (Richard Gast and
# Daniel Rose), the Max-Planck-Institute for Human Cognitive Brain
# Sciences ("MPI CBS") and contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>
#
# CITATION:
#
# Richard Gast and Daniel Rose et. al. in preparation
"""Functions for performing parameter grid simulations in a compute cluster with pyrates models.
"""

# external imports
import pandas as pd
import numpy as np
import paramiko

# system imports
import json
import getpass
from threading import Thread, currentThread, RLock

# pyrates internal imports
from pyrates.utility.grid_search import linearize_grid

# meta infos
__author__ = "Christoph Salomon"
__status__ = "development"


# TODO: Add filepath to a folder for result files as argument
def cluster_grid_search(hosts, config_file, param_grid=None, **kwargs):
    """

    Parameters
    ----------
    hosts
    config_file
    param_grid
    kwargs

    Returns
    -------

    """
    # If no parameter_grid given, create from config_file.json
    if not param_grid:
        try:
            print(f'Loading config file: {config_file}... ', end="")
            with open(config_file, "r") as file:
                param_dict = json.load(file)
                print("done!")
                print("Creating parameter grid... ", end="")
                try:
                    # Create a pandas.DataFrame() from param_grid{} in param_dict{}
                    param_grid = pd.DataFrame(param_dict["param_grid"])
                    # Add 'status' key for scheduler
                    param_grid['status'] = 'unsolved'
                    print("done!")
                except KeyError as err:
                    # If config_file does not contain a key named 'param_grid':
                    print("\nKeyError:", err)
                    return
        except IOError as err:
            # If config_file does not exist:
            print("\nIOError:", err)
            return
    else:
        print("Linearizing parameter grid...", end="")
        param_grid = linearize_grid(param_grid, permute=True)
        # Add 'status' key for scheduler
        param_grid['status'] = 'unsolved'
        print("done!")

    # TODO: Implement threadpool instead of single threads in a loop
    # TODO: Implement asynchronous computation instead of multithreading

    print("Starting threads...")

    # Get password to connect to remote hosts.
    password = getpass.getpass(
        prompt='Enter password:', stream=None)

    lock = RLock()
    threads = []
    results = pd.DataFrame
    # Start a thread for each host to handle the SSH-connection
    for host in hosts['hostnames']:
        threads.append(spawn_thread(host=host,
                                    host_cmd={'host_env': hosts['host_env'], 'host_file': hosts['host_file']},
                                    param_grid=param_grid,
                                    config_file=config_file,
                                    password=password,
                                    lock=lock,
                                    results=results))

    # Wait for all threads to finish
    for t in threads:
        t.join()

    # print(param_grid)
    print(results)
    # TODO: Create log file


def spawn_thread(host, host_cmd, param_grid, config_file, password, lock, results):
    t = Thread(
        name=host,
        target=thread_master,
        args=(host, host_cmd, param_grid, config_file, password, lock, results)
    )
    t.start()
    return t


def thread_master(host, host_cmd, param_grid, config_file, password, lock, results):
    # Optional via lock: Make sure to connect to every host before starting a computation
    # lock.acquire()
    thread_name = currentThread().getName()

    # TODO: Implement connection with host-key-pairs and no password
    # create SSH Client/Channel
    client = create_ssh_connection(host,
                                   username=getpass.getuser(),
                                   password=password)
    # lock.release()

    # Check if create_ssh_connection() returned 0
    if client:
        # Check if 'status'-key is present in param_grid
        if not fetch_param_idx(param_grid, set_status=False).isnull():

            # host_cmd['host_env']: Path to python executable inside a conda environment with installed packages:
            #   'pandas', 'pyrates'
            # host_cmd['host_file']: Path to python script to execute on the remote host
            command = host_cmd['host_env'] + ' ' + host_cmd['host_file']

            # TODO: Copy environment, script and config to shared or local directory on the remote host
            # Change paths of host_env and host_file respectively

            # TODO: Call exec_command only once and send updated param_grid via stdin to the host inside the loop
            # stdin.write()
            # stdin.flush()

            # Scheduler:
            # fetch_param_idx() returns empty index if all parameter combinations have been calculated
            while not fetch_param_idx(param_grid, set_status=False).empty:

                # Make sure all of the following commands are executed before switching to another thread
                lock.acquire()

                print(f'[T]\'{thread_name}\': Fetching index... ', end="")

                # Get index of a parameter combination that hasn't been computed yet
                param_idx = fetch_param_idx(param_grid)

                # Get parameter combination to pass as argument to the remote host
                param_grid_arg = param_grid.iloc[param_idx]

                print(f'{param_idx}')
                print(f'[T]\'{thread_name}\': Starting remote computation')

                stdin, stdout, stderr = client.exec_command(command +
                                                            f' --param_grid_arg="{param_grid_arg.to_dict()}"'
                                                            f' --config_file={config_file}',
                                                            get_pty=True)

                # While waiting for the remote computation to finish, other threads can now be active
                lock.release()

                # Wait for remote computation to finish
                exit_status = stdout.channel.recv_exit_status()

                # Print what has been sent to the channel standard output (e.g. print())
                for line in iter(stdout.readline, ""):
                    print(f'[H]\'{thread_name}\': {line}', end="")

                # # TODO: How to distinguish between normal prints and result file in stdout?
                # result = pd.read_csv(stdout)


                # TODO: Change status from current param_idx in param_grid from 'pending' to 'done'
        else:
            # If no key named 'status' in param_grid:
            print(f'[T]\'{host}\': "No key named \'status\' in param_grid')

        # TODO: If no shared memory is available, copy result files from host back to local workstation

        # TODO:Change current param_idx in param_grid from 'pending' to 'done'

        client.close()


def create_ssh_connection(host, username, password):
    """Connect to a host via SSH

    Parameters
    ----------
    host
        Name or IP-address of the host to connect to
    username
    password

    Returns
    -------
    paramiko.SSHClient()
        Throws exception and returns 0 if connection fails. See Paramiko documentation


    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f'Attempting to connect to host \'{host}\'...')
    try:
        client.connect(host, username=username, password=password)
        print(f'\'{host}\': Connection established')
        return client
        # return client.invoke_shell()
    except paramiko.ssh_exception.NoValidConnectionsError as err:
        print(f'\'{host}\': ', err)
        return 0
    except paramiko.ssh_exception.AuthenticationException as err:
        print(f'\'{host}\': ', err)
        return 0
    except paramiko.ssh_exception.SSHException as err:
        print(f'\'{host}\': ', err)
        return 0
    except IOError as err:
        print(f'\'{host}\': ', err)
        return 0


def fetch_param_idx(param_grid, num_params=1, set_status=True):
    """Fetch a pandas.Index([index_list]) with the indices of the first num_params rows of param_grid who's
    'status'-key equals 'unsolved'

    Parameters
    ----------
    param_grid
        Linearized parameter grid of type pandas.DataFrame.
    num_params
        Number of indices to fetch from param_grid. Is 1 by default.
    set_status
        If True, sets 'status' key of the fetched rows to 'pending', to exclude them from future calls.
        Can be used to check param_grid for fetchable or existend keys without changing their 'status' key.
        Is True by default.

    Returns
    -------
    pandas.Index([index_list])
        Is empty if there are no row indices to be fetched.
        Is np.nan if param_grid has no key named 'status'.
        Contains all remaining indices if num_params is higher than fetchable row indices.


    """
    try:
        # Get the first num_params row indices of lin_grid who's 'status' keys equal 'unsolved'
        param_idx = param_grid.loc[param_grid['status'] == 'unsolved'].index[:num_params]
    except KeyError:
        return pd.Index([np.nan])
    if set_status:
        param_grid.at[param_idx, 'status'] = 'pending'
    return param_idx


def create_cgs_config(filepath, circuit_template, param_grid, param_map, dt, simulation_time, inputs,
                      outputs, sampling_step_size=None, permute_grid=False, **kwargs):
    """Create a configfile.json containing a config_dict{} with input parameters as key-value pairs

    Parameters
    ----------
    filepath
    circuit_template
    param_grid
    param_map
    dt
    simulation_time
    inputs
    outputs
    sampling_step_size
    permute_grid
    kwargs

    Returns
    -------

    """
    if type(param_grid) is dict:
        # convert linear_grid from dict to pandas.DataFrame.
        param_grid = linearize_grid(param_grid, permute_grid)

    # TODO: Eliminate redundant brackets in inputs in config_file
    config_dict = {
        "circuit_template": circuit_template,
        "param_grid": param_grid.to_dict(),
        "param_map": param_map,
        "dt": dt,
        "simulation_time": simulation_time,
        "inputs": {str(*inputs.keys()): list(*inputs.values())},
        "outputs": outputs,
        "sampling_step_size": sampling_step_size,
        "permute_grid": permute_grid,
        "kwargs": kwargs
    }

    with open(filepath, "w") as f:
        json.dump(config_dict, f, indent=2)
