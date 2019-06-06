# -*- coding: utf-8 -*-
#
#
# PyRates software framework for flexible implementation of neural
# network model_templates and simulations. See also:
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

"""Contains wrapper classes for different backends that are needed by the parser module.

A new backend needs to implement the following methods

Methods
-------
__init__
run
add_var
add_op
add_layer

Currently supported backends:
- Tensorflow: TensorflowBackend.

"""

# external imports
import time as t
from typing import Optional, Dict, Callable, List, Union, Tuple, Any
import numpy as np
import tensorflow as tf
from copy import deepcopy
from numba import jit, prange
import os
import sys
from importlib import import_module
import threading

# meta infos
__author__ = "Richard Gast"
__status__ = "development"


#############################################
# basic classes for operators and variables #
#############################################

class NumpyVar(np.ndarray):

    def __new__(cls, vtype: str, dtype: str, shape: tuple, value: Any, name: str, backend: Any):

        # check whether necessary arguments were provided
        if all([arg is None for arg in [shape, value, dtype]]):
            raise ValueError('Either `value` or `shape` and `dtype` need to be provided')

        # get shape
        if not shape:
            shape = value.shape if hasattr(value, 'shape') else ()

        # get data type
        if not dtype:
            dtype = value.dtype if hasattr(value, 'dtype') else type(value)
        dtype = dtype.name if hasattr(dtype, 'name') else str(dtype)
        if dtype in backend.dtypes:
            dtype = backend.dtypes[dtype]
        else:
            for dtype_tmp in backend.dtypes:
                if dtype_tmp in dtype:
                    dtype = backend.dtypes[dtype_tmp]
                    break
            else:
                raise ValueError(f'Invalid data type: {dtype}. Check documentation of the backend wrapper in use for '
                                 'valid data types.')

        # get value
        if value is None:
            value = np.zeros(shape=shape, dtype=dtype)
        elif not hasattr(value, 'shape'):
            if type(value) is list:
                value = np.zeros(shape=shape, dtype=dtype) + np.asarray(value).reshape(shape)
            else:
                value = np.zeros(shape=shape, dtype=dtype) + value

        if vtype == 'constant':
            return value

        # create variable
        obj = np.array(value).view(cls)
        obj.short_name = name.split('/')[-1]
        obj.name = name

        return obj

    def eval(self):
        return self[:]


class TensorflowVar(tf.Variable):

    def __new__(cls, vtype: str, dtype: str, shape: tuple, value: Any, name: str, backend: Any):

        # check whether necessary arguments were provided
        if all([arg is None for arg in [shape, value, dtype]]):
            raise ValueError('Either `value` or `shape` and `dtype` need to be provided')

        # get shape
        if not shape:
            shape = value.shape if hasattr(value, 'shape') else ()

        # get data type
        if not dtype:
            dtype = value.dtype if hasattr(value, 'dtype') else type(value)
        dtype = dtype.name if hasattr(dtype, 'name') else str(dtype)
        if dtype in backend.dtypes:
            dtype = backend.dtypes[dtype]
        else:
            for dtype_tmp in backend.dtypes:
                if dtype_tmp in dtype:
                    dtype = backend.dtypes[dtype_tmp]
                    break
            else:
                raise ValueError(f'Invalid data type: {dtype}. Check documentation of the backend wrapper in use for '
                                 'valid data types.')

        # get value
        if value is None:
            value = tf.zeros(shape=shape, dtype=dtype)
        elif not hasattr(value, 'shape'):
            if type(value) is list:
                value = tf.zeros(shape=shape, dtype=dtype) + tf.constant(value).reshape(shape)
            else:
                value = tf.zeros(shape=shape, dtype=dtype) + value

        if vtype == 'constant':
            return value

        # create variable object
        obj = tf.Variable(value, name=name)
        obj.short_name = name.split('/')[-1]
        return obj


class PyRatesOp:

    n_consts = 0

    def __init__(self, op: str, name: str, decorator: str, *args) -> None:
        """

        Parameters
        ----------
        op
        backend
        args
        """

        if not decorator:
            decorator = "@jit(nopython=True, fastmath=True)"
        self.op = op
        self.short_name = name.split('/')[-1]
        self.name = name
        op_dict = self.generate_op(self.short_name, op, args, decorator)
        self.func = op_dict['func']
        self._callable = op_dict['callable']
        self.call = op_dict['call']
        self.return_val = op_dict['return_val']
        self.args = op_dict['args'].copy()
        self.arg_names = op_dict['arg_names'].copy()
        self.shape = op_dict['shape']
        self.dtype = op_dict['dtype']
        self.constant = op_dict['constant']
        self.input_ops = op_dict['input_ops']

    @classmethod
    def generate_op(cls, name, op, args, decorator):

        # initialization
        code_gen = CodeGen()
        results = {'func': None, 'args': [], 'arg_names': [], 'constant': False, 'shape': (), 'dtype': 'float32',
                   'call': None, 'return_val': None, 'input_ops': []}

        results_args = []
        results_arg_names = []

        # setup function head
        #####################

        code_gen.add_code_line(decorator)
        code_gen.add_linebreak()
        code_gen.add_code_line(f"def {name}(")

        # process arguments
        n_vars = 0
        for idx, arg in enumerate(args):
            if type(arg) is PyRatesOp or type(arg) is PyRatesIndexOp:
                results['input_ops'].append(arg.name)
                pop_indices = []
                for arg_tmp in arg.arg_names:
                    if arg_tmp in results['arg_names']:
                        pop_indices.append(arg.arg_names.index(arg_tmp))
                    else:
                        code_gen.add_code_line(f"{arg_tmp},")
                new_args = arg.args.copy()
                new_arg_names = arg.arg_names.copy()
                for i, pop_idx in enumerate(pop_indices):
                    new_args.pop(pop_idx-i)
                    new_arg_names.pop(pop_idx-i)
                results_args.append({'args': new_args, 'call': arg.return_val,
                                     'arg_names': new_arg_names})
                results_arg_names.append(arg.short_name)
                results['args'] += new_args
                results['arg_names'] += new_arg_names
                n_vars += 1
            elif type(arg) in (NumpyVar, TensorflowVar):
                n_vars += 1
                arg_name = arg.short_name
                results_args.append(arg)
                results_arg_names.append(arg_name)
                results['args'].append(arg)
                results['arg_names'].append(arg_name)
                code_gen.add_code_line(f"{arg_name},")
            elif type(arg) is tuple or type(arg) is list:
                tuple_begin = '('
                results_args.append(tuple_begin)
                results_arg_names.append(tuple_begin)
                results['args'].append(tuple_begin)
                results['arg_names'].append(tuple_begin)
                for arg_tmp in arg:
                    if type(arg_tmp) is PyRatesOp or type(arg_tmp) is PyRatesIndexOp:
                        results['input_ops'].append(arg_tmp.name)
                        pop_indices = []
                        for arg_tmp2 in arg_tmp.arg_names:
                            if arg_tmp2 in results['arg_names']:
                                pop_indices.append(arg_tmp.arg_names.index(arg_tmp2))
                            else:
                                code_gen.add_code_line(f"{arg_tmp2},")
                        new_args = arg_tmp.args.copy()
                        new_arg_names = arg_tmp.arg_names.copy()
                        for i, pop_idx in enumerate(pop_indices):
                            new_args.pop(pop_idx - i)
                            new_arg_names.pop(pop_idx - i)
                        results_args.append({'args': new_args, 'call': arg_tmp.return_val,
                                             'arg_names': new_arg_names})
                        results_arg_names.append(arg_tmp.short_name)
                        results['args'] += new_args
                        results['arg_names'] += new_arg_names
                        n_vars += 1
                    elif type(arg_tmp) in (NumpyVar, TensorflowVar):
                        n_vars += 1
                        arg_name = arg_tmp.short_name
                        results_args.append(arg_tmp)
                        results_arg_names.append(arg_name)
                        results['args'].append(arg_tmp)
                        results['arg_names'].append(arg_name)
                        code_gen.add_code_line(f"{arg_name},")
                    else:
                        cls.n_consts += 1
                        arg_name = f"c_{cls.n_consts}"
                        results_args.append(arg_tmp)
                        results_arg_names.append(arg_name)
                        results['args'].append(arg_tmp)
                        results['arg_names'].append(arg_name)
                        code_gen.add_code_line(f"{arg_name},")
                tuple_end = ')'
                results_args.append(tuple_end)
                results_arg_names.append(tuple_end)
                results['args'].append(tuple_end)
                results['arg_names'].append(tuple_end)
            else:
                if type(arg) is str:
                    arg_name = arg
                else:
                    cls.n_consts += 1
                    arg_name = f"c_{cls.n_consts}"
                    code_gen.add_code_line(f"{arg_name},")
                results_args.append(arg)
                results_arg_names.append(arg_name)
                results['args'].append(arg)
                results['arg_names'].append(arg_name)

        # end function head
        code_gen.code[-1] = code_gen.code[-1][:-1]
        code_gen.add_code_line(")")
        results['call'] = code_gen.generate()
        code_gen.add_code_line(":")
        code_gen.add_linebreak()
        code_gen.add_indent()

        # setup return line
        ###################

        code_gen.add_code_line(f"return ")
        return_gen = CodeGen()
        return_gen.add_code_line(f"{op}(")

        # add arguments
        for key, arg in zip(results_arg_names, results_args):
            if type(arg) is str:
                if arg is "[":
                    return_gen.code[-1] = code_gen.code[-1][:-1]
                if arg is "(":
                    return_gen.add_code_line(f"{arg}")
                else:
                    return_gen.add_code_line(f"{arg},")
                idx = results['args'].index(arg)
                results['args'].pop(idx)
                results['arg_names'].pop(idx)
            elif type(arg) is dict:
                return_gen.add_code_line(f"{arg['call']},")
            else:
                return_gen.add_code_line(f"{key},")

        # add function end
        return_gen.code[-1] = return_gen.code[-1][:-1]
        return_gen.add_code_line(")")
        results['return_val'] = return_gen.generate()
        code_gen.add_code_line(results['return_val'])

        # check whether operation arguments contain merely constants
        if n_vars == 0:
            results['constant'] = True

        # generate op
        results['func'] = code_gen.generate()
        func_dict = {}
        exec(results['func'], globals(), func_dict)
        results['callable'] = func_dict.pop(name)

        # set shape and dtype of op according to result of eval
        args_tmp = deepcopy(results['args'])
        op_tmp = results['callable'](*results['args'])
        results['shape'] = op_tmp.shape if hasattr(op_tmp, 'shape') else ()
        results['dtype'] = op_tmp.dtype if hasattr(op_tmp, 'dtype') else type(op_tmp)

        # reset initial values of args and kwargs
        for arg_tmp, arg in zip(args_tmp, results['args']):
            if hasattr(arg, 'shape') and len(arg.shape) > 0 and type(arg) is not PyRatesOp:
                arg[:] = arg_tmp[:]
            elif type(arg) is tuple or type(arg) is list and type(arg) is not PyRatesOp:
                for a_tmp, a in zip(arg_tmp, arg):
                    if hasattr(a, 'shape') and arg.shape:
                        a[:] = a_tmp[:]

        return results

    def eval(self):
        return self._callable(*self.args)


class PyRatesAssignOp(PyRatesOp):

    @classmethod
    def generate_op(cls, name, op, args, decorator):

        # initialization
        code_gen = CodeGen()
        results = {'func': None, 'args': [], 'arg_names': [], 'constant': False, 'shape': (), 'dtype': 'float32', 'call': None,
                   'input_ops': [], 'return_val': None}
        results_args = []
        results_arg_names = []

        # extract variables
        var, upd = args[0:2]
        if len(args) > 2:
            if hasattr(args[2], 'name'):
                var_idx = f"[{args[2].short_name}]"
                key = f"{args[2].short_name}"
            else:
                var_idx = "[idx]"
                key = "idx"
            results_args.append(args[2])
            results_arg_names.append(key)
        elif hasattr(var, 'shape') and len(var.shape) > 0:
            var_idx = "[:]"
        else:
            var_idx = ""
        upd_idx = "[:]" if hasattr(upd, 'shape') and len(upd.shape) > 0 else ""

        var_key = var.short_name
        results_args.append(var)
        results_arg_names.append(var_key)
        upd_key = upd.short_name if hasattr(upd, 'short_name') else "upd"
        upd_pos = len(results_args)
        results_args.append(upd)
        results_arg_names.append(upd_key)

        # setup function head
        #####################

        code_gen.add_code_line(decorator)
        code_gen.add_linebreak()
        code_gen.add_code_line(f"def {name}(")

        for idx, (key, arg) in enumerate(zip(results_arg_names, results_args)):
            if type(arg) is PyRatesOp or type(arg) is PyRatesIndexOp:
                pop_indices = []
                for arg_tmp in arg.arg_names:
                    if arg_tmp in results['arg_names']:
                        pop_indices.append(arg.arg_names.index(arg_tmp))
                    else:
                        code_gen.add_code_line(f"{arg_tmp},")
                new_args = arg.args.copy()
                new_arg_names = arg.arg_names.copy()
                for i, pop_idx in enumerate(pop_indices):
                    new_args.pop(pop_idx - i)
                    new_arg_names.pop(pop_idx - i)
                results_args[idx] = {'args': new_args, 'call': arg.return_val, 'arg_names': new_arg_names}
                results['input_ops'].append(arg.name)
                results['args'] += new_args
                results['arg_names'] += new_arg_names
            else:
                results['args'].append(arg)
                results['arg_names'].append(key)
                code_gen.add_code_line(f"{key},")
        code_gen.code[-1] = code_gen.code[-1][:-1]
        code_gen.add_code_line("):")
        results['call'] = code_gen.generate()
        code_gen.add_linebreak()
        code_gen.add_indent()

        # assign update to variable and return variable
        ###############################################

        upd_str = results_args[upd_pos]['call'] if type(results_args[upd_pos]) is dict else upd_key
        if op in ["=", "+=", "-=", "*=", "/="]:
            code_gen.add_code_line(f"{var_key}{var_idx} {op} {upd_str}{upd_idx}")
        else:
            code_gen.add_code_line(f"{var_key}{var_idx}.{op}({upd_str}{upd_idx})")
        code_gen.add_linebreak()
        code_gen.add_code_line(f"return {var_key}")
        results['return_val'] = var_key

        # generate op
        func_dict = {}
        results['func'] = code_gen.generate()
        exec(results['func'], globals(), func_dict)
        results['callable'] = func_dict.pop(name)

        # set shape and dtype of op according to result of eval
        results['shape'] = var.shape
        results['dtype'] = var.dtype

        return results


class PyRatesIndexOp(PyRatesOp):

    @classmethod
    def generate_op(cls, name, op, args, decorator):

        # initialization
        code_gen = CodeGen()
        results = {'func': None, 'args': [], 'arg_names': [], 'constant': False, 'shape': (), 'dtype': 'float32',
                   'call': None, 'input_ops': [], 'return_val': None}

        # extract variable
        var_tmp = args[0]
        if type(var_tmp) is PyRatesOp or type(var_tmp) is PyRatesIndexOp:
            var = var_tmp.return_val
            pop_indices = []
            for arg_tmp in var_tmp.arg_names:
                if arg_tmp in results['arg_names']:
                    pop_indices.append(var_tmp.arg_names.index(arg_tmp))
            new_args = var_tmp.args.copy()
            new_arg_names = var_tmp.arg_names.copy()
            for i, pop_idx in enumerate(pop_indices):
                new_args.pop(pop_idx - i)
                new_arg_names.pop(pop_idx - i)
            results['args'] += new_args
            results['arg_names'] += new_arg_names
        elif type(var_tmp) in (NumpyVar, TensorflowVar):
            var = var_tmp.short_name
            results['args'].append(var_tmp)
            results['arg_names'].append(var_tmp.short_name)
        else:
            var = f"c_{cls.n_consts}"
            results['args'].append(var_tmp)
            results['arg_names'].append(var)
            cls.n_consts += 1

        # extract idx
        idx = args[1]
        if type(idx) is PyRatesOp or type(idx) is PyRatesIndexOp:
            var_idx = f"[{idx.return_val}]"
            pop_indices = []
            for arg_tmp in idx.arg_names:
                if arg_tmp in results['arg_names']:
                    pop_indices.append(idx.arg_names.index(arg_tmp))
            new_args = idx.args.copy()
            new_arg_names = idx.arg_names.copy()
            for i, pop_idx in enumerate(pop_indices):
                new_args.pop(pop_idx - i)
                new_arg_names.pop(pop_idx - i)
            results['args'] += new_args
            results['arg_names'] += new_arg_names
        elif type(idx) in (NumpyVar, TensorflowVar):
            var_idx = f"[{idx.short_name}]"
            key = f"{idx.name}"
            results['args'].append(idx)
            results['arg_names'].append(key)
        elif type(idx) is str or "int" in str(type(idx)) or "float" in str(type(idx)):
            var_idx = f"[{idx}]"
        elif hasattr(idx, 'shape'):
            var_idx = "[idx]"
            key = "idx"
            results['args'].append(idx)
            results['arg_names'].append(key)
        else:
            raise ValueError(f'Index type not understood: {idx}. Please consider a nother form of variable indexing.')

        # setup function head
        #####################

        # beginning
        code_gen.add_code_line(decorator)
        code_gen.add_linebreak()
        code_gen.add_code_line(f"def {name}(")

        # variable and index
        for arg in results['arg_names']:
            code_gen.add_code_line(f"{arg},")

        # remaining arguments
        n_vars = 0
        for idx, arg in enumerate(args[2:]):
            if type(arg) is PyRatesOp or type(arg) is PyRatesIndexOp:
                results['input_ops'].append(arg.name)
                pop_indices = []
                for arg_tmp in arg.arg_names:
                    if arg_tmp in results['arg_names']:
                        pop_indices.append(arg.arg_names.index(arg_tmp))
                    else:
                        code_gen.add_code_line(f"{arg_tmp},")
                new_args = arg.args.copy()
                new_arg_names = arg.arg_names.copy()
                for i, pop_idx in enumerate(pop_indices):
                    new_args.pop(pop_idx - i)
                    new_arg_names.pop(pop_idx - i)
                results['args'] += new_args
                results['arg_names'] += new_arg_names
                n_vars += 1
            elif type(arg) in (NumpyVar, TensorflowVar) or hasattr(arg, 'numpy'):
                n_vars += 1
                arg_name = arg.short_name
                results['args'].append(arg)
                results['arg_names'].append(arg_name)
                code_gen.add_code_line(f"{arg_name},")
            elif type(arg) is tuple or type(arg) is list:
                tuple_begin = '('
                results['args'].append(tuple_begin)
                results['arg_names'].append(tuple_begin)
                for arg_tmp in arg:
                    if type(arg_tmp) is PyRatesOp or type(arg_tmp) is PyRatesIndexOp:
                        results['input_ops'].append(arg_tmp.name)
                        pop_indices = []
                        for arg_tmp2 in arg_tmp.arg_names:
                            if arg_tmp2 in results['arg_names']:
                                pop_indices.append(arg_tmp.arg_names.index(arg_tmp2))
                            else:
                                code_gen.add_code_line(f"{arg_tmp2},")
                        new_args = arg_tmp.args.copy()
                        new_arg_names = arg_tmp.arg_names.copy()
                        for i, pop_idx in enumerate(pop_indices):
                            new_args.pop(pop_idx - i)
                            new_arg_names.pop(pop_idx - i)
                        results['args'] += new_args
                        results['arg_names'] += new_arg_names
                        n_vars += 1
                    elif type(arg_tmp) in (NumpyVar, TensorflowVar):
                        n_vars += 1
                        arg_name = arg_tmp.short_name
                        results['args'].append(arg_tmp)
                        results['arg_names'].append(arg_name)
                        code_gen.add_code_line(f"{arg_name},")
                    else:
                        cls.n_consts += 1
                        arg_name = f"c_{cls.n_consts}"
                        results['args'].append(arg_tmp)
                        results['arg_names'].append(arg_name)
                        code_gen.add_code_line(f"{arg_name},")
                tuple_end = ')'
                results['args'].append(tuple_end)
                results['arg_names'].append(tuple_end)
            else:
                if type(arg) is str:
                    arg_name = arg
                else:
                    cls.n_consts += 1
                    arg_name = f"c_{cls.n_consts}"
                    code_gen.add_code_line(f"{arg_name},")
                results['args'].append(arg)
                results['arg_names'].append(arg_name)

        # end of function head
        code_gen.code[-1] = code_gen.code[-1][:-1]
        code_gen.add_code_line("):")
        results['call'] = code_gen.generate()
        code_gen.add_linebreak()
        code_gen.add_indent()

        # apply index to variable and return variable
        #############################################

        return_line = f"{var}{var_idx}"
        code_gen.add_code_line(f"return {return_line}")
        results['return_val'] = return_line

        # generate op
        func_dict = {}
        results['func'] = code_gen.generate()
        exec(results['func'], globals(), func_dict)
        results['callable'] = func_dict.pop(name)

        # set shape and dtype of op according to result of eval
        args_tmp = deepcopy(results['args'])
        op_tmp = results['callable'](*results['args'])
        results['shape'] = op_tmp.shape if hasattr(op_tmp, 'shape') else ()
        results['dtype'] = op_tmp.dtype if hasattr(op_tmp, 'dtype') else type(op_tmp)

        # reset initial values of args and kwargs
        for arg_tmp, arg in zip(args_tmp, results['args']):
            if hasattr(arg, 'shape') and len(arg.shape) > 0 and type(arg) is not PyRatesOp:
                try:
                    arg[:] = arg_tmp[:]
                except TypeError:
                    pass
            elif type(arg) is tuple or type(arg) is list and type(arg) is not PyRatesOp:
                for a_tmp, a in zip(arg_tmp, arg):
                    if hasattr(a, 'shape') and len(arg.shape) > 0:
                        try:
                            a[:] = a_tmp[:]
                        except TypeError:
                            pass

        return results


###########################
# backend wrapper classes #
###########################


class NumpyBackend(object):
    """Wrapper to numpy.

    Parameters
    ----------
    ops
        Additional operations this backend instance can perform, defined as key-value pairs.
    dtypes
        Additional data-types this backend instance can use, defined as key-value pairs.

    """

    def __init__(self,
                 ops: Optional[Dict[str, str]] = None,
                 dtypes: Optional[Dict[str, object]] = None,
                 ) -> None:
        """Instantiates tensorflow backend, i.e. a tensorflow graph.
        """

        super().__init__()

        # define operations and datatypes of the backend
        ################################################

        # base math operations
        self.ops = {"+": {'name': "numpy_add", 'call': "np.add"},
                    "-": {'name': "numpy_subtract", 'call': "np.subtract"},
                    "*": {'name': "numpy_multiply", 'call': "np.multiply"},
                    "/": {'name': "numpy_divide", 'call': "np.divide"},
                    "%": {'name': "numpy_modulo", 'call': "np.mod"},
                    "^": {'name': "numpy_power", 'call': "np.power"},
                    "**": {'name': "numpy_power_float", 'call': "np.float_power"},
                    "@": {'name': "numpy_dot", 'call': "np.dot"},
                    ".T": {'name': "numpy_transpose", 'call': "np.transpose"},
                    ".I": {'name': "numpy_invert", 'call': "np.invert"},
                    ">": {'name': "numpy_greater", 'call': "np.greater"},
                    "<": {'name': "numpy_less", 'call': "np.less"},
                    "==": {'name': "numpy_equal", 'call': "np.equal"},
                    "!=": {'name': "numpy_not_equal", 'call': "np.not_equal"},
                    ">=": {'name': "numpy_greater_equal", 'call': "np.greater_equal"},
                    "<=": {'name': "numpy_less_equal", 'call': "np.less_equal"},
                    "=": {'name': "assign", 'call': "="},
                    "+=": {'name': "assign_add", 'call': "+="},
                    "-=": {'name': "assign_subtract", 'call': "-="},
                    "*=": {'name': "assign_multiply", 'call': "*="},
                    "/=": {'name': "assign_divide", 'call': "/="},
                    "neg": {'name': "negative", 'call': "neg_one"},
                    "sin": {'name': "numpy_sin", 'call': "np.sin"},
                    "cos": {'name': "numpy_cos", 'call': "np.cos"},
                    "tan": {'name': "numpy_tan", 'call': "np.tan"},
                    "atan": {'name': "numpy_atan", 'call': "np.arctan"},
                    "abs": {'name': "numpy_abs", 'call': "np.abs"},
                    "sqrt": {'name': "numpy_sqrt", 'call': "np.sqrt"},
                    "sq": {'name': "numpy_square", 'call': "np.square"},
                    "exp": {'name': "numpy_exp", 'call': "np.exp"},
                    "max": {'name': "numpy_max", 'call': "np.max"},
                    "min": {'name': "numpy_min", 'call': "np.min"},
                    "argmax": {'name': "numpy_transpose", 'call': "np.argmax"},
                    "argmin": {'name': "numpy_argmin", 'call': "np.argmin"},
                    "round": {'name': "numpy_round", 'call': "np.round"},
                    "sum": {'name': "numpy_sum", 'call': "np.sum"},
                    "mean": {'name': "numpy_mean", 'call': "np.mean"},
                    "concat": {'name': "numpy_concatenate", 'call': "np.concatenate"},
                    "reshape": {'name': "numpy_reshape", 'call': "np.reshape"},
                    "shape": {'name': "numpy_shape", 'call': "np.shape"},
                    "dtype": {'name': "numpy_dtype", 'call': "np.dtype"},
                    'squeeze': {'name': "numpy_squeeze", 'call': "np.squeeze"},
                    "roll": {'name': "numpy_roll", 'call': "np.roll"},
                    "cast": {'name': "numpy_cast", 'call': "np.cast"},
                    "randn": {'name': "numpy_randn", 'call': "np.randn"},
                    "ones": {'name': "numpy_ones", 'call': "np.ones"},
                    "zeros": {'name': "numpy_zeros", 'call': "np.zeros"},
                    "range": {'name': "numpy_arange", 'call': "np.arange"},
                    "softmax": {'name': "pyrates_softmax", 'call': "pr_softmax"},
                    "sigmoid": {'name': "pyrates_sigmoid", 'call': "pr_sigmoid"},
                    "tanh": {'name': "numpy_tanh", 'call': "np.tanh"},
                    "index": {'name': "pyrates_index", 'call': "pyrates_index"},
                    "mask": {'name': "pyrates_mask", 'call': "pr_mask"},
                    "group": {'name': "pyrates_group", 'call': "pr_group"},
                    "no_op": {'name': "pyrates_identity", 'call': "pr_identity"},
                    }
        if ops:
            self.ops.update(ops)

        self.dtypes = {"float16": np.float16,
                       "float32": np.float32,
                       "float64": np.float64,
                       "int16": np.int16,
                       "int32": np.int32,
                       "int64": np.int64,
                       "uint16": np.uint16,
                       "uint32": np.uint32,
                       "uint64": np.uint64,
                       "complex64": np.complex64,
                       "complex128": np.complex128,
                       "bool": np.bool
                       }
        if dtypes:
            self.dtypes.update(dtypes)

        self.vars = dict()
        self.layers = [[]]
        self.var_counter = {}
        self.op_counter = {}
        self.layer = 0
        self.op_indices = {}

    def run(self,
            steps: int,
            inputs: List[dict],
            outputs: Dict[str, tf.Variable],
            layers: Optional[list] = None,
            sampling_steps: Optional[int] = None,
            sampling_layer: Optional[int] = None,
            out_dir: Optional[str] = None,
            profile: Optional[str] = None,
            **kwargs
            ) -> Union[Dict[str, tf.Variable], Tuple[dict, float, float]]:
        """Executes all operations in tensorflow graph for a given number of steps.

        Parameters
        ----------
        steps
            Number of graph evaluations.
        inputs
            Inputs fed into the graph.
        outputs
            Variables in the graph to store the history from.
        layers
            Indices of layers to evaluate. If None, all will be evaluated.
        sampling_steps
            Number of graph execution steps to combine into a single output step.
        sampling_layer
            Index of the layer containing sampling ops.
        out_dir
            Directory to write the session log into.
        profile
            Can be used to extract information about graph execution time and memory load. Can be:
            - `t` for returning the total graph execution time.
            - `m` for returning the peak memory consumption during graph excecution.
            - `mt` or `tm` for both

        Returns
        -------
        Union[Dict[str, tf.Variable], Tuple[dict, float, float]]
            If `profile` was requested, a tuple is returned that contains
                1) the results dictionary
                2) the simulation time if `t` was requested, else None.
                3) the peak memory consumption if `m` was requested, else None.
            If not, only the results dictionary is returned which contains a numpy array with results for each
            output key that was provided via `outputs`.

        """

        # initializations
        #################

        if not sampling_steps:
            sampling_steps = 1

        # initialize session log
        if out_dir:
            # TODO : implement log files
            pass

        # initialize profiler
        if profile is None:
            profile = ''
        if 'm' in profile:
            # TODO: implement memory tracker
            time_and_memory = None
        if 't' in profile:
            t0 = t.time()

        # set layers to evaluate and to sample
        if sampling_layer is None:
            sampling_layer = -1
        eval_layers = layers if layers else np.arange(len(self.layers)).tolist()
        if sampling_layer in eval_layers:
            idx = eval_layers.index(sampling_layer)
            eval_layers.pop(idx)

        # graph execution
        #################

        # map layers that need to be executed to compiled network structure
        eval_layers = list(set(eval_layers))
        layer_run_funcs = self.compile()
        for i, l in enumerate(eval_layers.copy()):
            if layer_run_funcs[l] is None:
                eval_layers.pop(eval_layers.index(l))
            else:
                eval_layers[i] = layer_run_funcs[l]
        sampling_layer = layer_run_funcs[sampling_layer]

        # simulate backend behavior for each time-step
        if any(inputs):
            self._run_inp(eval_layers, sampling_layer, inputs, steps, sampling_steps)
        else:
            self._run_no_inp(eval_layers, sampling_layer, steps, sampling_steps)

        # output storage and clean-up
        #############################

        # store output variables in output dictionary
        for key, var in outputs.items():
            outputs[key] = var.eval()

        # store profiling results
        if 't' in profile:
            sim_time = t.time() - t0
        else:
            sim_time = 0.
        if 'm' in profile:
            peak_memory = 'much'
        else:
            peak_memory = 0.

        if profile:
            return outputs, sim_time, peak_memory
        return outputs

    def add_var(self,
                vtype: str,
                name: str,
                value: Optional[Any] = None,
                shape: Optional[Union[tuple, list, np.shape]] = None,
                dtype: Optional[Union[str, np.dtype]] = None,
                **kwargs
                ) -> NumpyVar:
        """Adds a variable to the backend.

        Parameters
        ----------
        vtype
            Variable type. Can be
                - `state_var` for variables that can change over time.
                - `constant` for non-changing variables.
                - `placeholder` for variables with a value unknown during initialization.
        name
            Name of the variable.
        value
            Value of the variable. Not needed for placeholders.
        shape
            Shape of the variable.
        dtype
            Datatype of the variable.
        kwargs
            Additional keyword arguments passed to the tensorflow functions.

        Returns
        -------
        PyRatesVar
            Handle for the numpy variable.

        """

        # processs input arguments
        ##########################

        # extract variable scope
        scope = kwargs.pop('scope', None)
        if scope:
            name = f'{scope}/{name}'
        if name in self.var_counter:
            name_old = name
            name = f"{name}_{self.var_counter[name]}"
            self.var_counter[name_old] += 1
        else:
            self.var_counter[name] = 1

        # create variable
        #################

        var = self._create_var(vtype=vtype, dtype=dtype, shape=shape, value=value, name=name)
        self.vars[name] = var
        return var

    def add_op(self,
               op: str,
               *args,
               **kwargs
               ) -> Union[PyRatesOp, NumpyVar]:
        """Add operation to the backend.

        Parameters
        ----------
        op
            Key of the operation. Needs to be a key of `TensorflowGraph.ops`
        args
            Positional arguments to be passed to the operation.
        kwargs
            Keyword arguments to be passed to the operation.

        Returns
        -------
        Union[PyRatesOp, PyRatesVar]
            Handle for the lambda-numpy function

        """

        # process input arguments
        #########################

        # extract scope
        scope = kwargs.pop('scope', None)

        # extract graph dependencies
        dependencies = kwargs.pop('dependencies', [])

        # extract operator decorator
        decorator = kwargs.pop('decorator', "")

        name = kwargs.pop('name', None)
        if name and scope:
            name = f'{scope}/{name}'
        elif scope:
            name = f'{scope}/assign' if '=' in op else f"{scope}/{self.ops[op]['name']}"
        if name in self.op_counter:
            name_old = name
            name = f"{name}_{self.op_counter[name]}"
            self.op_counter[name_old] += 1
        else:
            self.op_counter[name] = 1

        if dependencies:
            found = False
            for dep in dependencies:
                if dep.name == name:
                    found = True
                    break
            if found:
                self.add_layer()

        # create operation
        ##################

        # generate op
        if op in ["=", "+=", "-=", "*=", "/="]:
            op = PyRatesAssignOp(self.ops[op]['call'], self.ops[op]['name'], decorator, *args)
        elif op is "index":
            op = PyRatesIndexOp(self.ops[op]['call'], self.ops[op]['name'], decorator, *args)
        else:
            if op is "cast":
                args = list(args)
                for dtype in self.dtypes:
                    if dtype in str(args[1]):
                        args[1] = self.dtypes[dtype]
                        break
                args = tuple(args)
            op = PyRatesOp(self.ops[op]['call'], self.ops[op]['name'], decorator, *args)

        # remove op inputs from layers (need not be evaluated anymore)
        for op_name in op.input_ops:
            idx_1, idx_2 = self.op_indices[op_name]
            self.layers[idx_1][idx_2] = None

        # add op to the graph
        if op.constant:
            new_var = op.eval()
            if hasattr(new_var, 'shape'):
                name = f'{name}_evaluated'
                return self.add_var(vtype='constant', name=name, value=new_var)
            else:
                return new_var

        self.layers[self.layer].append(op)
        self.op_indices[op.name] = (self.layer, len(self.layers[self.layer])-1)
        return op

    def add_layer(self, to_beginning=False) -> None:
        """Adds a new layer to the backend and sets cursor to that layer.

        Parameters
        ----------

        Returns
        -------
        None

        """

        if to_beginning:
            self.layers = [[]] + self.layers
            self.layer = 0
        else:
            self.layer = len(self.layers)
            self.layers.append([])

    def next_layer(self):
        if self.layer == len(self.layers)-1:
            self.add_layer()
        else:
            self.layer += 1

    def previous_layers(self):
        if self.layer == 0:
            self.add_layer(to_beginning=True)
        else:
            self.layer -= 1

    def top_layer(self):
        self.layer = len(self.layers)-1

    def bottom_layer(self):
        self.layer = 0

    def clear(self):
        """Resets all tensorflow operations on the graph.
        """
        self.vars.clear()
        self.layers = [[]]
        self.op_counter = 0
        self.var_counter = 0
        self.layer = 0

    def get_var(self, name, updated=True):
        if updated:
            return self.vars[name]
        else:
            try:
                return self.vars[f'{name}_old']
            except KeyError:
                return self.vars[name]

    def get_layer(self, idx):
        return self.layers[idx]

    def eval_var(self, var):
        return self.vars[var].eval()

    def eval_layer(self, layer):
        return [func(*args) for func, args in layer]

    def compile(self, build_dir=None):

        # remove empty layers and operators
        layer_mapping = {}
        new_layer_idx = 0
        for layer_idx, layer in enumerate(self.layers.copy()):
            for op in layer.copy():
                if op is None:
                    layer.pop(layer.index(op))
            if len(layer) == 0:
                self.layers.pop(new_layer_idx)
                layer_mapping.update({layer_idx: None})
            else:
                layer_mapping.update({layer_idx: new_layer_idx})
                new_layer_idx += 1

        # create directory in which to store layer scripts
        orig_path = os.getcwd()
        if build_dir:
            os.mkdir(build_dir)
        dir_name = f"{build_dir}/pyrates_build" if build_dir else "pyrates_build"
        try:
            os.mkdir(dir_name)
        except FileExistsError:
            pass
        os.chdir(dir_name)
        build_path = os.getcwd()

        # write layer operations to files
        for i, layer in enumerate(self.layers):
            l_dir = f"layer_{i}"
            try:
                os.mkdir(l_dir)
            except FileExistsError:
                pass
            os.chdir(l_dir)
            with open(f"__init__.py", 'w') as f_init:
                for j_tmp, op in enumerate(layer):
                    f_init.write(f"from .op_{j_tmp} import *\n")
                f_init.close()
            for j, op in enumerate(layer):
                if type(op) is not tuple:
                    op_fname = f"op_{j}"
                    with open(f"{op_fname}.py", 'w') as f:
                        f.write("import numpy as np\n")
                        f.write("from numba import jit\n")
                        f.write(op.func)
                        f.close()
            os.chdir(build_path)

        # replace layer ops with functions written to files
        sys.path.insert(0, os.getcwd())
        for i, layer in enumerate(self.layers):
            for j, op in enumerate(layer):
                if type(op) is not tuple:
                    module = import_module(f".op_{j}", package=f"layer_{i}")
                    func = getattr(module, op.name)
                    self.layers[i][j] = (func, op.args)
        os.chdir(orig_path)

        # map new layers to old layer indices
        for l_key in layer_mapping.keys():
            layer_mapping[l_key] = self.layers[layer_mapping[l_key]]

        return layer_mapping

    def eval(self, ops):
        return [op.eval() for op in ops]

    def broadcast(self, op1: Any, op2: Any, **kwargs) -> tuple:
        """Tries to match the shapes of op1 and op2 such that op can be applied. Then applies op to op1 and op2.

        Parameters
        ----------
        op1
            First argument to the operation.
        op2
            Second argument to the operation.
        return_ops
            If true, the adjusted arguments (op1 and op2) are returned.
        kwargs
            Additional keyword arguments to be passed to the backend.

        Returns
        -------
        tp.Union[tuple, tp.Any]
            Output of op applied to op1 and op2. If return_ops, op1 and op2 are also returned.

        """

        # get key and value of ops if they are dicts
        if type(op1) is dict:
            (op1_key, op1_val), = op1.items()
        else:
            op1_val = op1
        if type(op2) is dict:
            (op2_key, op2_val), = op2.items()
        else:
            op2_val = op2

        # try to match shapes
        if not self._compare_shapes(op1_val, op2_val):

            # try removing singleton dimensions from op1/op2
            op1_val_tmp, op2_val_tmp = self._match_shapes(op1_val, op2_val, adjust_second=True, assign=False)
            if not self._compare_shapes(op1_val_tmp, op2_val_tmp):
                op1_val_tmp, op2_val_tmp = self._match_shapes(op1_val_tmp, op2_val_tmp, adjust_second=False,
                                                              assign=False)
            if self._compare_shapes(op1_val_tmp, op2_val_tmp):
                op1_val, op2_val = op1_val_tmp, op2_val_tmp

        return op1_val, op2_val

    def apply_idx(self, var: Any, idx: str, update, *args):
        if update:
            return self.add_op('=', var, update, idx, *args)
        else:
            return self.add_op('index', var, idx, *args)

    def stack_vars(self, *vars, **kwargs):
        shape = (len(vars),) + vars[0].shape
        stack = self.add_var(vtype='state_var', name='stack', value=0., shape=shape, dtype=vars[0].dtype, **kwargs)
        updates = []
        for idx, var in enumerate(vars):
            updates.append(self.add_op('=', stack, var, idx, indexed=True))
        return stack, updates

    def _run_no_inp(self, layers, sampling_layer, steps, sampling_steps):
        if sampling_layer is None:
            for step in range(steps):
                for l in layers:
                    self.eval_layer(l)
        else:
            for step in range(steps):
                if step % sampling_steps == 0:
                    self.layer_run(sampling_layer)
                for l in layers:
                    self.eval_layer(l)
            if step+1 % sampling_steps == 0:
                self.eval_layer(sampling_layer)

    def _run_inp(self, layers, sampling_layer, inputs, steps, sampling_steps):
        if sampling_layer is None:
            for step, inp in zip(range(steps), inputs):
                for key, val in inp.items():
                    self.vars[key][:] = val
                for l in layers:
                    self.eval_layer(l)
        else:
            for step, inp in zip(range(steps), inputs):
                if step % sampling_steps == 0:
                    self.layer_run(sampling_layer)
                for key, val in inp.items():
                    self.vars[key][:] = val
                for l in layers:
                    self.eval_layer(l)
            if step+1 % sampling_steps == 0:
                self.eval_layer(sampling_layer)

    def _match_shapes(self, op1: Any, op2: Any, adjust_second: bool = True, assign: bool = False) -> tuple:
        """Re-shapes op1 and op2 such that they can be combined via mathematical operations.

        Parameters
        ----------
        op1
            First operator.
        op2
            Second operator.
        assign
            If true, the re-shaped operators will be assigned to new variables. Else, the manipulation will be performed
            in place.
        adjust_second
            If true, the second operator will be re-shaped according to the shape of the first operator. If false,
            it will be done the other way around.

        Returns
        -------
        tuple
            The re-shaped operators.

        """

        if adjust_second:
            op_adjust = op2
            op_target = op1
        else:
            op_adjust = op1
            op_target = op2

        if len(op_adjust.shape) == 0 and len(op_target.shape) > 0 and assign:

            # create array of zeros and fill it with op_adjust
            op_adjust = self.add_op('+', self.add_op("zeros", op_target.shape, op_target.dtype), op_adjust)

        elif (len(op_target.shape) > len(op_adjust.shape)) and (1 in op_target.shape) and (len(op_adjust.shape) > 0):

            # reshape op_adjust to match the shape of op_target
            target_shape = op_target.shape
            idx = list(target_shape).index(1)
            if idx == 0:
                op_adjust = self.add_op('reshape', op_adjust, [1, op_adjust.shape[0]])
            else:
                op_adjust = self.add_op('reshape', op_adjust, [op_adjust.shape[0], 1])

        elif (len(op_adjust.shape) > len(op_target.shape) and 1 in op_adjust.shape) or \
                (len(op_target.shape) == 2 and len(op_adjust.shape) == 2 and op_target.shape[1] != op_adjust.shape[0]
                 and 1 in op_adjust.shape):

            # cut singleton dimension from op_adjust
            old_shape = list(op_adjust.shape)
            idx = old_shape.index(1)
            op_adjust = self.add_op('reshape', op_adjust, old_shape.pop(idx))

        if adjust_second:
            return op_target, op_adjust
        return op_adjust, op_target

    def _create_var(self, vtype, dtype, shape, value, name):
        return NumpyVar(vtype=vtype, dtype=dtype, shape=shape, value=value, name=name, backend=self)

    @staticmethod
    def layer_run(layer):
        threads = [threading.Thread(target=op, args=args) for op, args in layer]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    @staticmethod
    def _compare_shapes(op1: Any, op2: Any) -> bool:
        """Checks whether the shapes of op1 and op2 are compatible with each other.

        Parameters
        ----------
        op1
            First operator.
        op2
            Second operator.

        Returns
        -------
        bool
            If true, the shapes of op1 and op2 are compatible.

        """

        if hasattr(op1, 'shape') and hasattr(op2, 'shape'):
            if op1.shape == op2.shape:
                return True
            elif len(op1.shape) > 1 and len(op2.shape) > 1:
                return True
            elif len(op1.shape) == 0 or len(op2.shape) == 0:
                return True
            else:
                return False
        else:
            return True


class TensorflowBackend(NumpyBackend):
    """Wrapper to tensorflow.

    Parameters
    ----------
    ops
        Additional operations this backend instance can perform, defined as key-value pairs.
    dtypes
        Additional data-types this backend instance can use, defined as key-value pairs.
    use_device
        Default default_device on which to place variables and operations.

    """

    def __init__(self,
                 ops: Optional[Dict[str, Callable]] = None,
                 dtypes: Optional[Dict[str, object]] = None,
                 use_device: str = 'cpu'
                 ) -> None:
        """Instantiates tensorflow backend, i.e. a tensorflow graph.
        """

        if use_device == 'cpu':
            device = '/cpu:0'
        elif use_device == 'gpu':
            device = '/gpu:0'
        else:
            device = use_device
        self.default_device = device

        super().__init__(ops, dtypes)

        # define operations and datatypes of the backend
        ################################################

        # base math operations
        self.ops.update({"+": {'name': "tensorflow_add", 'call': "tf.add"},
                         "-": {'name': "tensorflow_subtract", 'call': "tf.subtract"},
                         "*": {'name': "tensorflow_multiply", 'call': "tf.multiply"},
                         "/": {'name': "tensorflow_divide", 'call': "tf.divide"},
                         "%": {'name': "tensorflow_modulo", 'call': "tf.mod"},
                         "^": {'name': "tensorflow_power", 'call': "tf.pow"},
                         "**": {'name': "tensorflow_power", 'call': "tf.pow"},
                         "@": {'name': "tensorflow_dot", 'call': "tf.dot"},
                         ".T": {'name': "tensorflow_transpose", 'call': "tf.transpose"},
                         ".I": {'name': "tensorflow_invert", 'call': "tf.invert"},
                         ">": {'name': "tensorflow_greater", 'call': "tf.greater"},
                         "<": {'name': "tensorflow_less", 'call': "tf.less"},
                         "==": {'name': "tensorflow_equal", 'call': "tf.equal"},
                         "!=": {'name': "tensorflow_not_equal", 'call': "tf.not_equal"},
                         ">=": {'name': "tensorflow_greater_equal", 'call': "tf.greater_equal"},
                         "<=": {'name': "tensorflow_less_equal", 'call': "tf.less_equal"},
                         "=": {'name': "assign", 'call': "assign"},
                         "+=": {'name': "assign_add", 'call': "assign_add"},
                         "-=": {'name': "assign_subtract", 'call': "assign_sub"},
                         "neg": {'name': "negative", 'call': "neg_one"},
                         "sin": {'name': "tensorflow_sin", 'call': "tf.sin"},
                         "cos": {'name': "tensorflow_cos", 'call': "tf.cos"},
                         "tan": {'name': "tensorflow_tan", 'call': "tf.tan"},
                         "atan": {'name': "tensorflow_atan", 'call': "tf.arctan"},
                         "abs": {'name': "tensorflow_abs", 'call': "tf.abs"},
                         "sqrt": {'name': "tensorflow_sqrt", 'call': "tf.sqrt"},
                         "sq": {'name': "tensorflow_square", 'call': "tf.square"},
                         "exp": {'name': "tensorflow_exp", 'call': "tf.exp"},
                         "max": {'name': "tensorflow_max", 'call': "tf.max"},
                         "min": {'name': "tensorflow_min", 'call': "tf.min"},
                         "argmax": {'name': "tensorflow_transpose", 'call': "tf.argmax"},
                         "argmin": {'name': "tensorflow_argmin", 'call': "tf.argmin"},
                         "round": {'name': "tensorflow_round", 'call': "tf.round"},
                         "sum": {'name': "tensorflow_sum", 'call': "tf.sum"},
                         "mean": {'name': "tensorflow_mean", 'call': "tf.mean"},
                         "concat": {'name': "tensorflow_concatenate", 'call': "tf.concatenate"},
                         "reshape": {'name': "tensorflow_reshape", 'call': "tf.reshape"},
                         "shape": {'name': "tensorflow_shape", 'call': "tf.shape"},
                         "dtype": {'name': "tensorflow_dtype", 'call': "tf.dtype"},
                         'squeeze': {'name': "tensorflow_squeeze", 'call': "tf.squeeze"},
                         "roll": {'name': "tensorflow_roll", 'call': "tf.roll"},
                         "cast": {'name': "tensorflow_cast", 'call': "tf.cast"},
                         "randn": {'name': "tensorflow_randn", 'call': "tf.randn"},
                         "ones": {'name': "tensorflow_ones", 'call': "tf.ones"},
                         "zeros": {'name': "tensorflow_zeros", 'call': "tf.zeros"},
                         "range": {'name': "tensorflow_arange", 'call': "tf.arange"},
                         "softmax": {'name': "tensorflow_softmax", 'call': "tf.softmax"},
                         "sigmoid": {'name': "tensorflow_sigmoid", 'call': "tf.sigmoid"},
                         "tanh": {'name': "tensorflow_tanh", 'call': "tf.tanh"},
                         "index": {'name': "pyrates_index", 'call': "pyrates_index"},
                         "mask": {'name': "tensorflow_mask", 'call': "tf.mask"},
                         "group": {'name': "tensorflow_group", 'call': "tf.group"},
                         "no_op": {'name': "tensorflow_identity", 'call': "tf.identity"},
                         })

        self.dtypes = {"float16": tf.float16,
                       "float32": tf.float32,
                       "float64": tf.float64,
                       "int16": tf.int16,
                       "int32": tf.int32,
                       "int64": tf.int64,
                       "uint16": tf.uint16,
                       "uint32": tf.uint32,
                       "uint64": tf.uint64,
                       "complex64": tf.complex64,
                       "complex128": tf.complex128,
                       "bool": tf.bool
                       }

    def add_op(self,
               op: str,
               *args,
               **kwargs
               ) -> Union[PyRatesOp, TensorflowVar]:
        if 'decorator' not in kwargs:
            kwargs['decorator'] = "@tf.function"
        return super().add_op(op, *args, **kwargs)

    def _create_var(self, vtype, dtype, shape, value, name):
        return TensorflowVar(vtype=vtype, dtype=dtype, shape=shape, value=value, name=name, backend=self)

    def broadcast(self, op1: Any, op2: Any, **kwargs) -> tuple:
        """Tries to match the shapes of op1 and op2 such that op can be applied. Then applies op to op1 and op2.

        Parameters
        ----------
        op1
            First argument to the operation.
        op2
            Second argument to the operation.
        return_ops
            If true, the adjusted arguments (op1 and op2) are returned.
        kwargs
            Additional keyword arguments to be passed to the backend.

        Returns
        -------
        tp.Union[tuple, tp.Any]
            Output of op applied to op1 and op2. If return_ops, op1 and op2 are also returned.

        """

        # match shapes
        op1, op2 = super().broadcast(op1, op2, **kwargs)

        # match data types
        if not self._compare_dtypes(op1, op2):
            op1, op2 = self._match_dtypes(op1, op2)

        return op1, op2

    def _match_dtypes(self, op1: Any, op2: Any) -> tuple:
        """

        Parameters
        ----------
        op1
        op2

        Returns
        -------

        """

        if type(op1) is TensorflowVar:
            return op1, self.add_op('cast', op2, op1.dtype)
        elif type(op2) is TensorflowVar:
            return self.add_op('cast', op1, op2.dtype), op2
        elif hasattr(op1, 'numpy') or type(op1) is np.ndarray:
            return op1, self.add_op('cast', op2, op1.dtype)
        elif hasattr(op2, 'numpy') or type(op2) is np.ndarray:
            return self.add_op('cast', op1, op2.dtype), op2
        else:
            return op1, self.add_op('cast', op2, str(type(op1)).split('\'')[-2])

    @staticmethod
    def _compare_dtypes(op1: Any, op2: Any) -> bool:
        """Checks whether the data types of op1 and op2 are compatible with each other.

        Parameters
        ----------
        op1
            First operator.
        op2
            Second operator.

        Returns
        -------
        bool
            If true, the data types of op1 and op2 are compatible.

        """

        if hasattr(op1, 'dtpye') and hasattr(op2, 'dtype'):
            if op1.dtype != op2.dtype and op1.dtype.name != op2.dtype.name:
                return False
        elif hasattr(op1, 'dtype'):
            if str(type(op2)) not in op1.dtype.name:
                return False
        elif hasattr(op2, 'dtype'):
            if str(type(op1)) not in op2.dtype.name:
                return False
        else:
            return type(op1) == type(op2)
        return True


##############################################
# code generator class for backend functions #
##############################################

class CodeGen:
    """Generates code
    """

    def __init__(self):
        self.code = []
        self.lvl = 0

    def generate(self):
        return "".join(self.code)

    def add_code_line(self, code_str):
        self.code.append("    " * self.lvl + code_str)

    def add_linebreak(self):
        self.code.append("\n")

    def add_indent(self):
        self.lvl += 1

    def remove_indent(self):
        if self.lvl == 0:
            raise(SyntaxError("internal error in code generator"))
        self.lvl -= 1
