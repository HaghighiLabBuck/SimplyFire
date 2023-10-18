"""
Loader for the UI system. Connects to all components of the software.

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
import time
from simplyfire.setting import config
from tkinter import ttk, messagebox
import tkinter as Tk
import yaml
from PIL import Image
import os
from simplyfire.utils import custom_widgets, formatting
from simplyfire.backend import interpreter, plugin_manager, interface
from simplyfire.layout import trace_display, menubar, graph_panel, setting_tab, batch_popup, \
    results_display, log_display, plugin_tab
# debugging
from datetime import datetime




event_filename = None
inputs = {}

##################################################
#                    Methods                     #
##################################################

def _on_close():
    """
    The function is called when the program is closing (pressing X)
    Uses the config module to write out user-defined parameters
    :return: None
    """
    global inputs
    # if widgets['config_autosave'].get():
    # try:
    log_display.log('Closing...')
    dump_user_setting()
    dump_plugin_setting()
    dump_system_setting()
    # dump_key_setting() # implement this for customizable keys
    dump_log()
    root.destroy()
    temp_list = os.listdir(config.TEMP_DIR)
    for fname in temp_list:
        if os.path.splitext(fname)[1] in ('.temp','.tmp','.TEMP'):
            os.remove(os.path.join(config.TEMP_DIR, fname))

def load(window, splash):
    # debugging:
    print_time_lapse('Start loading main application')
    global t0
    global app_root
    # app_root = splash
    # tracemalloc.start()
    global root
    root = window
    global loaded
    loaded = False
    root.withdraw()


    global menu
    menu = Tk.Menu(root)
    root.config(menu=menu)
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    print_time_lapse('Load menubar')

    frame = Tk.Frame(root, bg='red')
    frame.grid(column=0, row=0, sticky='news')

    # root.bind(config.key_reset_focus, lambda e: data_display.table.focus_set())

    ##################################################
    #                   DATA PANEL                   #
    ##################################################
    global inputs
    global pw
    pw = Tk.PanedWindow(
        root,
        orient=Tk.HORIZONTAL,
        showhandle=True,
        sashrelief=Tk.SUNKEN,
        handlesize=config.get_value('pw_handlesize')
    )

    pw.grid(column=0, row=0, sticky='news')
    # set up frame
    right = Tk.Frame(pw, background='pink')
    right.grid(column=0, row=0, sticky='news')
    right.columnconfigure(0, weight=1)
    right.rowconfigure(0, weight=1)

    dp_notebook = ttk.Notebook(right)
    dp_notebook.grid(column=0, row=0, sticky='news')

    log_frame = log_display.load(root)
    config.load()
    global arrow_img
    arrow_img = Image.open(os.path.join(config.IMG_DIR, 'arrow.png'))

    global pw_2
    pw_2 = Tk.PanedWindow(
        right,
        orient=Tk.VERTICAL,
        showhandle=True,
        sashrelief=Tk.SUNKEN,
        handlesize=config.get_value('pw_handlesize')
    )


    # must set up a graph object that can 'refresh' and 'plot' etc
    global gp
    gp = graph_panel.load(root)
    root.update_idletasks()
    pw_2.add(gp)
    pw_2.paneconfig(gp, height=config.gp_height)

    global data_notebook
    data_notebook = ttk.Notebook(pw_2)
    data_notebook.bind('<ButtonRelease>', interface.focus, add='+')


    pw_2.add(data_notebook)
    dp_notebook.add(pw_2, text='trace')
    dp_notebook.add(log_frame, text='log')

    results_frame = results_display.load(root)
    dp_notebook.add(results_frame, text='results', sticky='news')
    print_time_lapse('Create datapanel')


    ##################################################
    #                 CONTROL PANEL                  #
    ##################################################

    # set up frame
    global cp
    cp = Tk.Frame(pw, background='blue')
    cp.grid(column=0, row=0, sticky='news')
    cp.grid_rowconfigure(0, weight=1)
    cp.grid_columnconfigure(0, weight=1)

    global cp_notebook
    cp_notebook = ttk.Notebook(cp)
    cp_notebook.grid(column=0, row=0, sticky='news')
    cp_notebook.bind('<<NotebookTabChanged>>', synch_tab_focus, add='+')
    cp_notebook.bind('<ButtonRelease>', interface.focus, add='+')

    print_time_lapse('Create control panel')

    for key in inputs:
        if type(inputs[key]) == custom_widgets.VarEntry:
            inputs[key].bind('<Return>', lambda e: interface.focus(), add='+')
        if type(inputs[key]) == custom_widgets.VarCheckbutton:
            inputs[key].bind('<ButtonRelease>', lambda e: interface.focus(), add='+')
        if type(inputs[key]) == custom_widgets.VarOptionmenu:
            inputs[key].bind('<ButtonRelease>', lambda e: interface.focus(), add='+')
        if type(inputs[key]) == custom_widgets.VarCheckbutton:
            inputs[key].bind('<ButtonRelease>', lambda e: interface.focus(), add='+')

    print_time_lapse('Bind mouse events')
    # set up font adjustment bar
    # fb = font_bar.load(left, config.font_size)
    # widgets['font_size'] = font_bar.font_scale
    # fb.grid(column=0, row=1, sticky='news')

    # set up progress bar
    global pb
    # pb = progress_bar.ProgressBar(left)
    pb = ttk.Progressbar(cp, length=100,
                         mode='determinate',
                         orient=Tk.HORIZONTAL)
    pb.grid(column=0, row=2, stick='news')

    # finis up the pw setting:

    pw.grid(column=0, row=0, sticky='news')
    pw.add(cp)
    pw.add(right)

    # adjust frame width
    root.update()
    pw.paneconfig(cp, width=int(config.cp_width))

    ##################################################
    #                    MENU BAR                    #
    ##################################################

    # set up menubar
    menubar.load(menu)

    globals()['menubar'] = menubar

    for k, v in menubar.inputs.items():
        inputs[k] = v

    setting_tab.load(root)
    for k, v in setting_tab.inputs.items():
        inputs[k] = v

    batch_popup.load()
    print_time_lapse('Create batch popup')
    menubar.batch_menu.add_command(label='Batch Processing', command=batch_popup.show)

    global control_panel_dict
    control_panel_dict = {}

    global data_notebook_dict
    data_notebook_dict = {}

    global modules
    modules = {}

    # with open(os.path.join(config.CONFIG_DIR, 'modules.yaml')) as f:
    #     module_list = yaml.safe_load(f)['modules']
    #     for module_name in module_list:
    #         load_module(module_name)
    # plugin_controller = plugin_tab.PluginController()
    # plugin_controller.load_plugins()
    plugin_tab.load()
    print_time_lapse('Create plugin panel')
    plugin_manager.load_plugins()
    print_time_lapse('Load plugins')

            # except Exception as e:
            #     print(e)
            #     pass
        # # only show one tab at a time
        # global data_tab_details
        # data_tab_details = {
        #     'mini': {'module': data_display, 'text': 'Mini Data'},
        #     'evoked': {'module': evoked_data_display, 'text': 'Evoked Data'}
        # }
        # for i, t in enumerate(data_tab_details):
        #     data_tab_details[t]['tab'] = data_tab_details[t]['module'].load(root)
        #     data_notebook.add(data_tab_details[t]['tab'], text=data_tab_details[t]['text'])
        #     data_tab_details[t]['index'] = i
    # set up closing sequence

    root.protocol('WM_DELETE_WINDOW', _on_close)

    # set up event bindings
    interpreter.initialize()
    print_time_lapse('Initialize Interpreter')

    # for modulename in config.start_module:
    #     try:
    #         modules[modulename].menu_var.set(True)
    #     except: # module removed from module-list
    #         pass
    # for module_name, module in modules.items():
    #     module.update_module_display()
    cp_notebook.add(setting_tab.frame, text='Setting', state='disabled')
    cp_notebook.add(setting_tab.frame, text='Setting', state='hidden')
    root.update()
    ## root2 = root
    loaded = True
    print_time_lapse('Add settings panel to the control panel')

    root.event_generate('<<LoadCompleted>>')
    print_time_lapse('Event <<LoadCompleted>> generated')

    root.title('SimplyFire v{}'.format(config.version))
    root.iconbitmap(os.path.join(config.IMG_DIR, 'logo_bw.ico'))
    if config.get_value('zoomed'):
        root.state('zoomed')
    root.focus_force()
    interface.focus()
    splash.destroy()

    root.deiconify()
    # # finalize the data viewer - table
    root.geometry(config.geometry)
    print_time_lapse('Finalize application')
    if config.user_config_load_error is not None:
        messagebox.showwarning('Warning', f'Error while loading user settings: {config.user_config_load_error}\nReverting to default configurations.')
    if not plugin_manager.error_free:
        messagebox.showwarning('Warning', f'Error encountered while loading plugins. See log-display for more details.')
    return None


def get_tab_focus():
    focus = {}
    focus['control_panel'] = cp_notebook.select()
    focus['data_panel'] = data_notebook.select()
    return focus

def synch_tab_focus(event=None):
    try:
        controller = root.children.get(cp_notebook.select().split('.')[-1]).controller
        controller.select()
    except:
        pass

def advance_progress_bar(value, mode='determinate'):
    if mode == 'determinate':
        pb['value'] += value
    else:
        pb['value'] = (pb['value'] + value) % 100
    pb.update()
def set_progress_bar(value):
    global pb
    pb['value'] = value
    pb.update()

def clear_progress_bar():
    global pb
    pb['value'] = 0
    pb.update()

def dump_user_setting(filename=None):
    global inputs
    ignore = ['system_', '_log', 'temp_']
    if filename is None:
        filename = os.path.join(inputs['system_data_dir'].var.get().strip(), config.get_value('system_user_path'))
        # filename = os.path.join(pkg_resources.resource_filename('PyMini', 'config'), 'test_user_config.yaml')
    with open(filename, 'w') as f:
        # pymini.pb.initiate()
        d = {}
        for key in inputs.keys():
            try:
                for ig in ignore:
                    if ig in key:
                        break
                else:
                    d[key] = inputs[key].get()
            except:
                d[key] = inputs[key].get()
        for key in graph_panel.inputs.keys():
            d[key] = graph_panel.inputs[key].get()
        global cp
        if loaded:
            d['zoomed'] = root.state() == 'zoomed'
            if not root.state() == 'zoomed':
                d['cp_width'] = cp.winfo_width()
                d['gp_height'] = gp.winfo_height()
                d['geometry'] = root.geometry().split('+')[0]
        d['user_config_version'] = config.version
        # d['compare_color_list'] = config.compare_color_list
        # d['compare_color_list'][:len(compare_tab.trace_list)] = [c['color_entry'].get() for c in compare_tab.trace_list]
        save_data = plugin_manager.save_plugin_data()
        for key,value in save_data.items():
            d[key] = value
        # write if no error takes place
        f.write("#################################################################\n")
        f.write("# PyMini user configurations\n")
        f.write("#################################################################\n")
        f.write("\n")
        f.write(yaml.safe_dump(d))
        # pymini.pb.clear()
        # f.write(yaml.safe_dump(user_vars))
    log_display.log(msg=f'User settings saved in: {filename}')

def dump_plugin_setting(filename=None):
    if filename is None:
        filename = os.path.join(inputs['system_data_dir'].var.get().strip(), config.get_value('system_plugin_path'))
        # filename = os.path.join(pkg_resources.resource_filename('PyMini', 'config'), 'test_user_config.yaml')
    with open(filename, 'w') as f:
        d = {'active_plugins':plugin_tab.get_plugins()}
        d['active_plugins_version'] = config.version
        f.write("#################################################################\n")
        f.write("# PyMini active plugin list\n")
        f.write("#################################################################\n")
        f.write("\n")
        f.write(yaml.safe_dump(d))
    log_display.log(msg=f'Plugin list saved in: {filename}')


def dump_system_setting():
    filename = config.SYS_PATH
    with open(filename, 'w') as f:
        f.write("#################################################################\n")
        f.write("# PyMini system configurations\n")
        f.write("#################################################################\n")
        f.write("\n")

        d = dict([(key, value.get()) for key, value in setting_tab.inputs.items() if 'system' in key])
        d['setting_config_version'] = config.version
        f.write(yaml.safe_dump(d))
    log_display.log(msg=f'System load settings saved in: {filename}')

def dump_config_var(key, filename, title=None):
    print('Saving "{}" config values...'.format(key))
    print(filename)
    with open(filename, mode='w') as f:
        f.write("#################################################################\n")
        f.write("# PyMini {} configurations\n".format(title))
        f.write("#################################################################\n")
        f.write("\n")
        f.write(yaml.safe_dump(dict([(n, getattr(config, n)) for n in config.user_vars if key in n])))
    print('Completed')

def dump_log():
    if not inputs['log_autosave'].get():
        return
    dirname = os.path.join(inputs['system_data_dir'].var.get().strip(), 'log')
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    filename = os.path.join(dirname, f'SimplyFire-{datetime.now().strftime("%m-%d-%y %H-%M-%S")}.txt')
    filename = formatting.format_save_filename(filename, overwrite=False)
    try:
        log_display.save(filename)
    except Exception as e:
        print(f'Error writing log file: {e}')

def load_config(filename=None):
    if not filename:
        return None
    with open(filename) as f:
        loaded_configs = yaml.safe_load(f)
    for key in inputs.keys():
        try:
            value = loaded_configs.get(key, None)
            if value:
                inputs[key].set(value)
        except:
            pass
    plugin_manager.load_values(loaded_configs)

def print_time_lapse(msg=""):
    global t0
    try:
        print(f"{msg}: {time.time() - t0}")
    except:
        print(msg)
        pass
    t0 = time.time()
