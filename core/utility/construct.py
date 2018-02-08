"""Function to construct circuits or other types of instances from a file or dictionary
"""
import json
from typing import Union

from core.axon import Axon
from core.circuit import Circuit
from core.population import Population
from core.synapse import Synapse
# from core.utility.json_filestorage import RepresentationBase

__author__ = "Daniel Rose"
__status__ = "Development"


def construct_circuit_from_file(filename: str, path: str="") -> Circuit:
    """Load a JSON file and construct a circuit from it"""

    import os

    filepath = os.path.join(path, filename)

    with open(filepath, "r") as json_file:
        config_dict = json.load(json_file)

    circuit = construct_instance_from_dict(config_dict)

    return circuit


def construct_instance_from_dict(config_dict: dict) -> Union[Population, Axon, Synapse, Circuit]:
    """Construct a class instance from a dictionary that describes class name and input"""

    from importlib import import_module
    import numpy as np

    cls_dict = config_dict.pop("class")

    module = import_module(cls_dict["__module__"])
    cls = getattr(module, cls_dict["__name__"])

    if "network_graph" in config_dict:
        raise NotImplementedError("Haven't implemented the construction of a circuit from a graph yet.")

    # parse items
    #############

    for key, item in config_dict.items():
        if isinstance(item, list):
            config_dict[key] = np.array(item)

    return cls(**config_dict)
