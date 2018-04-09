"""
Includes various benchmarks for the NMM framework.

Profiling:
##########
http://softwaretester.info/python-profiling-with-pycharm-community-edition/

# install packages
pip install snakeviz
pip install cprofilev

# Change “Benchmark Configuration”:
Interpreter options: -B -m cProfile -o profile.prof

# show results (terminal):
> snakeviz profile.prof

"""

import numpy as np
import time
# from memory_profiler import memory_usage
from scipy.io import loadmat

from pyrates.circuit import JansenRitCircuit

__author__ = "Richard Gast, Daniel Rose"
__status__ = "Development"


#######################
# benchmark functions #
#######################


def run_JR_circuit_benchmark(simulation_time=1.0, step_size=1 / 2048, param_names=None, param_values=None,
                             synaptic_inputs=None, verbose=False, max_synaptic_delay=0.05):
    """
    Runs a benchmark on a single Jansen-Rit type microcircuit (3 interconnected neural populations).

    :param simulation_time: length of the simulation [unit = s] (default = 60.0).
    :param step_size: simulation step-size [unit = s] (default = 1e-4).
    :param param_names: list with name of JR parameters to alter (see JR_parameter_study function).
    :param param_values: list with parameter values (see JR_parameter_study function).
    :param synaptic_inputs: input fed to the microcircuit (length must be simulation_time/step_size).
    :param verbose: If true, simulation progress will be displayed.
    :param variable_step_size: If true, variable step solver will be used.

    :return: simulation length in seconds (real-time).
    """

    #############################
    # set simulation parameters #
    #############################

    if synaptic_inputs is None:
        # synaptic inputs
        mu_stim = 200.0
        std_stim = 20.0
        synaptic_inputs = np.zeros((int(simulation_time / step_size), 3, 2))
        synaptic_inputs[:, 1, 0] = std_stim * np.random.random(synaptic_inputs.shape[0]) + mu_stim
        synaptic_inputs[:, 0, 0] = 0 * np.random.random(synaptic_inputs.shape[0]) + mu_stim / 2.

    #########################
    # initialize JR circuit #
    #########################

    nmm = JansenRitCircuit(step_size=step_size, max_synaptic_delay=max_synaptic_delay)

    if param_names:

        for i, p in enumerate(param_names):
            setattr(nmm, p, param_values[i])

    #####################
    # perform benchmark #
    #####################

    print('Starting simulation of single Jansen Rit Cirucit...')

    start_time = time.clock()

    nmm.run(simulation_time=simulation_time,
            synaptic_inputs=synaptic_inputs,
            verbose=verbose)

    end_time = time.clock()

    simulation_duration = end_time - start_time
    print("%.2f" % simulation_time, 's simulation of Jansen-Rit circuit finished after ',
          "%.2f" % simulation_duration, ' s.')

    return simulation_duration


def run_JR_network_benchmark(simulation_time=60.0, step_size=1e-4, N=33, C=None, connectivity_scaling=100.0, D=True,
                             velocity=1.0, synaptic_input=None, verbose=False, max_synaptic_delay=0.05):
    """
    Runs benchmark for a number of JR circuits connected in a network.

    :param simulation_time:
    :param step_size:
    :param N:
    :param C:
    :param connectivity_scaling:
    :param D:
    :param velocity:
    :param synaptic_input:
    :param verbose:
    :param variable_step_size:
    :param max_synaptic_delay:

    :return: simulation duration [unit = s]

    """

    #############################
    # set simulation parameters #
    #############################

    # connectivity matrix
    if C is None:

        # load connectivity matrix
        C = loadmat('../resources/SC')['SC']
        C *= connectivity_scaling

        # hack because, currently a third dimension is expected
        C = np.array([C, np.zeros_like(C)])
        print(C.shape)
        C = C.reshape((33, 33, 2))

        # create full connectivity matrix
        # n_pops = 3
        # C = np.zeros([N * n_pops, N * n_pops, 2])
        # for i in range(N):
        #     for j in range(N):
        #         if i == j:
        #             C[i * n_pops:i * n_pops + n_pops, j * n_pops:j * n_pops + n_pops, 0] = \
        #                 [[0, 0.8 * 135, 0], [1.0 * 135, 0, 0], [0.25 * 135, 0, 0]]
        #             C[i * n_pops:i * n_pops + n_pops, j * n_pops:j * n_pops + n_pops, 1] = \
        #                 [[0, 0, 0.25 * 135], [0, 0, 0], [0, 0, 0]]
        #         C[i * n_pops, j * n_pops, 0] = C_tmp[i, j]

    else:

        C *= connectivity_scaling

    # network delays
    if D:

        D = loadmat('../resources/D')['D']

        # D = np.zeros([N * n_pops, N * n_pops])
        # for i in range(N):
        #     for j in range(N):
        #         D[i * n_pops:i * n_pops + n_pops, j * n_pops:j * n_pops + n_pops] = D_tmp[i, j]

    else:

        D = np.zeros((33, 33))

    # connection arguments
    connection_strengths = list()
    source_populations = list()
    target_populations = list()
    target_synapses = list()
    delays = list()
    for i in range(C.shape[0]):
        for j in range(C.shape[1]):
            for k in range(C.shape[2]):
                if C[i, j, k] > 0:
                    connection_strengths.append(C[i, j, k])
                    source_populations.append(j*3)
                    target_populations.append(i*3)
                    target_synapses.append(k)
                    delays.append(D[i, j] / velocity)

    # network input
    n_pops = 3
    if synaptic_input is None:
        synaptic_input = np.zeros([int(np.ceil(simulation_time / step_size)), N * n_pops, 2])
        idx_pcs = np.mod(np.arange(N * n_pops), n_pops) == 0
        idx_eins = np.mod(np.arange(N * n_pops), n_pops) == 1
        synaptic_input[:, idx_pcs, 0] = np.random.randn(int(np.ceil(simulation_time / step_size)), N) + 100.0
        synaptic_input[:, idx_eins, 0] = 22 * np.random.randn(int(np.ceil(simulation_time / step_size)), N) + 200.0

    # circuits
    circuits = [JansenRitCircuit(step_size=step_size, max_synaptic_delay=max_synaptic_delay) for _ in range(33)]

    ################
    # set up model #
    ################

    from pyrates.circuit import CircuitFromPopulations
    from pyrates.circuit import CircuitFromCircuit
    nmm = CircuitFromCircuit(circuits=circuits,
                             connection_strengths=connection_strengths,
                             source_populations=source_populations,
                             target_populations=target_populations,
                             target_synapses=target_synapses,
                             delays=delays,
                             )

    #####################
    # perform benchmark #
    #####################

    print('Starting simulation of 33 connected Jansen-Rit circuits...')

    start_time = time.clock()

    nmm.run(synaptic_inputs=synaptic_input,
            simulation_time=simulation_time,
            verbose=verbose)

    end_time = time.clock()

    simulation_duration = end_time - start_time

    print("%.2f" % simulation_time, 's simulation of Jansen-Rit network with ', N, 'populations finished after ',
          "%.2f" % simulation_duration, ' s.')

    return simulation_duration


if __name__ == "__main__":

    import sys

    class CallError(Exception):
        pass
    try:
        arg = sys.argv[1]
    except IndexError:
        arg = "both"
    if arg == '1':
        run_first = True
        run_second = False
    elif arg == '2':
        run_second = True
        run_first = False
    elif arg == "both":
        run_first = run_second = True
    else:
        run_first = run_second = False

    ######################
    # perform benchmarks #
    ######################

    # parameters
    simulation_duration = 10.0
    step_size = 1e-3
    verbose = True
    D = True
    velocity = 2.0
    connectivity_scaling = 50.0
    max_synaptic_delay = 0.05

    if run_first:
        # single JR circuit
        sim_dur_JR_circuit = run_JR_circuit_benchmark(simulation_time=simulation_duration,
                                                      step_size=step_size,
                                                      verbose=verbose,
                                                      max_synaptic_delay=max_synaptic_delay)

    if run_second:
        # JR network (33 connected JR circuits)
        sim_dur_JR_network = run_JR_network_benchmark(simulation_time=simulation_duration,
                                                      step_size=step_size,
                                                      D=D,
                                                      velocity=velocity,
                                                      connectivity_scaling=connectivity_scaling,
                                                      verbose=verbose,
                                                      max_synaptic_delay=0.05)

    ################
    # memory usage #
    ################

    # single JR circuit
    # mem_use_JR_circuit = memory_usage((run_JR_circuit_benchmark, (simulation_duration, step_size)))
    # print("%.2f" % simulation_duration, 's simulation of Jansen-Rit circuit used ',
    #      "%.2f" % (np.sum(mem_use_JR_circuit) * 1e-2), ' MB RAM.')

    # JR network (33 connected JR circuits)
    # mem_use_JR_network = memory_usage((run_JR_network_benchmark, (simulation_duration, step_size)))
    # print("%.2f" % simulation_duration, 's simulation of network with 33 JR circuits used ',
    #      "%.2f" % (np.sum(mem_use_JR_network) * 1e-2), ' MB RAM.')
