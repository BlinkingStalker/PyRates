from pyrates.frontend import CircuitIR, CircuitTemplate
from pyrates.backend import ComputeGraph
from matplotlib.pyplot import *

# parameters
n_jrcs = 1

# circuit IR setup
circuit_temp = CircuitTemplate.from_yaml("pyrates.frontend.circuit.templates.JansenRitCircuit")
circuits = {}
for n in range(n_jrcs):
    circuits['jrc.' + str(n)] = circuit_temp
circuit_ir = CircuitIR.from_circuits('jrc_net', circuits=circuits).network_def()

# create backend
net = ComputeGraph(circuit_ir, vectorize='none')
inp_pc = np.zeros((1000, n_jrcs))
inp_pc[:, 0] = 220. + np.random.randn(1000)
inp_in = np.zeros((1000, n_jrcs))
results, _ = net.run(1., outputs={'v': ('all', 'JansenRitPRO.0', 'V')},
                     inputs={('jrc.0/JR_PC', 'JansenRitExcitatorySynapseRCO.0', 'u'): inp_pc,
                             ('jrc.0/JR_II', 'JansenRitExcitatorySynapseRCO.0', 'u'): inp_in,
                             ('jrc.0/JR_EI', 'JansenRitExcitatorySynapseRCO.0', 'u'): inp_in})
results.pop('time')
results.plot()
show()
