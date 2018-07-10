"""This module contains the node class used to create a network node from a set of operations.
"""

# external imports
from typing import Dict, List, Optional, Union
import tensorflow as tf

# pyrates imports
from pyrates.operator import Operator, OperatorTemplate
from pyrates.parser import parse_dict

# meta infos
from pyrates.abc import AbstractBaseTemplate
from pyrates.utility.yaml_parser import TemplateLoader

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
                 operations: Dict[str, List[str]],
                 operation_args: dict,
                 key: str,
                 tf_graph: Optional[tf.Graph] = None
                 ) -> None:
        """Instantiates node.
        """

        self.key = key
        self.operations = dict()
        self.tf_graph = tf_graph if tf_graph else tf.get_default_graph()

        # instantiate operations
        ########################

        with self.tf_graph.as_default():

            with tf.variable_scope(self.key):

                # get tensorflow variables and the variable names from operation_args
                tf_vars, var_names = parse_dict(operation_args, self.key, self.tf_graph)

                operator_args = dict()

                # bind tensorflow variables to node and save them in dictionary for the operator class
                for tf_var, var_name in zip(tf_vars, var_names):
                    setattr(self, var_name, tf_var)
                    operator_args[var_name] = tf_var

                tf_ops = []

                for op_name, op in operations.items():

                    # store operator equations
                    self.operations[op_name] = op

                    # create operator
                    operator = Operator(expressions=op,
                                        expression_args=operator_args,
                                        tf_graph=self.tf_graph,
                                        key=op_name,
                                        variable_scope=self.key,
                                        dependencies=tf_ops)

                    # collect tensorflow operator
                    tf_ops.append(operator.create())

                # group tensorflow versions of all operators
                self.update = tf.group(tf_ops, name='update')


class NodeTemplate(AbstractBaseTemplate):
    """Generic template for a node in the computational network graph. A single node may encompass several
    different operators. One template defines a typical structure of a given node type."""

    def __init__(self, name: str, path: str, operators: Union[str, List[str], dict],
                 description: str, label: str=None, options: dict = None):
        """For now: only allow single equation in operator template."""

        super().__init__(name, path, description)

        if label:
            self.label = label
        else:
            self.label = self.name

        self.operators = {}  # dictionary with operator path as key and variations to the template as values
        if isinstance(operators, str):
            operator_template = self._load_operator_template(operators)
            self.operators[operator_template] = {}  # single operator path with no variations
        elif isinstance(operators, list):
            for op in operators:
                operator_template = self._load_operator_template(op)
                self.operators[operator_template] = {}  # multiple operator paths with no variations
        elif isinstance(operators, dict):
            for op, variations in operators.items():
                operator_template = self._load_operator_template(op)
                self.operators[operator_template] = variations
        # for op, variations in operators.items():
        #     if "." not in op:
        #         op = f"{path.split('.')[:-1]}.{op}"
        #     self.operators[op] = variations

        self.options = options
        if options:
            raise NotImplementedError

    def _load_operator_template(self, path: str):
        """Load an operator template based on a path"""
        path = self._format_path(path)
        return OperatorTemplate.from_yaml(path)


class NodeTemplateLoader(TemplateLoader):
    """Template loader specific to an OperatorTemplate. """

    def __new__(cls, path):

        return super().__new__(cls, path, NodeTemplate)

    @classmethod
    def update_template(cls, base, name: str, path: str, label: str,
                        operators: Union[str, List[str], dict] = None,
                        description: str = None,
                        options: dict = None):
        """Update all entries of a base node template to a more specific template."""

        if operators:
            cls.update_operators(base.operators, operators)
        else:
            operators = base.operators

        if options:
            # copy old options dict
            options = cls.update_options(base.options, options)
        else:
            options = base.options

        if not description:
            description = base.__doc__  # or do we want to enforce documenting a template?

        return NodeTemplate(name=name, path=path, label=label, operators=operators,
                            description=description, options=options)

    @staticmethod
    def update_operators(base_operators: dict, updates: Union[str, List[str], dict]):
        """Update operators of a given template. Note that currently, only the new information is
        propagated into the operators dictionary. Comparing or replacing operators is not implemented.

        Parameters:
        -----------

        base_operators:
            Reference to one or more operators in the base class.
        updates:
            Reference to one ore more operators in the child class
            - string refers to path or name of single operator
            - list refers to multiple operators of the same class
            - dict contains operator path or name as key and options/defaults as sub-dictionaries
        """
        # updated = base_operators.copy()
        updated = {}
        if isinstance(updates, str):
            updated[updates] = {}  # single operator path with no variations
        elif isinstance(updates, list):
            for path in updates:
                updated[path] = {}  # multiple operator paths with no variations
        elif isinstance(updates, dict):
            for path, variations in updates.items():
                updated[path] = variations
            # dictionary with operator path as key and variations as sub-dictionary
        else:
            raise TypeError("Unable to interpret type of operator updates. Must be a single string,"
                            "list of strings or dictionary.")
        # # Check somewhere, if child operators have same input/output as base operators?
        #
        return updated