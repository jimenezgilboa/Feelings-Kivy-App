from kivy.uix.screenmanager import ScreenManager
from kivy.app import App
from comments_manager import MessageManager


def create_screen_manager():
    from settings import SettingsScreen
    from main import LoginScreen, MainScreen, SecondScreen, ThirdScreen
    sm = ScreenManager()
    sm.add_widget(LoginScreen(screen_manager=sm, name='login'))
    sm.add_widget(MainScreen(name='main'))
    sm.add_widget(SecondScreen(name='second'))
    sm.add_widget(ThirdScreen(screen_manager=sm, name='third'))
    sm.add_widget(SettingsScreen(name='settings'))
    return sm


class MyApp(App):
    def __init__(self, **kwargs):
        super(MyApp, self).__init__(**kwargs)
        self.user_id = None
        self.username = None
        self.key = None


    def build(self):
        return create_screen_manager()

    def on_login_success(self, user_id, username, key):
        from main import LoginScreen, DatabaseManager, MainScreen, SecondScreen, ThirdScreen
        from messagescreen import MessageScreen, UserListScreen
        from settings import SettingsScreen
        self.user_id = user_id
        self.username = username
        self.key = key
        self.root.clear_widgets()  # Clear the existing widgets/screens
        message_manager = MessageManager(user_id, username, key)
        # Create new instances of the screens with the necessary arguments
        message_screen = MessageScreen(user_id, username, message_manager, name='message_screen',
                                       database_manager=DatabaseManager("comments.db"))
        user_list_screen = UserListScreen(message_manager, self.root, DatabaseManager("comments.db"), name='UserList')
        login_screen = LoginScreen(screen_manager=self.root, name='login')
        main_screen = MainScreen(name='main')
        second_screen = SecondScreen(name='second')
        third_screen = ThirdScreen(screen_manager=self.root,
                                   name='third')
        settings_screen = SettingsScreen(name='settings')
        # Remove old instances of the screens
        for screen in ['message_screen', 'UserList', 'login', 'main', 'second', 'third', 'settings']:
            if self.root.has_screen(screen):
                self.root.remove_widget(self.root.get_screen(screen))
        # Add new instances of the screens
        self.root.add_widget(message_screen)
        self.root.add_widget(user_list_screen)
        self.root.add_widget(login_screen)
        self.root.add_widget(main_screen)
        self.root.add_widget(second_screen)
        self.root.add_widget(third_screen)
        self.root.add_widget(settings_screen)
        self.root.current = 'main'


if __name__ == '__main__':
    MyApp().run()




