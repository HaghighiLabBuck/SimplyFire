"""
Read abf files and store as Recording class
Data format for recording data used in the SimplyFire software.

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
import os
from pyabf import abf
from simplyfire.utils import abfWriter
from simplyfire.setting import config
from math import ceil
from psutil import Process

class Recording():
    def __init__(self, filepath):
        self.filepath = filepath
        # initialize metadata
        self.channel = 0
        self.added_sweep_count = 0
        self.sweep_count = 0
        self._open_file(filepath)

    def _open_file(self, filename):
        self.filetype = os.path.splitext(filename)[1]
        self.filedir, self.filename = os.path.split(filename)

        if self.filetype == '.abf':
            self.read_abf(filename)
        elif self.filetype == '.csv':
            self.read_csv(filename)

        else:
            # insert support for other filetypes here
            pass
    def read_abf(self, filename):
        data = abf.ABF(filename)
        # sampling rate of the recording
        self.sampling_rate = data.dataRate
        # sampling rate significant digits - used to round calculations
        self.x_sigdig = len(str(self.sampling_rate)) - 1
        # interval between each x-values (inverse of sampling rate)
        self.x_interval = 1 / self.sampling_rate

        # channel metadata
        self.channel_count = data.channelCount
        self.channel_names = data.adcNames
        self.channel_units = data.adcUnits
        self.channel_labels = [""] * self.channel_count
        for c in range(self.channel_count):
            data.setSweep(0, c)
            self.channel_labels[c] = data.sweepLabelY.replace('\x00','')
        # x_value metadata
        self.x_unit = data.sweepUnitsX
        self.x_label = data.sweepLabelX  # in the form of Label (Units)

        # y_value metadata
        self.sweep_count = data.sweepCount
        self.original_sweep_count = self.sweep_count
        self.sweep_points = data.sweepPointCount

        # extract y and x values and store as 3D numpy array (channel, sweep, datapoint)
        print('Before making data matrices')
        print(Process().memory_info().rss)
        self.y_data = np.reshape(data.data, (self.channel_count, self.sweep_count, self.sweep_points))
        print('After making Y data matrix')
        print(Process().memory_info().rss)
        self.x_data = np.repeat(np.reshape(data.sweepX, (1, 1, self.sweep_points)), self.sweep_count, axis=1)
        self.x_data = np.repeat(self.x_data, self.channel_count, axis=0)
        print('After making both data matrices')
        print(Process().memory_info().rss)

    def read_csv(self, filename):
        """
        only supports single channel data
        """
        self.channel_count = 1
        self.sweep_count = 0
        self.sweep_points = 0
        self.x_unit = ['sec']
        self.y_unit = ['N/A']
        self.y_label = ['N/A']
        with open(filename, 'r') as f:
            for l in f.readlines():
                l = l.strip()
                if l[0] == '@': #header
                    header_label = l[1:].split('=')[0]
                    header_data = l[1:].split('=')[1]
                    if header_label == 'version':
                        version = header_data
                    elif header_label == 'sweep_count':
                        self.sweep_count = int(header_data)
                        self.original_sweep_count = self.sweep_count
                    elif header_label == 'sweep_points':
                        self.sweep_points = int(header_data)
                    elif header_label == 'sampling_rate':
                        self.sampling_rate = float(header_data)
                        # sampling rate significant digits - used to round calculations
                        self.x_sigdig = len(str(self.sampling_rate)) - 1
                        # interval between each x-values (inverse of sampling rate)
                        self.x_interval = 1 / self.sampling_rate
                    elif header_label == 'channel_unit':
                        self.channel_units=[header_data]
                    elif header_label == 'channel_label':
                        self.channel_labels=[header_data]
                    elif header_label == 'x_unit':
                        self.x_unit = [header_data]
                    elif header_label == 'x_label':
                        self.x_label = [header_data]
                else:
                    if self.y_data.shape[2] > 0:
                        self.y_data = np.append(self.y_data,
                                            np.reshape(np.array([float(i) for i in l.split(',')]), (1, 1, self.sweep_points)),
                                            axis=1)
                    else:
                        ys = [float(i) for i in l.split(',')]
                        if self.sweep_points == 0:
                            self.sweep_points = len(ys)
                        self.y_data = np.reshape(np.array(ys),
                                                 (1, 1, self.sweep_points))
            if self.sweep_count == 0:
                self.sweep_count = self.y_data.shape[1]
            sweepX = np.arange(self.sweep_points)/self.sampling_rate
            self.x_data = np.repeat(np.reshape(np.array(sweepX), (1, 1, self.sweep_points)),
                                    self.sweep_count,
                                    axis=1)

    def save(self, filename, channels=None, suffix=0, handle_error=False):
        if channels is None:
            channels = [i for i in range(self.channel_count)]
        if suffix > 0:
            fname = f'{filename.split(".")[0]}({suffix}).{filename.split(".")[1]}'
        else:
            fname = filename
        if os.path.exists(fname):
            if handle_error:
                self.save(filename, channels, suffix+1, handle_error)
                return
            else:
                raise FileExistsError
        filetype = os.path.splitext(fname)[1]
        if filetype == '.abf':
            self.write_abf(fname)
        elif filetype == '.csv':
            self.write_csv(fname, channels)
    def write_abf(self, filename):
        abfWriter.writeABF1(self.y_data, filename, sampleRateHz=self.sampling_rate, units=self.channel_units, labels=self.channel_labels)
        # writeABF1(self.y_data, filename, self.sampling_rate, self.channel_units)

    def write_csv(self, filename, channel=None):
        if channel is None:
            channel = self.channel
        with open(filename, 'x') as f:
            f.write(f'@version={config.version}\n')
            f.write(f'@sweep_count={self.sweep_count}\n')
            f.write(f'@sweep_points={self.sweep_points}\n')
            f.write(f'@channel_unit={self.channel_units[channel]}\n')
            f.write(f'@channel_label={self.channel_labels[channel]}\n')
            f.write(f'@sampling_rate={self.sampling_rate}\n')
            f.write(f'@x_unit={self.x_unit}\n')
            f.write(f'@x_label={self.x_label}\n')
            for s in range(self.sweep_count):
                f.write(','.join([str(i) for i in self.y_data[channel, s, :].tolist()]))
                f.write('\n')




    def set_channel(self, channel):
        self.y_label = self.channel_labels[channel]
        self.y_unit = self.channel_units[channel]

        # if index out of bounds, the above code will raise an error
        # otherwise, store the channel value
        self.channel = channel


    def replace_y_data(self, mode='continuous', channels=None, sweeps=None, new_data=None, inplace=True):
        """
        replaces y-values in specified sweeps and channels with data provided

        mode: string {'continuous', 'overlay'} defaults to 'continuous'
        channels: list of int - if None, defaults to first N channels that match the dimension of the input data
        sweeps: list of int - only used for the 'overlay' plot_mode. If None, defaults to the first N sweeps that match the dimension of the input data
        new_data: new y-values to replace. Must be a 3D float numpy array
        """
        assert len(new_data.shape) == 3, 'Matrix shape mismatch - the input data must be a 3D numpy array'
        if channels is None:
            channels = range(new_data.shape[0])

        if mode == 'continuous':
            assert new_data.shape[
                       2] % self.sweep_points == 0, f'Sweep length mismatch. Each sweep in "continuous" mode must be a multiple of {self.sweep_points} datapoints'
            if sweeps is None:
                sweeps = range(int(new_data.shape[2] / self.sweep_points))

            new_data = np.reshape(new_data, (len(channels), len(sweeps), self.sweep_points))

        elif mode == 'overlay':
            assert new_data.shape[
                       2] == self.sweep_points, f'Sweep length mismatch. Each sweep in "overlay" mode must be {self.sweep_points} datapoints'
            if sweeps is None:
                sweeps = range(new_data.shape[1])
        else:
            return None
        if inplace:
            for i, c in enumerate(channels):
                self.y_data[c, sweeps, :] = new_data[i]
            return self.y_data
        else:
            result = self.y_data.copy()
            for i, c in enumerate(channels):
                result[c, sweeps, :] = new_data[i]
            return result


    def get_y_matrix(self, mode='continuous', sweeps=None, channels=None, xlim=None):
        """
        returns a slice of the y_data
        mode: string
            'continuous', 'overlay'
        channels: list of int - if None, defaults to all channels
        sweeps: list of int - If None, defaults to all sweeps
        xlim: float tuple [left, right] - If None, defaults to all data points in each sweep
        """
        print('Before getting Y array')
        print(Process().memory_info().rss)
        if channels == None:
            channels = range(self.channel_count)
        elif type(channels) == int:
            channels = [channels]
        if sweeps == None:
            sweeps = [i for i in range(self.sweep_count)]
        elif type(sweeps) == int:
            sweeps = [sweeps]
        if len(sweeps) == 1 and len(channels) == 1:
##        if False:
            print('Using single sweep case for get_ys')
            if mode == 'continuous':
                if xlim:
                    return self.y_data[channels[0], sweeps[0],
                           max(0, int(xlim[0] / self.x_interval)):min(self.sweep_count * self.sweep_points,
                                                                        ceil(xlim[1] / self.x_interval) + 1)]
                else:
                    return_val = self.y_data[channels[0],sweeps[0]]				
                    print('After getting Y array')
                    print(Process().memory_info().rss)				
                    return return_val
            if mode == 'overlay':
                if xlim:
                    return self.y_data[channels[0], sweeps[0],
                           max(0, int(xlim[0] / self.x_interval)):min(self.sweep_count * self.sweep_points,
                                                                  ceil(xlim[1] / self.x_interval) + 1)]
                return_val = self.y_data[channels[0], sweeps[0]]
                print('After getting Y array')
                print(Process().memory_info().rss)				
                return return_val               
        if mode == 'continuous':
            if xlim:
                return np.reshape(self.y_data[channels][:, sweeps, :],
                                  (len(channels), 1, len(sweeps) * self.sweep_points))[
                       :, :, max(0, int(xlim[0] / self.x_interval)):min(self.sweep_count * self.sweep_points,
                                                                        ceil(xlim[1] / self.x_interval) + 1)]
            else:
                return np.reshape(self.y_data[channels][:, sweeps, :],
                                  (len(channels), 1, len(sweeps) * self.sweep_points))[
                       :, :, :]
        if mode == 'overlay':
            if xlim:
                return self.y_data[channels][:, sweeps,
                       max(0, int(xlim[0] / self.x_interval)):min(self.sweep_count * self.sweep_points,
                                                                  ceil(xlim[1] / self.x_interval) + 1)]
            return self.y_data[channels][:, sweeps]

    def get_x_matrix(self, mode='continuous', sweeps=None, channels=None, xlim=None):
        """
        returns a slice of the x_data
        mode: string
            'continuous', 'overlay'
        channels: list of int - if None, defaults to all channels
        sweeps: list of int - only used for the 'overlay' plot_mode. If None, defaults to all sweeps
        xlim: float tuple [left, right] - If None, defaults to all data points in each sweep
        """
        print('Before getting X array')
        print(Process().memory_info().rss)
        if sweeps is None:
            sweeps = range(self.sweep_count)
        if channels == None:
            channels = range(self.channel_count)
        if len(sweeps) == 1 and len(channels) == 1:
##        if False:
            print('Using single sweep case for get_xs')
            if mode == 'continuous':
                offset = sweeps[0] * (self.sweep_points * self.x_interval)
                x_matrix = self.x_data[channels[0], sweeps[0]] + offset
                if xlim:
                    start_idx = max(0, int(xlim[0] / self.x_interval))
                    end_idx = min(self.sweep_count * self.sweep_points, ceil(xlim[1] / self.x_interval) + 1)
                    return x_matrix[:, :, start_idx:end_idx]
                print('Returning X array')
                print(Process().memory_info().rss)
                return x_matrix
            if mode == 'overlay':
                if xlim:
                    start_idx = max(0, int(xlim[0] / self.x_interval))
                    end_idx = min(self.sweep_count * self.sweep_points, ceil(xlim[1] / self.x_interval) + 1)
                    return self.x_data[channels[0], sweeps[0], start_idx:end_idx]
                return_val = self.x_data[channels[0], sweeps[0]]
                print('Returning X array')
                print(Process().memory_info().rss)
                return return_val
        if mode == 'continuous':
            mult = np.arange(0, len(sweeps))
            mult = np.reshape(mult, (1, len(sweeps), 1))
            offset = mult * (self.sweep_points * self.x_interval)
            x_matrix = np.reshape(self.x_data[channels][:, sweeps] + offset,
                                  (len(channels), 1, len(sweeps) * self.sweep_points))
            if xlim:
                start_idx = max(0, int(xlim[0] / self.x_interval))
                end_idx = min(self.sweep_count * self.sweep_points, ceil(xlim[1] / self.x_interval) + 1)
                return x_matrix[:, :, start_idx:end_idx]
            return x_matrix
        if mode == 'overlay':
            if xlim:
                start_idx = max(0, int(xlim[0] / self.x_interval))
                end_idx = min(self.sweep_count * self.sweep_points, ceil(xlim[1] / self.x_interval) + 1)
                return self.x_data[channels][:, sweeps][:, :, start_idx, end_idx]
            return self.x_data[channels][:, sweeps]

    def get_xs(self, mode='continuous', sweep=None, channel=None, xlim=None):
        """
        returns a 1D numpy array representing the x-values in the recording.
        Use this function to get x-values for plotting
        mode: string
            continuous, concatenate, or None
        sweep: int
        channel: int if None, defaults to current channel
        xlim: float tuple - [left, right] If None, defaults to all x-values
        """
        if not channel:
            channel = self.channel
        if mode == 'continuous':
            return self.get_x_matrix(mode='continuous', channels=[channel], xlim=xlim).ravel()
        return self.get_x_matrix(mode='overlay', sweeps=[sweep], channels=[channel], xlim=xlim).ravel()

    def get_ys(self, mode='continuous', sweep=None, channel=None, xlim=None):
        """
        returns a 1D numpy array representing the y-values of the recording.
        Use this functions to get y-values for plotting
        mode: string
            'continuous', 'overlay', or None
            if 'continuous', all sweeps are represented
        sweep: int
        channel: int
            if empty, the current channel in the object is used
        xlim: float tuple - [left, right] If None, defaults to all x-values
        """
        if channel == None:
            channel = self.channel
        if mode == 'continuous':
            return self.get_y_matrix(mode='continuous', channels=[channel], xlim=xlim).ravel()
        return self.get_y_matrix(mode=mode, channels=[channel], sweeps=[sweep], xlim=xlim).ravel()

    def save_y_data(self, filename, channels=None, sweeps=None):
        """
        saves y_data of specified channels and sweeps in a temporary file

        filename: str name of the file
        channels: list of int, defaults to all channels if None
        sweeps: list of int, defaults to all sweeps if None
        """
        if not channels:
            channels = range(self.channel_count)
        if not sweeps:
            sweeps = range(self.sweep_count)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as f:
            for c in channels:
                for s in sweeps:
                    f.write(','.join([str(d) for d in self.y_data[c][s]]))
                    f.write('\n')
        return None

    def load_y_data(self, filename, channels=None, sweeps=None):
        if not channels:
            channels = range(self.channel_count)
        if not sweeps:
            sweeps = range(self.sweep_count)
        with open(filename, 'r') as f:
            for c in channels:
                for i in sweeps:
                    self.y_data[c, i] = np.fromstring(f.readline(), dtype=float, sep=',')
        return None

    def append_sweep(self, new_data, channels=None, fill=0):
        """
        appends a new sweep to the end of y_data
        new_data: numpy array - if new_data is a 3D numpy array, it assumes the dimensions match the existing y_data
                if the new_data is a 1D or 2D numpy array, missing data is filled with the value specified in fill argument
        channels: list of int - used if the dimensions of new_data does not match the y_data (axis=0 does not match)
        fill: float - if sweep data for some channels are missing, this argument is used to fill the missing data
        """

        if new_data.shape == (self.channel_count, 1, self.sweep_points):
            # the dimension matches y_data for np.append()
            self.y_data = np.append(self.y_data, new_data, axis=1)

        else:  # the dimension needs to be fixed
            temp_data = np.full((self.channel_count, 1, self.sweep_points), dtype=np.float, fill_value=fill)
            assert new_data.shape[
                       -1] == self.sweep_points, 'dimension mismatch - the sweep length does not match the existing data'
            new_data_reshape = np.reshape(new_data, (len(channels), 1, self.sweep_points))
            temp_data[channels] = new_data_reshape
            self.y_data = np.append(self.y_data, temp_data, axis=1)

        self.x_data = np.append(self.x_data, self.x_data[:, -new_data.shape[1]:, :], axis=1)
        self.sweep_count += 1
        self.added_sweep_count += 1

    def delete_last_sweep(self):
        if self.sweep_count == self.original_sweep_count:
            return None  # cannot delete original data
        self.y_data = self.y_data[:, :-1, :]
        self.x_data = self.x_data[:, :-1, :]
        self.sweep_count -= 1
        self.added_sweep_count -= 1