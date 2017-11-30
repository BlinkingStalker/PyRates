"""Module that includes basic axon class plus parametrized derivations of it.

This module includes a basic axon class and parametric sub-classes that can calculate average firing rates from
average membrane potentials. Its behavior approximates the average axon hillok of a homogenous neural population.

"""

import matplotlib.pyplot as plt
import numpy as np
from typing import Optional, Callable, Union

__author__ = "Richard Gast, Daniel F. Rose"
__status__ = "Development"


class Axon(object):
    """Base axon class. Represents average behavior of generic axon hillok.

    Parameters
    ----------
    transfer_function
        Function used to transfer average membrane potentials into average firing rates. Takes membrane potentials
        [unit = V] as input and returns average firing rates [unit = 1/s].
    axon_type
        Name of axon type.
    **kwargs
        Keyword arguments for the transfer function

    Attributes
    ----------
    transfer_function
        See `transfer_function` in parameters section.
    axon_type
        See `axon_type` in parameters section.
    transfer_function_args
        Keyword arguments will be saved as dict on the object.

    Methods
    -------
    compute_firing_rate
        See method docstring.
    plot_transfer_function
        See method docstring.

    """

    def __init__(self, transfer_function: Callable[float, float], axon_type: Optional[str] = None,
                 **kwargs) -> None:
        """Instantiates base axon.
        """

        ##################
        # set attributes #
        ##################

        self.transfer_function = transfer_function
        self.axon_type = 'custom' if axon_type is None else axon_type
        self.transfer_function_args = kwargs

    def compute_firing_rate(self, membrane_potential: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """Computes average firing rate from membrane potential based on transfer function.

        Parameters
        ----------
        membrane_potential
            current average membrane potential of neural mass [unit = V].

        Returns
        -------
        float
            average firing rate at axon hillok [unit = 1/s]

        """

        return self.transfer_function(membrane_potential, **self.transfer_function_args)

    def plot_transfer_function(self, membrane_potentials: np.ndarray = None,
                               epsilon: float = 1e-4,
                               bin_size: float = 0.001,
                               create_plot: bool = True,
                               fig=None):
        """Creates figure of the transfer function transforming membrane potentials into output firing rates.

        Parameters
        ----------
        membrane_potentials
            Membrane potential values for which to plot transfer function value [unit = V].
        epsilon
            Determines min/max function value to plot, if membrane_potentials is None.
            Min = 0 + epsilon, max = max_firing_rate - epsilon [unit = 1/s] (default = 1e-4).
        bin_size
            Determines size of steps between membrane potentials at which function is evaluated. Not necessary if
            membrane_potentials is None [unit = V] (default = 0.001).
        create_plot
            If false, plot will bot be shown (default = True).
        fig
            If passed, plot will be created in respective figure (default = None).

        Returns
        -------
        figure handle
            Handle of the newly created or updated figure.

        """

        ##########################
        # check input parameters #
        ##########################

        if epsilon < 0:
            raise ValueError('Epsilon cannot be negative. See parameter description for further information.')

        if bin_size < 0:
            raise ValueError('Bin size cannot be negative. See parameter description for further information.')

        ##########################
        # calculate firing rates #
        ##########################

        firing_rates = self.compute_firing_rate(membrane_potentials)

        ##############################################
        # plot firing rates over membrane potentials #
        ##############################################

        # check whether new figure needs to be created
        if fig is None:
            fig = plt.figure('Wave-To-Pulse-Function')

        # plot firing rates over membrane potentials
        plt.hold('on')
        plt.plot(membrane_potentials, firing_rates)
        plt.hold('off')

        # set figure labels
        plt.xlabel('membrane potential [V]')
        plt.ylabel('firing rate [Hz]')
        plt.title('Axon Hillok Transfer Function')

        # show plot
        if create_plot:
            fig.show()

        return fig


class SigmoidAxon(Axon):
    """Sigmoid axon class. Represents average firing behavior at axon hillok via sigmoid as described by [1]_.

    Parameters
    ----------
    max_firing_rate
        Determines maximum firing rate of axon [unit = 1/s].
    membrane_potential_threshold
        Determines membrane potential for which output firing rate is half the maximum firing rate [unit = V].
    sigmoid_steepness
        Determines steepness of the sigmoidal transfer function mapping membrane potential to firing rate
        [unit = 1/V].
    axon_type
        See documentation of parameter `axon_type` in :class:`Axon`

    See Also
    --------
    :class:`Axon`: documentation for a detailed description of the object attributes and methods.

    References
    ----------
    .. [1] B.H. Jansen & V.G. Rit, "Electroencephalogram and visual evoked potential generation in a mathematical model
       of coupled cortical columns." Biological Cybernetics, vol. 73(4), pp. 357-366, 1995.

    """

    def __init__(self, max_firing_rate: float, membrane_potential_threshold: float, sigmoid_steepness: float,
                 axon_type: Optional[str] = None) -> None:
        """Initializes sigmoid axon instance.
        """

        ##########################
        # check input parameters #
        ##########################

        if max_firing_rate < 0:
            raise ValueError('Maximum firing rate cannot be negative.')

        if sigmoid_steepness < 0:
            raise ValueError('Sigmoid steepness cannot be negative.')

        ######################################
        # define sigmoidal transfer function #
        ######################################

        def parametric_sigmoid(membrane_potential: Union[float, np.ndarray], max_firing_rate: float,
                               membrane_potential_threshold: float,
                               sigmoid_steepness: float) -> Union[float, np.ndarray]:
            """Sigmoidal axon hillok transfer function. Transforms membrane potentials into firing rates.

            Parameters
            ----------
            membrane_potential
                Membrane potential for which to calculate firing rate [unit = V].
            max_firing_rate
                See parameter description of `max_firing_rate` of :class:`SigmoidAxon`.
            membrane_potential_threshold
                See parameter description of `membrane_potential_threshold` of :class:`SigmoidAxon`.
            sigmoid_steepness
                See parameter description of `sigmoid_steepness` of :class:`SigmoidAxon`.

            Returns
            -------
            float
                average firing rate [unit = 1/s]

            """

            return max_firing_rate / (1 + np.exp(sigmoid_steepness *
                                                 (membrane_potential_threshold - membrane_potential)))

        ###################
        # call super init #
        ###################

        super(SigmoidAxon, self).__init__(transfer_function=parametric_sigmoid,
                                          axon_type=axon_type,
                                          max_firing_rate=max_firing_rate,
                                          membrane_potential_threshold=membrane_potential_threshold,
                                          sigmoid_steepness=sigmoid_steepness)

    def plot_transfer_function(self, membrane_potentials: np.ndarray = None,
                               epsilon: float = 1e-4,
                               bin_size: float = 0.001,
                               create_plot: bool = True,
                               fig=None):
        """Plots axon hillok sigmoidal transfer function.

        See description of `plot_transfer_function` method of :class:`Axon` for a detailed input/output description.

        Notes
        -----
        Membrane potential is now an optional argument compared to base axon plotting function.

        """

        ##########################
        # calculate firing rates #
        ##########################

        if membrane_potentials is None:

            # start at membrane_potential_threshold and successively calculate the firing rate & reduce the membrane
            # potential until the firing rate is smaller or equal to epsilon
            membrane_potential = list()
            membrane_potential.append(self.transfer_function_args['membrane_potential_threshold'])
            firing_rate = self.compute_firing_rate(membrane_potential[-1])
            while firing_rate >= epsilon:
                membrane_potential.append(membrane_potential[-1] - bin_size)
                firing_rate = self.compute_firing_rate(membrane_potential[-1])
            membrane_potential_1 = np.array(membrane_potential)
            membrane_potential_1 = np.flipud(membrane_potential_1)

            # start at 70 mV and successively calculate the firing rate & increase the membrane
            # potential until the firing rate is greater or equal to max_firing_rate - epsilon
            membrane_potential = list()
            membrane_potential.append(self.transfer_function_args['membrane_potential_threshold'] + bin_size)
            firing_rate = self.compute_firing_rate(membrane_potential[-1])
            while firing_rate <= self.transfer_function_args['max_firing_rate'] - epsilon:
                membrane_potential.append(membrane_potential[-1] + bin_size)
                firing_rate = self.compute_firing_rate(membrane_potential[-1])
            membrane_potential_2 = np.array(membrane_potential)

            # concatenate the resulting membrane potentials
            membrane_potentials = np.concatenate((membrane_potential_1, membrane_potential_2))

        #####################
        # call super method #
        #####################

        super(SigmoidAxon, self).plot_transfer_function(membrane_potentials=membrane_potentials,
                                                        epsilon=epsilon,
                                                        bin_size=bin_size,
                                                        create_plot=create_plot,
                                                        fig=fig)
