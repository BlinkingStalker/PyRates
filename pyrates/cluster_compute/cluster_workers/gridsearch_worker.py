# system imports
import os
import sys
import ast
import json
import time
import argparse

# external imports
import pandas as pd
from pyrates.utility.grid_search import grid_search_2


def main(_):
    # disable TF-gpu warnings
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

    ##################################################
    # Load command line arguments and create logfile #
    ##################################################
    print("")
    print("***LOADING COMMAND LINE ARGUMENTS***")
    t0 = time.time()

    config_file = FLAGS.config_file
    subgrid = FLAGS.subgrid
    res_dir = FLAGS.res_dir
    grid_name = FLAGS.grid_name

    print(f'Elapsed time: {time.time()-t0:.3f} seconds')

    ###########################
    # Load global config file #
    ###########################
    print("")
    print("***LOADING GLOBAL CONFIG FILE***")
    t0 = time.time()

    with open(config_file) as g_conf:
        global_config_dict = json.load(g_conf)
        inputs = {ast.literal_eval(*global_config_dict['inputs'].keys()):
                  list(*global_config_dict['inputs'].values())}
        outputs = {str(*global_config_dict['outputs'].keys()):
                   tuple(*global_config_dict['outputs'].values())}
        circuit_template = global_config_dict['circuit_template']
        param_map = global_config_dict['param_map']
        sampling_step_size = global_config_dict['sampling_step_size']
        dt = global_config_dict['dt']
        simulation_time = global_config_dict['simulation_time']

    print(f'Elapsed time: {time.time()-t0:.3f} seconds')

    #########################
    # LOAD PARAMETER GRID #
    #########################
    print("")
    print("***LOADING PARAMETER GRID***")
    t0 = time.time()

    # Load subgrid into DataFrame
    param_grid = pd.read_hdf(subgrid, key='Data')

    # Exclude 'status'- and 'worker'-keys from param_grid since grid_search() can't handle the additional keywords
    param_grid = param_grid.loc[:, param_grid.columns != "status"]
    param_grid = param_grid.loc[:, param_grid.columns != "worker"]

    print(f'Total parameter grid computation time: {time.time()-t0:.3f} seconds')

    ##########################
    # COMPUTE PARAMETER GRID #
    ##########################
    print("")
    print("***COMPUTING PARAMETER GRID***")
    t0 = time.time()

    results, t, _ = grid_search_2(circuit_template=circuit_template,
                                  param_grid=param_grid,
                                  param_map=param_map,
                                  inputs=inputs,
                                  outputs=outputs,
                                  sampling_step_size=sampling_step_size,
                                  dt=dt,
                                  simulation_time=simulation_time,
                                  profile='t',
                                  timestamps=False)

    print(f'Total parameter grid computation time: {time.time()-t0:.3f} seconds')
    # print(f'Peak memory usage: {m} MB')

    ############################################
    # POSTPROCESS DATA AND CREATE RESULT FILES #
    ############################################
    print("")
    print("***POSTPROCESSING AND CREATING RESULT FILES***")
    start_res = time.time()

    for col in range(len(results.columns)):
        result = results.iloc[:, col]
        idx_label = result.name[:-1]
        idx = param_grid[(param_grid.values == idx_label).all(1)].index
        result = result.to_frame()
        result.columns.names = results.columns.names

        ##################
        # POSTPROCESSING #
        ##################
        result = postprocessing(result)

        # res_file = f'{res_dir}/CGS_result_{grid_name}_idx_{idx[0]}.csv'
        # result.to_csv(res_file, index=True)
        res_file = f'{res_dir}/CGS_result_{grid_name}_idx_{idx[0]}.h5'
        result.to_hdf(res_file, key='Data', mode='a')

    elapsed_res = time.time() - start_res
    print("Result files created. Elapsed time: {0:.3f} seconds".format(elapsed_res))


def postprocessing(data):
    # type(data) = <class 'pandas.core.frame.DataFrame'>
    # Can be processed like a slice received via (e.g.): data = results[J_e][J_i]

    # Postprocessing example (see EIC_coupling.py):
    # cut_off = 1.
    # max_freq = np.zeros((len(ei_ratio), len(io_ratio)))
    # freq_pow = np.zeros_like(max_freq)
    # if not data.isnull().any().any():
    #     _ = plot_psd(data, tmin=cut_off, show=False)
    #     pow = plt.gca().get_lines()[-1].get_ydata()
    #     freqs = plt.gca().get_lines()[-1].get_xdata()
    #     r, c = np.argmin(np.abs(ei_ratio - k1/k2)), np.argmin(np.abs(io_ratio - j_i/k2))
    #     max_freq[r, c] = freqs[np.argmax(pow)]
    #     freq_pow[r, c] = np.max(pow)
    #     plt.close(plt.gcf())
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # parser.register("type", "bool", lambda v: v.lower() == "true")

    parser.add_argument(
        "--config_file",
        type=str,
        default="",
        help="Config file with all necessary data to start grid_search() except for parameter grid"
    )

    parser.add_argument(
        "--subgrid",
        type=str,
        default="",
        help="Path to csv-file with subgrid to compute on the remote machine"
    )

    parser.add_argument(
        "--res_dir",
        type=str,
        default="",
        help="Directory to save result files to"
    )

    parser.add_argument(
        "--grid_name",
        type=str,
        default="",
        help="Name of the parameter grid currently being computed"
    )

    FLAGS = parser.parse_args()

    main(sys.argv)
