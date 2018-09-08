"""This module provides the network class that should be used to set-up any model. It creates a tensorflow graph that
manages all computations/operations and a networkx graph that represents the network structure (nodes + edges).
"""

# external imports
import tensorflow as tf
from typing import Optional, Tuple
from pandas import DataFrame
import time as t
import numpy as np
from networkx import MultiDiGraph
from networkx.classes.reportviews import NodeView, EdgeView
from copy import deepcopy

# pyrates imports
from pyrates.parser import ExpressionParser
from pyrates.node import Node
from pyrates.edge import Edge

# meta infos
__author__ = "Richard Gast, Karim Ahmed"
__status__ = "development"


class Network(MultiDiGraph):
    """Network level class used to set up and simulate networks of nodes and edges defined by sets of operators.

    Parameters
    ----------
    net_config
        Networkx MultiDiGraph that defines the configuration of the network. Following information need to be contained
        on nodes and edges:
            nodes
                Key, value pairs defining the nodes. They node keys should look as follows:
                `node_type_or_template_name:node_specific_identifier`. Each node value is again a dictionary with a
                key-value pair for `operators` and `operator_args`. Each operator is a key-value pair. The operator keys
                should follow the same naming convention as the node keys. The operator values are dictionaries with the
                following keys:
                    - `equations`: List of equations in string format (e.g. ['a = b + c']).
                    - `inputs`: List of input variable names (e.g. ['b', 'c']). Does not include constants or
                       placeholders.
                    - `output`: Output variable name (e.g. 'a')
                Operator arguments need keys that are equivalent to the respective variable names in the equations and
                their values are dictionaries with the following keys:
                    - `vtype`: Can be one of the following:
                        a) `state_var` for variables that change across simulation steps
                        b) `constant` for constants
                        c) `placeholder` for external inputs fed in during simulation time.
                        d) `raw` for variables that should not be turned into a tensorflow variable
                    - `dtype`: data-type of the variable. See tensorflow datatypes for all options
                       (not required for raw vars).
                    - `name`: Name of the variable in the graph (not required for raw vars).
                    - `shape`: Shape of the variable. Either tuple or list (not required for raw vars).
                    - `value`: Initial value.
            edges
                Key-value pairs defining the edges, similarly to the nodes dict. The edge keys should look as follows:
                `edge_type_or_template_name:source_node_name:target_node_name:edge_specific_identifier`. Each edge value
                is a dictionary with key-value pairs for `operators` and `operator_args`. The operator dictionary
                follows the same structure as on the node level. Operator arguments do in principle as well. However,
                for variables that should be retrieved from the source or target node, the following key-value pairs
                should be used:
                    - `vtype`: `source_var` or `target_var`
                    - 'name`: Name of the respective attribute on the node
    dt
        Integration step-size [unit = s]. Required for systems with differential equations.
    tf_graph
        Instance of a tensorflow graph. Operations/variables will be stored on the default graph if not passed.
    vectorize
        If true, operations and variables on the graph will be automatically vectorized to some extend. Tends to speed
        up simulations substantially.
    key
        Name of the network.

    Attributes
    ----------

    Methods
    -------

    References
    ----------

    Examples
    --------

    """

    def __init__(self,
                 net_config: MultiDiGraph,
                 dt: float = 1e-3,
                 tf_graph: Optional[tf.Graph] = None,
                 vectorize: bool = True,
                 key: Optional[str] = None
                 ) -> None:
        """Instantiation of network.
        """

        # call of super init
        ####################

        super().__init__()

        # additional object attributes
        ##############################

        self.key = key if key else 'net0'
        self.dt = dt
        self.tf_graph = tf_graph if tf_graph else tf.get_default_graph()
        self.states = []

        # vectorize passed dictionaries
        ###############################

        if vectorize:
            net_config = self.vectorize(net_config=net_config, first_lvl_vec=vectorize, second_lvl_vec=False)

        # create objects on tensorflow graph
        ####################################

        with self.tf_graph.as_default():

            with tf.variable_scope(self.key):

                # initialize nodes
                ##################

                node_updates = []

                for node_name, node_info in net_config.nodes.items():

                    # extract operators and their args
                    node_ops = node_info['data']['operators']
                    node_args = node_info['data']['operator_args']
                    node_args['dt'] = {'vtype': 'constant',
                                       'name': 'dt',
                                       'shape': (),
                                       'dtype': 'float32',
                                       'value': self.dt}

                    # add node to network
                    node = self.add_node(n=node_name,
                                         node_ops=node_ops,
                                         node_args=node_args)

                    # collect update operation of node
                    node_updates.append(node.update)

                # group the update operations of all nodes
                self.update = tf.tuple(node_updates, name='update')

                # initialize edges
                ##################

                with tf.control_dependencies(self.update):

                    projections = []

                    for source_name, target_name, edge_name in net_config.edges:

                        # extract edge properties
                        edge_info = net_config.edges[source_name, target_name, edge_name]['data']
                        edge_ops = edge_info['operators']
                        edge_args = edge_info['operator_args']
                        edge_args['dt'] = {'vtype': 'constant',
                                           'name': 'dt',
                                           'shape': (),
                                           'dtype': 'float32',
                                           'value': self.dt}

                        # add edge to network
                        edge = self.add_edge(u=source_name,
                                             v=target_name,
                                             coupling_op=edge_ops,
                                             coupling_op_args=edge_args,
                                             key=edge_name)

                        # collect project operation of edge
                        projections.append(edge.project)

                    # group project operations of all edges
                    if len(projections) > 0:
                        self.step = tf.tuple(projections, name='step')
                    else:
                        self.step = self.update

    def add_node(self, n, node_ops, node_args, **attr):

        # instantiate node
        node = Node(operations=node_ops,
                    operation_args=node_args,
                    key=n,
                    tf_graph=self.tf_graph)

        # call super method
        super().add_node(n, handle=node, **attr)

        return node

    def add_edge(self, u, v, coupling_op, coupling_op_args, key, **attr):

        # create edge
        edge = Edge(source=self.nodes[u]['handle'],
                    target=self.nodes[v]['handle'],
                    coupling_ops=coupling_op,
                    coupling_op_args=coupling_op_args,
                    tf_graph=self.tf_graph,
                    key=key)

        # call super method
        super().add_edge(u, v, key, handle=edge, **attr)

        return edge

    def _update_node(self, n, node_ops, node_args, **attr):
        """Not yet implemented: Method to update node properties (needs to change tf graph).
        """

        # create updated node on separate graph
        #######################################

        gr_tmp = tf.Graph()
        # node_new = Node(operations=node_ops,
        #                operation_args=node_args,
        #                key=n,
        #                tf_graph=gr_tmp)
        node_new = self.nodes[n]['handle']

        # collect tensors to replace in tensorflow graph
        ################################################

        node_old = self.nodes[n]['handle']
        replace_vars = {}
        for key, val in vars(node_old).items():
            if isinstance(val, tf.Tensor) or isinstance(val, tf.Variable):
                replace_vars[val.name] = getattr(node_new, key)

        # replace old node with new in graph
        ####################################

        graph_def = self.tf_graph.as_graph_def()

        with gr_tmp.as_default():
            tf.import_graph_def(graph_def=graph_def, input_map=replace_vars)

        with self.tf_graph.as_default():
            tf.reset_default_graph()

        self.tf_graph = gr_tmp

        # update fields on networkx node
        ################################

        self.nodes[n]['handle'] = node_new
        for key, val in attr.items():
            self.nodes[n][key] = val

    def _update_edge(self, u, v, coupling_op, coupling_op_args, key=None, **attr):
        """Not yet implemented: Method to update edge properties (needs to change tf graph).
        """

        # create updated edge on separate graph
        #######################################

        gr_tmp = tf.Graph()
        edge_new = Edge(source=self.nodes[u]['handle'],
                        target=self.nodes[v]['handle'],
                        coupling_ops=coupling_op,
                        coupling_op_args=coupling_op_args,
                        tf_graph=gr_tmp,
                        key=key)

        # replace old edge with new in graph
        ####################################

        graph_def = self.tf_graph.as_graph_def()

        with gr_tmp.as_default():
            tf.import_graph_def(graph_def=graph_def, input_map={key: edge_new})

        with self.tf_graph.as_default():
            tf.reset_default_graph()

        self.tf_graph = gr_tmp

        # update fields on networkx node
        ################################

        self.edges[key]['handle'] = edge_new
        for key_tmp, val in attr.items():
            self.edges[key][key_tmp] = val

    def vectorize(self, net_config: MultiDiGraph, first_lvl_vec: bool = True, second_lvl_vec: bool=True
                  ) -> MultiDiGraph:
        """Method that goes through the nodes and edges dicts and vectorizes those that are governed by the same
        operators/equations.

        Parameters
        ----------
        nodes
            See argument description at class level.
        edges
            See argument description at class level.
        first_lvl_vec
            If True, first stage (vectorization over nodes and edges) will be included.
        second_lvl_vec
            If True, second stage (vectorization over operations) will be performed as well.

        Returns
        -------
        Tuple[NodeView, EdgeView]

        """

        # First stage: Vectorize over nodes and edges
        #############################################

        if first_lvl_vec:

            new_net_config = MultiDiGraph()

            # node vectorization
            ####################

            # extract node-type related parts of node keys
            node_keys = []
            for key in net_config.nodes.keys():
                node_type, node_name = key.split('_')
                node_keys.append(node_type)

            # get unique node names
            node_keys_unique = list(set(node_keys))

            # create new node dict with nodes vectorized over multiples of the unique node keys
            node_arg_map = {}
            for new_node in node_keys_unique:

                op_args_new = {}
                n_nodes = 0
                arg_vals = {}

                # go through old nodes
                for node_name, node_info in net_config.nodes.items():

                    node_info = deepcopy(node_info['data'])

                    if new_node in node_name:

                        node_arg_map[node_name] = {}

                        if len(op_args_new) == 0:

                            # use first match to collect operations and operation arguments
                            ops_new = node_info['operators']
                            for key, arg in node_info['operator_args'].items():
                                op_args_new[key] = arg
                                if 'value' in arg.keys():
                                    arg_vals[key] = [arg['value']]
                                    node_arg_map[node_name][key] = n_nodes

                        else:

                            # add argument values to dictionary
                            for key, arg in node_info['operator_args'].items():
                                node_arg_map[node_name][key] = n_nodes
                                if 'value' in arg.keys():
                                    arg_vals[key].append(arg['value'])

                        # increment node counter
                        n_nodes += 1

                # go through new arguments and change shape and values
                for key, arg in op_args_new.items():

                    if 'value' in arg.keys():
                        arg['value'] = np.array(arg_vals[key]) if type(arg['value']) == np.ndarray else arg_vals[key]

                    if 'shape' in arg.keys():
                        arg['shape'] = [n_nodes, ] + list(arg['shape'])
                        if len(arg['shape']) == 1:
                            arg['shape'] = arg['shape'] + [1]

                # add new, vectorized node to dictionary
                if n_nodes > 0:
                    new_net_config.add_node(new_node, data={'operators': deepcopy(ops_new),
                                                            'operator_args': deepcopy(op_args_new)})

            # edge vectorization
            ####################

            # extract edge-type related parts of edge keys
            edge_keys = {}
            for source, target, key in net_config.edges:
                edge_type, edge_name = key.split('_')
                s = source.split('_')[0]
                t = target.split('_')[0]
                if s in edge_keys.keys():
                    if t in edge_keys[s].keys():
                        edge_keys[s][t].append(edge_type)
                    else:
                        edge_keys[s][t] = [edge_type]
                else:
                    edge_keys[s] = {t: [edge_type]}

            # get unique edge names
            for s, sval in edge_keys.items():
                for t, tval in sval.items():
                    edge_keys[s][t] = list(set(tval))

            # create new edge dict with edges vectorized over multiples of the unique edge keys
            for s, source in edge_keys.items():
                for t, target in source.items():
                    for e in target:

                        op_args_new = {}
                        n_edges = 0
                        arg_vals = {}
                        snode_idx = {}
                        tnode_idx = {}

                        # go through old edges
                        for source, target, edge in net_config.edges:

                            edge_info = deepcopy(net_config.edges[source, target, edge]['data'])

                            if s in source and t in target and e in edge:

                                if n_edges == 0:

                                    # use first match to collect operations and operation arguments
                                    # TODO: implement mapping from node to edge space and back
                                    ops_new = edge_info['operators']
                                    for key, arg in edge_info['operator_args'].items():
                                        op_args_new[key] = arg
                                        if 'value' in arg.keys():
                                            arg_vals[key] = [arg['value']]
                                        if arg['vtype'] == 'source_var':
                                            snode_idx[key] = ([node_arg_map[source][arg['name']]],
                                                              new_net_config.nodes[s]['data']['operator_args']
                                                              [arg['name']]['shape'][0])
                                        elif arg['vtype'] == 'target_var':
                                            tnode_idx[key] = ([node_arg_map[target][arg['name']]],
                                                              new_net_config.nodes[t]['data']['operator_args']
                                                              [arg['name']]['shape'][0])

                                else:

                                    # add argument values to dictionary
                                    for key, arg in edge_info['operator_args'].items():
                                        if 'value' in arg.keys():
                                            arg_vals[key].append(arg['value'])
                                        if arg['vtype'] == 'source_var':
                                            snode_idx[key][0].append(node_arg_map[source][arg['name']])
                                        elif arg['vtype'] == 'target_var':
                                            tnode_idx[key][0].append(node_arg_map[target][arg['name']])

                                # increment edge counter
                                n_edges += 1

                        # create mapping from source to edge space and edge to target space
                        if not second_lvl_vec and n_edges > 0:
                            for n, (key, val) in enumerate(snode_idx.items()):
                                edge_map = np.zeros((n_edges, val[1]))
                                for i, idx in enumerate(val[0]):
                                    edge_map[i, idx] = 1.
                                if not n_edges == val[1] and not edge_map == np.eye(n_edges):
                                    for op_key, op in ops_new.items():
                                        for i, eq in enumerate(op['equations']):
                                            eq = eq.replace(key, f'(map_{n} @ {key})')
                                            ops_new[op_key]['equations'][i] = eq
                                    op_args_new[f'map_{n}'] = {'vtype': 'constant',
                                                               'dtype': 'float32',
                                                               'name': f'map_{n}',
                                                               'shape': edge_map.shape,
                                                               'value': edge_map}
                            for key, val in tnode_idx.items():
                                target_map = np.zeros((val[1], n_edges))
                                for i, idx in enumerate(val[0]):
                                    target_map[idx, i] = 1.
                                if not n_edges == val[1] and not target_map == np.eye(n_edges):
                                    for op_key, op in ops_new.items():
                                        for i, eq in enumerate(op['equations']):
                                            _, rhs = eq.split(' = ')
                                            eq = eq.replace(rhs, f'tmap @ ({rhs})')
                                            ops_new[op_key]['equations'][i] = eq
                                    op_args_new['tmap'] = {'vtype': 'constant',
                                                           'dtype': 'float32',
                                                           'name': 'tmap',
                                                           'shape': target_map.shape,
                                                           'value': target_map}

                        # go through new arguments and change shape and values
                        for key, arg in op_args_new.items():

                            if 'map_' not in key and 'tmap' not in key:

                                if 'value' in arg.keys():
                                    arg['value'] = np.array(arg_vals[key]) if type(arg['value']) == np.ndarray else arg_vals[key]

                                if 'shape' in arg.keys():
                                    arg['shape'] = [n_edges, ] + list(arg['shape'])
                                    if len(arg['shape']) == 1:
                                        arg['shape'] = arg['shape'] + [1]

                        if n_edges > 0:

                            # add new, vectorized edge to networkx graph
                            new_net_config.add_edge(s, t, e, data={'operators': deepcopy(ops_new),
                                                                   'operator_args': deepcopy(op_args_new)})

            # replace old with new dictionaries
            net_config = new_net_config

        # Second stage: Vectorize over operations
        #########################################

        # if second_lvl_vec:
        #
        #     # vectorize node operations
        #     ###########################
        #
        #     # collect all operation keys of each node
        #     op_keys = []
        #     for node in nodes.values():
        #         op_keys.append(node['operation_args'].keys())
        #
        #     # create helper variables
        #     checked_ops = [[False for _ in range(len(node['operation_args']))] for node in nodes.values()]
        #     op_arg_map = {}
        #     new_node = {'operations': dict(), 'operation_args': dict()}
        #
        #     for i, (node_name, node_info) in enumerate(nodes.items()):
        #
        #         # find name of operation to vectorize
        #         op_to_vec = op_keys[i].pop(0)
        #
        #         # look for that operation in other nodes
        #         node_names = [node_name]
        #         for j, (node_name2, node_info2) in zip(range(len(op_keys)), nodes.items()):
        #
        #             if i != j:
        #
        #                 # get index of operation on node
        #                 idx = op_keys[j].index(op_to_vec) if op_to_vec in op_keys else -1
        #
        #                 if idx > 0:
        #
        #                     # reorder the nodes dictionary with node j being on top
        #                     new_nodes = {node_name2: node_info2}
        #                     for node_name, node_info in nodes.items():
        #                         if node_name != node_name2:
        #                             new_nodes[node_name] = node_info
        #
        #                     # call vectorize with re-ordered dict
        #                     return self.vectorize(nodes, edges, first_lvl_vec=False)
        #
        #                 elif idx == 0:
        #
        #                     # add operation of node j to vectorization
        #                     node_names.append(node_name2)
        #
        #         # retrieve arguments from the operation
        #         args = []
        #         for eq in node_info['operations'][op_to_vec]['equations']:
        #             lhs, rhs = eq.split(' = ')
        #             args.append(ExpressionParser(rhs, {}))
        #             args.append(ExpressionParser(lhs, {}))
        #
        #         # go through all arguments and check whether they need to be vectorized
        #         n_nodes = len(node_names)
        #         for n in range(len(args)):
        #
        #             arg = args.pop()
        #             if arg in node_info['operation_args'].keys():
        #
        #                 arg_tmp = node_info['operation_args'][arg]
        #                 if 'shape' in arg_tmp.keys():
        #                     arg_tmp['shape'] = [n_nodes] + list(arg_tmp['shape'])
        #                 if 'value' in arg_tmp.keys():
        #                     arg_val = [arg_tmp['value']]
        #                     for node_name2 in node_names[1:]:
        #                         arg_val.append(nodes[node_name2]['operation_args'][arg]['value'])
        #                     if type(arg_tmp['value']) == np.ndarray:
        #                         arg_val = np.array(arg_val)
        #                     arg_tmp['value'] = arg_val

        return net_config

    def run(self, simulation_time: Optional[float] = None, inputs: Optional[dict] = None,
            outputs: Optional[dict] = None, sampling_step_size: Optional[float] = None) -> Tuple[DataFrame, float]:
        """Simulate the network behavior over time via a tensorflow session.

        Parameters
        ----------
        simulation_time
        inputs
        outputs
        sampling_step_size

        Returns
        -------
        list

        """

        # prepare simulation
        ####################

        # basic simulation parameters initialization
        if simulation_time:
            sim_steps = int(simulation_time / self.dt)
        else:
            sim_steps = 1

        if not sampling_step_size:
            sampling_step_size = self.dt
        sampling_steps = int(sampling_step_size / self.dt)

        # define output variables
        if not outputs:
            outputs = dict()
            for name, node in self.nodes.items():
                outputs[name + '_v'] = getattr(node['handle'], 'name')

        # linearize input dictionary
        if inputs:
            inp = list()
            for step in range(sim_steps):
                inp_dict = dict()
                for key, val in inputs.items():
                    shape = key.shape
                    if len(val) > 1:
                        inp_dict[key] = np.reshape(val[step], shape)
                    else:
                        inp_dict[key] = np.reshape(val, shape)
                inp.append(inp_dict)
        else:
            inp = [None for _ in range(sim_steps)]

        # run simulation
        ################

        with tf.Session(graph=self.tf_graph) as sess:

            # writer = tf.summary.FileWriter('/tmp/log/', graph=self.tf_graph)

            # initialize all variables
            sess.run(tf.global_variables_initializer())

            results = []
            t_start = t.time()

            # simulate network behavior for each time-step
            for step in range(sim_steps):

                sess.run(self.step, inp[step])

                if step % sampling_steps == 0:
                    results.append([np.squeeze(var.eval()) for var in outputs.values()])

            t_end = t.time()

            # display simulation time
            if simulation_time:
                print(f"{simulation_time}s of network behavior were simulated in {t_end - t_start} s given a "
                      f"simulation resolution of {self.dt} s.")
            else:
                print(f"Network computations finished after {t_end - t_start} seconds.")
            # writer.close()

            # store results in pandas dataframe
            time = 0.
            times = []
            for i in range(sim_steps):
                time += sampling_step_size
                times.append(time)

            results = np.array(results)
            if len(results.shape) > 2:
                n_steps, n_vars, n_nodes = results.shape
            else:
                n_steps, n_vars = results.shape
                n_nodes = 1
            results = np.reshape(results, (n_steps, n_nodes * n_vars))
            columns = []
            for var in outputs.keys():
                columns += [f"{var}_{i}" for i in range(n_nodes)]
            results_final = DataFrame(data=results, columns=columns, index=times)

        return results_final, (t_end - t_start)
