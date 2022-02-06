# takes input from the Data Visualizers and takes appropriate action
from SimplyFire import app
from tkinter import filedialog, messagebox

import pandas as pd
from SimplyFire.DataVisualizer import log_display, trace_display, results_display
import os
from SimplyFire.Layout import graph_panel, menubar
from SimplyFire.Backend import interpreter, analyzer2

# This module is the workhorse of the GUI
# Use this module to connect analysis functions to the GUI
from SimplyFire.utils import abfWriter
from SimplyFire.utils.recording import Recording
global mini_df
mini_df = pd.DataFrame()

global al
al = analyzer2.Analyzer()

global current_channel
current_channel = 0

##########################
# Undo controls
##########################
def get_temp_num():
    global temp_num
    try:
        temp_num += 1
        return temp_num % int(app.widgets['config_undo_stack'].get())
    except:
        temp_num = 0
        return 0

def get_temp_filename():
    return os.path.join(app.config.TEMP_DIR,
                                       'temp_{}.temp'.format(get_temp_num()))
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

def is_accepting_undo():
    if not app.batch_popup.processing:
        return int(app.widgets['config_undo_stack'].get()) > 0
    else:
        return False

def undo(e=None):
    print(f'undo called: {undo_stack}')
    app.pb['value'] = 0
    app.pb.update()
    if len(undo_stack) > 0:
        task_stack = undo_stack.pop()
        len_task = len(task_stack)
        for i, task in enumerate(task_stack):
            app.pb['value'] = i / len_task * 100
            app.pb.update()
            try:
                task()
            except:
                pass
            del task

        del task_stack
    else:
        # app.root.bell()
        pass
    app.pb['value'] = 0
    app.pb.update()

    # if the stack is empty, disable the undo command in the menubar
    if len(undo_stack) == 0:
        menubar.undo_disable()


def configure(key, value): # delete?
    globals()[key] = value

#################################
# Handling recording data
#################################

global recordings
# store recording data in a list
# use index 0 for analysis
# use index > 0 only for comparison mode

recordings = []
def open_recording(fname: str,
               append: bool=False,
               xlim: tuple=None,
               ylim: tuple=None,
                   channel: int=None) -> None:
    """
    Opens electrophysiology recording data and stores it in recordings list
    
    fname: string, path to the file to be opened
    append: True/False, if append, data will be appended to the recordings list 
    xlim: float tuple, if not None, used to set the x-axis limits of the GUI
    ylim: float tuple, if not None, used to set the y-axis limist of the GUI
    """
    # import data as a Recording object
    # app.t0=time.time()
    global recordings
    try:
        record = Recording(fname)
    except Exception as e:
        messagebox.showerror('Read file error', f'The selected file could not be opened.\nError code: {e}')
        return None
    try:
        log_display.open_update(fname)
    except:
        return None
    if not append:
        app.root.event_generate('<<OpenRecording>>')
    # reset data from previous file
    clear_undo()
    global mini_df
    global current_channel
    if not append: # open a new file for analysis
        # mini_df = mini_df.iloc[0:0]
        # data_display.clear()
        # evoked_data_display.clear()
        # update save file directory
        # if app.setting_tab.widgets['config_file_autodir'].get() == '1':
        #     mpl.rcParams['savefig.directory'] = os.path.split(fname)[0]
        # set to channel specified by the user
        try:
            if channel:
                record.set_channel(channel)  # 0 indexing
                current_channel = channel
            elif app.graph_panel.widgets['force_channel'].get() == '1':
                record.set_channel(int(app.graph_panel.widgets['force_channel_id'].get()))  # 0 indexing
                current_channel = int(app.graph_panel.widgets['force_channel_id'].get())
            else:
                record.set_channel(0)
                current_channel = 0
        except (IndexError):  # forced channel does not exist
            record.set_channel(0)  # revert to the first channel
            current_channel = 0
            pass

        # update file info displayed in the GUI
        app.graph_panel.widgets['trace_info'].set(
            '{}: {}Hz : {} channel{}'.format(
                record.filename,
                record.sampling_rate,
                record.channel_count,
                's' if record.channel_count > 1 else ""
            )
        )
        app.trace_display.ax.autoscale(enable=True, axis='both', tight=True)
        # app.sweep_tab.populate_list(record.sweep_count)
        while len(recordings) > 0:
            r = recordings.pop()
            del r
    recordings.append(record)
    # if not append:
    #     app.compare_tab.reset_trace_list(fname)
    # else:
    #     app.compare_tab.increase_trace_list(fname)
    #     try:
    #         record.set_channel(recordings[0].channel)
    #     except:
    #         _change_channel(0, save_undo=False) # cannot open channel
    app.trace_display.clear()
    plot()
    app.trace_display.draw_ani()
    # param_guide.update()
    if not append:
        # if app.graph_panel.widgets['force_axis_limit'].get() == '1':
        #     app.trace_display.set_axis_limit('x', (app.widgets['min_x'].get(), app.widgets['max_x'].get()))
        #     app.trace_display.set_axis_limit('y', (app.widgets['min_y'].get(), app.widgets['max_y'].get()))
        if xlim:
            app.trace_display.set_axis_limit('x', xlim)
        if ylim:
            app.trace_display.set_axis_limit('y', ylim)


        app.graph_panel.y_scrollbar.config(state='normal')
        app.graph_panel.x_scrollbar.config(state='normal')

        app.trace_display.update_x_scrollbar()
        app.trace_display.update_y_scrollbar()

        app.graph_panel.widgets['channel_option'].clear_options()
        for i in range(record.channel_count):
            app.graph_panel.widgets['channel_option'].add_command(
                label='{}: {}'.format(i, record.channel_labels[i]),
                command=lambda c=i:change_channel(c)
            )

    # starting channel was set earlier in the code
        app.graph_panel.widgets['channel_option'].set('{}: {}'.format(record.channel, record.y_label))
    # print(f'interface finished opening: {time.time() - app.t0}')
    # app.t0 = time.time()
    app.root.event_generate('<<OpenedRecording>>')
    # print(f'end of all bindings: {time.time() - app.t0}')
    # app.t0 = time.time()
    app.pb['value'] = 0
    app.pb.update()

def save_recording(filename):
    app.pb['value']=50
    app.pb.update()
    # recordings[0].save(filename)
    abfWriter.writeABF1(recordings[0], filename)
    app.pb['value']=100
    app.pb.update()
    app.pb['value']=0
    app.pb.update()

def change_channel(num: int,
                   save_undo: bool=True) -> None:
    """
    Changes the channel data displayed on the GUI

    num: int, channel number (0 indexing) to be displayed
    save_undo: bool, whether or not to store the change in the undo stack (False if using this call as part of an undo command)
    """
    global recordings
    # store process in undo
    app.root.event_generate('<<ChangeChannel>>')
    global current_channel
    if save_undo and num != current_channel:
        add_undo(lambda n= current_channel, s=False:change_channel(n, s))
    try:
        current_channel = num
        for r in recordings:
            r.set_channel(num)
        log_display.log(f'@ graph_viewer: switch to channel {num}')
    except:
        current_channel = 0
        for r in recordings:
            r.set_channel(0)
        log_display.log(f'@ graph_viewer: unable to switch to channel {num}. Reverting to channel 0')
    app.graph_panel.widgets['channel_option'].set(f'{recordings[0].channel}: {recordings[0].y_label}') #0 indexing for channel num

    xlim = app.trace_display.ax.get_xlim()
    # plot data points
    plot(clear=False)
    # if app.menubar.widgets['trace_mode'].get() == 'continuous':
    #     plot_continuous(recordings[0], fix_x=True, draw=False)
    # elif app.menubar.widgets['trace_mode'].get() == 'compare':
    #     for i,r in enumerate(recordings):
    #         plot_overlay(r, fix_x=True, draw=False, append=(i!=0))
    # elif app.menubar.widgets['trace_mode'].get() == 'overlay':
    #     plot_overlay(recordings[0], fix_x=True, draw=False)
    # add other modes here
    # data_display.clear()

    # populate_data_display()
    # update_event_marker()

    # param_guide.update()
    app.root.event_generate('<<ChangedChannel>>')
    trace_display.set_axis_limit('x', xlim)
    trace_display.draw_ani()
    app.pb['value'] = 0
    app.pb.update()

def plot(fix_x=False, fix_y=False, clear=True, **kwargs):
    if len(recordings) == 0:
        return
    app.root.event_generate("<<Plot>>")
    xlim=None
    ylim=None
    if fix_x:
        xlim = trace_display.get_axis_limits('x')
    if fix_y:
        ylim=trace_display.get_axis_limits('y')
    if clear:
        trace_display.clear()
    if app.menubar.widgets['trace_mode'].get() == 'continuous':
        plot_continuous(recordings[0], draw=False, **kwargs)
    elif app.menubar.widgets['trace_mode'].get() == 'overlay':
        plot_overlay(recordings[0], draw=False, **kwargs)
    if xlim:
        trace_display.set_axis_limit('x', xlim)
    if ylim:
        trace_display.set_axis_limit('y', ylim)

    trace_display.ax.set_xlabel(recordings[0].x_label)#, fontsize=int(float(app.widgets['font_size'].get())))
    trace_display.ax.set_ylabel(recordings[0].y_label)#, fontsize=int(float(app.widgets['font_size'].get())))
    trace_display.ax.tick_params(axis='y', which='major')#, labelsize=int(float(app.widgets['font_size'].get())))
    trace_display.ax.tick_params(axis='x', which='major')#, labelsize=int(float(app.widgets['font_size'].get())))
    app.root.event_generate('<<Plotted>>')
    app.root.event_generate('<<PlotDone>>')
    app.trace_display.draw_ani()


def plot_continuous(recording, draw=False, sweep_name_suffix='Sweep'):
    global current_channel
    trace_display.plot_trace(recording.get_xs(mode='continuous', channel=current_channel),
                             recording.get_ys(mode='continuous', channel=current_channel),
                             draw=False,
                             relim=True,
                             name=f'{sweep_name_suffix}_0')
    if draw:
        trace_display.draw_ani()


def plot_overlay(recording, draw=False, sweep_name_suffix='Sweep'):
    for i in range(recording.sweep_count):
        app.pb['value'] = (i+1)/recording.sweep_count*100
        app.pb.update()
        xs = recording.get_xs(mode='overlay', sweep=i, channel=current_channel)
        ys = recording.get_ys(mode='overlay', sweep=i, channel=current_channel)
        trace_display.plot_trace(xs, ys,
                                 draw=False,
                                 relim=i == recording.sweep_count-1, #relim for the final sweep
                                 name = f"{sweep_name_suffix}_{i}")
    if draw:
        trace_display.draw_ani()
        trace_display.draw_ani()
    app.pb['value'] = 0
    app.pb.update()

######################################
# Handling GUI placements
######################################

def select_left(e=None):
    """
    invoked when selection key (default = Space bar) is pressed while in mini analysis mode
    If there are marked minis in the plot, the left most mini will be highlighted.
    If a mini in the viewing window is already highlighted, the highlight will move to the proceeding mini.
    """
    # check if mini analysis mode is activated
    if app.widgets['analysis_mode'].get()!= 'mini':
        return None
    # get the x-axis limits
    xlim_low, xlim_high = app.trace_display.ax.get_xlim()
    # check if a trace is open
    if len(recordings)==0:
        return None
    # check if any mini has been detected
    if len(app.data_display.table.get_children()) == 0:
        return None

    # look for highlighted mini within the viewing window
    selection = app.data_display.dataframe.table.selection()
    if len(selection)>0:
        max_xlim = 0
        for index in selection:
            if float(index) > max_xlim and xlim_low < float(index) <xlim_high:
                max_xlim = float(index)
        xlim_low = max(max_xlim, xlim_low)

    # look for mini data that match the criteria
    df = mini_df[(mini_df.t < xlim_high) & (mini_df.t > xlim_low) & (
                mini_df.channel == recordings[0].current_channel)].sort_values(by='t')
    if df.shape[0]>0:
        app.data_display.table.selection_set(str(df.iloc[0]['t']))
    else:
        app.data_display.unselect()
    focus()

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
    # trace_display.canvas.draw()
    trace_display.draw_ani()

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

def focus(event=None):
    app.trace_display.canvas.get_tk_widget().focus_set()

