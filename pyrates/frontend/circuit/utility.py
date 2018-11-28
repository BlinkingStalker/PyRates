from copy import deepcopy
from typing import Union, Dict

from networkx import MultiDiGraph, DiGraph, find_cycle, NetworkXNoCycle

from pyrates import PyRatesException
from pyrates.ir.circuit import CircuitIR


class BackendIRFormatter:
    # label_counter = {}  # type: Dict[str, int]

    @classmethod
    def network_def(cls, circuit: CircuitIR, revert_node_names=False):
        """A bit of a workaround to connect interfaces of frontend and backend.
        TODO: Remove BackendIRFormatter and adapt corresponding tests"""
        # import re

        network_def = MultiDiGraph()

        edge_list = []
        node_dict = {}

        # reorganize node to conform with backend API
        #############################################
        for node_key, data in circuit.graph.nodes(data=True):
            node = data["node"]
            # reformat all node internals into operators + operator_args
            if revert_node_names:
                names = node_key.split("/")
                node_key = ".".join(reversed(names))
            node_dict[node_key] = {}  # type: Dict[str, Union[list, dict]]
            node_dict[node_key] = dict(cls._nd_reformat_operators(node.op_graph))
            op_order = cls._nd_get_operator_order(node.op_graph)  # type: list
            # noinspection PyTypeChecker
            node_dict[node_key]["operator_order"] = op_order

        # reorganize edge to conform with backend API
        #############################################
        for source, target, data in circuit.graph.edges(data=True):
            # move edge operators to node
            if revert_node_names:
                source = ".".join(reversed(source.split("/")))
                target = ".".join(reversed(target.split("/")))
            node_dict[target], edge = cls._move_edge_ops_to_node(target, node_dict[target], data)

            edge_list.append((source, target, dict(**edge)))

        # network_def.add_nodes_from(node_dict)
        for key, node in node_dict.items():
            network_def.add_node(key, **node)
        network_def.add_edges_from(edge_list)

        return network_def  # return MultiDiGraph as needed by ComputeGraph class

    @staticmethod
    def _nd_reformat_operators(op_graph: DiGraph):
        operator_args = dict()
        operators = dict()

        for op_key, op_dict in op_graph.nodes(data=True):
            op_cp = deepcopy(op_dict)  # duplicate operator info
            var_dict = op_cp.pop("variables")

            for var_key, var_props in var_dict.items():
                var_prop_cp = deepcopy(var_props)  # duplicate variable properties

                # if var_key in op_dict["variables"]:  # workaround to get values back into operator_args
                #     var_prop_cp["value"] = deepcopy(op_dict["values"][var_key])

                var_prop_cp["shape"] = ()  # default to scalars for now
                var_prop_cp.pop("unit", None)
                var_prop_cp.pop("description", None)
                var_prop_cp.pop("name", None)
                # var_prop_cp["name"] = f"{new_op_key}/{var_key}"  # has been thrown out
                operator_args[f"{op_key}/{var_key}"] = deepcopy(var_prop_cp)

            op_cp["equations"] = op_cp["operator"].equations
            op_cp["inputs"] = op_cp["operator"].inputs
            op_cp["output"] = op_cp["operator"].output
            # op_cp.pop("values", None)
            op_cp.pop("operator", None)
            operators[op_key] = op_cp

        reformatted = dict(operator_args=operator_args,
                           operators=operators,
                           inputs={})
        return reformatted

    @staticmethod
    def _nd_get_operator_order(op_graph: DiGraph) -> list:
        """

        Parameters
        ----------
        op_graph

        Returns
        -------
        op_order
        """
        # check, if cycles are present in operator graph (which would be problematic
        try:
            find_cycle(op_graph)
        except NetworkXNoCycle:
            pass
        else:
            raise PyRatesException("Found cyclic operator graph. Cycles are not allowed for operators within one node.")

        op_order = []
        graph = op_graph.copy()  # type: DiGraph
        while graph.nodes:
            # noinspection PyTypeChecker
            primary_nodes = [node for node, in_degree in graph.in_degree if in_degree == 0]
            op_order.extend(primary_nodes)
            graph.remove_nodes_from(primary_nodes)

        return op_order

    @classmethod
    def _move_edge_ops_to_node(cls, target, node_dict: dict, edge_dict: dict) -> (dict, dict):
        """

        Parameters
        ----------
        target
            Key identifying target node in backend graph
        node_dict
            Dictionary of target node (to move operators into)
        edge_dict
            Dictionary with edge properties (to move operators from)
        Returns
        -------
        node_dict
            Updated dictionary of target node
        edge_dict
             Dictionary of reformatted edge
        """
        # grab all edge variables
        edge = edge_dict["edge_ir"]  # type: EdgeIR
        source_var = edge_dict["source_var"]
        target_var = edge_dict["target_var"]
        weight = edge_dict["weight"]
        delay = edge_dict["delay"]
        input_var = edge.input
        output_var = edge.output

        if len(edge.op_graph) > 0:
            # reformat all edge internals into operators + operator_args
            op_data = cls._nd_reformat_operators(edge.op_graph)  # type: dict
            op_order = cls._nd_get_operator_order(edge.op_graph)  # type: List[str]
            operators = op_data["operators"]
            operator_args = op_data["operator_args"]

            # operator keys refer to a unique combination of template names and changed values

            # add operators to target node in reverse order, so they can be safely prepended
            added_ops = False
            for op_name in reversed(op_order):
                # check if operator name is already known in target node
                if op_name in node_dict["operators"]:
                    pass
                else:
                    added_ops = True
                    # this should all go smoothly, because operator should not be known yet
                    # add operator dict to target node operators
                    node_dict["operators"][op_name] = operators[op_name]
                    # prepend operator to op_order
                    node_dict["operator_order"].insert(0, op_name)
                    # ToDo: consider using collections.deque instead
                    # add operator args to target node
                    node_dict["operator_args"].update(operator_args)

            out_op = op_order[-1]
            out_var = operators[out_op]['output']
            if added_ops:
                # append operator output to target operator sources
                # assume that only last operator in edge operator_order gives the output
                # for op_name in node_dict["operators"]:
                #     if out_var in node_dict["operators"][op_name]["inputs"]:
                #         if out_var_long not in node_dict["operators"][op_name]["inputs"][out_var]:
                #             # add reference to source operator that was previously in an edge
                #             node_dict["operators"][op_name]["inputs"][out_var].append(output_var)

                # shortcut, since target_var and output_var are known:
                target_op, target_vname = target_var.split("/")
                if output_var not in node_dict["operators"][target_op]["inputs"][target_vname]["sources"]:
                    node_dict["operators"][target_op]["inputs"][target_vname]["sources"].append(out_op)

            # simplify edges and save into edge_list
            # op_graph = edge.op_graph
            # in_ops = [op for op, in_degree in op_graph.in_degree if in_degree == 0]
            # if len(in_ops) == 1:
            #     # simple case: only one input operator? then it's the first in the operator order.
            #     target_op = op_order[0]
            #     target_inputs = operators[target_op]["inputs"]
            #     if len(target_var) != 1:
            #         raise PyRatesException("Either too many or too few input variables detected. "
            #                                "Needs to be exactly one.")
            #     target_var = list(target_inputs.keys())[0]
            #     target_var = f"{target_op}/{target_var}"
            # else:
            #     raise NotImplementedError("Transforming an edge with multiple input operators is not yet handled.")

            # shortcut to new target war:
            target_var = input_var
        edge_dict = {"source_var": source_var,
                     "target_var": target_var,
                     "weight": weight,
                     "delay": delay}
        # set target_var to singular input of last operator added
        return node_dict, edge_dict
