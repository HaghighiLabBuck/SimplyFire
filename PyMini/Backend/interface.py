# takes input from the Data Visualizers and takes appropriate action
# from PyMini import app
from PyMini import app
from tkinter import filedialog, messagebox
import tkinter as Tk

import pandas
from PyMini.DataVisualizer import data_display, log_display, trace_display, param_guide, results_display, evoked_data_display
import os
import pkg_resources
# from Layout import #, sweep_tab,
from PyMini.Layout import sweep_tab, detector_tab, graph_panel,  adjust_tab, menubar
import matplotlib as mpl
from PyMini.Backend import interpreter, analyzer2
import gc
import pandas as pd
from pandas import Series
import numpy as np
from threading import Thread

from time import time
# This module is the workhorse of the GUI
# All functions that connect inputs from the user to processes in the background should pass through here
# Any functions that require communications between different modules should be done here
#
# mini_df = pd.DataFrame(columns = [
#     # panel -- make sure this matches with the config2header dict
#     # = analyzer generates the data
#     't',  #
#     'amp',  #
#     'amp_unit',  #
#     'decay_const', #
#     'decay_unit', #
#     'decay_func', #
#     'rise_const',  #
#     'rise_unit',  #
#     'halfwidth', #
#     'halfwidth_unit', #
#     'baseline',  #
#     'baseline_unit',  #
#             #'auc',
#     't_start',  #
#     't_end',  #
#     'channel',  #
#     # plot
#     'peak_idx', #
#     'peak_coord_x',  # (x,y) #
#     'peak_coord_y',  #
#     'decay_coord_x',
#     'decay_coord_y',
#     'start_coord_x',  #
#     'start_coord_y',  #
#     'start_idx',  #
#     'end_coord_x',  #
#     'end_coord_y',  #
#     'end_idx',  #
#     'decay_fit', #
#
#     # data
#
#     'datetime'  #
# ])

global al
al = analyzer2.Analyzer()
def get_temp_num():
    global temp_num
    try:
        temp_num += 1
        return temp_num % int(app.widgets['config_undo_stack'].get())
    except:
        temp_num = 0
        return 0

def get_prev_temp_num():
    global temp_num
    try:
        return temp_num % int(app.widgets['config_undo_stack'].get())
    except:
        return None

global undo_stack
undo_stack = []

def clear_undo():
    global undo_stack
    for stack in undo_stack:
        del stack
    undo_stack = []

    # disable the undo command in the menubar
    menubar.undo_disable()

def add_undo(task):
    # enable the undo command in the menubar
    menubar.undo_enable()
    global undo_stack
    if isinstance(task, list):
        undo_stack.append(task)
    else:
        undo_stack.append([task])
    try:
        if len(undo_stack) > int(app.widgets['config_undo_stack'].get()):
            temp = undo_stack.pop(0)
            del temp
    except:
        pass
    return

def undo(e=None):
    app.pb['value'] = 0
    app.pb.update()
    if len(undo_stack) > 0:
        task_stack = undo_stack.pop()
        len_task = len(task_stack)
        for i, task in enumerate(task_stack):
            app.pb['value'] = i / len_task * 100
            app.pb.update()
            task()
            del task

        del task_stack
    app.pb['value'] = 0
    app.pb.update()

    # if the stack is empty, disable the undo command in the menubar
    if len(undo_stack) == 0:
        menubar.undo_disable()


def configure(key, value):
    globals()[key] = value

#################################
# Handling recording data
#################################

global recordings
recordings = []
def open_trace(fname, append=False):
    # trace stored in analyzer
    global recordings
    try:
        record = al.open_file(fname)
    except:
        messagebox.showerror('Read file error', 'The selected file could not be opened.')
        return None
    try:
        log_display.open_update(fname)
    except:
        return None

    clear_undo()
    if not append:
        al.clear_mini_df()
        data_display.clear()
        evoked_data_display.clear()
        # update save file directory
        if app.widgets['config_file_autodir'].get() == '1':
            mpl.rcParams['savefig.directory'] = os.path.split(fname)[0]

        # check if channel number is specified by user:
        if app.widgets['force_channel'].get() == '1':
            try:
                record.set_channel(int(app.widgets['force_channel_id'].get()))  # 0 indexing
            except (IndexError): # forced channel does not exist
                record.set_channel(0) # force to open the first channel
                pass
        else:
            record.set_channel(0)
        app.widgets['trace_info'].set(
            '{}: {}Hz : {} channel{}'.format(
                record.filename,
                record.sampling_rate,
                record.channel_count,
                's' if record.channel_count > 1 else ""
            )
        )
        trace_display.ax.autoscale(enable=True, axis='both', tight=True)
        sweep_tab.populate_list(record.sweep_count)
        while len(recordings) > 0:
            r = recordings.pop()
            del r
    recordings.append(record)
    if not append:
        app.compare_tab.reset_trace_list(fname)
    else:
        app.compare_tab.increase_trace_list(fname)
        try:
            record.set_channel(recordings[0].channel)
        except:
            _change_channel(0, save_undo=False) # cannot open channel

    if app.widgets['trace_mode'].get() == 'continuous':
        plot_continuous(record)
    elif app.widgets['trace_mode'].get() == 'overlay':
        plot_overlay(0, append=False)
    else:
        plot_overlay(len(recordings)-1, fix_x=append, append=append)

    param_guide.update()
    if not append:
        if app.widgets['force_axis_limit'].get() == '1':
            trace_display.set_axis_limit('x', (app.widgets['min_x'].get(), app.widgets['max_x'].get()))
            trace_display.set_axis_limit('y', (app.widgets['min_y'].get(), app.widgets['max_y'].get()))

        graph_panel.y_scrollbar.config(state='normal')
        graph_panel.x_scrollbar.config(state='normal')

        trace_display.update_x_scrollbar()
        trace_display.update_y_scrollbar()

        app.widgets['channel_option'].clear_options()
        for i in range(record.channel_count):
            app.widgets['channel_option'].add_command(
                label='{}: {}'.format(i, record.channel_labels[i]),
                command=lambda c=i:_change_channel(c)
            )
    # starting channel was set earlier in the code
        app.widgets['channel_option'].set('{}: {}'.format(record.channel, record.y_label))

    app.pb['value'] = 0
    app.pb.update()

    # trace_display.refresh()
def _change_channel(num, save_undo=True):
    global recordings

    if save_undo and num != recordings[0].channel:
        add_undo(lambda n= recordings[0].channel, s=False:_change_channel(n, s))

    try:
        for r in recordings:
            r.set_channel(num)
        log_display.log('@ graph_viewer: switch to channel {}'.format(num))
    except:
        for r in recordings:
            r.set_channel(0)
        log_display.log('@ graph_viewer: unable to switch to channel {}. Reverting to channel 0'.format(num))
    app.widgets['channel_option'].set('{}: {}'.format(recordings[0].channel, recordings[0].y_label)) #0 indexing for channel num
    if app.widgets['trace_mode'].get() == 'continuous':
        plot_continuous(recordings[0], fix_x=True, draw=False)
    elif app.widgets['trace_mode'].get() == 'compare':
        for i,r in enumerate(recordings):
            plot_overlay(i, fix_x=True, draw=False, append=(i!=0))
    else:
        plot_overlay(0, fix_x=True, draw=False)
        # for i, var in enumerate(sweep_tab.sweep_vars):
        #     if not var.get():
        #         trace_display.hide_sweep(i)
    trace_display.canvas.draw()
    data_display.clear()

    populate_data_display()
    update_event_marker()

    param_guide.update()

    app.pb['value'] = 0
    app.pb.update()


def plot_continuous(recording, fix_axis=False, draw=True, fix_x=False, fix_y=False):
    global idx_offset
    idx_offset = 0
    if fix_axis:
        xlim = trace_display.get_axis_limits('x')
        ylim = trace_display.get_axis_limits('y')
    if fix_x:
        xlim = trace_display.get_axis_limits('x')
    if fix_y:
        ylim=trace_display.get_axis_limits('y')
    trace_display.clear()
    trace_display.plot_trace(recording.get_xs(mode='continuous'),
                             recording.get_ys(mode='continuous'),
                             draw=draw,
                             relim=True)
    trace_display.ax.set_xlabel(recording.x_label, fontsize=int(float(app.widgets['font_size'].get())))
    trace_display.ax.set_ylabel(recording.y_label, fontsize=int(float(app.widgets['font_size'].get())))
    trace_display.ax.tick_params(axis='y', which='major', labelsize=int(float(app.widgets['font_size'].get())))
    trace_display.ax.tick_params(axis='x', which='major', labelsize=int(float(app.widgets['font_size'].get())))

    if fix_axis:
        trace_display.set_axis_limit('x', xlim)
        trace_display.set_axis_limit('y', ylim)
    if fix_x:
        trace_display.set_axis_limit('x', xlim)
    if fix_y:
        trace_display.set_axis_limit('y', ylim)

    # if len(al.mini_df.index)>0:
    #     xs = al.mini_df.index.where(al.mini_df['channel'] == al.recording.channel)
    #     xs = xs.dropna()
    #
    #     data_display.append(al.mini_df.loc[xs])

    update_event_marker()

def delete_last_sweep():
    recordings[0].delete_last_sweep()
    sweep_tab.delete_last_sweep()
    trace_display.delete_last_sweep()

######################################
# Handling GUI placements
######################################

global trace_mode
trace_mode = 'continuous'

def config_cp_tab(tab_name, **kwargs):
    """
    use this function to display a hidden tab in the control panel

    Args:
        tab_name: str tab name must be one of the keys in app.cp_tab_details

    Returns:
        None
    """
    # check if current tab would be replaced by the new tab being displayed
    try:
        if kwargs['state'] == 'normal':
            idx = app.cp_notebook.index('current')
            if idx in [app.cp_tab_details[tab]['index'] for tab in app.cp_tab_details[tab_name]['partner']]:
                idx = app.cp_tab_details[tab_name]['index']
            for partner in app.cp_tab_details[tab_name]['partner']:
                app.cp_notebook.tab(app.cp_tab_details[partner]['tab'], state='hidden')
            app.cp_notebook.tab(app.cp_tab_details[tab_name]['tab'], state='normal')
            app.cp_notebook.select(idx)
            return
    except Exception as e:
        print(f'config_cp_tab error {e}')
        pass
    else:
        app.cp_notebook.tab(app.cp_tab_details[tab_name]['tab'], **kwargs)

def config_data_tab(tab_name, **kwargs):
    """
    use this function to enable a disabled tab
    """
    try:
        if kwargs['state'] == 'normal':
            for key, tab in app.data_tab_details.items():
                app.data_notebook.tab(tab['tab'], state='hidden')
            pass
    except:
        pass
    app.data_notebook.tab(app.data_tab_details[tab_name]['tab'], **kwargs)
    app.data_notebook.select(app.data_tab_details[tab_name]['index'])
    app.root.update()
    app.data_tab_details[tab_name]['module'].fit_columns()

    pass


######################################
# Handling mini data
######################################

def save_events(filename, mode='w', suffix_num=0, handle_error=True):
    if suffix_num > 0:
        fname = f'{os.path.splitext(filename)[0]}({suffix_num}){os.path.splitext(filename)[1]}'
    else:
        fname = filename
    try:
        with open(fname, mode) as f:
            f.write(f'@filename:{recordings[0].filename}\n')
            f.write(f'@version:{app.config.version}\n')
            f.write(al.mini_df.to_csv(index=False))
    except (FileExistsError):
        if handle_error:
            save_events(filename, mode, suffix_num+1)
        pass



def save_events_dialogue(e=None):
    if not app.event_filename:
        save_events_as_dialogue()
        return None
    try:
        if len(al.mini_df) > 0:
            save_events(app.event_filename, mode='w')
        else:
            messagebox.showerror('Error', 'No minis to save')
    except:
        messagebox.showerror('Write error', 'Could not write data to selected filename.')
    return None


def save_events_as_dialogue(e=None):
    if len(al.mini_df) > 0:
        try:
            initialfilename = os.path.splitext(recordings[0].filename)[0] + '.event'
        except:
            initialfilename = app.event_filename
        filename=filedialog.asksaveasfilename(filetypes=[('event files', '*.event'), ('All files', '*.*')], defaultextension='.event',
                                              initialfile=initialfilename)
        try:
            # al.mini_df.to_csv(filename, index=True)
            # app.event_filename = filename
            # print(filename)
            save_events(filename, mode='w')
        except:
            messagebox.showerror('Write error', 'Could not write data to selected filename.')
    else:
        messagebox.showerror('Error', 'No minis to save')
    return

def open_events(filename, log=True, undo=True, append=False):
    if len(recordings) == 0:
        # recording file not open yet
        messagebox.showerror('Open error', 'Please open a recording file first.')
    if undo and int(app.widgets['config_undo_stack'].get()) > 0:
        temp_filename = os.path.join(pkg_resources.resource_filename('PyMini', 'temp/'), 'temp_{}.temp'.format(get_temp_num()))
        save_events(temp_filename)
        add_undo([
            data_display.clear,
            lambda f=temp_filename, l=False, u=False:open_events(f, l, u),
            lambda msg='Undo open event file':log_display.log(msg),
            update_event_marker,
        ])
    filetype = os.path.splitext(filename)[1]
    if filetype == ".csv" or filetype == '.temp' or filetype =='.event':
        df = open_events_csv(filename)
    elif filetype == ".minipy":
        df = open_events_mini(filename)
    df = df.replace({np.nan: None})
    df['compound'] = df['compound'].replace([0.0, 1.0], [False, True])
    if not append:
        al.mini_df = df
        app.event_filename = filename
        data_display.clear()
        populate_data_display()
    else:
        al.mini_df = al.mini_df.append(df)
        data_display.append(df[df.channel == recordings[0].channel])
    update_event_marker()
    if log:
        log_display.open_update('mini data: {}'.format(filename))
    app.pb['value']=0
    app.pb.update()

def open_events_csv(filename):
    df = pd.read_csv(filename, comment='@')
    return df

def open_events_mini(filename):
    """
    open mini files from Minipy (ancestral version)
    """
    channel = 0
    minis = []
    header_idx = {}
    with open(filename, 'r') as f:
        lines = f.readlines()
        for l in lines:
            info = l.strip().split(',')
            if info[0] == "@Trace":
                recording_filename = info[1]
            elif info[0] == '@Channel':
                channel = int(info[1])
            elif info[0] == '@Header':
                for i,h in enumerate(info):
                    header_idx[h] = i
                xs = recordings[0].get_xs(mode='continuous', channel=channel)
                ys= recordings[0].get_ys(mode='continuous', channel=channel)
            elif info[0] == '@Data':
                mini = {
                    't':float(info[header_idx['x']]),
                    'peak_coord_x':float(info[header_idx['x']]),
                    'peak_coord_y':float(info[header_idx['y']]),
                    'amp':float(info[header_idx['Vmax']])*float(info[header_idx['direction']]),
                    'baseline':float(info[header_idx['baseline']]),
                    'compound': False,
                    'decay_A':float(info[header_idx['Vmax']]),
                    'decay_const':float(info[header_idx['tau']])*1000,
                    'decay_baseline':0,
                    'decay_coord_x':float(info[header_idx['tau_x']]),
                    'decay_coord_y':float(info[header_idx['tau_y']]),
                    'decay_max_points':int(float(app.widgets['detector_core_decay_max_interval'].get())/1000*recordings[0].sampling_rate),
                    'failure':None,
                    'lag':int(info[header_idx['lag']]),
                    'rise_const':float(info[header_idx['rise_time']])*1000,
                    'start_coord_x':float(info[header_idx['left_x']]),
                    'start_coord_y':float(info[header_idx['left_y']]),
                    'amp_unit':recordings[0].channel_units[channel],
                    'baseline_unit':recordings[0].channel_units[channel],
                    'decay_unit':'ms',
                    'halfwidth_unit': 'ms',
                    'rise_unit':'ms',
                    'channel':channel,
                    'delta_x':0,
                    'direction':int(info[header_idx['direction']]),
                    'end_coord_x':float(info[header_idx['right_x']]),
                    'end_coord_y':float(info[header_idx['right_y']]),
                    'max_amp':np.inf,
                    'min_amp':0.0,
                    'max_rise': np.inf,
                    'min_rise': 0.0,
                    'max_decay': np.inf,
                    'min_decay': 0.0,
                    'max_hw': np.inf,
                    'min_hw': 0.0,
                    'max_s2n':np.inf,
                    'min_s2n':0.0,
                    'stdev_unit':recordings[0].channel_units[channel],
                    'success':True,
                }
                pass
                mini['start_idx'] = int(analyzer2.search_index(mini['start_coord_x'], xs, rate=recordings[0].sampling_rate))
                mini['baseline_idx'] = mini['start_idx']
                mini['base_idx_L'] = mini['start_idx'] - mini['lag']
                mini['base_idx_R'] = mini['start_idx']
                mini['decay_idx'] = int(analyzer2.search_index(mini['start_coord_x']+mini['decay_const'], xs, rate=recordings[0].sampling_rate))
                mini['peak_idx'] = int(analyzer2.search_index(mini['peak_coord_x'], xs, rate=recordings[0].sampling_rate))
                mini['decay_start_idx'] = mini['peak_idx']
                mini['end_idx'] = analyzer2.search_index(mini['end_coord_x'], xs, rate=recordings[0].sampling_rate)
                mini['stdev'] = np.std(ys[mini['base_idx_L']:mini['base_idx_R']])

                #try finding halfwidth
                hw_start_idx,hw_end_idx = al.find_mini_halfwidth(amp=mini['amp'],
                                                                 xs=xs[mini['baseline_idx']:mini['end_idx']],
                                                                 ys=ys[mini['baseline_idx']:mini['end_idx']],
                                                                 peak_idx=mini['peak_idx'] - mini['baseline_idx'],
                                                                 baseline=mini['baseline'],
                                                                 direction=mini['direction'])
                if hw_start_idx is not None and hw_end_idx is None:
                    if app.widgets['detector_core_extrapolate_hw'].get():
                        t = np.log(0.5)*(-1)*mini['decay_const']/1000
                        hw_end_idx = analyzer2.search_index(xs[mini['peak_idx']]+t,xs[mini['baseline_idx']:], recordings[0].sampling_rate)
                if hw_start_idx is None or hw_end_idx is None:
                    mini['halfwidth'] = 0 # could not be calculated
                else:
                    mini['halfwidth_start_idx'] = hw_start_idx + mini['baseline_idx']
                    mini['halfwidth_end_idx'] = hw_end_idx + mini['baseline_idx']
                    mini['halfwidth'] = (xs[int(mini['halfwidth_end_idx'])] - xs[int(mini['halfwidth_start_idx'])])*1000
                    mini['halfwidth_start_coord_x'] = xs[mini['halfwidth_start_idx']]
                    mini['halfwidth_end_coord_x'] = xs[mini['halfwidth_end_idx']]
                    mini['halfwidth_start_coord_y'] = mini['halfwidth_end_coord_y'] = mini['baseline']+0.5*mini['amp']


                minis.append(mini)
        df = pd.DataFrame.from_dict(minis)
        return df

def populate_data_display():
    try:
        xs = al.mini_df.index.where(al.mini_df['channel'] == recordings[0].channel)
        xs = xs.dropna()
        data_display.set(al.mini_df.loc[xs])
    except:
        pass

#######################################
# Mini Analysis
#######################################

def pick_event_manual(x):
    try:
        param_guide.configure_buttons(state='disabled')
    except:
        pass
    data_display.unselect()

    xlim=trace_display.ax.get_xlim()
    xlim = (min(xlim), max(xlim))
    ylim=trace_display.ax.get_ylim()
    ylim = (min(ylim), max(ylim))

    #convert % x-axis to points search using sampling rate?
    params = detector_tab.extract_mini_parameters()
    r = (xlim[1]-xlim[0])*float(params['manual_radius'])/100
    xs = trace_display.ax.lines[0].get_xdata()
    ys = trace_display.ax.lines[0].get_ydata()

    guide = False
    if app.widgets['window_param_guide'].get() == '1':
        guide = True
        param_guide.clear()

    mini = al.find_mini_manual(xlim=(max(x-r, xlim[0]), min(x+r,xlim[1])), xs=xs, ys=ys, x_sigdig=recordings[0].x_sigdig,
                               sampling_rate=recordings[0].sampling_rate, channel=recordings[0].channel,
                               reference_df=True, y_unit=recordings[0].y_unit,
                               x_unit=recordings[0].x_unit, **params)
    if guide:
        # param_guide.report(xs, ys, mini)
        param_guide.report(xs, ys, mini)
    if mini['success']:
        data_display.add({key: value for key,value in mini.items() if key in data_display.mini_header2config})
        update_event_marker()
        if int(app.widgets['config_undo_stack'].get()) > 0:
            add_undo([
                lambda iid=[mini['t']], u=False:delete_event(iid, undo=u),
                lambda msg='Undo manual mini detection at {}'.format(x):detector_tab.log(msg)
            ])
    if detector_tab.changed:
        log_display.search_update('Manual')
        log_display.param_update(detector_tab.changes)
        detector_tab.changes = {}
        detector_tab.changed = False

def interrupt_analyzer():
    al.stop = True

def interrupt(process=''):
    if process == 'find_mini' or process == 'Find all' or process == 'Find in window':
        al.stop = True
    pass

def find_mini_in_range(xlim=None, ylim=None):
    try:
        param_guide.configure_buttons(state='disabled')
    except:
        pass
    app.pb['value'] = 0
    app.pb.update()

    t0 = time()
    data_display.unselect()
    t0=time()
    try:
        xs = trace_display.ax.lines[0].get_xdata()
        ys = trace_display.ax.lines[0].get_ydata()
    except:
        app.pb['value'] = 0
        app.pb.update()
        return
    t0=time()
    # temp_filename = os.path.join(pkg_resources.resource_filename('PyMini', 'temp/'), 'temp_{}.temp'.format(get_temp_num()))
    # save_events(temp_filename)
    # add_undo([
    #     lambda f=temp_filename: al.load_minis_from_file(f),
    #     restore_events,
    #     lambda msg='Undo auto mini detection in range: {} - {}'.format(xlim[0], xlim[1]): detector_tab.log(msg)
    # ])
    params = detector_tab.extract_mini_parameters()

    df = al.find_mini_auto(xlim=xlim, xs=xs, ys=ys, x_sigdig=recordings[0].x_sigdig,
                               sampling_rate=recordings[0].sampling_rate, channel=recordings[0].channel,
                      reference_df=True, y_unit=recordings[0].y_unit,
                               x_unit=recordings[0].x_unit, progress_bar=app.pb, **params)
    if df.shape[0]>0:
        if int(app.widgets['config_undo_stack'].get()) > 0:
            add_undo([
                lambda iid=df['t'].values, u=False: delete_event(iid, undo=u),
                lambda msg='Undo mini search': detector_tab.log(msg)
            ])
        update_event_marker()
        trace_display.canvas.draw()
        data_display.append(df)

    if detector_tab.changed:
        log_display.search_update('Auto')
        log_display.param_update(detector_tab.changes)
        detector_tab.changes = {}
        detector_tab.changed = False
    app.pb['value'] = 0
    app.pb.update()

def filter_mini(xlim=None):
    app.pb['value'] = 1
    if int(app.widgets['config_undo_stack'].get()) > 0:
        temp_filename = os.path.join(pkg_resources.resource_filename('PyMini', 'temp/'), 'temp_{}.temp'.format(get_temp_num()))
        save_events(temp_filename)
        add_undo([
            data_display.clear,
            lambda f=temp_filename, l=False, u=False:open_events(f, l, u),
            lambda msg='Undo mini filtering':log_display.log(msg),
            update_event_marker,
        ])
    app.pb.update()
    params = detector_tab.extract_mini_parameters()
    app.pb['value']=20
    app.pb.update()
    try:
        new_df = al.filter_mini(mini_df=None, xlim=xlim, **params)
    except:
        pass
    al.mini_df = new_df
    app.pb['value']=40
    app.pb.update()
    data_display.clear()
    app.pb['value']=60
    app.pb.update()
    populate_data_display()
    app.pb['value']=80
    app.pb.update()
    update_event_marker()
    app.pb['value']=100
    app.pb['value']=0
    app.pb.update()

def select_single_mini(iid):
    data = al.mini_df[al.mini_df.t == float(iid)].squeeze().to_dict()
    if app.widgets['window_param_guide'].get() == '1':
        param_guide.report(trace_display.ax.lines[0].get_xdata(), trace_display.ax.lines[0].get_ydata(), data, clear_plot=True)

def select_left(e=None):
    if app.widgets['analysis_mode'].get()!= 'mini':
        return None
    xlim=app.trace_display.ax.get_xlim()
    if len(recordings)==0:
        return None
    if al.mini_df.shape[0]==0:
        return None
    df = al.mini_df[(al.mini_df.t<xlim[1])&(al.mini_df.t>xlim[0])&(al.mini_df.channel==recordings[0].channel)]
    if df.shape[0]>0:
        app.data_display.table.selection_set(str(df.iloc[0]['t']))
    focus()
# def select_in_data_display(iid):
#     print('selecting one: ')
#     data_display.select_one(iid)
#     print('selected one!')
#     data_display.table.update()
#     if len(data_display.selected)<1:
#         print('select again')
#         data_display.select_one(iid)

def reanalyze(data, accept_all=False):
    peak_idx = data['peak_idx']
    if al.mini_df.shape[0]>0:
        if al.mini_df['t'].isin([data['t']]).any():
            delete_event([data['t']], undo=False)

    params = detector_tab.extract_mini_parameters()
    if accept_all:
        params['min_amp'] = 0.0
        params['max_amp'] = np.inf
        params['min_decay'] = 0.0
        params['max_decay'] = np.inf
        params['min_hw'] = 0.0
        params['max_hw'] = np.inf
        params['min_rise'] = 0.0
        params['max_rise'] = np.inf
        params['min_drr'] = 0.0
        params['max_drr'] = np.inf
        params['min_s2n'] = 0.0
        params['max_s2n'] = np.inf
    xs = trace_display.ax.lines[0].get_xdata()
    ys = trace_display.ax.lines[0].get_ydata()

    guide = False
    if app.widgets['window_param_guide'].get() == '1':
        guide = True
        param_guide.clear()

    mini = al.analyze_candidate_mini(xs=xs, ys=ys, peak_idx=peak_idx, x_sigdig=recordings[0].x_sigdig,
                               sampling_rate=recordings[0].sampling_rate, channel=recordings[0].channel,
                               reference_df=True, y_unit=recordings[0].y_unit,
                               x_unit=recordings[0].x_unit,
                               **params)
    if guide:
        # param_guide.report(xs, ys, mini)
        param_guide.report(xs, ys, mini)
    if mini['success']:
        al.mini_df = al.mini_df.append(Series(mini), ignore_index=True, sort=False)
        al.mini_df = al.mini_df.sort_values(by='t')

        data_display.add({key: value for key,value in mini.items() if key in data_display.mini_header2config})
        update_event_marker()
        if int(app.widgets['config_undo_stack'].get()) > 0:
            if data['success']:
                add_undo([
                    lambda iid=[mini['t']], u=False:delete_event(iid, undo=u),
                    lambda data=data: add_event(data),
                    lambda msg='Undo reanalyze mini detection at {}'.format(data['t']):detector_tab.log(msg)
                ])
            else:
                add_undo([
                    lambda iid=[mini['t']], u=False: delete_event(iid, undo=u),
                    lambda msg='Undo reanalyze mini detection at {}'.format(data['t']): detector_tab.log(msg)
                ])
    if detector_tab.changed:
        log_display.search_update('Manual')
        log_display.param_update(detector_tab.changes)
        detector_tab.changes = {}
        detector_tab.changed = False


def add_event(data):
    # populate this and replace with repeated calls in interpreter
    # also include add to data display after removing calls
    data_display.add({key:value for key, value in data.items() if key in data_display.mini_header2config})
    al.mini_df = al.mini_df.append(pd.Series(data, name=data['t']), ignore_index=False, verify_integrity=True, sort=True)

def report_to_param_guide(xs, ys, data, clear=False):
    if clear:
        param_guide.clear()
    if data['failure'] is not None:
        param_guide.msg_label.insert(data['failure'] + '\n')
    try:
        start = int(min(max(data['start_idx'] - data['lag'] - data['delta_x'], 0), data['xlim_idx'][0]))
        if data['compound']:
            start = min(start, int(data['prev_peak_idx']))
        end = int(max(min(data['peak_idx'] + data['decay_max_points'], len(xs)), data['xlim_idx'][1]))
        param_guide.plot_recording(
            xs[start:end],
            ys[start:end],
            xlim=(xs[int(max(data['start_idx'] - data['lag'], 0))],
                  xs[int(min(data['peak_idx'] + data['decay_max_points'], len(xs)-1))])
        )
        param_guide.plot_start(data['start_coord_x'], data['start_coord_y'])
    except:  # start not found
        pass
    # try:
    #     param_guide.plot_search(xs[data['xlim_idx'][0]:data['xlim_idx'][1]],
    #                         ys[data['xlim_idx'][0]:data['xlim_idx'][1]], )
    # except:
    #     pass

    try:
        param_guide.msg_label.insert(f"Peak: {data['peak_coord_x']:.3f},{data['peak_coord_y']:.3f}\n")
        param_guide.plot_peak(data['peak_coord_x'], data['peak_coord_y'])
        param_guide.plot_amplitude((data['peak_coord_x'], data['peak_coord_y']), data['baseline'])
    except: # peak not found
        pass

    try:
        if data['base_idx'] is not None and not data['compound']:
            param_guide.plot_base_range(
                xs[int(data['base_idx'][0]):int(data['base_idx'][1])],
                ys[int(data['base_idx'][0]):int(data['base_idx'][1])]
            )
    except:
        pass
    try:
        param_guide.msg_label.insert('Baseline: {:.3f} {}\n'.format(data['baseline'], data['baseline_unit']))
        param_guide.msg_label.insert('Amplitude: {:.3f} {}\n'.format(data['amp'], data['amp_unit']))
        param_guide.msg_label.insert('Rise: {:.3f} {}\n'.format(data['rise_const'], data['rise_unit']))
    except:
        pass
    try:
        if not data['compound']:
            param_guide.plot_base_simple(xs[int(data['start_idx'])], xs[end], data['baseline'])
        else:
            param_guide.plot_base_extrapolate(
                xs=xs[int(data['prev_peak_idx']):end],
                A=data['prev_decay_A'],
                decay=data['prev_decay_const']/1000,
                baseline=data['prev_baseline'],
                direction=data['direction']
            )
            pass
    except:
        pass
    try:
        param_guide.msg_label.insert('Decay: {:.3f} {}\n'.format(data['decay_const'], data['decay_unit']))
        param_guide.msg_label.insert(f'Decay:rise ratio: {data["decay_const"]/data["rise_const"]}\n')

        param_guide.plot_decay_fit(xs[int(data['peak_idx']):end],
                                   data['decay_A'],
                                   data['decay_const']/1000,
                                   data['baseline'],
                                   data['direction'])
        param_guide.plot_decay_point(data['decay_coord_x'], data['decay_coord_y'])
    except:
        pass
    try:
        param_guide.plot_halfwidth((data['halfwidth_start_coord_x'], data['halfwidth_start_coord_y']),
                                   (data['halfwidth_end_coord_x'], data['halfwidth_end_coord_y']))
        param_guide.msg_label.insert(f'Halfwidth: {data["halfwidth"]} {data["halfwidth_unit"]}\n')
    except:
        pass
    param_guide.show_legend()
    param_guide.canvas.draw()


def get_column(colname, t = None):
    global recordings
    if len(recordings) == 0:
        return None
    if len(al.mini_df) == 0:
        return None
    if t:
        try:
            return list(al.mini_df[al.mini_df['t'].isin(t)][colname])
        except:
            return al.mini_df[al.mini_df.t.isin(t)][colname]
    else:
        xs = al.mini_df.index.where(al.mini_df['channel'] == recordings[0].channel)
        xs = xs.dropna()
        return list(al.mini_df.loc[xs][colname])


def toggle_marker_display(type):
    if app.widgets[type].get():
        getattr(trace_display, 'plot_{}'.format(type[5:]))(get_column("{}_coord_x".format(type[5:])),
                                                           get_column('{}_coord_y'.format(type[5:])))
        trace_display.canvas.draw()
    else:
        trace_display.clear_markers(type[5:])

def highlight_selected_mini(selection):
    if len(selection)>0:
        selection = [float(i) for i in selection]
        trace_display.plot_highlight(get_column('peak_coord_x', selection), get_column('peak_coord_y', selection))
        # focus display on the selected events:
        if len(selection) == 1:
            trace_display.center_plot_on(get_column('peak_coord_x', selection), get_column('peak_coord_y', selection))
        else:
            xs = get_column('peak_coord_x', selection)
            ys = get_column('peak_coord_y', selection)
            trace_display.center_plot_area(min(xs), max(xs), min(ys), max(ys))
    else:
        trace_display.clear_markers('highlight')
    trace_display.canvas.draw()

def highlight_events_in_range(xlim=None, ylim=None):
    # called when right click drag on plot surrounding peak event markers
    if xlim and xlim[0] > xlim[1]:
        xlim = (xlim[1], xlim[0])
    if ylim and ylim[0] > ylim[1]:
        ylim = (ylim[1], ylim[0])
    if al.mini_df.shape[0] == 0:
        return None
    mini_df = al.mini_df[al.mini_df['channel'] == recordings[0].channel]
    if xlim:
        mini_df = mini_df[al.mini_df['t'] > xlim[0]]
        mini_df = mini_df[mini_df['t'] < xlim[1]]
    if ylim:
        mini_df = mini_df[mini_df['peak_coord_y'] > ylim[0]]
        mini_df = mini_df[mini_df['peak_coord_y'] < ylim[1]]
    data_display.table.selection_set([str(x) for x in mini_df['t']])


def update_event_marker():
    global recordings
    if len(recordings)==0:
        return None
    if app.widgets['show_peak'].get():
        trace_display.plot_peak(get_column('peak_coord_x'), get_column('peak_coord_y'))
    if app.widgets['show_start'].get():
        trace_display.plot_start(get_column('start_coord_x'), get_column('start_coord_y'))
    if app.widgets['show_decay'].get():
        try:
            trace_display.plot_decay(get_column('decay_coord_x'), get_column('decay_coord_y'))
        except:
            pass
    trace_display.canvas.draw()

def delete_event(selection, undo=True):
    if al.mini_df.shape[0]==0:
        return None
    if len(selection)>0:
        selection = [float(i) for i in selection]
        if int(app.widgets['config_undo_stack'].get()) > 0 and undo:
            ########### Save temp file ##############
            temp_filename = os.path.join(pkg_resources.resource_filename('PyMini', 'temp/'),
                                         'temp_{}.temp'.format(get_temp_num()))
            al.mini_df[(al.mini_df['t'].isin(selection)) & (al.mini_df['channel'] == recordings[0].channel)].to_csv(
                temp_filename)
            add_undo([
                lambda f=temp_filename: open_events(temp_filename, log=False, undo=False, append=True),
                lambda f=temp_filename: os.remove(f)
            ])
        al.mini_df = al.mini_df[(~al.mini_df['t'].isin(selection)) | (al.mini_df['channel'] != recordings[0].channel)]
        data_display.delete(selection)
        update_event_marker() ##### maybe make this separate
    if app.widgets['window_param_guide'].get():
        param_guide.clear()

def delete_events_in_range(xlim, undo=True):
    if al.mini_df.shape[0] == 0:
        return None
    selection=al.mini_df[(al.mini_df['t']>xlim[0]) &
               (al.mini_df['t']<xlim[1]) &
               (al.mini_df['channel'] == recordings[0].channel)].t.values
    delete_event(selection, undo=undo)
def delete_all_events(undo=True):
    if al.mini_df.shape[0] == 0:
        return None
    if int(app.widgets['config_undo_stack'].get()) > 0 and undo:
    ########## Save temp file ##############
        temp_filename = os.path.join(pkg_resources.resource_filename('PyMini', 'temp/'),
                                     'temp_{}.temp'.format(get_temp_num()))
        al.mini_df[al.mini_df['channel'] == recordings[0].channel].to_csv(temp_filename)
        add_undo([
            lambda f=temp_filename, l=False, u=False, a=True: open_events(filename=f, log=l, undo=u, append=a),
            lambda f=temp_filename:os.remove(f)
        ])
    try:
        al.mini_df = al.mini_df[al.mini_df['channel']!=recordings[0].channel]
        data_display.clear()
        update_event_marker()
    except:
        pass



#######################################
# Sweeps
#######################################

def plot_overlay(idx, fix_axis=False, fix_x=False, draw=False, append=False, sweeps=None):
    recording = recordings[idx]
    global idx_offset
    if fix_axis:
        xlim = trace_display.get_axis_limits('x')
        ylim = trace_display.get_axis_limits('y')
    if fix_x:
        xlim = trace_display.get_axis_limits('x')
    if not append:
        trace_display.clear()
        # data_display.clear()
        trace_display.ax.set_xlabel(recording.x_label, fontsize=int(float(app.widgets['font_size'].get())))
        trace_display.ax.set_ylabel(recording.y_label, fontsize=int(float(app.widgets['font_size'].get())))
        trace_display.ax.tick_params(axis='y', which='major', labelsize=int(float(app.widgets['font_size'].get())))
        trace_display.ax.tick_params(axis='x', which='major', labelsize=int(float(app.widgets['font_size'].get())))
        idx_offset = 0
    if app.widgets['trace_mode'].get() == 'compare':
        color = app.compare_tab.get_color(idx)
    else:
        color = app.widgets['style_trace_line_color'].get()
    for i in range(recording.sweep_count):
        app.pb['value'] = (i+1)/recording.sweep_count*100
        app.pb.update()
        trace_display.plot_trace(recording.get_xs(mode='overlay', sweep=i),
                                 recording.get_ys(mode='overlay', sweep=i),
                                 draw=False,
                                 relim=False,
                                 idx=i + idx_offset,
                                 color=color)
    trace_display.show_all_plot(update_default=True)
    if app.widgets['trace_mode'].get() == 'overlay':
        sweeps = [i for i,v in enumerate(app.sweep_tab.sweep_vars) if v.get()]
    elif app.widgets['trace_mode'].get() == 'compare':
        sweeps = app.compare_tab.get_sweep_list(idx)
    if sweeps:
        for i in range(recording.sweep_count):
            trace_display.hide_sweep(i+idx_offset)
        for i in sweeps:
            trace_display.show_sweep(i+idx_offset)
    idx_offset += recording.sweep_count
    if fix_axis:
        trace_display.set_axis_limit('x', xlim)
        trace_display.set_axis_limit('y', ylim)
    if fix_x:
        trace_display.set_axis_limit('x', xlim)
    if draw:
        trace_display.canvas.draw()

    app.pb['value'] = 0
    app.pb.update()

def toggle_sweep(idx, v, draw=True):
    if v == 1:
        # trace_display.plot_trace(al.recording.get_xs(mode='overlay', sweep=idx),
        #                          al.recording.get_ys(mode='overlay', sweep=idx),
        #                          draw=draw,
        #                          relim=False,
        #                          idx=idx)
        trace_display.show_sweep(idx, draw)
    else:
        trace_display.hide_sweep(idx, draw)

def select_trace_from_plot(x, y):
    if len(recordings) == 0:
        return None
    #called by trace_display during mouse click near trace
    min_d = np.inf
    pick = None
    offset = float(app.widgets['style_trace_pick_offset_percent'].get())
    xlim = trace_display.ax.get_xlim()
    radius = abs(xlim[1] - xlim[0]) * offset/100
    ylim = trace_display.ax.get_ylim()
    x2y = (xlim[1] - xlim[0])/(ylim[1] - ylim[0])
    for i, var in enumerate(sweep_tab.sweep_vars):
        if var.get():
            line = trace_display.get_sweep(i)
            d, idx, _ = analyzer2.point_line_min_distance((x, y), xs=line.get_xdata(), ys=line.get_ydata(), sampling_rate=recordings[0].sampling_rate, radius=radius,
                                             xy_ratio=x2y)
            if d and d < min_d:
                min_d = d
                pick = i
    if pick is None:
        trace_display.remove_highlight_sweep(draw=True)
    trace_display.toggle_sweep_highlight(pick, not interpreter.multi_select, draw=True)

def hide_highlighted_sweep():
    for idx in trace_display.highlighted_sweep:
        sweep_tab.sweep_vars[idx].set(0)
        toggle_sweep(idx, 0, draw=False)
    trace_display.canvas.draw()

def highlight_all_sweeps():
    for i in range(len(sweep_tab.sweep_vars)):
        if sweep_tab.sweep_vars[i].get():
            trace_display.set_highlight_sweep(i, highlight=True, draw=False)
    trace_display.canvas.draw()
    return

def unhighlight_all_sweeps(draw=True):
    for i in range(len(sweep_tab.sweep_vars)):
        if sweep_tab.sweep_vars[i].get():
            trace_display.set_highlight_sweep(i, highlight=False, draw=False)
    if draw:
        trace_display.canvas.draw()
    return

def highlight_sweep_in_range(xlim=None, ylim=None, draw=True):
    # called when right click drag on plot
    unhighlight_all_sweeps(draw=True)
    if xlim and xlim[0] > xlim[1]:
        xlim = (xlim[1], xlim[0])
    if ylim and ylim[0] > ylim[1]:
        ylim = (ylim[1], ylim[0])

    # for sweep in trace_display.sweeps:
    #     if al.contains_line(xlim, ylim, trace_display.sweeps[sweep].get_xdata(),
    #                               trace_display.sweeps[sweep].get_ydata(), rate=al.recording.sampling_rate):
    #         trace_display.set_highlight_sweep(int(sweep.split('_')[-1]), highlight=True, draw=False)
    for i, s in get_sweep_in_range(xlim, ylim):
        trace_display.set_highlight_sweep(int(i), highlight=True, draw=False)
    if draw:
        trace_display.canvas.draw()


def get_sweep_in_range(xlim=None, ylim=None):
    ls = []
    for i, sweep in enumerate(trace_display.sweeps):
        if analyzer2.contains_line(xlim, ylim, trace_display.sweeps[sweep].get_xdata(),
                                  trace_display.sweeps[sweep].get_ydata(), rate=recordings[0].sampling_rate):
            ls.append((i, sweep))
    return ls


# def delete_hidden(delete):
#     if len(delete) == al.recording.sweep_count:
#         messagebox.showerror(message='Must have at least 1 visible trace')
#         return None
#     if len(mini_df.index) > 0:
#         selection = messagebox.askokcancel(message='You have more than 1 mini data. Deleting sweeps may cause the events to misalign.\n'+
#                                'Continue?', icon=messagebox.WARNING)
#         if not selection:
#             return None
#     count = 0
#     for idx in delete:
#         al.recording.delete_sweep(idx - count)
#         count += 1
#
#     sweep_tab.populate_list(al.recording.sweep_count)
#     # should only be called during 'overlay' mode
#     plot_overlay(fix_axis=True)



######################################
# Save Trace
######################################
# def save_trace_as(fname):
#     """
#     not done
#     """
#     c = recordings[0].channel
#     for i in range(recordings[0].sweep_count):
#         try:
#             ys = trace_display.get_sweep(i).get_ydata()
#             recordings[0].update_datea(channel=c, sweep=i, data=ys)
#         except:
#             pass



########################################
# Adjust tab
########################################

# update changes made to the y-data in the recording data to the plot
def update_plot_ys(sweeps):
    global recordings
    if app.widgets['trace_mode'].get() == 'continuous':
        trace_display.get_sweep(0).set_ydata(recordings[0].get_ys(mode='continuous'))
    else:
        for s in sweeps:
            trace_display.get_sweep(s).set_ydata(recordings[0].get_ys(mode='overlay', sweep=s))
    trace_display.canvas.draw()

def adjust_baseline(all_channels=False, target='All sweeps', mode='mean', xlim=None, fixed_val=None):
    global recordings
    if len(recordings) == 0:
        return None
    if all_channels:
        channels = range(recordings[0].channel_count)
    else:
        channels = [recordings[0].channel]

    # determine sweeps to apply adjustment
    plot_mode = app.widgets['trace_mode'].get()
    target_sweeps = None
    if plot_mode == 'continuous':
        target_sweeps = range(recordings[0].sweep_count)
    elif target == 'All sweeps':
        target_sweeps = range(recordings[0].sweep_count)
    elif target == 'Visible sweeps':
        target_sweeps = [i for i, v in enumerate(sweep_tab.sweep_vars) if v.get()]
    elif target == 'Highlighted sweeps':
        target_sweeps = [i for i in trace_display.highlighted_sweep] # make a getter?
    if not target_sweeps:
        return None # no target to be adjusted

    # clean unwanted params
    if mode != 'range':
        xlim = None
    if mode != 'fixed':
        fixed_val = None

    # perform adjustment
    baseline = al.subtract_baseline(recordings[0], plot_mode=plot_mode,
                               channels=channels, sweeps=target_sweeps, xlim=xlim,
                               fixed_val=fixed_val)
    update_plot_ys(target_sweeps)

    # save undo functions
    undo_baseline = baseline*(-1)
    def shift_back_y_data(shift, plot_mode='continuous', channels=None, sweeps=None):
        recordings[0] = al.shift_y_data(recording=recordings[0], shift=shift, plot_mode=plot_mode, channels=channels, sweeps=sweeps)

    add_undo([
        lambda b=undo_baseline, m=plot_mode, c=channels, s=target_sweeps: shift_back_y_data(b, m, c, s),
        lambda s=target_sweeps: update_plot_ys(s)
    ])

    app.pb['value'] = 0
    app.pb.update()

    ###### Log output ######
    log('Baseline adjustment', True)
    log('Sweeps: {}'.format(analyzer2.format_list_indices(target_sweeps)), False)
    log('Channels: {}'.format(channels), False)
    ########################
    if target == 'fixed':
        log('Subtract a fixed number', False)
        for c in channels:
            log('Channel {}: {}{}'.format(c, fixed_val, recordings[0].channel_units[c]), False)
    elif mode == 'mean':
        log('Subtract the mean of all sweeps', False)
        for i, c in enumerate(channels):
            log('Channel {}: {:.6f}{}'.format(c, baseline[i, 0, 0], recordings[0].channel_units[c]), False)
    elif mode == 'range':
        log('Subtract the mean of range {} from each sweep'.format(xlim), False)
        mean = np.mean(baseline, axis=1, keepdims=True)
        std = np.std(baseline, axis=1, keepdims=True)
        for i,c in enumerate(channels):
            log('Channel {}: mean: {:.6f}{} stdev: {:.6f}'.format(c,
                                                          mean[i, 0, 0],
                                                          recordings[0].channel_units[c],
                                                          std[i, 0, 0]),
                False)

def average_y_data(all_channels=False, target='All sweeps', report_minmax=False, limit_minmax_window=False, hide_all=False):
    global recordings
    if len(recordings)==0:
        return None
        # no recording file open
    if all_channels:
        channels = range(recordings[0].channel_count)
    else:
        channels = [recordings[0].channel]
    if app.widgets['trace_mode'].get() == 'continuous':
        return None
    target_sweeps=[]

    if target == 'All sweeps':
        target_sweeps = range(recordings[0].sweep_count)
    elif target == 'Visible sweeps':
        target_sweeps = [i for i, v in enumerate(sweep_tab.sweep_vars) if v.get()] #check visible sweeps
    elif target == 'Highlighted sweeps':
        target_sweeps = [i for i in trace_display.highlighted_sweep]
    if not target_sweeps:
        return None # no target to be adjusted

    visible_sweep_list = None
    if hide_all:
        visible_sweep_list = tuple([i for i, v in enumerate(sweep_tab.sweep_vars) if v.get()])
        sweep_tab.hide_all()
    if report_minmax:
        xlim = None
        if limit_minmax_window:
            xlim = trace_display.ax.get_xlim()
        mins, mins_std = al.calculate_min_sweeps(recordings[0], plot_mode='overlay', channels=channels, sweeps=target_sweeps, xlim=xlim)
        maxs, maxs_std = al.calculate_max_sweeps(recordings[0], plot_mode='overlay', channels=channels, sweeps=target_sweeps, xlim=xlim)
    al.append_average_sweeps(recordings[0], channels=channels, sweeps=target_sweeps)

    sweep_tab.populate_list(1, replace=False, prefix='Avg ')
    trace_display.plot_trace(recordings[0].get_xs(mode='overlay', sweep=-1),
                             recordings[0].get_ys(mode='overlay', sweep=-1),
                             draw=True,
                             relim=False,
                             idx=recordings[0].sweep_count-1)

    # sweep_tab.checkbuttons[-1].invoke()

    add_undo([
        delete_last_sweep,
        lambda s=visible_sweep_list, d=False: sweep_tab.show(s, d),
        trace_display.canvas.draw,
        lambda msg='Undo trace averaging', h=True: log(msg, h)
    ])
    log('Trace Averaging', True)
    log('Sweeps {}'.format(analyzer2.format_list_indices(target_sweeps)), False)
    log('Channels: {}'.format(channels), False)
    if report_minmax:
        for i,c in enumerate(channels):
            results_display.dataframe.add({
                'filename': recordings[0].filename,
                'channel': c,  # 0 indexing
                'analysis': 'trace averaging',
                'min': np.mean(mins[i], axis=0, keepdims=False)[0],
                'min_unit': recordings[0].channel_units[c],
                'min_std': mins_std[i, 0, 0],
                'max': np.mean(maxs[i], axis=0, keepdims=False)[0],
                'max_unit': recordings[0].channel_units[c],
                'max_std': maxs_std[i,0,0],
            })
            log('Channel {}: min: {:.6f} {} stdev: {:.6f}'.format(c,
                                                         mins[i,0,0],
                                                         recordings[0].channel_units[c],
                                                         mins_std[i,0,0]), False)
            log('           max: {:.6f} {} stdev: {:.6f}'.format(maxs[i, 0, 0],
                                                        recordings[0].channel_units[c],
                                                        maxs_std[i, 0, 0]), False)


def filter_y_data(all_channels=False, target='All sweeps', mode='Boxcar', params=None):
    global recordings
    if len(recordings) == 0:
        return None
    if all_channels:
        channels = range(recordings[0].channel_count)
    else:
        channels = [recordings[0].channel]
    if app.widgets['trace_mode'].get() == 'continuous':
        target_sweeps = range(recordings[0].sweep_count)
    elif target == 'All sweeps':
        target_sweeps = range(recordings[0].sweep_count)
    elif target == 'Visible sweeps':
        target_sweeps = [i for i, v in enumerate(sweep_tab.sweep_vars) if v.get()] #check visible sweeps
    elif target == 'Highlighted sweeps':
        target_sweeps = [i for i in trace_display.highlighted_sweep]
    if not target_sweeps:
        return None # no target to be adjusted

    app.pb['value'] = 25
    app.pb.update()

    if int(app.widgets['config_undo_stack'].get()) > 0:
        ########### Save temp file ##############
        temp_filename = os.path.join(pkg_resources.resource_filename('PyMini', 'temp/'), 'temp_{}.temp'.format(get_temp_num()))
        recordings[0].save_y_data(filename=temp_filename,
                                       channels=channels,
                                       sweeps=target_sweeps)
        add_undo([
            lambda f=temp_filename, c=channels, s=target_sweeps: recordings[0].load_y_data(f, c, s),
            lambda s=target_sweeps: update_plot_ys(s),
            lambda f=temp_filename: os.remove(f)
        ])
        #########################################
    app.pb['value'] = 50
    app.pb.update()

    al.filter_sweeps(recordings[0], filter=mode, params=params, channels=channels, sweeps=target_sweeps)
    update_plot_ys(target_sweeps)

    app.pb['value'] = 100
    app.pb.update()

    app.pb['value'] = 0
    app.pb.update()


    log('Filter trace', header=True)
    log('Sweeps: {}'.format(analyzer2.format_list_indices(target_sweeps)), False)
    log('Channels: {}'.format(channels), False)

    log('Algorithm: {}'.format(mode), False)
    log('Parameters: {}'.format(str(params)), False)


#####################
# log
#####################

def log(msg, header=False):
    if not header:
        msg = '    '+msg
    log_display.log(msg, header)

##########################
# Controls
##########################

def focus():
    try:
        if app.widgets['analysis_mode'].get() == 'mini':
            app.data_display.dataframe.table.focus_set()
            return None
    except:
        app.trace_display.canvas.get_tk_widget().focus_set()
