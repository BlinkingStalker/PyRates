"""This module contains the node class used to create a network node from a set of operations.
"""

# external imports
from typing import Dict, List, Optional
import tensorflow as tf

# pyrates imports
from pyrates.operator import Operator
from pyrates.parser import parse_dict

# meta infos
__author__ = "Richard Gast"
__status__ = "Development"


class Node(object):
    """Basic node class. Creates a node from a set of operations plus information about the variables contained therein.
    This node is a tensorflow sub-graph with an `update` operation that can be used to update all state variables
    described by the operators.

    Parameters
    ----------

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
                 operations: dict,
                 operation_args: dict,
                 key: str,
                 tf_graph: Optional[tf.Graph] = None
                 ) -> None:
        """Instantiates node.
        """

        self.key = key
        self.operations = dict()
        self.tf_graph = tf_graph if tf_graph else tf.get_default_graph()

        # create tensorflow operations/variables on graph
        #################################################

        with self.tf_graph.as_default():

            with tf.variable_scope(self.key):

                # handle operation arguments
                ############################

                # get tensorflow variables and the variable names from operation_args
                tf_vars, var_names = parse_dict(var_dict=operation_args,
                                                var_scope=self.key,
                                                tf_graph=self.tf_graph)

                operator_args = dict()

                # bind tensorflow variables to node and save them in dictionary for the operator class
                for tf_var, var_name in zip(tf_vars, var_names):
                    setattr(self, var_name, tf_var)
                    operator_args[var_name] = {'var': tf_var, 'dependency': False}

                # instantiate operations
                ########################

                tf_ops = []
                for op_name, op in operations.items():

                    # store operator equations
                    self.operations[op_name] = op['equations']

                    # set input dependencies
                    for inp in op['inputs']:
                        operator_args[inp]['dependency'] = True
                        if 'op' not in operator_args[inp].keys():
                            raise ValueError(f"Invalid dependencies found in operator: {op['equations']}. Input "
                                             f"Variable {inp} has not been calculated yet.")

                    # create operator
                    operator = Operator(expressions=op['equations'],
                                        expression_args=operator_args,
                                        tf_graph=self.tf_graph,
                                        key=op_name,
                                        variable_scope=self.key)

                    # collect tensorflow operator
                    tf_ops.append(operator.create())

                    # handle dependencies
                    operator_args[op['output']]['op'] = tf_ops[-1]
                    for arg in operator_args.values():
                        arg['dependency'] = False

                    # bind newly created tf variables to node
                    for var_name, tf_var in operator.args.items():
                        if not hasattr(self, var_name):
                            setattr(self, var_name, tf_var)
                            operator_args[var_name]['var'] = tf_var

                # group tensorflow versions of all operators
                self.update = tf.group(tf_ops, name=f"{self.key}_update")
