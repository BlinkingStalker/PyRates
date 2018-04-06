"""Includes several derivations of base observer class for certain electrophysiological/neuroimaging modalities.
"""

_status__ = "development"
__author__ = "Richard Gast"


import numpy as np
from typing import Union, Optional, Callable, List
from pandas import DataFrame

FloatLike = Union[float, np.float64]

from pyrates.observer import ExternalObserver, CircuitObserver


#################
# fMRI observer #
#################


class fMRIObserver(ExternalObserver):
    """Uses the Balloon-Windkessel model to enable observation of BOLD/CBF/CBV from the circuit activity.
    """

    def __init__(self,
                 observer: CircuitObserver,
                 target_populations: Optional[list] = None,
                 target_population_weights: Optional[Union[List[list], list]] = None,
                 target_state: str = 'membrane_potential',
                 beta: float = 1/0.65,
                 gamma: float = 1/0.41,
                 tau: float = 0.98,
                 alpha: float = 0.33,
                 p: float = 0.34,
                 normalize: bool = True,
                 init_states: Optional[np.ndarray] = None
                 ) -> None:

        # call super init
        super().__init__(observer=observer,
                         target_populations=target_populations,
                         target_population_weights=target_population_weights,
                         target_state=target_state)

        # normalize population states
        if normalize:
            self.states.iloc[:] = self.states.iloc[:] - np.min(self.states.iloc[:])
            self.states.iloc[:] = self.states.iloc[:] / np.max(self.states.iloc[:])

        # set balloon-windkessel parameters
        self.beta = beta
        self.gamma = gamma
        self.tau = tau
        self.alpha = alpha
        self.p = p
        self.N = self.states.shape[1]

        # initial states
        if init_states is None:
            self.bwk_states = np.zeros((self.N, 4))
            self.bwk_states[:, 1:] = 1.
        self.delta_bwk_states = np.zeros_like(self.bwk_states)

    def observe(self,
                observation_variable: str = 'BOLD',
                store_observations: bool=False,
                filename: Optional[str] = None,
                path: Optional[str] = None,
                time_window: Optional[list] = None,
                ) -> np.ndarray:
        """Generates observation data from population states.
        """

        if time_window:
            start = int(time_window[0] / self.sampling_step_size)
            stop = int(time_window[1] / self.sampling_step_size)
        else:
            start = 0
            stop = int(self.time[-1] / self.sampling_step_size)

        output_length = stop - start
        output = DataFrame(data=np.zeros((output_length, self.N)), columns=list(self.states.keys()))

        if observation_variable == 'BOLD':

            for t in range(start, stop):
                self.bwk_states = self.take_step(f=self.get_delta_bwk_states, y_old=self.bwk_states,
                                                 neural_activity=self.states.iloc[t, :].values)

                output.iloc[t, :] = self.calculate_bold()

        elif observation_variable == 'CBF':

            for t in range(start, stop):
                self.bwk_states = self.take_step(f=self.get_delta_bwk_states, y_old=self.bwk_states,
                                                 neural_activity=self.states.iloc[t, :].values)

                output.iloc[t, :] = self.bwk_states[:, 1]

        elif observation_variable == 'CBV':

            for t in range(start, stop):
                self.bwk_states = self.take_step(f=self.get_delta_bwk_states, y_old=self.bwk_states,
                                                 neural_activity=self.states.iloc[t, :].values)

                output.iloc[t, :] = self.bwk_states[:, 2]

        return output

    def take_step(self,
                  f: Callable,
                  y_old: Union[FloatLike, np.ndarray],
                  **kwargs
                  ) -> FloatLike:
        """Takes a step of an ODE with right-hand-side f using Euler formalism.

        Parameters
        ----------
        f
            Function that represents right-hand-side of ODE and takes `t` plus `y_old` as an argument.
        y_old
            Old value of y that needs to be updated according to dy(t)/dt = f(t, y)
        **kwargs
            Name-value pairs to be passed to f.

        Returns
        -------
        float
            Updated value of left-hand-side (y).

        """

        return y_old + self.sampling_step_size * f(y_old, **kwargs)

    def get_delta_bwk_states(self, bwk_states_old, neural_activity):

        # calculate change in signal
        self.delta_bwk_states[:, 0] = neural_activity - self.beta * bwk_states_old[:, 0] - \
                                      self.gamma * (bwk_states_old[:, 1] - 1)

        # calculate change in blood flow
        self.delta_bwk_states[:, 1] = bwk_states_old[:, 0]

        # calculate change in blood volume
        self.delta_bwk_states[:, 2] = (bwk_states_old[:, 1] - bwk_states_old[:, 2]**(1/self.alpha)) / self.tau

        # calculate change in de-oxyhaemoglobin concentration in blood
        self.delta_bwk_states[:, 3] = ((bwk_states_old[:, 1] / self.p) * (1 - (1-self.p)**(1/bwk_states_old[:, 1]))
                                       - (bwk_states_old[:, 3] / bwk_states_old[:, 2])
                                       * bwk_states_old[:, 2]**(1/self.alpha)) / self.tau

        return self.delta_bwk_states

    def calculate_bold(self,
                       v0: float = 0.02,
                       k1: Optional[float] = None,
                       k2: float = 2.,
                       k3: Optional[float] = None):

        if not k1:
            k1 = 7*self.p
        if not k3:
            k3 = 2*self.p - 0.2

        hemodynamic_signal = k1 * (1-self.bwk_states[:, 3]) + k2 * (1 - self.bwk_states[:, 3] / self.bwk_states[:, 2]) \
                             + k3 * (1 - self.bwk_states[:, 2])

        return (100. * v0 * hemodynamic_signal) / self.p


class EEGMEGObserver(ExternalObserver):
    """Generates the source- or sensor-space EEG/MEG signal from the circuit states.
    """

    def __init__(self,
                 observer: CircuitObserver,
                 target_populations: Optional[list] = None,
                 target_population_weights: Optional[Union[List[list], list]] = None,
                 target_state: str = 'membrane_potential',
                 signal_space: str = 'source',
                 lead_field_matrix: Optional[np.ndarray] = None,
                 source_positions: Optional[np.ndarray] = None,
                 dipole_positions: Optional[np.ndarray] = None,
                 distance_metric: str = 'euclidean',
                 sensor_labels: Optional[list] = None
                 ) -> None:

        # call super init
        #################

        super().__init__(observer=observer,
                         target_populations=target_populations,
                         target_population_weights=target_population_weights,
                         target_state=target_state)

        # project states into source space if wished for
        ################################################

        if signal_space == 'sensor':

            # get leadfield matrix into correct shape
            if lead_field_matrix.shape[0] != self.states.shape[1]:
                lead_field_matrix = lead_field_matrix.T

            # if source + dipole positions are given, reduce leadfield matrix to the given sources
            if source_positions is not None:

                from scipy.spatial.distance import cdist
                distances = cdist(source_positions, dipole_positions, metric=distance_metric)
                dipole_idx = np.argmin(distances, axis=1)
                lead_field_matrix = lead_field_matrix[dipole_idx, :]

            # apply leadfield matrix
            states_tmp = self.states.values @ lead_field_matrix

            # create new dataframe with sensor space data
            if not sensor_labels:
                sensor_labels = ['S' + str(i) for i in range(states_tmp.shape[1])]
            self.states = DataFrame(data=states_tmp, columns=sensor_labels)
