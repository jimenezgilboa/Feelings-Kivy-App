from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.anchorlayout import AnchorLayout
from kivy.app import App
from main import RoundedButton, DatabaseManager, BaseScreen
from kivy.uix.popup import Popup
from bcrypt import gensalt, hashpw
from kivy.uix.label import Label
import binascii
from kivy.uix.image import Image


class SettingsScreen(BaseScreen):
    def __init__(self, **kwargs):
        super(SettingsScreen, self).__init__(**kwargs)
        self.bg = Image(source='images/back4.jpg', pos_hint={'center_x': 0.5, 'center_y': 0.5},
                        size_hint=(1, 1), fit_mode='fill')
        self.add_widget(self.bg)
        self.db_manager = DatabaseManager('comments.db')
        self.is_private = False

        self.is_anonymous = False

        layout = BoxLayout(orientation='vertical', size_hint=(1, None), padding=[50, 0], spacing=10)
        layout.bind(minimum_height=layout.setter('height'))

        self.privacy_button = Button(text='Switch to Private Mode', size_hint=(0.5, None),
                                     pos_hint={'center_x': 0.5, 'center_y': 0.5},
                                     height=60, halign='center')

        self.privacy_button.bind(on_release=self.on_privacy_button_release)
        layout.add_widget(self.privacy_button)
        self.anonymous_button = Button(text='Switch to Anonymous Mode', size_hint=(0.5, None),
                                       pos_hint={'center_x': 0.5, 'center_y': 0.5},
                                       height=60, halign='center')

        self.anonymous_button.bind(on_release=self.on_anonymous_button_release)
        layout.add_widget(self.anonymous_button)

        # Add a spacer
        spacer = BoxLayout(size_hint_y=None, height=5)
        layout.add_widget(spacer)
        # Add go-back button at the top
        go_back_button = RoundedButton(text="Go back", size_hint=(0.2, None), pos_hint={'x': 0.03, 'top': 0.98},
                                       color=[15, 1605, 170, 0.25], height=60)
        go_back_button.bind(on_press=self.go_back)
        layout.add_widget(go_back_button)
        # Add a spacer
        spacer = BoxLayout(size_hint_y=None, height=5)
        layout.add_widget(spacer)

        self.delete_account_button = Button(text='Delete Account', size_hint=(0.28, None),
                                            pos_hint={'x': 0.74, 'top': 0.98},
                                            height=60, font_size=18)

        self.delete_account_button.bind(on_release=self.confirm_delete_account)
        layout.add_widget(self.delete_account_button)
        # Add a spacer
        spacer = BoxLayout(size_hint_y=None, height=5)
        layout.add_widget(spacer)

        self.username_input = TextInput(hint_text='New username', multiline=False, size_hint=(1, None), height=60)
        self.password_input = TextInput(hint_text='New password', password=True, multiline=False,
                                        size_hint=(1, None), height=60)
        change_username_button = Button(text='Change Username', font_name="dejavusans", size_hint=(0.5, None),
                                        height=60, pos_hint={'center_x': 0.5})
        change_username_button.bind(on_press=self.change_username)
        change_password_button = Button(text='Change Password', font_name="dejavusans", size_hint=(0.5, None),
                                        height=60, pos_hint={'center_x': 0.5})
        change_password_button.bind(on_press=self.change_password)
        layout.add_widget(self.username_input)
        layout.add_widget(change_username_button)
        layout.add_widget(self.password_input)
        layout.add_widget(change_password_button)

        anchor_layout = AnchorLayout(anchor_x='center', anchor_y='center')
        anchor_layout.add_widget(layout)  # Add the BoxLayout to the AnchorLayout
        self.add_widget(anchor_layout)  # Add the AnchorLayout to the screen

    def show_message(self, title, text):
        popup = Popup(title=title, content=Label(text=text), size_hint=(None, None), size=(400, 200))
        popup.open()

    def change_username(self, instance):
        new_username = self.username_input.text
        if len(new_username) < 3 or len(new_username) > 20:
            self.error_label.text = "Username must be between 3 and 20 characters"
            return
        if not new_username.isalnum():
            self.error_label.text = "Username must be alphanumeric"
            return

        # Check if username is empty
        if not new_username:
            self.error_label.text = "Please enter a username"
            return

        user_id = App.get_running_app().user_id  # Get the user ID
        db_manager = DatabaseManager('comments.db')
        db_manager.update_user(user_id, new_username, None)  # Update the username
        db_manager.close()
        self.show_message('Success', 'Username changed successfully')  # Show a message to the user

    def change_password(self, instance):
        new_password = self.password_input.text
        # Generate a unique salt for each user
        salt = gensalt()
        # Hash the password with the salt
        hashed_password = hashpw(new_password.encode('utf-8'), salt)
        hashed_password = binascii.hexlify(hashed_password).decode('utf-8')
        user_id = App.get_running_app().user_id  # Get the user ID
        db_manager = DatabaseManager('comments.db')
        db_manager.update_user(user_id, None, hashed_password)  # Update the password with the hashed one
        db_manager.close()
        self.show_message('Success', 'Password changed successfully')  # Show a message to the user

    def confirm_delete_account(self, instance):
        box = BoxLayout(orientation='vertical')
        box.add_widget(Label(text='Are you sure you want to delete your account?\n    This action cannot be undone.'))
        popup = Popup(title='Confirm Delete Account', content=box, size_hint=(None, None), size=(600, 300))
        yes_button = Button(text='Yes')
        yes_button.bind(on_press=self.delete_account)
        yes_button.bind(on_press=popup.dismiss)
        no_button = Button(text='No', on_press=popup.dismiss)
        box.add_widget(yes_button)
        box.add_widget(no_button)
        popup.open()

    def delete_account(self, instance):
        user_id = App.get_running_app().user_id
        self.db_manager.delete_user(user_id)
        self.manager.current = 'login'
        self.username_input.text = ''
        self.password_input.text = ''

    def on_privacy_button_release(self, instance):
        self.is_private = not self.is_private
        user_id = App.get_running_app().user_id
        self.db_manager.update_privacy_mode(user_id, self.is_private)

        if self.is_private:
            self.privacy_button.text = 'Switch to Public Mode'
            self.privacy_button.color = [0, 1, 0, 1]  # Green for public mode
        else:
            self.privacy_button.text = 'Switch to Private Mode'
            self.privacy_button.color = [1, 0, 0, 1]  # Red for private mode

    def on_anonymous_button_release(self, instance):
        self.is_anonymous = not self.is_anonymous

        if self.is_anonymous:
            self.anonymous_button.text = 'Switch to Regular Mode'
            self.anonymous_button.color = [1, 1, 1, 1]  # White for public mode
        else:
            self.anonymous_button.text = 'Switch to Anonymous Mode'
            self.anonymous_button.color = [0, 0, 0, 0]  # Red for private mode

    def go_back(self, instance):
        self.manager.current = 'main'
