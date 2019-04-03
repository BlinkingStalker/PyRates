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

# external imports
import scipy.signal as sp
import matplotlib.pyplot as plt
from seaborn import cubehelix_palette

# PyRates internal imports
from pyrates.cluster_compute.cluster_compute import *
from pyrates.utility import plot_timeseries, plot_psd, plot_connectivity

dts = 1e-2

# Create parameter grid
#######################
Cs = [15.0, 20.0, 25.0, 30.0]

ei_ratio = np.linspace(0.5, 4.0, 101)
io_ratio = np.linspace(0.5, 4.0, 101)

fig, ax = plt.subplots(ncols=len(Cs), nrows=3, figsize=(20, 15), gridspec_kw={})
for idx, C in enumerate(Cs):
    k_ee = np.zeros((int(len(ei_ratio) * len(io_ratio))))
    k_ei = np.zeros_like(k_ee)
    k_ie = np.zeros_like(k_ee)
    k_ii = np.zeros_like(k_ee)

    n = 0
    k_ee += C
    for ei in ei_ratio:
        for io in io_ratio:
            k_ei[n] += C / (ei * io)
            k_ie[n] += C / io
            k_ii[n] += C / ei
            n += 1

    params = {'k_ee': k_ee, 'k_ei': k_ei, 'k_ie': k_ie, 'k_ii': k_ii}

    res_file = f'/nobackup/spanien1/salomon/ClusterGridSearch/Montbrio/EIC/Coupling_alpha_0_high_res/Results/DefaultGrid_{idx}/CGS_result_DefaultGrid_{idx}.h5'
    results = pd.read_hdf(res_file, key='/Results/r_E0_df')

    peaks_freq = np.zeros((len(ei_ratio), len(io_ratio)))
    peaks_amp = np.zeros_like(peaks_freq)
    peaks_freq_masked = np.zeros_like(peaks_freq)

    for k_ee_, k_ei_, k_ie_, k_ii_ in zip(params['k_ee'], params['k_ei'], params['k_ie'], params['k_ii']):
        if not results[k_ee_][k_ei_][k_ie_][k_ii_].isnull().any().any():
            r, c = np.argmin(np.abs(ei_ratio - k_ee_ / k_ii_)), np.argmin(np.abs(io_ratio - k_ee_ / k_ie_))
            data = np.array(results[k_ee_][k_ei_][k_ie_][k_ii_].loc[100.0:])
            peaks, props = sp.find_peaks(data.squeeze(), prominence=0.6 * (np.max(data) - np.mean(data)))
            if len(peaks) > 1:
                diff = np.mean(np.diff(peaks)) * dts * 0.01
                peaks_freq[r, c] = 1 / diff
                peaks_amp[r, c] = np.mean(props['prominences'])

    mask = peaks_amp > 0.1
    peaks_freq_masked = peaks_freq * mask

    step_tick_x, step_tick_y = int(peaks_freq.shape[1] / 10), int(peaks_freq.shape[0] / 10)
    cm1 = cubehelix_palette(n_colors=int(len(ei_ratio) * len(io_ratio)), as_cmap=True, start=2.5, rot=-0.1)
    cax1 = plot_connectivity(peaks_freq, ax=ax[0, idx], yticklabels=list(np.round(ei_ratio, decimals=2)),
                             xticklabels=list(np.round(io_ratio, decimals=2)), cmap=cm1)
    for n, label in enumerate(ax[0, idx].xaxis.get_ticklabels()):
        if n % step_tick_x != 0:
            label.set_visible(False)
    for n, label in enumerate(ax[0, idx].yaxis.get_ticklabels()):
        if n % step_tick_y != 0:
            label.set_visible(False)
    cax1.set_xlabel('intra/inter pcs')
    cax1.set_ylabel('exc/inh pcs')
    cax1.set_title(f'max freq (C = {C})')

    cm2 = cubehelix_palette(n_colors=int(len(ei_ratio) * len(io_ratio)), as_cmap=True, start=-2.0, rot=-0.1)
    cax2 = plot_connectivity(peaks_amp, ax=ax[1, idx], yticklabels=list(np.round(ei_ratio, decimals=2)),
                             xticklabels=list(np.round(io_ratio, decimals=2)), cmap=cm2)
    for n, label in enumerate(ax[1, idx].xaxis.get_ticklabels()):
        if n % step_tick_x != 0:
            label.set_visible(False)
    for n, label in enumerate(ax[1, idx].yaxis.get_ticklabels()):
        if n % step_tick_y != 0:
            label.set_visible(False)
    cax2.set_xlabel('intra/inter pcs')
    cax2.set_ylabel('exc/inh pcs')
    cax2.set_title(f'mean peak amp (C = {C})')

    cm3 = cubehelix_palette(n_colors=int(len(ei_ratio) * len(io_ratio)), as_cmap=True, start=3, rot=-0.1)
    cax3 = plot_connectivity(peaks_freq_masked, ax=ax[2, idx], yticklabels=list(np.round(ei_ratio, decimals=2)),
                             xticklabels=list(np.round(io_ratio, decimals=2)), cmap=cm3)
    for n, label in enumerate(ax[2, idx].xaxis.get_ticklabels()):
        if n % step_tick_x != 0:
            label.set_visible(False)
    for n, label in enumerate(ax[2, idx].yaxis.get_ticklabels()):
        if n % step_tick_y != 0:
            label.set_visible(False)
    cax3.set_xlabel('intra/inter pcs')
    cax3.set_ylabel('exc/inh pcs')
    cax3.set_title(f'max freq masked (C = {C})')

plt.suptitle('EI-circuit sensitivity to population Coupling strengths (pcs), alpha=0, C={Cs}')

# plt.tight_layout(pad=2.5, rect=(0.01, 0.01, 0.99, 0.96))
# fig.savefig('/data/hu_salomon/Documents/EIC_Coupling_alpha_0_high_res', format="svg")

plt.show()

