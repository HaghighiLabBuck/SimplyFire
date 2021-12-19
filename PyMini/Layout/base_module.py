from utils.scrollable_option_frame import ScrollableOptionFrame

class BaseModule(ScrollableOptionFrame):
    name = 'base_module'

    def __init__(self, parent, app, interface):
        super().__init__(parent)
        self.app=app
        self.interface = interface

    def log(self, msg, header=True):
        if header:
            self.root.log_display.log(f'@ {name}: {msg}')
        else:
            self.root.log_display.log(f'    {msg}')

    def undo(self, func):
        def inner(*args, **kwargs):
            self.log('Undo', True)
            func(*args, **kwargs)
        return inner




