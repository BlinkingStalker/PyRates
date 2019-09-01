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

# system imports
import os
import sys
import ast
import json
import time
import argparse
import warnings

# external imports
from numba import njit, config
import numpy as np
import pandas as pd
from pyrates.utility.grid_search import grid_search


def load_config(config_file):
    with open(config_file) as g_conf:
        config_dict = json.load(g_conf)

    if 'sampling_step_size' not in config_dict.keys():
        config_dict['sampling_step_size'] = config_dict['dt']

    if 'backend' not in config_dict.keys():
        config_dict['backend'] = 'numpy'

    try:
        inputs_temp = config_dict['inputs']
        if inputs_temp:
            inputs = {}
            for key, value in inputs_temp.items():
                inputs[ast.literal_eval(key)] = list(value)
            config_dict['inputs'] = inputs
        else:
            config_dict['inputs'] = {}
    except KeyError:
        config_dict['inputs'] = {}

    try:
        outputs_temp = config_dict['outputs']
        if outputs_temp:
            outputs = {}
            for key, value in outputs_temp.items():
                outputs[str(key)] = tuple(value)
            config_dict['outputs'] = outputs
        else:
            config_dict['outputs'] = {}
    except KeyError:
        config_dict['outputs'] = {}

    return config_dict


def run_grid_search(conf, param_grid, build_dir):
    results, _t, _ = grid_search(
        circuit_template=conf["circuit_template"],
        param_grid=param_grid,
        param_map=conf["param_map"],
        simulation_time=conf["simulation_time"],
        dt=conf["dt"],
        sampling_step_size=conf["sampling_step_size"],
        permute_grid=False,
        inputs=conf["inputs"],
        outputs=conf["outputs"],
        init_kwargs={
            'backend': conf['backend'],
            'vectorization': 'nodes'
        },
        profile='t',
        build_dir=build_dir,
        decorator=njit,
        parallel=False)

    return results


def main(_):
    config.THREADING_LAYER = 'omp'

    # Disable general warnings
    warnings.filterwarnings("ignore")

    # disable TF-gpu warnings
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    t_total = time.time()

    # Load command line arguments and create logfile
    ################################################
    print("")
    print("***LOADING COMMAND LINE ARGUMENTS***")
    t0 = time.time()

    config_file = FLAGS.config_file
    subgrid = FLAGS.subgrid
    local_res_file = FLAGS.local_res_file
    build_dir = FLAGS.build_dir

    print(f'Elapsed time: {time.time()-t0:.3f} seconds')

    # Load grid search configuration parameters from config file
    ############################################################
    print("")
    print("***LOADING GLOBAL CONFIG FILE***")
    t0 = time.time()

    config_dict = load_config(config_file=config_file)

    print(f'Elapsed time: {time.time()-t0:.3f} seconds')

    # Load parameter subgrid from subgrid file
    ##########################################
    print("")
    print("***PREPARING PARAMETER GRID***")
    t0 = time.time()

    param_grid = pd.read_hdf(subgrid, key="subgrid")

    # Drop all columns that don't contain a parameter map value (e.g. status, chunk_idx, err_count) since grid_search()
    # can't handle additional columns
    param_grid = param_grid[list(config_dict['param_map'].keys())]
    print(f'Elapsed time: {time.time()-t0:.3f} seconds')

    # Compute parameter subgrid using grid_search
    #############################################
    print("")
    print("***COMPUTING PARAMETER GRID***")
    t0 = time.time()

    results = run_grid_search(conf=config_dict, param_grid=param_grid, build_dir=build_dir)

    out_vars = results.columns.levels[-1]

    print(f'Total parameter grid computation time: {time.time()-t0:.3f} seconds')

    # Post process results and write data to local result file
    ##########################################################
    print("")
    print("***POSTPROCESSING AND CREATING RESULT FILES***")
    t0 = time.time()

    with pd.HDFStore(local_res_file, "w") as store:
        for out_var in out_vars:
            res_lst = []

            # Order results according to rows in parameter grid
            ###################################################
            # Iterate over rows in param_grid and use its values to index columns in results
            for i, column_values in enumerate(param_grid.values):
                result = results.loc[:, tuple([column_values, out_var])]
                result.columns.names = results.columns.names
                res_lst.append(result)

            # Concatenate all DataFrame in res_lst to one global ordered DataFrame
            result_ordered = pd.concat(res_lst, axis=1)

            # Postprocess ordered results (optional)
            ########################################

            # Write DataFrames to local result file
            ######################################
            store.put(key=out_var, value=result_ordered)

    # TODO: Copy local result file back to master if needed

    print(f'Result files created. Elapsed time: {time.time()-t0:.3f} seconds')
    print("")
    print(f'Total elapsed time: {time.time()-t_total:.3f} seconds')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config_file",
        type=str,
        default=f'/nobackup/spanien1/salomon/WorkerTestData/simple_test_model/test_config.json',
        help="File to load grid_search configuration parameter from"
    )

    parser.add_argument(
        "--subgrid",
        type=str,
        default=f'/nobackup/spanien1/salomon/WorkerTestData/simple_test_model/test_grid.h5',
        help="File to load parameter grid from"
    )

    parser.add_argument(
        "--local_res_file",
        type=str,
        default=f'/nobackup/spanien1/salomon/WorkerTestData/simple_test_model/test_result.h5',
        help="File to save results to"
    )

    parser.add_argument(
        "--build_dir",
        type=str,
        default=os.getcwd(),
        help="Custom PyRates build directory"
    )

    FLAGS = parser.parse_args()

    main(sys.argv)


def postprocessing_1(data_):
    """Compute spike frequency based on frequency in PSD with the highest energy"""

    from pyrates.utility import plot_psd
    import matplotlib.pyplot as plt

    # Store columns for later reconstruction
    cols = data_.columns

    # Plot_psd expects only the out_var as column value
    index_dummy = pd.Index([cols.values[-1][-1]])
    data_.columns = index_dummy
    if not any(np.isnan(data_.values)):
        _ = plot_psd(data_, tmin=1.0, show=False)
        pow_ = plt.gca().get_lines()[-1].get_ydata()
        freqs = plt.gca().get_lines()[-1].get_xdata()
        plt.close()
        max_freq = freqs[np.argmax(pow_)]
        freq_pow = np.max(pow_)
        temp = [max_freq, freq_pow]
        psd = pd.DataFrame(temp, index=['max_freq', 'freq_pow'], columns=cols)
        data_.columns = cols
        return psd

    data_.columns = cols

    # Return empty DataFrame if data contains NaN
    return pd.DataFrame(columns=cols)


def postprocessing_2(data, simulation_time):
    """Compute spike frequency based on average number of spikes (local maxima) per second"""

    import scipy.signal as sp

    cols = data.columns

    np_data = np.array(data.values)

    peaks = sp.argrelextrema(np_data, np.greater)
    num_peaks_temp = int(len(peaks[0]) / simulation_time)

    return pd.DataFrame(num_peaks_temp, index=['num_peaks'], columns=cols)


def postprocessing_3(data, dt):
    """Compute spike frequency based on average time between spikes (local maxima)"""

    import scipy.signal as sp

    cols = data.columns

    np_data = np.array(data.values)

    peaks = sp.argrelextrema(np_data, np.greater)
    diff = np.diff(peaks[0])
    diff = np.mean(diff) * dt
    return 1 / diff

