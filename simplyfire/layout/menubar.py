"""
Loads and handles the application menu bar

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
import tkinter as Tk
from tkinter import filedialog, messagebox
import os
from simplyfire.utils import abfWriter, formatting
from simplyfire.backend import interface
from simplyfire.layout import results_display
import gc
from simplyfire import app
# from PyMini.Layout import keybind_popup


def load(menubar):
    global inputs
    inputs = {}
    global prev_trace_mode
    prev_trace_mode = app.config.get_value('trace_mode')

    parent=menubar.master

    ##################################
    # add menu bar commands here
    ##################################

    # File menu
    global file_menu
    file_menu = Tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label='File', menu=file_menu)

    file_menu.add_command(label="Open recording \t Alt+o", command=ask_open_recording)
    file_menu.add_command(label='Save recording data as...', command=ask_save_recording)
    file_menu.add_separator()

    file_menu.add_command(label='Export plot', command=ask_save_plot)
    # file_menu.add_command(label='Export mini analysis table', command=export_events)
    # file_menu.add_command(label='Export evoked analysis table', command=export_evoked)
    file_menu.add_command(label='Export results table', command=ask_export_results)
    file_menu.add_separator()
    file_menu.add_separator()

    # Edit menu
    global edit_menu
    edit_menu = Tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label='Edit', menu=edit_menu)
    edit_menu.add_command(label='Undo \t Ctrl+z', command=interface.undo, state='disabled')

    # View menu
    global view_menu
    view_menu = Tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label='View', menu=view_menu)
    # track trace_mode
    trace_var = Tk.StringVar(parent, 0)
    inputs['trace_mode'] = trace_var
    view_menu.add_radiobutton(label='Continuous', command=set_view_continuous, variable=trace_var,
                              value='continuous')
    view_menu.add_radiobutton(label='Overlay', command=set_view_overlay, variable=trace_var, value='overlay')

    # Analysis menu
    global batch_menu
    batch_menu = Tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label='Batch', menu=batch_menu)

    # Window menu
    global plugin_menu
    plugin_menu = Tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label='Plug-ins', menu=plugin_menu)

    global settings_menu
    settings_menu = Tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label='Settings', menu=settings_menu)


    # inputs['analysis_mode'].set(config.analysis_mode)
    inputs['trace_mode'].set(app.config.get_value('trace_mode'))
    # view_menu.invoke({'continuous': 0, 'overlay': 1, 'compare':2}[config.trace_mode])
    # batch_menu.invoke({'mini': 0, 'evoked': 1}[config.analysis_mode])

    undo_disable()
    return menubar

def ask_open_recording():
    gc.collect()
    app.root.event_generate('<<AskOpenRecording>>')
    fname = filedialog.askopenfilename(title='Open', filetypes=[('abf files', "*.abf"), ('All files', '*.*')])
    app.root.update()
    if not fname:
        return None
    interface.open_recording(fname)
    # app.compare_tab.start_msg.grid_forget()
    interface.focus()
    app.root.event_generate('<<AskedOpenRecording>>')
    return fname

def ask_save_plot(e=None):
    app.trace_display.canvas.toolbar.save_figure()

def ask_save_recording(e=None):
    if len(interface.recordings)==0:
        messagebox.showerror(title='Error', message='No recording to export. Please open a recording first.')
        return None
    app.root.event_generate('<<AskSaveRecording>>')
    initialfname = formatting.format_save_filename(os.path.splitext(interface.recordings[0].filepath)[0] + '_Modified.abf', overwrite=False)
    initialfname = os.path.split(initialfname)[-1]
    filename = filedialog.asksaveasfilename(filetype=[('abf files', '*.abf'), ('All files', '*.*')],
                                            defaultextension='.abf',
                                            initialfile=initialfname)
    try:
        if filename:
            save_recording(filename)
    except (FileExistsError):
        messagebox.showerror(title='Error', message='ABF files cannot be overwritten. Please choose another filename.')
        ask_save_recording(save_events=False)
    app.root.event_generate('<<AskedSaveRecording>>')

def save_recording(filename):
    recording = app.interface.recordings[0]
    abfWriter.writeABF1(recording, filename)
    recording.filepath = filename
    recording.filename= os.path.splitext(filename)[1]
    recording.filedir, recording.filename = os.path.split(filename)
    app.graph_panel.inputs['trace_info'].set(
        f'{recording.filename}: {recording.sampling_rate}Hz : {recording.channel_count} channels')

def ask_export_results():
    app.root.event_generate('<<AskExportResults>>')
    if len(app.results_display.dataframe.table.get_children()) == 0:
        answer = messagebox.askyesno('Warning', 'No entries in results table. Proceed?')
    else:
        answer = True
    if answer:
        filename = filedialog.asksaveasfilename(filetype=[('csv files', '*.csv'), ('ALl files', '*.*')],
                                                defaultextension='.csv',
                                                initialfile='results.csv')
        if filename:
            results_display.dataframe.export(filename)
    app.root.event_generate('<<AskedExportResults>>')
def set_view_continuous(save_undo=True):
    global inputs
    global prev_trace_mode
    if prev_trace_mode == 'continuous':
        return
    app.root.event_generate('<<ChangeToContinuousView>>')
    if save_undo and prev_trace_mode == 'overlay':
        interface.add_undo([
            lambda s=False: set_view_overlay(s),
        ])
    inputs['trace_mode'].set('continuous')
    app.log_display.log('change to continuous mode')
    # switch to continuous mode tab
    # interface.config_cp_tab('continuous', state='normal')

    try:
        # interface.plot_continuous(interface.recordings[0], fix_axis=True)
        interface.plot(fix_y=True, fix_x=False, relim=True)
    except:
        pass
    # if inputs['analysis_mode'].get() == 'mini':
    #     interface.config_cp_tab('mini', state='normal')
    #     interface.config_data_tab('mini', state='normal')
    # interface.config_cp_tab('adjust', state='normal')
    prev_trace_mode = 'continuous'
    app.root.event_generate('<<ChangedToContinuousView>>')
    pass

def set_view_overlay(save_undo=True):
    global prev_trace_mode
    global inputs
    if prev_trace_mode == 'overlay':
        return
    app.root.event_generate('<<ChangeToOverlayView>>')
    if save_undo and prev_trace_mode == 'continuous':
        interface.add_undo([
            lambda d=False: set_view_continuous(d)
        ])
    # elif save_undo and trace_mode == 'compare':
    #     interface.add_undo([
    #         lambda d=False: set_view_compare(d)
    #     ])
    inputs['trace_mode'].set('overlay')
    app.log_display.log('change to overlay mode')
    # interface.config_cp_tab('overlay', state='normal')
    try:
        interface.plot(fix_x=False, fix_y=True, relim=True)
    except:
        pass
    prev_trace_mode = 'overlay'
    app.root.event_generate('<<ChangedToOverlayView>>')
    pass

def undo_disable():
    global edit_menu
    edit_menu.entryconfig(0, state='disabled')

def undo_enable():
    global edit_menu
    edit_menu.entryconfig(0, state='normal')

def make_file_menu_cascade(label):
    cascade = Tk.Menu(file_menu, tearoff=0)
    file_menu.add_cascade(label=label, menu=cascade)
    return cascade
