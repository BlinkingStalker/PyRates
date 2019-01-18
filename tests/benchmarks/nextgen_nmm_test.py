from pyrates.frontend.template.circuit.circuit import CircuitTemplate
from pyrates.backend import ComputeGraph
from pyrates.utility import plot_timeseries, grid_search
import numpy as np
import matplotlib.pyplot as plt
from pandas import DataFrame

# parameters
dt = 1e-4
T = 2.
inp = 2. + np.random.randn(int(T/dt), 1) * 1.0

params = {'J_e': np.arange(8., 16., 2.), 'J_i': np.arange(2., 12., 2.)}
param_map = {'J_e': {'var': [('Op_e.0', 'J_e'), ('Op_i.0', 'J_e')],
                     'nodes': ['PC.0', 'IIN.0']},
             'J_i': {'var': [('Op_e.0', 'J_i'), ('Op_i.0', 'J_i')],
                     'nodes': ['PC.0', 'IIN.0']}
             }

# perform simulation
results = grid_search(circuit_template="pyrates.examples.simple_nextgen_NMM.Net5",
                      param_grid=params, param_map=param_map,
                      inputs={("PC", "Op_e.0", "inp"): inp}, outputs={"r": ("PC", "Op_e.0", "r")},
                      dt=dt, simulation_time=T, permute_grid=True)

# plotting
for j_e in params['J_e']:
    for j_i in params['J_i']:
        ax = plot_timeseries(results[j_e][j_i], title=f"J_e={j_e}, J_i={j_i}")
plt.show()