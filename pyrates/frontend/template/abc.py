
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
""" Abstract base classes
"""
from importlib import import_module

# from pyrates.ir.abc import AbstractBaseIR
from pyrates.frontend.yaml import to_dict

__author__ = "Daniel Rose"
__status__ = "Development"


class AbstractBaseTemplate:
    """Abstract base class for templates"""

    target_ir = None  # placeholder for template-specific intermediate representation (IR) target class

    def __init__(self, name: str, path: str, description: str = "A template."):
        self.name = name
        self.path = path
        self.__doc__ = description  # overwrite class-specific doc with user-defined description

    def __repr__(self):
        return f"<{self.__class__.__name__} '{self.path}'>"

    def _format_path(self, path):
        """Check if path contains a folder structure and prepend own path, if it doesn't"""
        # ToDo: rename to something more meaningful like _prepend_parent_path or _check_path_prepend_parent

        if "." not in path:
            if "/" in self.path or "\\" in self.path:
                import os
                basedir, _ = os.path.split(self.path)
                path = os.path.normpath(os.path.join(basedir, path))
            else:
                path = ".".join((*self.path.split('.')[:-1], path))
        return path

    @classmethod
    def from_yaml(cls, path):
        """Convenience method that looks for a loader class for the template type and applies it, assuming
        the class naming convention '<template class>Loader'.

        Parameters:
        -----------
        path
            Path to template in YAML file of form 'directories.file.template'
        """
        # ToDo: add AbstractBaseTemplate._format_path functionality here
        module = import_module(cls.__module__)
        loader = getattr(module, f"{cls.__name__}Loader")
        return loader(path)

    def apply(self, *args, **kwargs):

        raise NotImplementedError


class TemplateLoader:
    """Class that loads templates from YAML and returns an OperatorTemplate class instance"""

    cache = {}  # dictionary that keeps track of already loaded templates

    def __new__(cls, path: str, template_cls: type):
        """Load template recursively and return OperatorTemplate class.

        Parameters
        ----------

        path
            string containing path of YAML template of the form path.to.template
        template_cls
            class that the loaded template will be instantiated with
        """

        if path in cls.cache:
            template = cls.cache[path]
        else:
            template_dict = to_dict(path)
            try:
                base_path = template_dict.pop("base")
            except KeyError:
                raise KeyError(f"No 'base' defined for template {path}. Please define a "
                               f"base to derive the template from.")
            if base_path == template_cls.__name__:
                # if base refers to the python representation, instantiate here
                template = template_cls(**template_dict)
            else:
                # load base if needed
                if "." in base_path:
                    # reference to template in different file
                    # noinspection PyCallingNonCallable
                    template = cls(base_path)
                else:
                    # reference to template in same file
                    base_path = ".".join((*path.split(".")[:-1], base_path))
                    # noinspection PyCallingNonCallable
                    template = cls(base_path)
                template = cls.update_template(template, **template_dict)
                # may fail if "base" is present but empty

            cls.cache[path] = template

        return template

    @classmethod
    def update_template(cls, *args, **kwargs):
        """Updates the template with a given list of arguments."""
        raise NotImplementedError


