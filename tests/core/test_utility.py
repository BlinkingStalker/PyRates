""" Testing utility functions
"""

import pytest
import numpy as np

# from core.utility.json_filestorage import CustomEncoder, get_attrs

__author__ = "Daniel Rose"
__status__ = "Development"

#########
# Setup #
#########


def setup_module():
    print("\n")
    print("====================================")
    print("| Test Suite 5 : Utility Functions |")
    print("====================================")

#########
# Tests #
#########


# @pytest.mark.xfail
def test_store_circuit_config():
    """As title says."""

    from core.circuit import JansenRitCircuit
    import json

    step_size = 1e-4

    circuit = JansenRitCircuit(step_size)

    # try without defaults
    ######################
    # config_dict = circuit.to_dict(include_defaults=False, recursive=True)

    # comment/uncomment this to create new target JSON file if necessary
    # assuming, the cwd is the tests root directory
    # circuit.to_json(include_defaults=False, path="resources/", filename="jr_config_target_no_defaults.json")

    with open("resources/jr_config_target_no_defaults.json", "r") as json_file:
        target_config_dict = json.load(json_file)

    config_dict = json.loads(circuit.to_json(include_defaults=False))

    assert config_dict == target_config_dict

    # try with defaults
    # #################

    # comment/uncomment this to create new target JSON file if necessary
    # assuming, the cwd is the tests root directory
    # circuit.to_json(include_defaults=True, path="resources/", filename="jr_config_target_with_defaults.json")

    config_dict = json.loads(circuit.to_json(include_defaults=True))

    with open("resources/jr_config_target_with_defaults.json", "r") as json_file:
        target_config_dict = json.load(json_file)

    assert config_dict == target_config_dict

    # try with graph
    # ##############

    # comment/uncomment this to create new target JSON file if necessary
    # assuming, the cwd is the tests root directory
    # circuit.to_json(include_defaults=False, include_graph=True,
    #                 path="resources/", filename="jr_config_target_with_graph.json")

    config_dict = json.loads(circuit.to_json(include_defaults=False, include_graph=True))

    with open("resources/jr_config_target_with_graph.json", "r") as json_file:
        target_config_dict = json.load(json_file)

    assert config_dict == target_config_dict


def test_store_circuit_config_dict_as_json():
    """As title says."""

    from core.circuit import JansenRitCircuit

    step_size = 1e-4

    circuit = JansenRitCircuit(step_size)

    outpath = "output/"
    filename = "jr_config_target_test_result.json"
    circuit.to_json(path=outpath, filename=filename)

    # with open("../resources/jr_config_test_result.json", "w") as json_file:
    #     json.dump(config_dict, json_file)

    import filecmp
    from os import path

    result = path.join(outpath, filename)
    target = "resources/jr_config_target_no_defaults.json"

    assert filecmp.cmp(result, target)

    filecmp.clear_cache()


# @pytest.mark.xfail
# def test_read_circuit_config_from_file():
#     """As title says."""
#
#     from core.circuit import JansenRitCircuit
#     from core.utility import read_config_from_file, read_config_from_circuit
#
#     step_size = 1e-4
#
#     target_circuit = JansenRitCircuit(step_size)
#
#     target_config_dict = read_config_from_circuit(target_circuit)
#
#     test_dict = read_config_from_file("../resources/jr_config_target.json")
#
#     assert test_dict == target_config_dict


# @pytest.mark.xfail
def test_construct_circuit_from_file_or_dict():
    """As title says."""

    from core.circuit import JansenRitCircuit
    from core.utility.construct import construct_circuit_from_file

    step_size = 1e-4
    # TODO: move step_size definition to pytest fixture

    target_circuit = JansenRitCircuit(step_size)

    target_config_dict = target_circuit.to_dict()

    # Construct circuit from template's dict and compare against template
    #####################################################################

    # test_circuit = construct_circuit_from_dict(target_config_dict)
    #
    # test_config_dict = read_config_from_circuit(test_circuit)
    #
    # assert test_config_dict == target_config_dict

    # Construct from file and test against template
    ###############################################

    path = "resources/"
    filename = "jr_config_target_no_defaults.json"

    test_circuit = construct_circuit_from_file(filename, path)

    test_config_dict = test_circuit.to_dict()

    assert deep_compare(test_config_dict, target_config_dict)
    assert repr(test_circuit) == repr(target_circuit)

    # test if the resulting circuit actually runs
    #############################################

    # synaptic_inputs = test_circuit.stored_synaptic_inputs
    # simulation_time = test_circuit.stored_simulation_time
    # test_circuit.run(synaptic_inputs, simulation_time)


# @pytest.mark.xfail
# def test_compare_circuit_repr_and_constructor():
#     # load_json
#     # load_reference_circuit
#     assert repr(circuit) == circuit_constructor_str


def test_construct_circuit_from_repr_eval():
    from core.circuit import JansenRitCircuit

    step_size = 1e-4

    circuit = JansenRitCircuit(step_size)

    _repr = repr(circuit)
    prefix, *suffix = _repr.split("(")
    cls = prefix.split(".")[-1]
    suffix = "(" + "(".join(suffix)
    _repr = cls + suffix
    new_circuit = eval(_repr)

    assert repr(circuit) == repr(new_circuit)


# @pytest.mark.xfail
def test_save_run_data_to_file():
    """Run a simulation and save the states to file."""

    from core.utility.construct import construct_circuit_from_file
    from core.utility.filestorage import get_simulation_data
    from core.utility.filestorage import save_simulation_data_to_file



    # set parameters
    ################
    path = "resources/"
    filename = "JR_runtest_config_I.json"

    # recreate circuit from file
    circuit = construct_circuit_from_file(filename, path)
    n_pop = circuit.n_populations
    n_syn = circuit.n_synapses
    # save a new config, if necessary
    # circuit.to_json(path=path, filename=filename)

    # simulation parameters
    simulation_time = 1.0  # s
    step_size = circuit.step_size  # s

    # synaptic inputs
    start_stim = 0.3  # s
    start_stim = int(start_stim / step_size)
    len_stim = 0.05  # s
    end_stim = int(start_stim / step_size + len_stim / step_size)
    mag_stim = 200.0  # 1/s

    n_time_steps = int(simulation_time / step_size)

    synaptic_inputs = np.zeros((n_time_steps, n_pop, n_syn))
    synaptic_inputs[start_stim:end_stim, 1, 0] = mag_stim

    # run network simulation
    ########################

    # print('| Test VII - Jansen-Rit Circuit |')

    circuit.run(synaptic_inputs=synaptic_inputs,
                simulation_time=simulation_time)

    # noinspection PyTypeChecker
    states = circuit.get_population_states(state_variable_idx=0) - 0.075  # type: np.ndarray
    states = states[1:, :]
    # for some reason, the get_population_states function returns one more time point than the input.

    assert states.shape == (n_time_steps, n_pop)

    # Now try to save data to a file
    run_info, original_sim_data = get_simulation_data(circuit, state_variable_idx=0,
                                                      pop_indices=None, time_window=None)

    dirname = "JR_simulation_data"
    path = "output/"

    save_simulation_data_to_file(output_data=original_sim_data, run_info=run_info,
                                 dirname=dirname, path=path, out_format="csv")  # implement include_config?
    saved_sim_data = read_simulation_data_from_file(filename, path)
    assert deep_compare(original_sim_data, saved_sim_data)


def deep_compare(left, right):
    """Hack to compare the config dictionaries"""

    if isinstance(left, np.ndarray):
        return (left == right).all()
    elif isinstance(left, dict):
        for key in left:
            return deep_compare(left[key], right[key])

    # I think this is actually not stable
    try:
        if not left.__dict__:
            return left == right

        for key in left.__dict__:
            if key not in right.__dict__:
                return False
            else:
                return deep_compare(left[key], right[key])
    except (AttributeError, TypeError):
        return left == right
