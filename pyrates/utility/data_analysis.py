# external imports
import pandas as pd
import numpy as np

# meta infos
__author__ = "Richard Gast"
__status__ = "development"


def functional_connectivity(data, metric='cov', **kwargs):
    """Calculate functional connectivity of node timeseries in data.

    Parameters
    ----------
    data
        Pandas dataframe containing the simulation results.
    metric
        Type of connectivtiy measurement that should be used.
            - `cov` for covariance (uses `np.cov`)
            - `corr` for pearsson correlation (uses `np.corrcoef`)
            - `csd` for cross-spectral density (uses `mne.time_frequency.csd_array_morlet`)
            - `coh` for coherenc (uses `mne.connectivtiy.spectral_connectivity`)
            - `cohy` for coherency (uses `mne.connectivtiy.spectral_connectivity`)
            - `imcoh` for imaginary coherence (uses `mne.connectivtiy.spectral_connectivity`)
            - `plv` for phase locking value (uses `mne.connectivtiy.spectral_connectivity`)
            - `ppc` for pairwise phase consistency (uses `mne.connectivtiy.spectral_connectivity`)
            - `pli` for phase lag index (uses `mne.connectivtiy.spectral_connectivity`)
            - `pli2_unbiased` for unbiased estimate of squared phase lag index
               (uses `mne.connectivtiy.spectral_connectivity`)
            - `wpli`for weighted phase lag index (uses `mne.connectivtiy.spectral_connectivity`)
            - `wpli2_debiased` for debiased weighted phase lag index (uses `mne.connectivtiy.spectral_connectivity`)
    kwargs
        Additional keyword arguments passed to respective function used for fc calculation.

    Returns
    -------
    np.ndarray
        Pairwise functional connectivity

    """

    if 'time' in data.columns.values:
        idx = data.pop('time')
        data.index = idx

    # calculate functional connectivity
    ###################################

    if metric == 'cov':

        # covariance
        fc = np.cov(data.values.T, **kwargs)

    elif metric == 'corr':

        # pearsson correlation coefficient
        fc = np.corrcoef(data.values.T, **kwargs)

    elif metric == 'csd':

        from mne.time_frequency import csd_array_morlet
        fc = np.abs(csd_array_morlet(X=np.reshape(data.values, (1, data.shape[1], data.shape[0])),
                                     sfreq=1./(data.index[1] - data.index[0]),
                                     ch_names=data.columns.values,
                                     **kwargs).mean().get_data())

    elif metric in 'cohcohyimcohplvppcplipli2_unbiasedwpliwpli2_debiased':

        # phase-based connectivtiy/synchronization measurement
        from mne.connectivity import spectral_connectivity
        fc, _, _, _, _ = spectral_connectivity(np.reshape(data.values.T, (1, data.shape[1], data.shape[0])),
                                               method=metric,
                                               sfreq=1./(data.index[1] - data.index[0]),
                                               **kwargs)
        fc = fc[:, :, 0]

    else:

        raise ValueError(f'FC metric is not supported by this function: {metric}. Check the documentation of the '
                         f'argument `metric` for valid options.')

    return fc


def analytic_signal(data, fmin, fmax, nodes=None, **kwargs):
    """Calculates analytic signal from simulation results, using the hilbert transform.

    Parameters
    ----------
    data
        Simulation results.
    fmin
        Lower bound frequency for bandpass filter that will be applied to the data.
    fmax
        Upper bound frequency for bandpass filter that will be applied to the data.
    nodes
        List of node names for which to calculate the analytic signal.
    kwargs
        Additional keyword arguments that will be passed to the `mne.Raw.filter` method.

    Returns
    -------
    pd.DataFrame
        Dataframe containing the fields `time`, `node`, `amplitude` and `phase`.

    """

    if 'time' in data.columns.values:
        idx = data.pop('time')
        data.index = idx

    if nodes:
        if type(nodes[0]) is str:
            data = data.loc[:, nodes]
        else:
            data = data.iloc[:, nodes]

    # create mne raw data object
    from pyrates.utility import mne_from_dataframe
    raw = mne_from_dataframe(data)

    # bandpass filter the raw data
    raw.filter(l_freq=fmin, h_freq=fmax, **kwargs)

    # apply hilbert transform
    raw.apply_hilbert()

    # get phase of analytic signal
    def get_angle(x):
        return np.angle(x) + np.pi
    raw_phase = raw.copy()
    raw_phase.apply_function(get_angle)
    raw_phase.apply_function(np.real, dtype=np.float32)
    raw_phase.apply_function(np.unwrap)

    # get amplitude of analytic signal
    raw_amplitude = raw.copy()
    raw_amplitude.apply_function(np.abs)
    raw_amplitude.apply_function(np.real, dtype=np.float32)

    # combine phase and amplitude into dataframe
    time = data.index
    data_phase = raw_phase.to_data_frame(scalings={'eeg': 1.})
    data_phase['time'] = time
    data_amp = raw_amplitude.to_data_frame(scalings={'eeg': 1.})
    data_amp['time'] = time
    data = pd.melt(data_phase, id_vars=['time'], var_name='node', value_name='phase')
    data_tmp = pd.melt(data_amp, id_vars=['time'], var_name='node', value_name='amplitude')
    data['amplitude'] = data_tmp['amplitude']

    return data


def time_frequency(data, freqs, method='morlet', output='avg_power', **kwargs):
    """Calculates time-frequency representation for each node.

    Parameters
    ----------
    data
        Simulation results.
    freqs
        Frequencies of interest.
    method
        Method to be used for TFR calculation. Can be `morlet` for `mne.time_frequency.tfr_array_morlet` or
        `multitaper` for `mne.time_frequency.tfr_array_multitaper`.
    output
        Type of the output variable to be calculated. For options, see `mne.time_frequency.tfr_array_morlet`.
    kwargs
        Additional keyword arguments to be passed to the function used for tfr calculation.

    Returns
    -------
    np.ndarray
        Time-frequency representation (n x f x t) for each node (n) at each frequency of interest (f) and time (t).

    """

    if 'time' in data.columns.values:
        idx = data.pop('time')
        data.index = idx

    if method == 'morlet':

        from mne.time_frequency import tfr_array_morlet
        return tfr_array_morlet(np.reshape(data.values.T, (1, data.shape[1], data.shape[0])),
                                sfreq=1./(data.index[1] - data.index[0]),
                                freqs=freqs, output=output, **kwargs)

    elif method == 'multitaper':

        from mne.time_frequency import tfr_array_multitaper
        return tfr_array_multitaper(np.reshape(data.values.T, (1, data.shape[1], data.shape[0])),
                                    sfreq=1. / (data.index[1] - data.index[0]),
                                    freqs=freqs, output=output, **kwargs)