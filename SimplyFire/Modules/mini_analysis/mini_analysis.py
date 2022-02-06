from SimplyFire.Modules.base_module import BaseModule
from SimplyFire import app
import os
from SimplyFire.utils import formatting
from SimplyFire.Layout import batch_popup
class Module(BaseModule):
    def __init__(self):
        super().__init__(
            name='mini_analysis',
            menu_label='Mini Analysis',
            tab_label='Mini',
            filename=__file__,
            file_menu=True
        )

        if app.widgets['trace_mode'].get() != 'continuous':
            try:
                self._add_disable()
            except:
                pass
        print('loading batch')
        self._load_batch()
        self._modify_GUI()

    def update_module_display(self, table=False):
        super().update_module_display()

        if self.menu_var.get():
            self.control_tab.update_event_markers(draw=True)
        else:
            for m in self.control_tab.markers:
                try:
                    self.control_tab.markers[m].remove()
                except:
                    pass
            app.trace_display.draw_ani()
        app.pb['value'] = 0
        app.pb.update()

    def _load_batch(self):
        self.create_batch_category()
        def find_all():
            self.control_tab.find_mini_all_thread(popup=False, undo=False)
            batch_popup.batch_log.insert(f'{self.control_tab.mini_df.shape[0]} minis found.\n')
        self.add_batch_command('Find all', func=find_all, interrupt=app.interface.al)

        def find_in_range():
            self.control_tab.find_mini_range_thread(popup=False, undo=False)
            batch_popup.batch_log.insert(f'{self.control_tab.mini_df.shape[0]} minis found.\n')
        self.add_batch_command('Find in window', func=lambda u=False:find_in_range(undo=u), interrupt=app.interface.al)

        self.add_batch_command('Delete all', func=lambda u=False:self.control_tab.delete_all(undo=u))

        self.add_batch_command('Delete in window', func=lambda u=False:self.control_tab.delete_in_window(undo=u))

        self.add_batch_command('Report results', func=self.control_tab.report_results)

        def save_minis():
            if self.control_tab.mini_df.shape[0]== 0:
                batch_popup.batch_log.insert('Warning: Exporting an empty data table\n')
            fname = formatting.format_save_filename(
                os.path.splitext(batch_popup.current_filename)[0] + '.mini', overwrite=False)
            self.control_tab.save_minis(fname, overwrite=False)
            batch_popup.batch_log.insert(f"Saved minis to: {fname}\n")
        self.add_batch_command('Save minis', func=save_minis)

        def export_minis():
            if len(self.data_tab.table.get_children()) == 0:
                batch_popup.batch_log.insert('Warning: Exporting an empty data table\n')
            fname = formatting.format_save_filename(
                os.path.splitext(batch_popup.current_filename)[0] + '_minis.csv', overwrite=False)
            self.data_tab.export(fname, overwrite=False)
            batch_popup.batch_log.insert(f"Exported minis to: {fname}\n")
        self.add_batch_command('Export minis', ffunc=export_minis)


    def _modify_GUI(self):
        self.add_file_menu_command(label='Open mini file', command=self.control_tab.ask_open_minis)
        self.add_file_menu_command(label='Save minis as...', command=self.control_tab.ask_save_minis)
        self.add_file_menu_command(label='Export data table', command=self.data_tab.ask_export_data)
