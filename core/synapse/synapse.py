"""Module that includes basic synapse class plus derivations of it.

This module includes a basic parametrized synapse class that can transform incoming average firing rates into average
synaptic currents.

"""

import matplotlib.pyplot as plt
import numpy as np
from typing import Optional, Union, Callable

__author__ = "Richard Gast, Daniel Rose"
__status__ = "Development"

# TODO: find out reversal potentials for conductance based synapses


class Synapse(object):
    """Basic synapse class. Represents average behavior of a defined post-synapse of a population.

    Parameters
    ----------
    kernel_function
        Function that specifies kernel value given the time-point after arrival of synaptic input. Output will be either
        a synaptic current or conductance change [unit = S or A respectively].
    efficacy
        Determines strength and direction of the synaptic response to input [unit = S if synapse is modulatory else A].
    bin_size
        Size of the time-steps between successive bins of the synaptic kernel [unit = s].
    epsilon
        Minimum kernel value. Kernel values below epsilon will be set to zero [unit = S or A] (default = 1e-14).
    max_delay
        Maximum time after which incoming synaptic input still affects the synapse [unit = s] (default = None). If set,
        epsilon will be ignored.
    conductivity_based
        If true, synaptic input will be translated into synaptic current indirectly via a change in synaptic
        conductivity. Else translation to synaptic current will be direct (default = False).
    reversal_potential
        Synaptic reversal potential. Only needed for conductivity based synapses (default = -0.075) [unit = V].
    modulatory
        If true, synapse will have multiplicative instead of additive effect on change in membrane potential of
        population (default = False).
    synapse_type
        Name of synapse type (default = None).
    **kwargs
        Keyword arguments for the kernel function

    Attributes
    ----------
    synaptic_kernel : np.ndarray
        Vector including the synaptic kernel value at each time-bin [unit = S if conductivity based else A].
    kernel_function
        See parameter description.
    kernel_function_args
        Keyword arguments will be saved as dict on the object.
    efficacy
        Determines strength and direction of the synaptic response to input [unit = S if synapse is modulatory else A].
    conductivity_based
        See parameter description.
    reversal_potential
        See parameter description.
    bin_size
        See parameter description.
    max_delay
        See parameter description.
    modulatory
        See parameter description.
    synapse_type
        See parameter description.

    """

    def __init__(self, kernel_function: Callable[[float], float],
                 efficacy: float,
                 bin_size: float,
                 epsilon: float = 1e-14,
                 max_delay: Optional[float] = None,
                 conductivity_based: bool = False,
                 reversal_potential: float = -0.075,
                 modulatory: bool = False,
                 synapse_type: Optional[str] = None,
                 **kernel_function_args: float
                 ) -> None:
        """Instantiates base synapse.
        """

        ##########################
        # check input parameters #
        ##########################

        if bin_size < 0 or (max_delay and max_delay < 0):
            raise ValueError('Time constants (bin_size, max_delay) cannot be negative. '
                             'See docstring for further information.')

        if epsilon < 0:
            raise ValueError('Epsilon is an absolute error term that cannot be negative.')

        ##################
        # set attributes #
        ##################

        self.efficacy = efficacy
        self.conductivity_based = conductivity_based
        self.reversal_potential = reversal_potential
        self.bin_size = bin_size
        self.epsilon = epsilon
        self.max_delay = max_delay
        self.modulatory = modulatory
        self.kernel_function = kernel_function
        self.kernel_function_args = kernel_function_args

        ####################
        # set synapse type #
        ####################

        if synapse_type is None:

            # define synapse type via synaptic kernel efficacy and type (current- vs conductivity-based)
            if conductivity_based:
                self.reversal_potential = reversal_potential
                self.synapse_type = 'excitatory_conductance' if efficacy >= 0 else 'inhibitory_conductance'
            else:
                self.synapse_type = 'excitatory_current' if efficacy >= 0 else 'inhibitory_current'

        else:

            self.synapse_type = synapse_type

        # set decorator for synaptic current getter (only relevant for conductivity based synapses)
        if conductivity_based:
            self.kernel_scaling = lambda membrane_potential: self.reversal_potential - membrane_potential
        else:
            self.kernel_scaling = lambda membrane_potential: 1.

        #########################
        # build synaptic kernel #
        #########################

        self.synaptic_kernel = self.evaluate_kernel(build_kernel=True)

    def evaluate_kernel(self,
                        build_kernel: bool,
                        time_points: Union[float, np.ndarray] = 0.
                        ) -> Union[float, np.ndarray]:
        """Builds synaptic kernel or computes value of it at specified time point(s).

        Parameters
        ----------
        build_kernel
            If true, kernel will be evaluated at all relevant time-points for current parametrization. If false, kernel
            will be evaluated at each provided t.
        time_points
            Time(s) at which to evaluate kernel. Only necessary if build_kernel is False (default = None) [unit = s].

        Returns
        -------
        np.ndarray
            Synaptic kernel value at each t [unit = A or S]

        """

        #########################
        # check input parameter #
        #########################

        if np.sum(time_points < 0) > 0:
            raise ValueError('Time-point(s) t cannot be negative. See docstring for further information.')

        ####################################################################
        # check whether to build kernel or just evaluate it at time_points #
        ####################################################################

        if build_kernel and self.max_delay:

            # create time vector from max_delay
            time_points = np.arange(self.max_delay, 0.+0.5*self.bin_size, -self.bin_size)

        elif build_kernel:

            # create time vector from epsilon
            time_points = list()
            time_points.append(0.)
            kernel_val = self.kernel_function(time_points[-1], **self.kernel_function_args) * self.efficacy
            while True:
                time_points.append(time_points[-1] + self.bin_size)
                kernel_val_tmp = self.kernel_function(time_points[-1], **self.kernel_function_args) * self.efficacy
                if kernel_val_tmp - kernel_val < 0. and abs(kernel_val_tmp) < self.epsilon:
                    break
                kernel_val = kernel_val_tmp
            time_points = np.flip(np.asarray(time_points), axis=0)

        return self.kernel_function(time_points, **self.kernel_function_args) * self.efficacy

    def get_synaptic_current(self,
                             synaptic_input: np.ndarray,
                             membrane_potential: Union[float, np.float64] = -0.075
                             ) -> Union[np.float64, float]:
        """Applies synaptic kernel to synaptic input (should be incoming firing rate).

        Parameters
        ----------
        synaptic_input
            Vector of incoming firing rates over time. [unit = 1/s].
        membrane_potential
            Membrane potential of post-synapse. Only to be used for conductivity based synapses (default = None)
            [unit = V].

        Returns
        -------
        float
            Resulting synaptic current [unit = A].

        """

        #########################
        # apply synaptic kernel #
        #########################

        # multiply firing rate input with kernel
        kernel_value = synaptic_input * self.synaptic_kernel[-len(synaptic_input):]

        # integrate over time
        kernel_value = np.trapz(kernel_value, dx=self.bin_size)

        return kernel_value * self.kernel_scaling(membrane_potential)

    def plot_synaptic_kernel(self,
                             create_plot: bool = True,
                             axes: Optional[object] = None
                             ) -> object:
        """Creates plot of synaptic kernel over time.

        Parameters
        ----------
        create_plot
            If false, no plot will be shown (default = True).
        axes
            figure handle, can be passed optionally (default = None).

        Returns
        -------
        :obj:`figure handle`
            Handle of the newly created or updated figure.

        """

        ##################################
        # plot synaptic kernel over time #
        ##################################

        # check whether new figure has to be created
        if axes is None:
            fig, axes = plt.subplots(num='Impulse Response Function')

        # plot synaptic kernel
        # plt.hold('on')  # deprecated
        axes.plot(self.synaptic_kernel[-1:0:-1])
        # plt.hold('off')  # deprecated

        # set figure labels
        axes.set_xlabel('time-steps')
        if self.modulatory:
            axes.set_ylabel('modulation strength')
        elif self.conductivity_based:
            axes.set_ylabel('synaptic conductivity [S]')
        else:
            axes.set_ylabel('synaptic current [A]')
        axes.set_title('Synaptic Kernel')

        # show plot
        if create_plot:
            fig.show()

        return axes


class DoubleExponentialSynapse(Synapse):
    """Basic synapse class. Represents average behavior of a defined post-synapse of a population.

    Parameters
    ----------
    efficacy
        See documentation of parameter `efficacy` in :class:`Synapse`.
    tau_decay
        Lumped time delay constant that determines how fast the exponential synaptic kernel decays [unit = s].
    tau_rise
        Lumped time delay constant that determines how fast the exponential synaptic kernel rises [unit = s].
    bin_size
        See documentation of parameter `bin_size` in :class:`Synapse`.
    max_delay
        See documentation of parameter `max_delay` in :class:`Synapse`.
    conductivity_based
        See documentation of parameter `conductivity_based` in :class:`Synapse`.
    reversal_potential
        See documentation of parameter `reversal_potential` in :class:`Synapse`.
    modulatory
        See documentation of parameter `modulatory` in :class:`Synapse`.
    synapse_type
        Name of synapse type (default = None).

    See Also
    --------
    :class:`Synapse`: documentation for a detailed description of the object attributes and methods.
                              
    """

    def __init__(self,
                 efficacy: float,
                 tau_decay: float,
                 tau_rise: float,
                 bin_size: float,
                 epsilon: float = 1e-14,
                 max_delay: float = None,
                 conductivity_based: bool = False,
                 reversal_potential: float = -0.075,
                 modulatory: bool = False,
                 synapse_type: Optional[str] = None
                 ) -> None:

        ##########################
        # check input parameters #
        ##########################

        if tau_decay < 0 or tau_rise < 0:
            raise ValueError('Time constants tau cannot be negative. See docstring for further information.')

        ##########################
        # define kernel function #
        ##########################

        def double_exponential(time_points: Union[float, np.ndarray],
                               tau_decay: float,
                               tau_rise: float
                               ) -> Union[float, np.ndarray]:
            """Uses double exponential function to calculate synaptic kernel value for each passed time-point.

            Parameters
            ----------
            time_points : Union[float, np.ndarray]
                Vector of time-points for which to calculate kernel value [unit = s].
            tau_decay
                See parameter documentation of `tau_decay` of :class:`DoubleExponentialSynapse`.
            tau_rise
                See parameter documentation of `tau_rise` of :class:`DoubleExponentialSynapse`.

            Returns
            -------
            Union[float, np.ndarray]
                Kernel values at the time-points [unit = S if conductivity based else A].

            """

            return np.exp(-time_points / tau_decay) - np.exp(-time_points / tau_rise)

        ###################
        # call super init #
        ###################

        super().__init__(kernel_function=double_exponential,
                         efficacy=efficacy,
                         bin_size=bin_size,
                         epsilon=epsilon,
                         max_delay=max_delay,
                         conductivity_based=conductivity_based,
                         reversal_potential=reversal_potential,
                         modulatory=modulatory,
                         synapse_type=synapse_type,
                         tau_rise=tau_rise,
                         tau_decay=tau_decay)
