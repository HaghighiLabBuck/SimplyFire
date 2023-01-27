"""
Matplotlib interface with the UI. Handles plotting of the traces in the base UI.

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
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle
from matplotlib.animation import FuncAnimation
from simplyfire import app
import gc
from simplyfire.utils import calculate
from psutil import Process

sweeps = {}
x_arrays = {}
y_arrays = {}

event_pick = False

highlighted_sweep = []

rect = None

def load(parent):
    frame = Tk.Frame(parent)
    global fig
    fig = Figure()
    fig.set_tight_layout(True)

    global focus_in_edge_color
    focus_in_edge_color = '#90EE90'

    global focus_out_edge_color
    focus_out_edge_color = '#FFB6C1'

    fig.set_edgecolor(focus_in_edge_color)
    fig.set_linewidth(1)


    global ax
    ax = fig.add_subplot(111)
    fig.subplots_adjust(right=1, top=1)

    global canvas
    canvas = FigureCanvasTkAgg(fig, master=parent)
    # canvas.get_tk_widget().pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
    canvas.get_tk_widget().grid(column=1, row=1,sticky='news')
    def focus_in(event=None):
        fig.set_edgecolor(focus_in_edge_color)
        draw_ani()
    def focus_out(event=None):
        fig.set_edgecolor(focus_out_edge_color)
        draw_ani()
    canvas.get_tk_widget().bind('<FocusIn>', focus_in)
    canvas.get_tk_widget().bind('<FocusOut>', focus_out)
    ax.plot()

    ax.set_xlabel('Time (n/a)')
    ax.set_ylabel('y (n/a)')

    global default_xlim
    default_xlim = ax.get_xlim()

    global default_ylim
    default_ylim = ax.get_ylim()

    global trace_color
    trace_color = 'Black'
    global trace_width
    trace_width = 1
    global transparent_background
    transparent_background = True
    # connect user events:
    # canvas.mpl_connect('pick_event', _on_event_pick)

    # canvas.mpl_connect('button_release_event', _on_mouse_release)

    draw_ani()
    # canvas.draw()
    # refresh()
    return frame


################# Navigation ####################

def start_animation():
    for l in ax.lines:
        ax.draw_artist(l)
        l.set_animated(True)
    for c in ax.collections:
        ax.draw_artist(c)
        c.set_animated(True)


def pause_animation():
    for l in ax.lines:
        ax.draw_artist(l)
        l.set_animated(False)
    for c in ax.collections:
        ax.draw_artist(c)
        c.set_animated(False)


def scroll_x_by(dir=1, percent=0):
    dir = dir
    xlim = ax.get_xlim()
    width = xlim[1] - xlim[0]
    delta = width * percent / 100
    new_lim = (xlim[0] + delta * dir, xlim[1] + delta * dir)

    if new_lim[0] < default_xlim[0]:
        delta = default_xlim[0] - new_lim[0]
        new_lim = (new_lim[0] + delta, new_lim[1] + delta)
    elif new_lim[1] > default_xlim[1]:
        delta = new_lim[1] - default_xlim[1]
        new_lim = (new_lim[0] - delta, new_lim[1] - delta)
    update_x_limits_data(new_lim)

    global fig
    global ani
    draw_ani()
    # ani._start()
    update_x_scrollbar(new_lim)
    scroll_y_by(0)


def scroll_y_by(dir=1, percent=0):
    dir = dir
    ylim = ax.get_ylim()
    height = ylim[1] - ylim[0]
    delta = height * percent / 100
    new_lim = (ylim[0] + delta * dir, ylim[1] + delta * dir)
    # update_x_scrollbar()
    # update_y_scrollbar(ylim=new_lim)
    ax.set_ylim(new_lim)
    global fig
    global ani
    # ani = FuncAnimation(
    #     fig,
    #     anim_func,
    #     frames=1,
    #     interval=int(1),
    #     repeat=False
    # )
    draw_ani()
    # ani._start()
    update_y_scrollbar(new_lim)


def scroll_x_to(num):
    # start_animation()
    xlim = ax.get_xlim()
    if xlim[1] == default_xlim[1] and xlim[0] == default_xlim[0]:
        app.graph_panel.x_scrollbar.set(50)
        return None
    start = (default_xlim[1] - default_xlim[0] - (xlim[1] - xlim[0])) * float(num) / 100 + default_xlim[0]
    end = start + xlim[1] - xlim[0]

    update_x_limits_data((start, end))
    global fig
    global ani
    draw_ani()
    # ani._start()
    scroll_y_by(0)


def scroll_y_to(num):
    ylim = ax.get_ylim()
    height = ylim[1] - ylim[0]
    xlim = ax.get_xlim()
    ys = sweeps[list(sweeps.keys())[0]].get_ydata()
    y = ys[calculate.search_index(xlim[0], sweeps[list(sweeps.keys())[0]].get_xdata())]
    y1 = float(num) / 100 * (height) + y
    ax.set_ylim((y1 - height, y1))
    global fig
    global ani
    # ani = FuncAnimation(
    #     fig,
    #     anim_func,
    #     frames=1,
    #     interval=int(1),
    #     repeat=False
    # )
    draw_ani()
    # ani._start()


def center_plot_on(x, y):
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()

    new_xlim = xlim
    new_ylim = ylim


    if xlim[0] < x < xlim[1] and ylim[0] < y < ylim[1]:
        return None
    if xlim[0] > x or xlim[1] < x:
        xlim_width = xlim[1] - xlim[0]
        new_xlim_left = x - xlim_width / 2
        new_xlim_right = x + xlim_width / 2

        adjust = max(0, default_xlim[0] - new_xlim_left)
        new_xlim_right += adjust
        adjust = min(0, default_xlim[1] - new_xlim_right)
        new_xlim_left += adjust

        new_xlim_left = max(default_xlim[0], new_xlim_left)
        new_xlim_right = min(default_xlim[1], new_xlim_right)
        update_x_limits_data((new_xlim_left, new_xlim_right))
        update_x_scrollbar((new_xlim_left, new_xlim_right))
        new_xlim = (new_xlim_left, new_xlim_right)

    if ylim[0] > y or ylim[1] < y:
        ylim_width = ylim[1] - ylim[0]
        new_ylim_bottom = y - ylim_width / 2
        new_ylim_top = y + ylim_width / 2
        ax.set_ylim(new_ylim_bottom, new_ylim_top)
        new_ylim = (new_ylim_bottom, new_ylim_top)
    update_y_scrollbar(xlim=new_xlim, ylim=new_ylim)
    # canvas.draw()
    draw_ani()

def center_plot_area(x1, x2, y1, y2):
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    pad = 0.05
    if xlim[1] == default_xlim[1] and xlim[0] == default_xlim[0]:  # currently showing max xlim
        new_xlim_left = xlim[0]
        new_xlim_right = xlim[1]
    elif x1 > xlim[0] + pad and x2 < xlim[1] - pad:  # x1 and x2 are within current xlim
        new_xlim_left = xlim[0]
        new_xlim_right = xlim[1]
    elif x2 - x1 < xlim[1] - xlim[0]:  # current x-axis zoom will x1 and x2 if shifted
        delta = ((xlim[1] + xlim[0]) / 2) - ((x2 + x1) / 2)
        new_xlim_left = max(xlim[0] - delta, default_xlim[0])
        new_xlim_right = min(xlim[1] - delta, default_xlim[1])
    else:
        padx = (x2 - x1) * pad
        new_xlim_left = max(min(xlim[0], x1 - padx), default_xlim[0])
        new_xlim_right = min(max(xlim[1], x2 + padx), default_xlim[1])

    pady = (y2 - y1) * pad

    new_ylim_bottom = min(ylim[0], y1 - pady)
    new_ylim_top = max(ylim[1], y2 + pady)

    update_x_limits_data((new_xlim_left, new_xlim_right))
    update_x_scrollbar((new_xlim_left, new_xlim_right))
    ax.set_ylim(new_ylim_bottom, new_ylim_top)
    update_y_scrollbar(xlim=(new_xlim_left, new_xlim_right), ylim=(new_ylim_bottom, new_ylim_top))

    # canvas.draw()
    draw_ani()

def zoom_x_by(direction=1, percent=0, event=None):
    # direction 1 = zoom in, -1=zoom out
    xlim = ax.get_xlim()
    if percent == 100 and direction == -1:
        percent = 99

    width = xlim[1] - xlim[0]
    new_width = width + width * direction * percent/100

    center_ratio = 0.5
    try:
        center_ratio = (event.xdata - xlim[0])/width
    except:
        pass
    center_x = center_ratio * width + xlim[0]
    new_lim = (center_x - new_width*center_ratio, center_x + new_width*(1-center_ratio))

    if new_lim[0] < default_xlim[0]:
        width = new_lim[1] - new_lim[0]
        new_lim = (default_xlim[0], min(new_lim[0] + width, default_xlim[1]))
    elif new_lim[1] > default_xlim[1]:
        width = new_lim[1] - new_lim[0]
        new_lim = (max(new_lim[1] - width, default_xlim[0]), default_xlim[1])

    update_x_limits_data(new_lim)
    global fig
    global ani
    # ani = FuncAnimation(
    #     fig,
    #     anim_func,
    #     frames=1,
    #     interval = int(1),
    #     repeat=False
    # )
    draw_ani()
    # ani._start()
    update_x_scrollbar(new_lim)
    scroll_y_by(0)

def anim_func(idx):
    return None

def zoom_y_by(direction=1, percent=0, event=None):
    if percent == 100 and direction == -1:
        precent = 99 # avoid resulting in 0
    win_lim = ax.get_ylim()
    delta = (win_lim[1] - win_lim[0]) * percent * direction / 100
    center_pos = 0.5
    try:
        center_pos = (event.ydata - win_lim[0]) / (win_lim[1] - win_lim[0])
    except:
        pass
    new_lim = (win_lim[0] + center_pos * delta, win_lim[1] - (1- center_pos) * delta)
    ax.set_ylim(new_lim)
    global fig
    global ani
    # ani = FuncAnimation(
    #     fig,
    #     anim_func,
    #     frames=1,
    #     interval=int(1),
    #     repeat=False
    # )
    draw_ani()
    # ani._start()
    update_y_scrollbar(new_lim)

################## Navigation by Scrollbar ###################

def update_x_scrollbar(xlim=None):
    if xlim is None:
        xlim = ax.get_xlim()
    if abs(xlim[0] - default_xlim[0]) < 0.001 and abs(xlim[1] - default_xlim[1]) < 0.001:
        app.graph_panel.x_scrollbar.set(50)
        return
    if (default_xlim[1] - default_xlim[0]) - (xlim[1] - xlim[0]) < 0.001:
        app.graph_panel.x_scrollbar.set(50)
        return
    pos = xlim[0] - default_xlim[0]
    percent = pos / (default_xlim[1] - default_xlim[0] - (xlim[1] - xlim[0])) * 100
    app.graph_panel.x_scrollbar.set(percent)
    return


def update_y_scrollbar(ylim=None, xlim=None):
    if ylim is None:
        ylim = ax.get_ylim()
    if xlim is None:
        xlim = ax.get_xlim()
    try:
        idx = calculate.search_index(xlim[0],sweeps[list(sweeps.keys())[0]].get_xdata())
        y = sweeps[list(sweeps.keys())[0]].get_ydata()[idx]

        percent = (ylim[1] - y) / (ylim[1] - ylim[0]) * 100
        app.graph_panel.y_scrollbar.set(percent)
    except:
        pass

def clear():
    for s in sweeps.keys():
        try:
            sweeps[s].remove()
        except:
            pass
    sweeps.clear()
    gc.collect()
    # canvas.draw()
    draw_ani()

def refresh():
    for s in sweeps.keys():
        try:
            sweeps[s].remove()
        except:
            pass
    sweeps.clear()
    for l in ax.lines:
        l.remove()
    for c in ax.collections:
        c.remove()
    ax.clear()
    gc.collect()
    # canvas.draw()
    draw_ani()

def plot_trace(xs, ys, draw=True, relim=True, idx=0, color=None, width=None, name="", relim_axis='both'):
    global sweeps
    global x_arrays
    global y_arrays
    global trace_color
    global trace_width
    if not width:
        width=trace_width
    if relim:
        ax.autoscale(enable=False, axis='both')
        ax.relim(visible_only=True)
        # canvas.draw()
        draw_ani()
        if relim_axis == 'x' or relim_axis == 'both':
            minX = min(xs)
            maxX = max(xs)
            global default_xlim
            if len(xs) > 100000:
                ax.set_xlim(minX,xs[99999])
            else:
                ax.set_xlim(minX,maxX)
            default_xlim = (minX,maxX)
        if relim_axis == 'y' or relim_axis == 'both':
            ax.autoscale(enable=True, axis='y', tight=True)
            global default_ylim
            default_ylim = ax.get_ylim()    
    	
    if name == "":
        name = f'Sweep_{len(sweeps)}'
    print('Before assigning arrays to trace display')
    print(Process().memory_info().rss)
    x_arrays[name] = xs
    y_arrays[name] = ys	
    	
    xlims = ax.get_xlim()
    left_idx = calculate.search_index(xlims[0],xs)
    right_idx = calculate.search_index(xlims[1],xs)
    print('Before plotting trace')
    print(Process().memory_info().rss)
    if sweeps.get(name, None):
        sweeps.get(name).set_xdata(xs[left_idx:right_idx+1])
        sweeps.get(name).set_ydata(ys[left_idx:right_idx+1])
    else:
        if not color:
            # color = app.widgets['style_trace_line_color'].get()
            color = trace_color
        sweeps[name], = ax.plot(xs[left_idx:right_idx+1], ys[left_idx:right_idx+1],
                                              linewidth=width,
                                              c=color,
                                              animated=False)  # pickradius=int(app.widgets['style_event_pick_offset'].get())
    print('After plotting trace')
    print(Process().memory_info().rss)
    if draw:
        # canvas.draw()
        # refresh()
        draw_ani()
		
def update_x_limits_data(new_lims):
    for name, sweep in sweeps.items():
        left_idx = calculate.search_index(new_lims[0],x_arrays[name])
        right_idx = calculate.search_index(new_lims[1],x_arrays[name])
        sweep.set_xdata(x_arrays[name][left_idx:right_idx+1])
        sweep.set_ydata(y_arrays[name][left_idx:right_idx+1])
    ax.set_xlim(new_lims)

def hide_sweep(idx, draw=False):
    try:
        sweeps['sweep_{}'.format(idx)].set_linestyle('None')
        # del sweeps['sweep_{}'.format(idx)]
    except:
        pass
    if draw:
        # canvas.draw()
        draw_ani()

def show_sweep(idx, draw=False):
    sweeps['sweep_{}'.format(idx)].set_linestyle('-')
    try:
        pass
    except:
        pass
    if draw:
        # canvas.draw()
        draw_ani()

def get_sweep(idx):
    try:
        return sweeps['sweep_{}'.format(idx)]
    except:
        return None

def show_all_plot(update_default=False):
    ax.autoscale(enable=True, axis='both', tight=True)
    ax.relim(visible_only=True)
    # canvas.draw()
    draw_ani()
    if update_default:
        global default_xlim
        default_xlim = ax.get_xlim()
        global default_ylim
        default_ylim = ax.get_ylim()

def update_default_lim(x=True, y=True, fix_x=False, fix_y=False):
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    ax.autoscale(enable=True, axis='both', tight=True)
    ax.relim(visible_only=True)
    draw_ani()
    if x:
        global default_xlim
        default_xlim = ax.get_xlim()
    if y:
        global default_ylim
        default_ylim = ax.get_ylim()
    if fix_x:
        update_x_limits_data(xlim)
    if fix_y:
        ax.set_ylim(ylim)

get_axis_limits = lambda axis: getattr(ax, 'get_{}lim'.format(axis))()

def adjust_default_ylim(adjust):
    global default_ylim
    default_ylim = (default_ylim[0]+adjust,
                    default_ylim[1]+adjust)

def set_axis_limit(axis, lim, draw=True):
    if axis == 'x':
        l = [float(e) if e != 'auto' else default_xlim[i] for i, e in enumerate(lim)]
        if l[0] < default_xlim[0] or l[0] > default_xlim[1]:
            l[0] = default_xlim[0]
        if l[1] < default_xlim[0] or l[1] > default_xlim[1]:
            l[1] = default_xlim[1]
        update_x_limits_data(l)
    if axis == 'y':
        l = [float(e) if e != 'auto' else default_ylim[i] for i, e in enumerate(lim)]
        ax.set_ylim(l)
    # canvas.draw()
    if draw:
        draw_ani()

##################
def draw_rect(coord_start, coord_end):
    global rect
    if coord_start and coord_end:
        height = coord_end[1] - coord_start[1]
        width = coord_end[0] - coord_start[0]
        if rect:
            rect.set_width(width)
            rect.set_height(height)
        else:
            rect = Rectangle(coord_start, width, height, angle=0.0,
                      edgecolor='blue',
                      facecolor='gray',
                      fill=True,
                      alpha=0.2,
                      animated=True)
            ax.add_patch(rect)
        canvas.draw()
        # draw_ani()
        global bg
        bg = canvas.copy_from_bbox(fig.bbox)
        ax.draw_artist(rect)
        canvas.blit(fig.bbox)
        return
    if rect:
        try:
            ax.patches.remove(rect)
        except: # rect was deleted elsewhere
            pass
        rect = None
        # canvas.draw()
        draw_ani()
def draw_ani():
    global ani
    ani = FuncAnimation(
        fig,
        anim_func,
        frames=1,
        interval=int(1),
        repeat=False
    )
    ani._start()