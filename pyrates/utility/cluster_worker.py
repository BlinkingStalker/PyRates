# system imports
import argparse
import sys
import ast

# external imports
import pandas as pd
from numpy import array

from pyrates.utility import grid_search

# TODO: Recreate all necessary input for grid_search from config_file
# TODO: Change argparse so config_file will be the only argument. Then wait for param_grid from stdin
def main(_):
    # Recreate dictionaries from their string representation and recreate DataFrames
    circuit_template = FLAGS.circuit_template
    param_grid = pd.DataFrame(ast.literal_eval(FLAGS.param_grid))
    param_map = ast.literal_eval(FLAGS.param_map)
    # inputs = ast.literal_eval(FLAGS.inputs)
    outputs = ast.literal_eval(FLAGS.outputs)
    sampling_step_size = FLAGS.sampling_step_size
    dt = FLAGS.dt
    simulation_time = FLAGS.simulation_time

    print(f'circuit template: {type(circuit_template)}')
    print(f'param_grid: {type(param_grid)}')
    print(f'param_map: {type(param_map)}')
    # print(f'inputs: {type(inputs)}')
    print(f'outputs: {type(outputs)}')
    print(f'sampling_step_size: {type(sampling_step_size)}')
    print(f'dt: {type(dt)}')
    print(f'simulation_time: {type(simulation_time)}')

    # Exclude 'status'-key param_grid because grid_search() can't handle the additional keyword
    # param_grid_arg = param_grid.loc[:, param_grid.columns != "status"]
    #
    # results = grid_search(circuit_template=circuit_template,
    #                       param_grid=param_grid_arg,
    #                       param_map=param_map,
    #                       inputs=inputs,
    #                       outputs=outputs,
    #                       sampling_step_size=sampling_step_size,
    #                       dt=dt,
    #                       simulation_time=simulation_time)
    #
    # print(results.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # parser.register("type", "bool", lambda v: v.lower() == "true")

    parser.add_argument(
        "--circuit_template",
        type=str,
        default="",
        help=""
    )

    parser.add_argument(
        "--param_grid",
        type=str,
        default="",
        help=""
    )

    parser.add_argument(
        "--param_map",
        type=str,
        default="",
        help=""
    )

    parser.add_argument(
        "--inputs",
        type=str,
        default="",
        help=""
    )

    parser.add_argument(
        "--outputs",
        type=str,
        default="",
        help=""
    )

    parser.add_argument(
        "--sampling_step_size",
        default=None,
        help=""
    )

    parser.add_argument(
        "--dt",
        type=float,
        default=0.0,
        help=""
    )

    parser.add_argument(
        "--simulation_time",
        type=float,
        default=0.0,
        help=""
    )

    FLAGS = parser.parse_args()

    main(sys.argv)