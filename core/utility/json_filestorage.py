""" Utility functions to store Circuit configurations and data in JSON files
and read/construct circuit from JSON.
"""
from collections import OrderedDict
from typing import Generator, Tuple, Any

from networkx import node_link_data

__author__ = "Daniel Rose"
__status__ = "Development"

# from typing import Union, List
from inspect import getsource
import numpy as np
import json


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):

        # from core.population import Population
        # from core.synapse import Synapse

        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        # elif hasattr(obj, "to_json"):
        #     return obj.to_dict()
        # elif isinstance(obj, Synapse):
        #     attr_dict = obj.to_dict()
        #     # remove synaptic_kernel from dict, if kernel_function is specified
        #     if "kernel_function" in attr_dict:
        #       JansenRitCircuit  attr_dict.pop("synaptic_kernel", None)
        #     return attr_dict
        # elif isinstance(obj, Axon):
        #     return get_attrs(obj)
        elif callable(obj):
            return getsource(obj)
        else:
            return super().default(obj)


class RepresentationBase(object):
    """Class that implements a __repr__ that yields the __init__ function signature with provided arguments in the
    form 'module.Class(arg1, arg2, arg3)'"""

    def __new__(cls, *args, **kwargs):

        # noinspection PyArgumentList
        instance = super().__new__(cls)
        _init_dict = {**kwargs}
        if args:
            _init_dict["args"] = args

        instance._init_dict = _init_dict

        return instance

    def __repr__(self) -> str:
        """Magic method that returns to repr(object). It retrieves the signature of __init__ and maps it to class
        attributes to return a representation in the form 'module.Class(arg1=x, arg2=y, arg3=3)'. Raises AttributeError,
        if the a parameter in the signature cannot be found (is not saved). The current implementation """

        # repr_str = f"{self.__module__!r}.{self.__class__!r}("
        # params = self._get_params()
        from copy import copy
        init_dict = copy(self._init_dict)

        if "args" in init_dict:
            args = init_dict.pop("args", None)
            args = ", ".join((f"{value!r}" for value in args))

        kwargs = ", ".join((f"{name}={value!r}" for name, value in init_dict))
        param_str = f"{args}, {kwargs}"
        _module = self.__class__.__module__
        _class = self.__class__.__name__
        return f"{_module}.{_class}({param_str})"

    def _defaults(self) -> Generator[Tuple[str, Any], None, None]:
        """Inspects the __init__ special method and yields tuples of init parameters and their default values."""

        import inspect

        # retrieve signature of __init__ method
        sig = inspect.signature(self.__init__)

        # retrieve parameters in the signature
        for name, param in sig.parameters.items():
            # check if param has a default value
            if np.all(param.default != inspect.Parameter.empty):
                # yield parameter name and default value
                yield name, param.default

    def to_dict(self, include_defaults=False, include_graph=False, recursive=False) -> OrderedDict:
        """Parse representation string to a dictionary to later convert it to json."""

        _dict = OrderedDict()
        _dict["class"] = {"__module__": self.__class__.__module__, "__name__": self.__class__.__name__}
        # _dict["module"] = self.__class__.__module__
        # _dict["class"] = self.__class__.__name__

        # obtain parameters that were originally passed to __init__
        ###########################################################

        for name, value in self._init_dict.items():
            _dict[name] = value

        # include defaults of parameters that were not specified when __init__ was called.
        ##################################################################################

        if include_defaults:
            default_dict = {}
            for name, value in self._defaults():
                if name not in _dict:  # this fails to get positional arguments that override defaults to keyword args
                    default_dict[name] = value
            _dict["defaults"] = default_dict

        # Include graph if desired
        ##########################

        # check if it quacks like a duck... eh.. has a network_graph like a circuit
        if include_graph and hasattr(self, "network_graph"):
            net_dict = node_link_data(self.network_graph)
            if recursive:
                for node in net_dict["nodes"]:
                    node["data"] = node["data"].to_dict(include_defaults=include_defaults, recursive=True)
            _dict["network_graph"] = net_dict

        # Apply dict transformation recursively to all relevant objects
        ###############################################################

        if recursive:
            for key, item in _dict.items():
                # check if it quacks like a duck... eh.. represents like a RepresentationBase
                # note, however, that "to_dict" is actually implemented by a number of objects outside this codebase
                if hasattr(item, "to_dict"):
                    _dict[key] = item.to_dict(include_defaults=include_defaults, recursive=True)

        return _dict

    def to_json(self, include_defaults=False, include_graph=False, path="", filename=""):
        """Parse a dictionary into """

        # from core.utility.json_filestorage import CustomEncoder

        _dict = self.to_dict(include_defaults=include_defaults, include_graph=include_graph, recursive=True)

        if filename:
            import os
            import errno

            filepath = os.path.join(path, filename)

            # create directory if necessary
            if not os.path.exists(os.path.dirname(filepath)):
                try:
                    os.makedirs(os.path.dirname(filepath))
                except OSError as exc:  # Guard against race condition
                    if exc.errno != errno.EEXIST:
                        raise

            with open(filepath, "w") as outfile:
                json.dump(_dict, outfile, cls=CustomEncoder, indent=4)

        # return json as string
        return json.dumps(_dict, cls=CustomEncoder, indent=2)
