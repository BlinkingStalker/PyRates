[![](https://img.shields.io/github/license/pyrates-neuroscience/PyRates.svg)](https://github.com/pyrates-neuroscience/PyRates) 
[![Build Status](https://travis-ci.com/pyrates-neuroscience/PyRates.svg?branch=master)](https://travis-ci.com/pyrates-neuroscience/PyRates)

# PyRates
PyRates is a framework for neural modeling and simulations, developed by Richard Gast and Daniel Rose at the Max Planck Institute of Human Cognitive and Brain Sciences Leipzig. 

Basic features:
---------------
- Every model implemented in PyRates is translated into a tensorflow graph, a powerful compute engine that provides efficient CPU and GPU parallelization. 
- Each model is internally represented by a networkx graph of nodes and edges, with the former representing the model units (i.e. single cells, cell populations, ...) and the latter the information transfer between them. In principle, this allows to implement any kind of dynamic neural system that can be expressed as a graph via PyRates.
- The user has full control over the mathematical equations that nodes and edges are defined by. 
- Model configuration and simulation can be done within a few lines of code.  
- Various templates for rate-based population models are provided that can be used for neural network simulations imediatly.
- Visualization and data analysis tools are provided.
- Tools for the exploration of model parameter spaces are provided.

Documentation
-------------
For a full API of PyRates, see READTHEDOCSLINK.
For examplary simulations and model configurations, please have a look at the jupyter notebooks in the documenation folder.

Reference
---------

If you use this framework, please cite:
PYRATESPAPERCITATION

Contact
-------

If you have questions, problems or suggestions regarding PyRates, please write an email to PYRATESMAIL.
