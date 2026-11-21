from kivy.lang import Builder
from kivy.properties import StringProperty,ColorProperty,BooleanProperty
from kivymd.uix.navigationbar import MDNavigationBar, MDNavigationItem,MDNavigationItemIcon

from content.util.paths import Paths

class NavBarIcon(MDNavigationItemIcon):
    icon = StringProperty()
    active = BooleanProperty(False)

class NavBarItem(MDNavigationItem):
    icon_source = StringProperty()
    text = StringProperty()
    color_active = ColorProperty("#1E88E5") 
    color_inactive = ColorProperty("#1a1a1a")
    active = BooleanProperty(False)

class NavBar(MDNavigationBar):
    def select(self, name):
        for item in self.children:
            if getattr(item, "text", None) == name:
                self.set_active_item(item)
                return


Builder.load_file(Paths.file("_components", "Navbar.kv"))