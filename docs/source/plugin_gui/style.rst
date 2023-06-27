Style Plugin
=============

The purpose of this plugin is to control the stylistic aspects of the
trace plot.

.. figure:: /docs/source/_static/img/style.png
  :align: center

  A typical layout of the Style Plugin.

Tab title: Style

Basic Features
---------------
Trace plot: size
  Specifies the linewidth of the trace.
  Must be an integer.

Trace plot: color
  Specifies the color of the trace.
  Color should be a hex code or a color name accepted by ``matplotlib``.
  See the `matplotlib documentation <https://matplotlib.org/stable/gallery/color/named_colors.html>`_
  for more details on supported color names.

Apply button
  Applies the changes to the plot.
  Changes are also applied after pressing :guilabel:`Return`/:guilabel:`Enter`
  or whenever the system focus leaves the entry widgets.

Default button
  Sets the trace plot parameters to default values.

Other features
-----------------

Other plugins may use the space in the Style Plugin **control-panel** tab to
populate other stylistic options.
