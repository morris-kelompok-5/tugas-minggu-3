from kivy.lang import Builder
from kivymd.uix.floatlayout import MDFloatLayout


from content._components.Navbar import NavBar
from content.page.Home.page import Home
from content.page.Map.page import Map
from content.page.Record.page import Record
from content.page.Time.page import Time
from content.page.Profile.page import Profile
from content.util.paths import Paths


class Manager(MDFloatLayout):
    pass


Builder.load_file(Paths.file("page", "Manager", "page.kv"))