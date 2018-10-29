"""Visualization functionality for pyrates networks and network simulations.
"""

# external imports
import seaborn as sb
import networkx.drawing.nx_pydot as pydot
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# pyrates internal imports

# meta infos
__author__ = "Richard Gast"
__status__ = "development"


def plot_timeseries(data, variable='value', bg_style="darkgrid", **kwargs):
    """Plot timeseries

    Parameters
    ----------
    data
        Pandas dataframe containing the results of a pyrates simulation.
    variable
        Name of the variable to be plotted
    bg_style
        Background style of the seaborn plot
    kwargs
        Additional key-word arguments for the seaborn.lineplot() function.

    Returns
    -------
    handle
        Figure handle of the plot.

    """

    sb.set_style(bg_style)

    # Convert the dataframe to long-form or "tidy" format
    df = pd.melt(data,
                 id_vars=['time'],
                 var_name='node',
                 value_name=variable)

    if 'ax' not in kwargs.keys():
        _, ax = plt.subplots()
        kwargs['ax'] = ax

    return sb.lineplot(data=df, x='time', y=variable, hue='node', **kwargs)


def plot_fc(data, metric='cov', threshold=None, plot_style='heatmap', bg_style='whitegrid', **kwargs):
    """Plot functional connectivity between nodes in network.

    Parameters
    ----------
    data
        Pandas dataframe containing the timeseries (rows) for each node of interest (columns).
    metric
        Type of connectivtiy measurement that should be used. Can be `cov` for covariance, `corr` for correlation or
        one of the following synchronization metrics that will be calculated via
        mne.connectivtiy.spectral_connectivity (check out this function for information on its arguments - these can be
        passed via kwargs):
            - `coh` for coherence
            - `cohy` for coherency
            - `imcoh` for imaginary coherence
            - `plv` for phase locking value
            - `ppc` for pairwise phase consistency
            - `pli` for phase lag index
            - `pli2_unbiased` for unbiased estimate of squared phase lag index
            - `wpli`for weighted phase lag index
            - `wpli2_debiased` for debiased weighted pahse lag index
    threshold
        Connectivtiy threshold to be applied (only connectivities larger than the threshold will be shown).
    plot_style
        Can either be `heatmap` for plotting with seaborn.heatmap or `circular_graph` for plotting with
         mne.viz.plot_connectivity_circle. Check out the respective function docstrings for information on
         their arguments (can be passed to kwargs).
    bg_style
        Only relevant if plot_style == heatmap. Then this will define the style of the background of the plot.
    kwargs
        Additional arguments for the fc calculation or fc plotting that can be passed.

    Returns
    -------
    ax
        Handle of the axis the plot was created in.
    fc
        Matrix containing the pairwise functional connectivities.

    """

    if 'time' in data.columns.values:
        idx = data.pop('time')
        data.index = idx

    # calculate functional connectivity
    ###################################

    if metric == 'cov':

        # covariance
        fc = np.cov(data.values.T)

    elif metric == 'corr':

        # pearsson correlation coefficient
        fc = np.corrcoef(data.values.T)

    elif metric in 'cohcohyimcohplvppcplipli2_unbiasedwpliwpli2_debiased':

        # phase-based connectivtiy/synchronization measurement
        from mne.connectivity import spectral_connectivity
        mne_args = ['indices', 'mode', 'fmin', 'fmax', 'fskip', 'faverage', 'tmin', 'tmax', 'mt_bandwidth',
                    'mt_adaptive', 'mt_low_bias', 'cwt_freqs', 'cwt_n_cycles', 'block_size', 'n_jobs']
        kwargs_tmp = {}
        for key, arg in kwargs.copy().items():
            if key in mne_args:
                kwargs_tmp[key] = kwargs.pop(key)
        fc, _, _, _, _ = spectral_connectivity(np.reshape(data.values.T, (1, data.shape[1], data.shape[0])),
                                               method=metric,
                                               sfreq=1./(data.index[1] - data.index[0]),
                                               verbose=False,
                                               **kwargs_tmp)
        fc = fc[:, :, 0]

    else:

        raise ValueError(f'FC metric is not supported by this function: {metric}. Check the documentation of the '
                         f'argument `metric` for valid options.')

    if threshold:
        fc[fc < threshold] = 0.

    # plot the functional connectivities
    ####################################

    # choose plot style
    if plot_style == 'heatmap':

        # seaborn plot
        if not 'xticklabels' in kwargs.keys():
            kwargs['xticklabels'] = data.columns.values
        if not 'yticklabels' in kwargs.keys():
            kwargs['yticklabels'] = data.columns.values
        if 'ax' not in kwargs.keys():
            _, ax = plt.subplots()
            kwargs['ax'] = ax
        sb.set_style(bg_style)
        ax = sb.heatmap(fc, **kwargs)

    elif plot_style == 'circular_graph':

        # mne python plot
        from mne.viz import circular_layout, plot_connectivity_circle

        # create circular node layout
        node_names = data.columns.values
        if 'node_order' in kwargs.keys():
            node_order = kwargs['node_oders']
        else:
            node_order = list(node_names)
        kwargs_tmp = {}
        layout_args = ['start_pos', 'start_between', 'group_boundaries', 'group_sep']
        for key in kwargs.keys():
            if key in layout_args:
                kwargs_tmp[key] = kwargs.pop(key)
        node_angles = circular_layout(node_names, node_order, **kwargs_tmp)

        # plot the circular graph
        ax = plot_connectivity_circle(fc, node_names, node_angles=node_angles, **kwargs)

    else:

        raise ValueError(f'Plot style is not supported by this function: {plot_style}. Check the documentation of the '
                         f'argument `plot_style` for valid options.')

    return ax, fc


def plot_phase(data, fmin, fmax, bg_style='whitegrid', picks=None, **kwargs):
    """Plot phase of populations in a polar plot.
    """

    if 'time' in data.columns.values:
        idx = data.pop('time')
        data.index = idx

    if picks:
        if type(picks[0]) is str:
            data = data.loc[:, picks]
        else:
            data = data.iloc[:, picks]

    # create mne raw data object
    from pyrates.utility import mne_from_dataframe
    raw = mne_from_dataframe(data)

    # bandpass filter the raw data
    filter_args = ['filter_length', 'l_trans_bandwidth', 'h_trans_bandwidth', 'n_jobs', 'method', 'iir_params',
                   'copy', 'phase', 'fir_window', 'fir_design', 'pad', 'verbose']
    kwargs_tmp = {}
    for key in kwargs.keys():
        if key in filter_args:
            kwargs_tmp[key] = kwargs.pop(key)
    raw.filter(l_freq=fmin, h_freq=fmax, **kwargs_tmp)

    # apply hilbert transform and calculate phase of band-passed data
    raw.apply_hilbert()

    raw_phase = raw.copy()
    raw_phase.apply_function(get_angle)
    raw_phase.apply_function(np.real, dtype=np.float32)
    raw_phase.apply_function(np.unwrap)

    raw_amplitude = raw.copy()
    raw_amplitude.apply_function(np.abs)
    raw_amplitude.apply_function(np.real, dtype=np.float32)

    # plot the phase data with seaborn
    time = data.index
    data_phase = raw_phase.to_data_frame(scalings={'eeg': 1.})
    data_phase['time'] = time
    data_amp = raw_amplitude.to_data_frame(scalings={'eeg': 1.})
    data_amp['time'] = time
    data = pd.melt(data_phase, id_vars=['time'], var_name='node', value_name='phase')
    data_tmp = pd.melt(data_amp, id_vars=['time'], var_name='node', value_name='amplitude')
    data['amplitude'] = data_tmp['amplitude']
    sb.set(style=bg_style)
    ax = sb.FacetGrid(data, hue='node', subplot_kws=dict(polar=True), sharex=False, sharey=False,
                      despine=False, legend_out=True)
    ax.map(sb.scatterplot, 'phase', 'amplitude')
    ax.facet_axis(0, 0).set_ylim(0., 0.01)

    return ax


def write_graph(net, out_file='png'):
    """Draw graph from network config.
    """

    pydot_graph = pydot.to_pydot(net)

    file_format = out_file.split('.')[1]
    if file_format == 'png':
        pydot_graph.write_png(out_file)

def get_angle(x):
    return np.angle(x) + np.pi
