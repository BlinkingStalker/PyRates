"""This module contains an edge class that allows to connect variables on a source and a target node via an operator.
"""

# external imports
import tensorflow as tf
from typing import Optional, List

# pyrates imports
from pyrates.operator import Operator
from pyrates.parser import parse_dict
from pyrates.node import Node

# meta infos
__author__ = "Richard Gast"
__status__ = "Development"


class Edge(object):
    """Base edge class to connect a tensorflow variable on source to a tensorflow variable on target via an
    operator.

    Parameters
    ----------
    source
    target
    coupling_op
    coupling_op_args
    key
    tf_graph

    Attributes
    ----------

    Methods
    -------

    Examples
    --------

    References
    ----------

    """
    def __init__(self,
                 source: Node,
                 target: Node,
                 coupling_op: List[str],
                 coupling_op_args: dict,
                 key: Optional[str] = None,
                 tf_graph: Optional[tf.Graph] = None):
        """Instantiates edge.
        """

        self.operator = coupling_op
        self.key = key if key else 'edge0'
        self.tf_graph = tf_graph if tf_graph else tf.get_default_graph()

        with self.tf_graph.as_default():

            with tf.variable_scope(self.key):

                # create operator
                #################

                # replace the coupling operator arguments with the fields from source and target
                inp = getattr(target, coupling_op_args['input'])
                outp = getattr(source, coupling_op_args['output'])
                coupling_op_args['input'] = {'variable_type': 'raw', 'variable': inp}
                coupling_op_args['output'] = {'variable_type': 'raw', 'variable': outp}

                # create tensorflow variables from the additional operator args
                tf_vars, var_names = parse_dict(coupling_op_args, self.key, self.tf_graph)

                operator_args = dict()

                # bind operator args to edge
                for tf_var, var_name in zip(tf_vars, var_names):
                    setattr(self, var_name, tf_var)
                    operator_args[var_name] = tf_var

                # instantiate operator
                operator = Operator(expressions=coupling_op,
                                    expression_args=operator_args,
                                    tf_graph=self.tf_graph,
                                    key=self.key,
                                    variable_scope=self.key)

                # connect source and target variables via operator
                self.project = operator.create()
