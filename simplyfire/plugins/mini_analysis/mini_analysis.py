"""
mini_analysis plugin - analysis algorithms to find mini synaptic events
The module can be imported independently of the base UI system.

SimplyFire - Customizable analysis of electrophysiology data
Copyright (C) 2022 Megumi Mori
This program comes with ABSOLUTELY NO WARRANTY

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import numpy as np
import pandas as pd
from simplyfire.utils import calculate
from scipy import optimize
from datetime import datetime

def filter_mini(mini_df: pd.DataFrame = None,
                xlim=None,
                min_amp: float = 0.0,
                max_amp: float = np.inf,
                min_rise: float = 0.0,
                max_rise: float = np.inf,
                min_decay: float = 0.0,
                max_decay: float = np.inf,
                min_hw: float = 0.0,
                max_hw: float = np.inf,
                min_drr: float = 0.0,
                max_drr: float = np.inf,
                min_s2n: float = 0.0,
                max_s2n: float = np.inf,
                **kwargs):
    """
    Filters the previously found mini based on criteria
    df: DataFrame containing mini data
        If None, defaults to mini_df
    xlim: x-axis limits to apply the filter (the peak x-value ('t') is considered)
    max_amp: float representing the maximum accepted mini amplitude (y-axis unit of the recording)
    min_amp: float representing the minimum accepted mini amplitude (y-axis unit of the recording)
    max_rise: float representing the maximum accepted mini rise (ms)
    min_rise: float representing the minimum accepted mini rise (ms)
    max_decay: float representing the maximum accepted mini decay constant (ms)
    min_Decay: float representing the minimum accepted mini decay constant (ms)
    max_hw: float representing the maximum accepted mini halfwidth (ms)
    min_hw: float representing the minimum accepted mini halfwdith (ms)
    max_drr: float representing the maximum decay:rise ratio (no unit)
    min_drr: float representing the minimum decay:rise ratio (no unit)
    max_s2n: signal to noise ratio (amp/stdev) min
    min_s2n: signal to noise ratio (amp/stdev) max
    xlim: tuple representing the x-axis limits to apply the filter. If None, all entries in the dataframe are considered
    """
    if mini_df is None:
        return None
    if xlim is None:
        xlim = (0.0, np.inf)
    if min_amp is not None:
        mini_df = mini_df[
            (mini_df['amp'] * mini_df['direction'] >= min_amp) | (mini_df['t'] < xlim[0]) | (mini_df['t'] > xlim[1])]
    if max_amp is not None:
        mini_df = mini_df[
            (mini_df['amp'] * mini_df['direction'] < max_amp) | (mini_df['t'] < xlim[0]) | (mini_df['t'] > xlim[1])]
    if min_rise is not None:
        mini_df = mini_df[(mini_df['rise_const'] >= min_rise) | (mini_df['t'] < xlim[0]) | (mini_df['t'] > xlim[1])]
    if max_rise is not None:
        mini_df = mini_df[(mini_df['rise_const'] < max_rise) | (mini_df['t'] < xlim[0]) | (mini_df['t'] > xlim[1])]
    if min_decay is not None:
        mini_df = mini_df[(mini_df['decay_const'] >= min_decay) | (mini_df['t'] < xlim[0]) | (mini_df['t'] > xlim[1])]
    if max_decay is not None:
        mini_df = mini_df[(mini_df['decay_const'] < max_decay) | (mini_df['t'] < xlim[0]) | (mini_df['t'] > xlim[1])]
    if min_hw is not None:
        mini_df = mini_df[(mini_df['halfwidth'] >= min_hw) | (mini_df['t'] < xlim[0]) | (mini_df['t'] > xlim[1])]
    if max_hw is not None:
        mini_df = mini_df[(mini_df['halfwidth'] < max_hw) | (mini_df['t'] < xlim[0]) | (mini_df['t'] > xlim[1])]
    if min_drr is not None:
        mini_df = mini_df[(mini_df['decay_const'] / mini_df['rise_const'] > min_drr) | (mini_df['t'] < xlim[0]) | (
                mini_df['t'] > xlim[1])]
    if max_drr is not None:
        mini_df = mini_df[(mini_df['decay_const'] / mini_df['rise_const'] < max_drr) | (mini_df['t'] < xlim[0]) | (
                mini_df['t'] > xlim[1])]
    if min_s2n is not None and min_s2n > 0:
        mini_df = mini_df[
            (mini_df['stdev'] is not None) & (mini_df['amp'] * mini_df['direction'] / mini_df['stdev'] > min_s2n)]
    if max_s2n is not None and max_s2n < np.inf:
        mini_df = mini_df[
            (mini_df['stdev'] is not None) & (mini_df['amp'] * mini_df['direction'] / mini_df['stdev'] < max_s2n)]

    return mini_df


from simplyfire import app


def interrupt():
    # temporary deal with analyzer, will become contained later
    global stop
    stop = True


def find_mini_auto(xlim=None,
                   xs=None,
                   ys=None,
                   recording=None,
                   x_sigdig=6,
                   sampling_rate=None,
                   channel=0,
                   sweeps=None,
                   auto_radius=None,
                   kernel=100,
                   stride=None,
                   direction=1,
                   reference_df=None,
                   progress_bar=None,
                   **kwargs
                   ):
    """
    Searches for mini events and populates mini_df attribute within the recording attribute data

    If multiple searches are performed on the same xs and ys data, it is recommended to
    store the xs and ys data outside of the Analyzer and pass them as arguments to speed up
    the search time. If ys and xs are not provided as arguments, continuous sequence of
    xs and ys data are created on the fly from the recording data every function call.


    Args:
        xlim: float tuple representing the search window limits. [left, right] If None, defaults to entire dataset
        xs: float numpy array representing the x-values of the recording sequence.
            If None, data will be extracted from the recording attribute using the channel and sweeps arguments.
        ys: float numpy array representing the y-values of the recording sequence.
            If None, data will be extracted from the recording attribute using the channel and sweeps arguments.
        x_sigdig: int number of significant digit for the x-value. Used to round calculations
        sampling_rate: float - sampling rate of xs
        channel: int indicating the channel number to analyze. Only required if xs and ys are not provided
        sweeps: list of int indicating the sweeps to analyzer. If left None, all sweeps will be considered
        auto_radius: x-axis window to be considered per iteration in ms.
            If left empty, defaults to the values indicated in kernel and stride parameters
        kernel: int representing the number of indices to consider per iteration.
            The most extreme data point within the kernel will be tested as a candidate mini peak.
            Should be smaller than the shortest interval between two minis within the recording.
            Larger kernel size can speed up the search.
        stride: int representing the number of data points to shift every iteration.
            Recommended to be less than kernel.
            Larger strides can speed up the search.
        direction: int
        reference_df: pd.DataFrame to check for duplicates
        progress_bar: object pass a progress bar object. The value of the progressbar must be updatable using
            progress_bar['value'] = int
        **kwargs: see list of parameters in analyze_candidate_mini()

    Returns:
        pandas DataFrame containing the information on search parameters and mini characteristics.
        In addition to the search parameters passed as arguments, the following data are included
        in the result:
            #### list columns here
    """
    show_time = False
    global stop
    stop = False
    if xs is None or ys is None:
        if recording is None:
            return None  # cannot analyze
    if xs is None:
        xs = recording.get_xs(mode='continuous', channel=channel, xlim=xlim)
    if ys is None:
        ys = recording.get_ys(mode='continuous', channel=channel, xlim=xlim)
    else:
        ys = ys.copy()  # make a copy to edit
    try:
        xlim_idx = (
            calculate.search_index(xlim[0], xs, sampling_rate), calculate.search_index(xlim[1], xs, sampling_rate))
    except:
        xlim_idx = (0, len(xs))

    if auto_radius is not None:
        if sampling_rate is None:
            sampling_rate = 1 / np.mean(xs[1:5] - xs[0:4])
        elif sampling_rate == 'auto':
            try:
                sampling_rate = recording.sampling_rate
            except:
                sampling_rate = 1 / np.mean(xs[1:5] - xs[0:4])
        kernel = int(auto_radius / 1000 * sampling_rate)
    if stride is None:
        stride = int(kernel / 2)

    # calculate intervals for progres bar
    increment = (xlim_idx[1] - xlim_idx[0]) / 20
    pb_idx = 0

    start_idx = xlim_idx[0]
    end_idx = start_idx + kernel
    if progress_bar:
        total = xlim_idx[1] - xlim_idx[0]
        start = start_idx
        progress_bar['value'] = 0
        progress_bar.update()
    hits = []
    prev_peak = None
    while start_idx < xlim_idx[1] and not stop:
        peak_idx = find_peak_recursive(xs, ys, start=start_idx, end=end_idx, direction=direction)
        try:
            different_peak = (peak_idx != prev_peak['peak_idx'])
        except:
            different_peak = True
        if peak_idx is not None and different_peak:
            # print(f'before analysis, prev peak is: {prev_peak}')
            mini = analyze_candidate_mini(
                xs=xs,
                ys=ys,
                peak_idx=peak_idx,
                x_sigdig=x_sigdig,
                sampling_rate=sampling_rate,
                channel=channel,
                direction=direction,
                reference_df=reference_df,
                prev_peak=prev_peak,
                **kwargs
            )
            if mini['success']:
                mini['xlim_idx_L'] = start_idx
                mini['xlim_coord_L'] = xs[start_idx]
                mini['xlim_idx_R'] = min(len(xs)-1,end_idx)
                mini['xlim_coord_R'] = xs[min(len(xs)-1,end_idx)]
                hits.append(mini)
                prev_peak = mini
            else:
                if mini['failure'] == 'Mini was previously found':
                    # make sure the failure code matches here
                    prev_peak = mini

            # print(f'end of analysis, mini was: {mini}')
            # print(f'end of analysis, prev_peak is set to: {prev_peak}')
        start_idx += stride
        end_idx = min(start_idx + kernel, xlim_idx[1])
        try:
            # if start_idx > increment:
            #     progress_bar['value'] = progress_bar['value'] + 5
            #     progress_bar.update()
            #     progress_bar.after(5, None)
            #     increment += increment
            progress_bar['value'] = int((start_idx - start) / total * 100)
            progress_bar.update()
        except:
            pass
    new_df = pd.DataFrame.from_dict(hits)
    # if reference_df:
    #     if len(reference_df.index)>0:
    #         new_df = pd.concat([reference_df,new_df]) # indexing is NOT UNIQUE
    return new_df


def find_mini_manual(xlim: tuple = None,
                     xlim_idx: tuple = None,
                     xs: np.ndarray = None,
                     ys: np.ndarray = None,
                     recording=None,
                     x_sigdig: int = 6,
                     sampling_rate: float = None,
                     channel=0,
                     sweeps=None,
                     direction=1,
                     reference_df=None,
                     offset: int = 0,
                     **kwargs
                     ):
    """
    Searches for a biggest mini event within xlim

    If ys and xs are not provided as arguments, continuous sequence of
    xs and ys data are created on the fly from the recording data every function call.

    Args:
        xlim: float tuple representing the search window limits. [left, right]
        xs: float numpy array representing the x-values of the recording sequence.
            If None, data will be extracted from the recording attribute using the channel and sweeps arguments.
        ys: float numpy array representing the y-values of the recording sequence.
            If None, data will be extracted from the recording attribute using the channel and sweeps arguments.
        x_sigdig: int number of significant digit for the x-value. Used to round calculations
        sampling_rate: float - sampling rate of xs
        channel: int indicating the channel number to analyze. Only required if xs and ys are not provided
        sweeps: list of int indicating the sweeps to analyzer. If left None, all sweeps will be considered
        direction: int
        reference_df: pd.DataFrame to check for duplicates
        offset: used to change the indexing of the xs and ys arrays
        **kwargs: see list of parameters in find_single_mini()

    Returns:
        pandas DataFrame containing the information on search parameters and mini characteristics.
        In addition to the search parameters passed as arguments, the following data are included
        in the result:
            #### list columns here
    """
    if xs is None or ys is None:
        if recording is None:
            return None  # insufficient data
    if xs is None:
        xs = recording.get_x_matrix(mode='continuous', channels=[channel], sweeps=sweeps, xlim=xlim).flatten()
    if ys is None:
        ys = recording.get_y_matrix(mode='continuous', channels=[channel], sweeps=sweeps, xlim=xlim).flatten()
    else:
        ys = ys.copy()
    if xlim_idx is None:
        if xlim is None:
            return {'success': False, 'failure': 'insufficient info'}
        try:
            xlim_idx = (
                calculate.search_index(xlim[0], xs, sampling_rate), calculate.search_index(xlim[1], xs, sampling_rate))
        except:
            return {'success': False,
                    'failure': 'xlim could not be found'}  # limits of the search window cannot be determined

    peak_idx = find_peak_recursive(xs, ys, start=xlim_idx[0], end=xlim_idx[1], direction=direction)
    if peak_idx is not None:
        mini = analyze_candidate_mini(
            xs=xs,
            ys=ys,
            peak_idx=peak_idx,
            x_sigdig=x_sigdig,
            sampling_rate=sampling_rate,
            channel=channel,
            direction=direction,
            reference_df=reference_df,
            offset=offset,
            **kwargs
        )
        mini['xlim_idx_L'] = xlim_idx[0]
        mini['xlim_idx_R'] = xlim_idx[1]
        return pd.Series(mini)
    return {'success': False, 'failure': 'peak could not be found', 'xlim_idx': xlim_idx}


def find_peak_recursive(xs,
                        ys,
                        start,
                        end,
                        direction=1):
    """
    recursively seeks local extremum within a given index range
    Args:
        xs: float 1D numpy array - x-values
        ys: float 1D numpy array - y-values
        start: int - index within xs,ys to start the search
        end: int - index within xs,ys to end the search
            [start, end)
        direction: int {-1, 1} - direction of the expected peak. -1 for current (local minimum), 1 for potential (local maximum). Default 1
    Returns:
        peak_idx: int where the peak data point is located
        peak_val: value at peak_idx
    """
    FUDGE = 10  # margin at the edge of search window required to be considered peak (used to avoid edge cases)
    if end - start < FUDGE * 2:
        return None  # the search window is too narrow
    try:
        peak_y = max(ys[start:end] * direction)
    except:
        print(ys[start:end] * direction)
        print(ys[start:end])
        print(len(ys))
        print(f'peak search error, start:end: {start, end}')
    peaks = np.where(ys[start:end] * direction == peak_y)[0] + start  # get list of indices where ys is at peak
    peak_idx = peaks[int(len(peaks) / 2)]  # select the middle index of the peak

    # check if the peak is at the edge of the search window
    # if the peak is at the edge, the slope could continue further beyond the window
    # recursively narrow the search window and look for another local extremum within the new window

    if peak_idx < start + FUDGE:  # the local extremum is at the left end of the search window
        return find_peak_recursive(xs, ys, start + FUDGE, end, direction)
    if peak_idx > end - FUDGE:  # the local extremum is at the right end of the search window
        return find_peak_recursive(xs, ys, start, end - FUDGE, direction)
    return peak_idx

##@njit
def find_mini_start(peak_idx: int,
                    ys: np.ndarray,
                    lag: int = 100,
                    delta_x: int = 400,
                    direction: int = 1) -> tuple:
    """
    Calculates estimated baseline value and the index of start of a mini event

    Args:
        peak_idx: int representing the index at which the candiate mini peak was found in ys array
        ys: 1D numpy array representing the y-value to seearch for mini
        lag: int representing the number of datapoints averaged to find the trailing average. Default 100
            The result of the trailing average is used to estamate the baseline.
            The point at which the mini data crosses the trailing average is considered the start of the mini.
        delta_x: int representing the number of datapoints before peak to reference as the baseline.
            Baseline y-value is calculated as: mean of [peak_idx - delta_x - lag:peak_idx - delta_x)
        direction: int {-1, 1} indicating the expected sign of the mini event. -1 for current, 1 for potential.
            Default 1
    Returns:
        idx: index where ys data point reaches baseline (start of mini)
        baseline: estimated baseline value. This is the trailing average of lag data points
                prior to the baseline_idx in ys
    """
    # initialize search at the index previous to the peak
    # left of peak for start of mini
    idx = peak_idx - 1

    # NB: by multiplying the direction, the ys values will always peak in the positive direction
    if idx < lag:
        return None, None  # there are less than lag data points to the left of starting index

    # baseline = np.mean(ys[peak_idx - delta_x -lag: peak_idx - delta_x])  # average sometime before the peak
    #
    # while idx > lag:
    #     if ys[idx] * direction <= baseline * direction:
    #         break
    #     idx -= 1
    # else:
    #     return None, baseline  # couldn't find the corresponding datapoint
    # return idx, baseline

    if delta_x == 0:
        tma = np.mean(ys[idx - lag:idx]) * direction  # avg lag data points - trailing moving average
        while lag <= idx:
            idx -= 1
            tma = tma + (ys[idx - lag] - ys[idx]) * direction / lag  # update trailing avg
            if tma >= ys[idx] * direction:
                return idx, tma * direction
        else:
            return None, None

    # estimate baseline using avg data points at delta_x before peak
    tma = np.mean(ys[int(peak_idx - delta_x):int(peak_idx - delta_x + lag)]) * direction
    while idx > peak_idx - delta_x:
        if tma >= ys[idx] * direction:
            return idx, tma * direction
        idx -= 1
    else:
        return None, None

    # cma = np.mean(ys[idx - int(lag/2):idx] * direction) # central moving average
    #
    # update_tma=True
    # update_cma=True
    #
    # tma_idx = idx
    # cma_idx = idx
    # while lag <= idx:
    #     idx -= 1
    #     if update_cma:
    #         next_cma = cma + (ys[idx - int(lag/2)] + ys[idx+int(lag/2)]) * direction/ (int(lag/2)*2)
    #         if next_cma > cma: # heading backwards in a downwards slope
    #             update_cma = False
    #             cma_idx = idx + 1
    #         else:
    #             cma = next_cma
    #     if update_tma:
    #         tma = tma + (ys[idx - lag] - ys[idx]) * direction / lag # update trailing avg
    #         # equivalent to np.mean(ys[base_idx-lag: base_idx])
    #         if tma >= ys[idx] * direction: # y-value dips below the estimated baseline
    #             update_tma = False
    #             tma_idx = idx + 1
    #     if not update_cma and not update_tma:
    #         break
    # else:
    #     return None, None # could not find baseline until base_idx < lag or base_idx > len(ys) - lag
    # print(f'cma: {cma_idx}, tma: {tma_idx}')
    # return min(cma_idx, tma_idx), min(tma, cma) * direction


def find_mini_end(peak_idx: int,
                  ys: np.ndarray,
                  lag: int = 100,
                  direction: int = 1) -> tuple:
    """
    Calculates the baseline value and estimated end index of a mini event
    Args:
        peak_idx: int representing the index at which the candiate mini peak was found in ys array
        ys: 1D numpy array representing the y-value to seearch for mini
        lag: int representing the number of datapoints averaged to find the trailing average. Default 100
            The result of the trailing average is used to estamate the baseline.
            The point at which the mini data crosses the trailing average is considered the start of the mini.
        direction: int {-1, 1} indicating the expected sign of the mini event. -1 for current, 1 for potential.
            Default 1
    Returns:
        idx: index where ys data point reaches baseline (end of mini)
        baseline: estimated baseline value. This is the trailing average of lag data points
                ahead of idx in ys

    """
    # initialize search at the index after the peak
    idx = peak_idx + 1

    # NB: by multiplying the direction, the ys values will always peak in the positive direction
    if idx > len(ys) - lag:
        return None, None  # there are less than lag data points to the right of the starting index
    tma = np.mean(ys[idx:idx + lag]) * direction  # avg lag data points - trailing moving average
    while idx <= len(ys) - lag:
        idx += 1
        tma = tma + (ys[idx + lag] - ys[idx]) * direction / lag  # update trailing avg
        if tma >= ys[idx] * direction:
            return idx, tma * direction
    else:
        return None, None

    # tma = np.mean(ys[idx:idx + lag] * direction)  # avg lag data points, trailing moving average
    # cma = np.mean(ys[idx - int(lag / 2): idx + int(lag / 2)])  # central moving average
    #
    # update_tma = True
    # update_cma = True
    #
    # tma_idx = idx
    # cma_idx = idx
    # while lag <= idx <= len(ys) - lag:
    #     if update_cma:
    #         next_cma = cma + (ys[idx + int(lag / 2)] - ys[idx - int(lag / 2)]) * direction / (int(lag / 2) * 2)
    #         if next_cma > cma:  # upward slope
    #             update_cma = False
    #             cma_idx = idx - 1
    #         else:
    #             cma = next_cma
    #     if update_tma:
    #         tma = tma + (ys[idx + lag] - ys[idx]) * direction / lag  # update trailing avg
    #         # equivalent to np.mean(ys[base_idx-lag: base_idx])
    #         if tma >= ys[idx] * direction and next_cma >= cma:  # y-value dips below the estimated baseline
    #             update_tma = False
    #             tma_idx = idx - 1
    #     if not update_cma and not update_tma:
    #         break
    #     idx += 1
    # else:
    #     return None, None  # could not find baseline until base_idx < lag or base_idx > len(ys) - lag
    # return max(cma_idx, tma_idx), min(tma, cma) * direction


def find_mini_halfwidth(amp: float,
                        xs: np.ndarray,
                        ys: np.ndarray,
                        peak_idx: int,
                        baseline: float,
                        direction: int = 1,
                        prev_mini_t: float = None,
                        prev_mini_A: float = None,
                        prev_mini_decay: float = None,
                        prev_mini_decay_baseline: float = None,
                        prev_mini_baseline: float = None,
                        prev_mini_direction: float = None
                        ):
    """
    calculates the halfwidth of a mini event

    Args:
        amp: float representing the estimated amplitude of the mini. Used to calculate 50% amplitude
        ys: float numpy array of the y-value data
        xs: float numpy array of the x-value data
        start_idx: int representing the index in xs and ys that marks the start of the mini event
        end_idx: int representing the index in xs and ys that marks the end of the mini event
        peak_idx: int representing the index in xs and ys that marks the peak of the mini event
        baseline: float - the estimated baseline for the mini event
        direction: int {-1, 1}
    Returns:
        halfwidth_start_index: int representing the index at which y-value is 50% of the amplitude
        halfwidth_end_index: int reperesenting the index at which y-value is 50% of the amplitude
        halfwidth: time it takes for the mini to reach 50% of amplitude and return to 50% of amplitude
    """
    if prev_mini_A is not None:
        prev_mini_t_ms = prev_mini_t * 1000
        if prev_mini_direction is None:
            prev_mini_direction = direction
        y_data = ys - prev_mini_baseline
        y_data = y_data - single_exponent_constant((xs * 1000 - prev_mini_t_ms), prev_mini_A, prev_mini_decay,
                                                   prev_mini_decay_baseline) * prev_mini_direction
        y_data = y_data * direction

    else:
        y_data = (ys - baseline) * direction
    left_idx = np.argmax(y_data[:peak_idx] >= (amp * 0.5) * direction)
    if left_idx == -1:
        left_idx = None
    right_idx = np.argmax(y_data[peak_idx:] <= (amp * 0.5) * direction)
    if right_idx > -1:
        right_idx += peak_idx
    else:
        right_idx = None
    return left_idx, right_idx  # pick the shortest length


def fit_mini_decay(xs: np.ndarray,
                   ys: np.ndarray,
                   sampling_rate: float,
                   end_idx: int,
                   amplitude: float = None,
                   decay_guess: float = None,
                   direction: int = 1,
                   baseline: float = 0.0,
                   prev_mini_decay: float = None,
                   prev_mini_A: float = None,
                   prev_mini_decay_baseline: float = None,
                   prev_mini_baseline: float = None,
                   prev_mini_t: int = None,
                   prev_mini_direction: int = None
                   ):
    """
    decay fitting, takes into account prev mini
    xs: np.ndarray of the data segment to be fitted - start = peak, and end = end of fit
    ys: np.ndarray of the data segment to be fitted -
    sampling_rate: in Hz
    start_idx: int index within xs and ys of the peak
    end_idx: int index within xs and ys of the end of mini
    direction: int {-1, 1}
    prev_mini_const: if compound mini, the decay function constant (tau) of the previous mini
    prev_mini_A: if compound mini, the amplitude (A) of the previous mini
    prev_mini_peak_t: previous peak's t
    num_points: max number of points to fit
    """

    x_data = (xs - xs[0]) * 1000
    # print(x_data)

    if prev_mini_t is not None:  # compound mini
        prev_mini_t_ms = prev_mini_t * 1000
        if prev_mini_direction is None:
            prev_mini_direction = direction

        y_data = ys - prev_mini_baseline
        y_data = y_data - single_exponent_constant((xs * 1000 - prev_mini_t_ms), prev_mini_A, prev_mini_decay,
                                                   prev_mini_decay_baseline) * prev_mini_direction
        y_data = y_data * direction

    else:
        y_data = (ys - baseline) * direction  # baseline subtract
    y_data[end_idx:] = 0

    p0 = [1] * 2
    if amplitude is not None:
        p0[0] = amplitude
    if decay_guess is not None:
        p0[1] = decay_guess

    # initialize weights for gradient descent
    y_weight = np.empty(len(y_data))
    y_weight.fill(10)
    y_weight[0] = 0.001
    # fit
    results = optimize.curve_fit(single_exponent,
                                 x_data,
                                 y_data,
                                 p0=p0,
                                 sigma=y_weight,
                                 absolute_sigma=True,
                                 maxfev=15000)
    a = results[0][0]
    t = results[0][1]
    # d = results[0][2]
    d = 0
    # print((a, t, d))

    return a, t, d


def calculate_mini_decay(xs: np.ndarray,
                         ys: np.ndarray,
                         sampling_rate: float,
                         start_idx: int,
                         end_idx: int,
                         num_points: int,
                         direction: int = 1,
                         baseline: float = 0.0):
    """
    calculates decay of a mini

    Args:
        xs: float numpy array of the x values
        ys: float numpy array of the y values
        start_idx: int representing the index to start the fit (should be peak of mini)
        end_idx: int reprsenting the index to end the mini
        num_points: int number of datapoints to use for fit
        direction: int {-1, 1}
        baseline: float to subtract from ys

    Returns:
        a, t, d: float, single exponential function parameters
        decay_constant_idx: int representing the index of xs, ys where y-value is e^-1 of max amplitude

    """

    ########## is it better the constrain a? ##############

    x_data = (xs[start_idx:min(start_idx + num_points, len(xs))] - xs[start_idx]) * 1000
    # print(x_data)
    y_data = (ys[start_idx:min(start_idx + num_points, len(xs))] - baseline) * direction
    y_data[end_idx - start_idx:] = 0

    # initialize weights for gradient descent
    y_weight = np.empty(len(y_data))
    y_weight.fill(10)
    y_weight[0] = 0.001

    # fit
    results = optimize.curve_fit(single_exponent,
                                 x_data,
                                 y_data,
                                 sigma=y_weight,
                                 absolute_sigma=True,
                                 maxfev=15000)
    a = results[0][0]
    t = results[0][1]
    decay_constant_idx = calculate.search_index(t, x_data, sampling_rate) + start_idx  # offset to start_idx

    return a, t, decay_constant_idx

def calculate_mini_10_90_rise(xs:np.ndarray,
                              ys:np.ndarray,
                              baseline:float,
                              amp:float,
                              start_idx:int,
                              peak_idx:int,
                              direction:int=1,
                              sampling_rate:int=None):
    low_idx = np.argmax((ys[start_idx:peak_idx+1]-baseline)*direction > amp*direction*0.1)
    high_idx = np.argmax((ys[start_idx:peak_idx+1]-baseline)*direction > amp*direction*0.9)

    if sampling_rate:
        return (high_idx-low_idx)*1/sampling_rate*1000
    else:
        return (xs[high_idx] - xs[low_idx]) *1000


def analyze_candidate_mini(xs,
                           ys,
                           peak_idx=None,
                           peak_t=None,
                           x_sigdig=None,
                           sampling_rate=None,
                           channel=0,
                           reference_df=None,
                           reanalyze=False,
                           ## parameters defined in GUI ##
                           direction=1,
                           delta_x_ms=None,
                           delta_x=0,
                           lag_ms=None,
                           lag=100,
                           ## compound parameters defined in GUI ##
                           compound=1,
                           p_valley=50,
                           max_compound_interval=0,
                           min_peak2peak_ms=0,
                           extrapolate_hw=0,
                           ## decay algorithm parameters ##
                           decay_algorithm='% amplitude',
                           decay_p_amp=0.37,
                           decay_ss_min=0.0,
                           decay_ss_max=10,
                           decay_ss_interval=0.01,
                           decay_best_guess=4,
                           decay_max_interval=40,
                           decay_max_points=None,
                           ## filtering parameters defined in GUI ##
                           min_amp=0.0,
                           max_amp=np.inf,
                           min_rise=0.0,
                           max_rise=np.inf,
                           min_10_90=0.0,
                           max_10_90=np.inf,
                           min_hw=0.0,
                           max_hw=np.inf,
                           min_decay=0.0,
                           max_decay=np.inf,
                           min_drr=0.0,
                           max_drr=np.inf,
                           min_s2n=0,
                           max_s2n=np.inf,
                           #################################
                           offset=0,
                           y_unit='mV',
                           x_unit='s',
                           ##################################
                           prev_peak_idx=None,
                           prev_peak=None,
                           manual_radius = 0,
                           **kwargs
                           ):
    """
        peak_idx: int - Index within the xs data corresponding to a peak.
        peak_t: float - if provided, takes precedence over peak_idx
        x_sigdig: significant digits in x
        sampling_rate: sampling rate of xs in Hz
        direction: int {-1, 1} indicating the expected sign of the mini event. -1 for current, 1 for potential.
        delta_x_ms: float, prioritized
        delta_x: int
        lag_ms: float representing the x-axis window to be averaged to estimate the baseline and start of the mini.
            If given, this parameter is prioritized over the lag parameter
        lag: int indicating the number of data points used to calculate the baseline.
            See calculate_mini_baseline() for algorithm on baseline estimation.
            If None, lag_ms must be provided
        direction: int {-1, 1} indicating the expected sign of the mini event. -1 for current, 1 for potential.
        min_amp: float indicating the minimum amplitude required in a candidate mini.
        max_amp: float indicating the maximum amplitude accepted in a candidate mini.
        min_rise: float indicating the minimum rise required in a candidate mini.
        max_rise: float indicating the maximum rise accepted in a candidate mini.
        min_hw: float indicating the minimum halfwidth required in a candidate mini.
            See calculate_mini_halfwidth() for algorithm on halfwidth calculation
        max_hw: float indicating the maximum halfwidth accepted in a candidate mini.
            See calculate_mini_halfwidth() for algorithm on halfwidth calculation
        min_decay: float indicating the minimum decay constant required in a candidate mini.
            See calculate_mini_decay() for algorithm on decay constant calculation.
        max_decay: float indicating the maximum decay constant accepted in a candidate mini.
            See calculate_mini_decay() for algorithm on decay constant calculation.
        reference_df: pd.DataFrame to compare the results against previously found minis
        reanalyze: bool indicating whether the candidate mini is already in mini_df
            Set to True if reanalyzing a previously found mini.
            If set to False, previously found minis will be ignored.

    """
    # print(f'start of analysis, prev peak passed is: {prev_peak}')
    show_time = False
    # perform conversions
    if sampling_rate == 'auto':
        sampling_rate = 1 / np.mean(xs[1:5] - xs[0:4])
    # convert lag_ms to lag
    if lag_ms is not None:
        lag = int(lag_ms / 1000 * sampling_rate)
    if decay_max_interval is not None:
        decay_max_points = int(decay_max_interval / 1000 * sampling_rate)
    if delta_x_ms is not None:
        delta_x = int(delta_x_ms / 1000 * sampling_rate)
    if peak_t:
        peak_idx = calculate.search_index(peak_t, xs, sampling_rate)
    elif peak_idx:
        peak_idx = int(peak_idx)  # make sure is int
    if peak_t is None and peak_idx is None:
        return {'success': False, 'failure': 'peak idx not provided'}
    min_peak2peak = min_peak2peak_ms / 1000 * sampling_rate
    if prev_peak:  # had the prev peak provided as dict
        try:
            prev_peak_idx = prev_peak['peak_idx']
        except:
            print('prev peak is None')
            prev_peak = None
    elif prev_peak_idx:  # had index provided but not the dict  
        try:
            prev_peak_candidate = reference_df.loc[(reference_df['peak_idx'] == prev_peak_idx) &
                                                   (reference_df['channel'] == channel)]
            if prev_peak_candidate.shape[0] > 0:
                prev_peak = prev_peak_candidate.squeeze().to_dict()

        except:
            prev_peak = None
    # initiate mini data dict
    mini = {'direction': direction, 'lag': lag, 'delta_x': delta_x, 'channel': channel, 'min_amp': min_amp,
            'max_amp': max_amp,
            'min_rise': min_rise, 'max_rise': max_rise, 'min_hw': min_hw, 'max_hw': max_hw, 'min_decay': min_decay,
            'min_s2n': min_s2n, 'max_s2n': max_s2n, 'min_drr': min_drr, 'max_drr': max_drr,
            'max_decay': max_decay, 'decay_max_points': decay_max_points, 'decay_max_interval': decay_max_interval,
            'datetime': datetime.now().strftime('%m-%d-%y %H:%M:%S'), 
            'failure': None, 'success': True,
            't': xs[peak_idx], 'peak_idx': peak_idx + offset, 'compound': False,
            'baseline_unit': y_unit}
    max_compound_interval_idx = max_compound_interval * sampling_rate / 1000
    if x_unit in ['s', 'sec', 'second', 'seconds']:
        mini['decay_unit'] = mini['rise_unit'] = mini['halfwidth_unit'] = 'ms'
    else:
        mini['decay_unit'] = mini['rise_unit'] = mini['halfwidth_unit'] = x_unit + 'E-3'
    mini['amp_unit'] = mini['stdev_unit'] = y_unit

    # extract peak datapoint
    if x_sigdig is not None:
        mini['t'] = round(mini['t'], x_sigdig)  # round the x_value of the peak to indicated number of digits

    # check if the peak is duplicate of existing mini data
    if reference_df is not None and not reanalyze:
        try:
            if mini['t'] in reference_df[
                (reference_df['channel'] == channel)].t.values:  # check if t exists in the channel
                mini = reference_df.loc[(reference_df['t'] == mini['t']) &
                                        (reference_df['channel'] == channel)].squeeze().to_dict()
                mini['success'] = False
                mini['failure'] = 'Mini was previously found'
                return mini
        except:  # if df is empty, will throw an error
            pass

    # store peak coordinate
    mini['peak_coord_x'] = xs[peak_idx]
    mini['peak_coord_y'] = ys[peak_idx]

    baseline_idx, mini['baseline'] = find_mini_start(peak_idx=peak_idx,
                                                     ys=ys,
                                                     lag=lag,
                                                     delta_x=delta_x,
                                                     direction=direction)

    # check if baseline calculation was successful
    if baseline_idx is None:  # not successful
        mini['success'] = False
        mini['failure'] = 'Baseline could not be found'
        return mini
    if delta_x is None or delta_x == 0:
        base_idx = (baseline_idx - lag, baseline_idx)
    else:
        base_idx = (int(peak_idx - delta_x - lag / 2), int(peak_idx - delta_x + lag / 2))
    mini['base_idx_L'] = base_idx[0] + offset
    mini['base_coord_L'] = xs[base_idx[0] + offset]
    mini['base_idx_R'] = base_idx[1] + offset
    mini['base_coord_R'] = xs[base_idx[1] + offset]
    ####### search baseline #######
    # find baseline/start of event
    mini['start_idx'] = baseline_idx + offset

    if reference_df is not None or prev_peak is not None:
##    if False:  
        # find the peak of the previous mini
        # peak x-value must be stored in the column 't'
        # check that the channels are the same
        try:
            prev_peak_candidate_idx = reference_df.loc[(reference_df['channel'] == channel) & (
                    reference_df['t'] < mini['t'])].peak_idx
            prev_peak_candidate_idx = max(prev_peak_candidate_idx)
        except:
            prev_peak_candidate_idx = None

        if prev_peak_candidate_idx is not None:
            # check if provided peak is closer
            if (prev_peak_idx is not None and prev_peak_idx < prev_peak_candidate_idx) or prev_peak_idx is None:
                prev_peak_idx = prev_peak_candidate_idx

                prev_peak = reference_df.loc[(reference_df['peak_idx'] == prev_peak_idx) &
                                             (reference_df['channel'] == channel)].squeeze().to_dict()
                # print(f'got prev peak from ref df: {prev_peak["peak_idx"]}')
        if prev_peak is not None:
            # print(prev_peak['peak_idx'])
            # print(f'at the problematic location, prev peak is set to: {prev_peak}')
            prev_peak_idx_offset = int(prev_peak['peak_idx']) - offset
            if xs[peak_idx] - xs[prev_peak_idx_offset] < min_peak2peak_ms/1000: # mini already found but was missed by an earlier check
                mini['success'] = False
                mini['failure'] = 'Minimum peak to peak separation not met'
                return mini
            # check if previous peak has decayed sufficiently
            if min((ys[prev_peak_idx_offset:peak_idx] - prev_peak['baseline']) * direction) > prev_peak[
                'amp'] * direction * (100 - p_valley) / 100:
                mini['success'] = False
                mini['failure'] = 'Minimum peak_to_valley % not reached for the previous mini'
                return mini
            # calculate start and baseline based on previous decay
            if compound:
                if prev_peak_idx_offset + max_compound_interval * sampling_rate / 1000 > peak_idx:
                    # current peak is within set compound interval from the previous peak
                    mini['compound'] = True
                    prev_t = prev_peak['t']
                    mini['prev_t'] = prev_t
                    mini['prev_peak_idx'] = prev_peak['peak_idx']
                    if prev_peak_idx_offset < 0 or prev_peak_idx_offset > len(ys):  # not sufficient datapoints
                        mini['success'] = False
                        mini['failure'] = 'The compound mini could not be analyzed - need more data points'

                    mini['prev_baseline'] = prev_peak['baseline']
                    mini['prev_decay_const'] = prev_peak['decay_const']
                    mini['prev_decay_A'] = prev_peak['decay_A']
                    mini['prev_mini_direction'] = prev_peak['direction']
                    try:
                        mini['prev_decay_baseline'] = prev_peak['decay_baseline']
                    except:
                        mini['prev_decay_baseline'] = prev_peak['baseline']

                    # extrapolate start from previous decay
                    # plot the previous mini decay
                    y_decay = single_exponent((xs[prev_peak_idx_offset:peak_idx + 1] - xs[prev_peak_idx_offset]) * 1000,
                                              mini['prev_decay_A'], mini['prev_decay_const'])
                    # orient the decay to the direction of the previous mini
                    y_decay = y_decay * mini['prev_mini_direction']
                    # add the offset from the baselin of the previous mini
                    y_decay = y_decay + mini['prev_baseline']

                    # calculate where the intersection between the decay and the raw data
                    # mark point right before the raw data crosses the decay function
                    try:
                        baseline_idx_ex = np.where(y_decay * direction >= ys[prev_peak_idx_offset:peak_idx + 1] * direction)[0][
                                              -1]
                        # reset the index value (np.where will set first index to 0)
                        baseline_idx_ex += prev_peak_idx_offset

                    except:
                        baseline_idx_ex = None
                    # find where the 'min' valley value is between previous peak and current peak
                    baseline_idx_min = np.where(ys[prev_peak_idx_offset:peak_idx] * direction == min(
                        ys[prev_peak_idx_offset:peak_idx] * direction))[0][0] + prev_peak_idx_offset
                    # update start_idx
                    try:
                        baseline_idx = max(baseline_idx_ex, baseline_idx_min)
                    except:
                        baseline_idx = baseline_idx_min
                    mini['start_idx'] = baseline_idx + offset
                    # extrapolate baseline at peak from previous decay
                    mini['baseline'] = single_exponent((xs[peak_idx] - xs[prev_peak_idx_offset]) * 1000,
                                                       mini['prev_decay_A'],
                                                       mini['prev_decay_const']) * mini['prev_mini_direction'] + mini[
                                           'prev_baseline']  # get the extrapolated baseline value
##    print("Before amplitude check: " + str(mini['success']))
    mini['amp'] = (mini['peak_coord_y'] - mini['baseline'])  # signed
    # store coordinate for start of mini (where the plot meets the baseline)
    mini['start_coord_x'] = xs[baseline_idx]
    mini['start_coord_y'] = ys[baseline_idx]

    if min_amp and (mini['amp'] * direction) < min_amp:
        mini['success'] = False
        mini['failure'] = 'Min amp not met'
        return mini
		
##    print("After amplitude check: " + str(mini['success']))

    if max_amp and mini['amp'] * direction > max_amp:
        mini['success'] = False
        mini['failure'] = 'Max amp exceeded'
        return mini

    ####### calculate stdev ########
    if mini['compound'] is False:
        mini['stdev'] = np.std(ys[max(0, baseline_idx - lag):baseline_idx])
    else:
        mini['stdev'] = prev_peak['stdev'] #
    # else:
    #     mini['stdev'] = None
    #     if (min_s2n and min_s2n > 0) or (max_2n and max_s2n < np.inf): # cannot filter
    #         mini['success'] = False
    #         mini['failure'] = 'Not enough data to calculate stdev of baseline'
    #         return mini
    if mini['stdev'] and min_s2n and mini['amp'] * direction / mini['stdev'] < min_s2n:
        mini['success'] = False
        mini['failure'] = 'Min signal to noise ratio not met'
        return mini
    if mini['stdev'] and max_s2n is not None and mini['amp'] * direction / mini['stdev'] > max_s2n:
        mini['success'] = False
        mini['failure'] = 'Max signal to noise exceeded'
        return mini
    ####### calculate end of event #######
    next_peak_idx = None
    if compound:
        next_search_start = np.where((ys[int(peak_idx):int(peak_idx + max_compound_interval_idx)] -
                                      mini['baseline']) * direction < mini['amp'] * (100 - p_valley) / 100 * direction)
        if len(next_search_start[0]) > 0:
            next_peak_idx = find_peak_recursive(xs=xs,
                                                ys=ys,
                                                start=int(min(next_search_start[0][0] + peak_idx,
                                                              len(ys) - 1)),
                                                end=int(min(peak_idx + max_compound_interval_idx,
                                                            len(ys) - 1)),
                                                direction=direction
                                                )
            if next_peak_idx is not None and next_peak_idx < peak_idx + min_peak2peak and peak_idx+min_peak2peak<len(ys)-1:
                next_peak_idx = find_peak_recursive(xs=xs,
                                                    ys=ys,
                                                    start=int(peak_idx+min_peak2peak),
                                                    end=int(min(peak_idx + max_compound_interval_idx,
                                                                len(ys) - 1)),
                                                    direction=direction
                                                    )
    end_idx = None
    if next_peak_idx is not None:
        # estimate amplitude of next peak
        if min_amp is None or (ys[next_peak_idx] - mini['baseline']) * direction > min_amp:
            # include peak_idx:peak_idx+min_peak2peak because the valley happens before the next peak
            # pick the last point if there are multiple minimums
            end_idx = np.where(ys[int(peak_idx):next_peak_idx] * direction == min(
                ys[int(peak_idx):next_peak_idx] * direction))[0][-1] + int(peak_idx)
    if end_idx is None:
        end_idx = min(peak_idx + decay_max_points, len(xs) - 1)

    mini['end_idx'] = end_idx + offset

    # store the coordinate for the end of mini (where the plot crosses the trailing average)
    mini['end_coord_x'] = xs[end_idx]
    mini['end_coord_y'] = ys[end_idx]

    ####### calculate rise #######
    mini['rise_const'] = (mini['peak_coord_x'] - mini['start_coord_x']) * 1000  # convert to ms
    # print(f'min_rise: {min_rise}')
    # check against min_rise and max_rise
    if min_rise and mini['rise_const'] < min_rise:
        mini['success'] = False
        mini['failure'] = 'Min rise not met'
        return mini

    if max_rise is not None and mini['rise_const'] > max_rise:
        mini['success'] = False
        mini['failure'] = 'Max rise exceeded'
        return mini

    ###### calculate 10-90 rise ######
    mini['10_90_rise'] = calculate_mini_10_90_rise(xs, ys, baseline=mini['baseline'], amp=mini['amp'], start_idx=mini['start_idx'],
                              peak_idx=mini['peak_idx'],direction=direction, sampling_rate=sampling_rate)

    ####### calculate decay ########
    mini['decay_start_idx'] = mini['peak_idx']  # peak = start of decay
    # mini['decay_end_idx'] = min(mini['peak_idx'] + decay_max_points, len(xs) + offset)
    mini['decay_end_idx'] = mini['end_idx']

    # try:
    if decay_algorithm == 'Curve fit':
        try:
            mini['decay_A'], mini['decay_const'], mini['decay_baseline'] = fit_mini_decay(
                xs=xs[peak_idx:min(peak_idx + decay_max_points, len(xs))],
                ys=ys[peak_idx:min(peak_idx + decay_max_points, len(ys))],
                sampling_rate=sampling_rate,
                end_idx=end_idx - peak_idx,  # short for compound, all available data for non compound
                amplitude=mini['amp'] * direction,
                decay_guess=decay_best_guess,
                direction=direction,
                baseline=mini['baseline'],
                prev_mini_decay=mini['prev_decay_const'],
                prev_mini_A=mini['prev_decay_A'],
                prev_mini_decay_baseline=mini['prev_decay_baseline'],
                prev_mini_t=mini['prev_t'],
                prev_mini_baseline=mini['prev_baseline'],
                prev_mini_direction=mini['prev_mini_direction']
            )
        except:
            mini['decay_A'], mini['decay_const'], mini['decay_baseline'] = fit_mini_decay(
                xs=xs[peak_idx:min(peak_idx + decay_max_points, len(xs))],
                ys=ys[peak_idx:min(peak_idx + decay_max_points, len(ys))],
                sampling_rate=sampling_rate,
                end_idx=end_idx - peak_idx,  # short for compound, all available data for non compound
                amplitude=mini['amp'] * direction,
                decay_guess=decay_best_guess,
                direction=direction,
                baseline=mini['baseline'],
            )
    elif decay_algorithm == '% amplitude':
        # mimics Mini Analysis
        mini['decay_A'] = mini['amp'] * direction
        mini['decay_baseline'] = 0
        decay_idx = np.argmax((ys[int(peak_idx): int(min(peak_idx + decay_max_points, len(ys)))] - mini[
            'baseline']) * direction < decay_p_amp * mini['amp'] * direction / 100)
        if decay_idx > 0:
            mini['decay_const'] = decay_idx / sampling_rate * 1000
        else:
            mini['failure'] = 'Decay constant could not be calculated'
            mini['success'] = False
            return mini
    elif decay_algorithm == 'None':
        mini['decay_A'] = None
        mini['decay_const'] = None
        mini['decay_baseline'] = None
        mini['decay_idx'] = None
        mini['decay_coord_x'] = None
        mini['decay_coord_y'] = None

    # except Exception as e:
    #     print(f'decay error {e}')
    #     mini['success'] = False
    #     mini['failure'] = 'decay cannot be calculated'
    #     return mini
    if decay_algorithm != 'None':
        decay_idx = int(peak_idx + mini['decay_const'] / 1000 * sampling_rate)
        mini['decay_idx'] = decay_idx + offset

        if mini['decay_const'] < min_decay:
            mini['success'] = False
            mini['failure'] = 'Min decay not met'
            return mini
        if max_decay and mini['decay_const'] > max_decay:
            mini['success'] = False
            mini['failure'] = 'Max decay exceeded'
            return mini
        # print('here')
        try:
            mini['decay_coord_x'] = xs[decay_idx]
            prev_decay_y = single_exponent_constant(
                mini['decay_const'] + (mini['t'] - mini['prev_t']) * 1000,
                mini['prev_decay_A'],
                mini['prev_decay_const'],
                mini['prev_decay_baseline']
            ) * mini['prev_mini_direction'] + mini['prev_baseline']
            mini['decay_coord_y'] = prev_decay_y + single_exponent_constant(
                mini['decay_const'],
                mini['decay_A'],
                mini['decay_const'],
                mini['decay_baseline']
            ) * direction  #### add support for compound (add back subtracted baseline)
        except:
            mini['decay_coord_y'] = single_exponent_constant(
                mini['decay_const'],
                mini['decay_A'],
                mini['decay_const'],
                mini['decay_baseline']
            ) * direction + mini['baseline']
            pass
    ####### calculate halfwidth #######
    # need to incorporate compound #
    mini['halfwidth_start_coord_y'] = mini['halfwidth_end_coord_y'] = None
    if compound and mini['compound']:
        halfwidth_start_idx, halfwidth_end_idx = find_mini_halfwidth(
            amp=mini['amp'], xs=xs[baseline_idx:end_idx], ys=ys[baseline_idx:end_idx],
            peak_idx=peak_idx - baseline_idx, baseline=mini['baseline'], direction=direction,
            prev_mini_t=mini['prev_t'], prev_mini_decay=mini['prev_decay_const'], prev_mini_A=mini['prev_decay_A'],
            prev_mini_decay_baseline=mini['prev_decay_baseline'],
            prev_mini_baseline=mini['prev_baseline'],
            prev_mini_direction=mini['prev_mini_direction']
        )
    else:
        halfwidth_start_idx, halfwidth_end_idx = find_mini_halfwidth(
            amp=mini['amp'], xs=xs[baseline_idx:end_idx], ys=ys[baseline_idx:end_idx],
            peak_idx=peak_idx - baseline_idx, baseline=mini['baseline'], direction=direction
        )
    if halfwidth_start_idx is not None and halfwidth_end_idx is None:  # decay doesn't happen long enough?
        if mini['decay_const'] is not None and extrapolate_hw:  # use decay to extrapolate 50% value of decay
            t = np.log(0.5) * -1 * mini['decay_const'] / 1000
            halfwidth_end_idx = calculate.search_index(xs[peak_idx] + t, xs[baseline_idx:], sampling_rate)

    if halfwidth_end_idx is None or halfwidth_start_idx is None:
        mini['success'] = False
        mini['failure'] = 'Halfwidth could not be calculated'
        return mini
    halfwidth_end_idx += baseline_idx
    halfwidth_start_idx += baseline_idx

    if halfwidth_end_idx >= len(xs):
        mini['success'] = False
        mini['failure'] = 'Halfwidth out of bounds'
        return mini
    mini['halfwidth'] = (xs[int(halfwidth_end_idx)] - xs[int(halfwidth_start_idx)]) * 1000

    mini['halfwidth_start_idx'] = halfwidth_start_idx + offset
    mini['halfwidth_end_idx'] = halfwidth_end_idx + offset

    mini['halfwidth_start_coord_x'] = xs[halfwidth_start_idx]
    mini['halfwidth_end_coord_x'] = xs[halfwidth_end_idx]

    if compound and mini['compound']:
        mini['halfwidth_start_coord_y'] = single_exponent_constant((xs[halfwidth_start_idx] - mini['prev_t']) * 1000,
                                                                   mini['prev_decay_A'],
                                                                   mini['prev_decay_const'],
                                                                   mini['prev_decay_baseline']
                                                                   ) * mini['prev_mini_direction'] + mini['prev_baseline'] + 0.5 * \
                                          mini['amp']
        mini['halfwidth_end_coord_y'] = single_exponent_constant((xs[halfwidth_end_idx] - mini['prev_t']) * 1000,
                                                                 mini['prev_decay_A'],
                                                                 mini['prev_decay_const'],
                                                                 mini['prev_decay_baseline']
                                                                 ) * mini['prev_mini_direction'] + mini['prev_baseline'] + 0.5 * mini[
                                            'amp']
    else:
        mini['halfwidth_start_coord_y'] = mini['halfwidth_end_coord_y'] = mini['baseline'] + 0.5 * mini['amp']

    if min_hw and mini['halfwidth'] < min_hw:
        mini['success'] = False
        mini['failure'] = 'Min halfwidth not met'
        return mini

    if max_hw is not None and mini['halfwidth'] > max_hw:
        mini['success'] = False
        mini['failure'] = 'Max halfwidth exceeded'
        return mini

    ###### calculate decay:rise ratio #####
    if decay_algorithm != 'None':
        drr = mini['decay_const'] / mini['rise_const']
        if min_drr and drr < min_drr:
            mini['success'] = False
            mini['failure'] = 'Min Decay:Rise ratio not met'
            return mini
        if max_drr is not None and drr > max_drr:
            mini['success'] = False
            mini['failure'] = 'Max Decay:Rise ratio not met'
            return mini

    return mini


def calculate_frequency(mini_df, channel):
    df = mini_df[mini_df['channel'] == channel]
    freq = (df['t'].max() - df['t'].min()) / df.shape[0]

    return freq


def single_exponent_constant(x, a, t, d):
    return a * np.exp(-(x) / t) + d


def single_exponent(x, a, t):
    return a * np.exp(-(x) / t)
