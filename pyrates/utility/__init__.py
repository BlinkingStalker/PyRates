
# -*- coding: utf-8 -*-
#
#
# PyRates software framework for flexible implementation of neural 
# network models and simulations. See also: 
# https://github.com/pyrates-neuroscience/PyRates
# 
# Copyright (C) 2017-2018 the original authors (Richard Gast and 
# Daniel Rose), the Max-Planck-Institute for Human Cognitive Brain 
# Sciences ("MPI CBS") and contributors
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>
# 
# CITATION:
# 
# Richard Gast and Daniel Rose et. al. in preparation
"""
"""

__author__ = "Daniel F. Rose, Richard Gast"
__status__ = "Development"

from .visualization import *
from .data_analysis import *
from .grid_search import grid_search
from .helper_functions import set_instance
from .helper_functions import update_param
from .helper_functions import interpolate_array
from .helper_functions import nmrse
from .helper_functions import deep_compare
from .helper_functions import make_iterable
from .bio_features import *
from .filestorage import get_simulation_data
from .filestorage import save_simulation_data_to_file
from .filestorage import read_simulation_data_from_file
from .mne_wrapper import mne_from_csv, mne_from_dataframe

# from .construct import construct_circuit_from_file  # this one fails tests due to circular import


# from .json_filestorage import read_config_from_circuit

# from .pyRates_wrapper import circuit_wrapper
