from kivy.config import Config
from kivy.utils import platform

if platform != "android":
    Config.set('graphics', 'width', '360')
    Config.set('graphics', 'height', '640')
    Config.set('graphics', 'resizable', '0')

from kivy.core.window import Window


Window.clearcolor = (1, 1, 1, 1)

