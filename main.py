import kivy
from kivy.config import Config
from datetime import datetime, timedelta
import os
from kivy.app import App
from kivy.graphics import RoundedRectangle, Color
from kivy.properties import StringProperty, DictProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.core.window import Window
from kivy.uix.textinput import TextInput
import sqlite3
from kivy.uix.widget import Widget
from kivy_garden.mapview import MapView
from kivy.clock import Clock
from kivy.uix.dropdown import DropDown
import requests
from kivy.uix.behaviors import ButtonBehavior
import binascii
from kivy.uix.spinner import Spinner
from bcrypt import gensalt, hashpw
from kivy.uix.image import Image
from comments_manager import CommentManager, CommentMarker, MessageManager
from encryption_manager import EncryptionManager


# Set the icon of the app
Config.set('kivy', 'window_icon', 'path_to_your_icon.png')

# Set the title of the app
Config.set('kivy', 'window_title', 'Your App Title')

# Set the orientation of the app
Config.set('kivy', 'orientation', 'portrait')

# Set the size of the app
Config.set('graphics', 'width', '440')
Config.set('graphics', 'height', '580')

Config.write()

# Convert hex color to RGB
color = '#3498db'  # Replace with your hex color
r = int(color[1:3], 16) / 255
g = int(color[3:5], 16) / 255
b = int(color[5:7], 16) / 255

your_api_key = os.getenv("API-KEY")
conn = sqlite3.connect('comments.db')
c = conn.cursor()


# Get the key from the environment variable
key = os.getenv("ENCRYPTION_KEY")
# Create an instance of EncryptionManager
encryption_manager = EncryptionManager(key)


kivy.require('2.1.0')


class RoundedButton(ButtonBehavior, Label):
    def __init__(self, **kwargs):
        super(RoundedButton, self).__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        with self.canvas.before:
            Color(rgba=self.color)  # Use button's color for RoundedRectangle
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[30])
        self.bind(pos=self.update_rect, size=self.update_rect)
        self.color = (1, 1, 1, 1)  # Set text color to white

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


class DatabaseManager:
    def __init__(self, db_comments):
        self.db_comments = db_comments
        self.conn = sqlite3.connect(self.db_comments)

    def insert_comment(self, user_id, topic, comment, location, is_private, is_anonymous):
        cursor = self.conn.cursor()
        timestamp = datetime.now().strftime('%d/%m/%y %H:%M')
        is_encrypted = 0
        if is_private:
            # Encryption using EncryptionManager
            comment = encryption_manager.encrypt_message(comment)
            is_encrypted = 1
        if is_anonymous:
            username = 'Anonymous'
        else:
            # Fetch the actual username from the users table
            cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
            username = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO comments (user_id, topic, comment, location, is_private, is_encrypted, is_anonymous, username, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, topic, comment, location, is_private, is_encrypted, is_anonymous, username, timestamp))
        self.conn.commit()

    def get_comments(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, user_id, topic, comment, location, is_encrypted, is_anonymous, anonymous_username, username, timestamp FROM comments WHERE is_private = 0 OR user_id = ?",
            (user_id,))
        comments = cursor.fetchall()
        decrypted_comments = []
        for comment in comments:
            if comment[5]:  # If the comment is encrypted
                # Decryption using EncryptionManager
                decrypted_comment = encryption_manager.decrypt_message(comment[3])
                comment = (
                    comment[0], comment[1], comment[2], decrypted_comment, comment[4], comment[5], comment[6],
                    comment[7], comment[8])
            decrypted_comments.append(comment)
        return decrypted_comments

    def update_user(self, user_id, new_username, new_password):
        cursor = self.conn.cursor()
        if new_username is not None:
            cursor.execute("UPDATE users SET username = ? WHERE id = ?", (new_username, user_id))
            cursor.execute("UPDATE comments SET anonymous_username = ? WHERE user_id = ? AND is_anonymous = 1",
                           (new_username, user_id))
        if new_password is not None:
            cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))
        self.conn.commit()

    def delete_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM comments WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()

    def update_privacy_mode(self, user_id, is_private):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE comments SET is_private = ? WHERE id = ?", (is_private, user_id))
        self.conn.commit()

    def get_users(self, current_user_id):
        with sqlite3.connect(self.db_comments) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT users.id, users.username FROM users
                JOIN messages ON users.id = messages.sender_id OR users.id = messages.receiver_id
                WHERE (messages.sender_id = ? OR messages.receiver_id = ?) AND users.id != ?
            """, (current_user_id, current_user_id, current_user_id,))
            users = cursor.fetchall()
            return users

    def get_thread_id(self, user1_id, user2_id):
        with sqlite3.connect(self.db_comments) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT thread_id FROM messages 
                WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
                ORDER BY timestamp DESC
                LIMIT 1
            """, (user1_id, user2_id, user2_id, user1_id))
            thread_id = cursor.fetchone()
            return thread_id[0] if thread_id else None

    def create_new_thread_id(self):
        with sqlite3.connect(self.db_comments) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO threads DEFAULT VALUES")
            new_thread_id = cursor.lastrowid
            conn.commit()
            return new_thread_id

    def get_thread_ids(self, user_id):
        with sqlite3.connect(self.db_comments) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT thread_id FROM messages
                WHERE sender_id = ? OR receiver_id = ?
            """, (user_id, user_id,))
            thread_ids = [row[0] for row in cursor.fetchall()]
            return thread_ids

    def fetch_user_id(self, username):
        with sqlite3.connect(self.db_comments) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            user_ids = cursor.fetchone()
            if user_ids is not None:
                user_id = user_ids[0]
                return user_id
            else:
                return None

    def fetch_username(self, user_id):
        with sqlite3.connect(self.db_comments) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
            usernames = cursor.fetchone()
            if usernames is not None:
                username = usernames[0]
                return username

    def fetch_key(self):
        key = os.getenv("ENCRYPTION_KEY")
        return key.encode()

    def close(self):
        self.conn.close()


class APIManager:
    def __init__(self, api_key):
        self.api_key = api_key

    def get_location_coordinates(self, location):
        url = f'https://api.opencagedata.com/geocode/v1/json?q={location}&key={self.api_key}'
        response = requests.get(url)
        data = response.json()
        if 'results' in data and data['results']:
            return data['results'][0]['geometry']


class BaseScreen(Screen):

    def __init__(self, **kwargs):
        super(BaseScreen, self).__init__(**kwargs)
        self.session = {}
        # Set the session timeout in minutes
        self.session_timeout = 30
        # Start the session
        self.start_session()

    def create_button(self, text, color, on_press_method):
        btn = RoundedButton(text=text,
                            font_name="dejavusans",
                            color=color,
                            size_hint=(0.5, None), height=60,
                            pos_hint={'center_x': 0.5})
        btn.bind(on_press=on_press_method)
        return btn

    def create_text_input(self, hint_text, multiline=False, password=False,
                          height=60, size_hint=(1, None)):
        return TextInput(hint_text=hint_text, multiline=multiline, password=password,
                         height=height, size_hint=size_hint)

    def logout(self):
        # Clear session data
        self.clear_session_data()

        # Redirect to login screen
        self.manager.current = 'login'

    def clear_session_data(self):
        self.session = {}

    def start_session(self):
        self.session['user_id'] = App.get_running_app().user_id
        self.session_expiration = datetime.now() + timedelta(minutes=self.session_timeout)
        Clock.schedule_interval(self.check_session, 60)

    def check_session(self, dt):
        # Check if the current time is past the session expiration time
        if datetime.now() > self.session_expiration:
            # Session has expired, logout
            self.logout()
            # Unschedule check_session
            Clock.unschedule(self.check_session)

    def update_session(self):
        # Update session expiration time
        # This is the current time plus the session timeout
        self.session_expiration = datetime.now() + timedelta(minutes=self.session_timeout)

    def on_touch_down(self, touch):
        # Call the parent method
        super(BaseScreen, self).on_touch_down(touch)

        # Update the session
        self.update_session()

    def on_enter(self, *args):
        # Call the parent method
        super(BaseScreen, self).on_enter(*args)

        # Update the session
        self.update_session()


class LoginScreen(BaseScreen):
    def __init__(self, screen_manager, **kwargs):
        super(LoginScreen, self).__init__(**kwargs)
        self.screen_manager = screen_manager

        # Add a background image to the screen
        self.bg = Image(source='images/abs_col.jpg', pos_hint={'center_x': 0.5, 'center_y': 0.5},
                        size_hint=(1, 1), fit_mode='fill')
        self.add_widget(self.bg)

        layout = BoxLayout(orientation='vertical', size_hint=(1, None), padding=[50, 0], spacing=4)
        layout.bind(minimum_height=layout.setter('height'))

        self.username = self.create_text_input('Enter your username')
        self.password = self.create_text_input('Enter your password', password=True)
        self.confirm_password = self.create_text_input('Confirm your password', password=True)
        self.confirm_password.opacity = 0  # Initially hidden

        sign_up_button = self.create_button('Sign up', [0, 0, 0, 1], self.sign_up)
        sign_in_button = self.create_button('Sign in', [0, 0, 0, 1], self.sign_in)

        layout.add_widget(self.username)
        layout.add_widget(self.password)
        layout.add_widget(self.confirm_password)  # Add it to your layout
        layout.add_widget(sign_up_button)

        # Add a spacer
        spacer = BoxLayout(size_hint_y=None, height=5)
        layout.add_widget(spacer)

        layout.add_widget(sign_in_button)

        anchor_layout = AnchorLayout(anchor_x='center', anchor_y='center')
        anchor_layout.add_widget(layout)  # Add the BoxLayout to the AnchorLayout
        self.add_widget(anchor_layout)  # Add the AnchorLayout to the screen

        # Add a spacer
        spacer = Widget(size_hint_y=None, height=50)
        layout.add_widget(spacer)

        # Create a label for error messages
        self.error_label = Label(text='', color=[1, 0, 0, 1])  # Red color for error messages
        layout.add_widget(self.error_label)

    def sign_in(self, instance):
        username = self.username.text
        password = self.password.text
        if len(username) < 3 or len(username) > 20:
            self.error_label.text = "Username must be between 3 and 20 characters"
            return
        if not username.isalnum():
            self.error_label.text = "Username must be alphanumeric"
            return

        # Check if username or password is empty
        if not username or not password:
            self.error_label.text = "Please enter a username and password"
            return

        c.execute('''SELECT * FROM users WHERE username = ?''', (username,))
        user = c.fetchone()
        if user is not None:
            # The username exists, now we check the password
            stored_password = user[2]  # assuming 'password' is the third column
            stored_password = binascii.unhexlify(stored_password.encode('utf-8'))

            # Hash the input password with the stored hashed password (which includes the salt)
            hashed_password = hashpw(password.encode('utf-8'), stored_password)

            if hashed_password == stored_password:
                user_id = user[0]  # Store the user ID
                username = user[1]  # Store the username
                key = os.getenv("ENCRYPTION_KEY").encode()
                # Set the logged_in status to 1 for the current user
                self.message_manager = MessageManager(user_id, username, key)
                c.execute("UPDATE users SET logged_in = 1 WHERE id = ?", (user_id,))
                conn.commit()
                app = App.get_running_app()
                app.user_id = user_id
                app.username = username
                app.key = key
                app.on_login_success(user_id, username, key)
                self.screen_manager.current = 'main'
            else:
                # The password is incorrect
                self.error_label.text = "Incorrect username or password"
        else:
            # The username does not exist
            self.error_label.text = "Incorrect username or password"

    def sign_up(self, instance):
        self.confirm_password.opacity = 1  # Make the confirmed password field visible
        username = self.username.text
        password = self.password.text
        confirm_password = self.confirm_password.text
        if username and password:  # Check if both fields are not empty
            if password == confirm_password:
                # Generate a unique salt for each user
                salt = gensalt()

                # Hash the password with the salt
                hashed_password = hashpw(password.encode('utf-8'), salt)

                hashed_password = binascii.hexlify(hashed_password).decode('utf-8')

                c.execute('''SELECT COUNT(*) FROM users''')
                user_count = c.fetchone()[0]

                if user_count == 0:
                    # If there are no existing users, make this user an admin
                    c.execute('''INSERT INTO users (username, password, admin) VALUES (?, ?, 1)''',
                              (username, hashed_password))
                else:
                    c.execute('''INSERT INTO users (username, password) VALUES (?, ?)''', (username, hashed_password))

                conn.commit()
                # After inserting the new user into the database
                c.execute('''SELECT id FROM users WHERE username = ?''', (username,))
                user_id = c.fetchone()[0]

                # Set the user_id in your MyApp instance
                App.get_running_app().user_id = user_id

                self.manager.current = 'main'  # Switch to the main screen
            else:
                self.error_label.text = "Passwords do not match. Try again."

    def new_session(self):
        # Get the current user's id
        user_id = App.get_running_app().user_id
        # Set the logged_in status to 0 for the current user
        c.execute("UPDATE users SET logged_in = 0 WHERE id = ?", (user_id,))
        conn.commit()
        # Clear the username and password fields
        self.username.text = ""
        self.password.text = ""

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size


class MainScreen(BaseScreen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        Window.clearcolor = (r, g, b, 1)

        # Add a background image to the screen
        self.bg = Image(source='images/back4.jpg', pos_hint={'center_x': 0.5, 'center_y': 0.5},
                        size_hint=(1, 1), fit_mode='fill')
        self.add_widget(self.bg)

        user_list_button = RoundedButton(text='User List', size_hint=(0.2, None), color=[0, 154, 193, 0.73], height=60)
        layout1 = AnchorLayout(anchor_x='right', anchor_y='bottom')
        user_list_button.bind(on_release=self.go_to_user_list)
        layout1.add_widget(user_list_button)
        self.add_widget(layout1)

        settings_button = Button(background_normal='images/gear_wheel.png', size_hint=(.1, .1),
                                 pos_hint={"right": 0.95, "top": 1})
        settings_button.bind(on_press=self.open_settings)
        # Add the button to the top right corner using an AnchorLayout
        layout = AnchorLayout(anchor_x='right', anchor_y='top')
        layout.add_widget(settings_button)
        self.add_widget(layout)

        layout = BoxLayout(orientation='vertical', padding=[50, 50, 50, 50], spacing=10)

        # Add go-back button at the top
        go_back_button = RoundedButton(text="Go back", size_hint=(0.2, None), pos_hint={'x': 0.03, 'top': 0.98},
                                       color=[15, 1605, 170, 0.25], height=60)
        go_back_button.bind(on_press=self.go_back)
        self.add_widget(go_back_button)
        app_name = Label(text="My app", font_size='80sp', font_name='KINKIE__.TTF',
                         pos_hint={'center_x': 0.5}, height=280, color=(0.41, 0.42, 0.74, 1), size_hint=(1, None))
        layout.add_widget(app_name)
        label = Label(text="Please select the corresponding button", font_name="dejavusans", size_hint=(1, None),
                      pos_hint={'center_x': .5}, height=40, color=(0, 0, 0, 1))
        layout.add_widget(label)

        self.colors = {'Anger': '#FF0000', 'Envy': '#00FF00', 'Sadness': '#0000FF', 'Joy': '#FFFF00',
                       'Shame': '#00FFFF', 'Happiness': '#FF00FF', 'Indifference': '#33a68b'}

        for topic, color2 in self.colors.items():
            btn = self.create_button(topic,
                                     [int(color2[j:j + 2], 16) / 255 for j in (1, 3, 5)],
                                     self.switch_screen)
            layout.add_widget(btn)

        self.add_widget(layout)

        # Add log out button at the bottom left corner using an AnchorLayout
        log_out_button = RoundedButton(text="Log out", size_hint=(0.2, None),
                                       color=[0, 154, 193, 0.73], height=60)
        log_out_button.bind(on_press=self.log_out)
        layout = AnchorLayout(anchor_x='left', anchor_y='bottom')
        layout.add_widget(log_out_button)
        self.add_widget(layout)

    def switch_screen(self, instance):  # Define switch_screen method
        self.manager.current = 'second'  # Switch to second screen
        self.manager.get_screen('second').topic = instance.text  # Pass button text as topic
        self.manager.get_screen('third').color = self.colors[instance.text]  # Pass color of the topic
        self.manager.get_screen('third').colors = self.colors  # Pass the colors dictionary

    def go_back(self, instance):
        self.manager.current = 'login'

    def open_settings(self, instance):
        self.manager.transition.direction = 'left'  # Slide from right to left
        self.manager.current = 'settings'  # Switch to the settings screen

    def go_to_user_list(self, instance):
        self.manager.current = 'UserList'

    def log_out(self, instance):
        self.manager.current = 'login'  # Switch to the login screen
        self.manager.get_screen('login').new_session()  # Call the new session method to reset the login screen

    def new_session(self):
        # This method will clear the username and password fields and reset the login status
        self.username.text = ""
        self.password.text = ""
        self.login_status.text = ""


class AutocompleteTextInput(TextInput):
    def __init__(self, dropdown_parent=None, **kwargs):
        super(AutocompleteTextInput, self).__init__(**kwargs)
        self.api_manager = APIManager('your_api_key')
        self.dropdown = DropDown(max_height=200, size_hint=(1, None), height=60)
        self.dropdown_parent = dropdown_parent
        self.dropdown.background_color = [1, 0, 0, 1]  # Set to red for visibility
        self.bind(text=self.on_text)
        self.bind(on_focus=self.on_focus)
        self.timer = None

    def on_text(self, instance, value):
        if self.timer:
            self.timer.cancel()
        self.timer = Clock.schedule_once(lambda dt: self.get_suggestions(value), 1)
        if value:
            if self.dropdown.parent:
                self.dropdown.parent.remove_widget(self.dropdown)
            if self.dropdown_parent:
                self.dropdown_parent.add_widget(self.dropdown)
        else:
            if self.dropdown.parent:
                self.dropdown.parent.remove_widget(self.dropdown)

    def on_focus(self, instance, value):
        if value and self.text:
            self.dropdown.open(self)
        else:
            self.dropdown.dismiss()

    def get_suggestions(self, value):
        if value and len(value) <= 150:
            try:
                url = f'https://api.opencagedata.com/geocode/v1/json?q={value}&key={your_api_key}'
                response = requests.get(url)
                data = response.json()
                if 'results' in data and data['results']:
                    self.dropdown.clear_widgets()
                    for result in data['results']:
                        btn1 = Button(text=result['formatted'], size_hint_y=None,
                                      height=44, background_color=[0, 1, 0, 1])
                        btn1.bind(on_release=lambda btn1: self.select_suggestion(btn1.text))
                        self.dropdown.add_widget(btn1)
            except Exception as e:
                print(f"Failed to get suggestions for location '{value}': {e}")
        else:
            if not value:
                print('Invalid input: input is empty')
            elif len(value) > 150:
                print('Invalid input: input is too long')

    def select_suggestion(self, text):
        self.text = text
        self.dropdown.dismiss()

    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        if keycode[1] == 'tab':
            if self.dropdown.children:
                self.dropdown.select(self.dropdown.children[0].text)
            return True
        return super(AutocompleteTextInput, self).keyboard_on_key_down(window, keycode, text, modifiers)


class SecondScreen(BaseScreen):
    def __init__(self, **kwargs):
        super(SecondScreen, self).__init__(**kwargs)
        self.db_manager = DatabaseManager('comments.db')

        # Add a background image to the screen
        self.bg = Image(source='images/back3.jpg', pos_hint={'center_x': 0.5, 'center_y': 0.5},
                        size_hint=(1, 1), fit_mode='fill')
        self.add_widget(self.bg)

        # Add log out button at the bottom left corner using an AnchorLayout
        log_out_button = RoundedButton(text="Log out", size_hint=(0.2, None),
                                       color=[0, 154, 193, 0.73], height=60)
        layout = AnchorLayout(anchor_x='left', anchor_y='bottom')
        layout.add_widget(log_out_button)
        self.add_widget(layout)

        user_list_button = RoundedButton(text='User List', size_hint=(0.2, None), color=[0, 154, 193, 0.73], height=60)
        layout1 = AnchorLayout(anchor_x='right', anchor_y='bottom')
        user_list_button.bind(on_release=self.go_to_user_list)
        layout1.add_widget(user_list_button)
        self.add_widget(layout1)

        grid_layout = GridLayout(rows=3)
        self.add_widget(grid_layout)
        # Create a BoxLayout for the top row
        top_layout = BoxLayout()
        # Add go-back button at the top
        go_back_button = RoundedButton(text="Go back", size_hint=(0.2, None), pos_hint={'x': 0.1, 'top': 0.9},
                                       color=[0, 0, 0, 1], height=60)
        go_back_button.bind(on_press=self.go_back)
        top_layout.add_widget(go_back_button)

        # Add empty widget to take up remaining space in the top row
        top_layout.add_widget(Widget())
        grid_layout.add_widget(top_layout)

        layout = BoxLayout(orientation='vertical', padding=[50, 50, 50, 50], spacing=10)
        self.topic_label = Label(text="", font_name="dejavusans", size_hint=(1, None), height=40)
        layout.add_widget(self.topic_label)

        self.text_input = TextInput(text="", multiline=False, hint_text="enter your thoughts here",
                                    size_hint=(1, None), height=60)
        layout.add_widget(self.text_input)
        self.dropdown_parent = BoxLayout()
        layout.add_widget(self.dropdown_parent)

        self.location_input = AutocompleteTextInput(dropdown_parent=self.dropdown_parent,
                                                    text="", hint_text="enter your location here", multiline=False,
                                                    size_hint=(1, None),
                                                    height=60)
        layout.add_widget(self.location_input)
        self.submit_button = Button(text="Submit", font_name="dejavusans", size_hint=(0.5, None), height=60,
                                    pos_hint={'center_x': 0.5})
        self.submit_button.bind(on_press=self.publish)
        layout.add_widget(self.submit_button)
        grid_layout.add_widget(layout)

        # Add empty BoxLayout at the bottom
        grid_layout.add_widget(BoxLayout())

    @property
    def topic(self):  # Define topic property
        return self.topic_label.text

    @topic.setter
    def topic(self, value):  # Set topic property and update label text
        self.topic_label.text = value

    def publish(self, instance):
        comment = self.text_input.text.strip()
        location = self.location_input.text.strip()
        if comment and len(comment) <= 500:
            try:
                user_id = App.get_running_app().user_id
                is_private = 1 if self.manager.get_screen('settings').is_private else 0
                is_anonymous = 1 if self.manager.get_screen('settings').is_anonymous else 0
                self.db_manager.insert_comment(user_id, self.topic, comment, location, is_private, is_anonymous)
                self.text_input.text = ""
                self.location_input.text = ""
                self.manager.current = 'third'
            except sqlite3.Error as e:
                print(f"An error occurred: {e}")
        else:
            print('Invalid input!')

    def on_button_press(self, button):
        self.manager.get_screen('third').topic = button.text
        self.manager.get_screen('third').color = self.colors[button.text]

    def go_to_user_list(self, instance):
        self.manager.current = 'UserList'

    def go_back(self, instance):
        self.manager.current = 'main'


class ThirdScreen(BaseScreen):
    topic = StringProperty()
    color = StringProperty()
    colors = DictProperty()

    def __init__(self, screen_manager, **kwargs):
        super(ThirdScreen, self).__init__(**kwargs)
        self.db_manager = DatabaseManager('comments.db')
        self.api_manager = APIManager(your_api_key)
        self.comment_manager = CommentManager(self.db_manager, self.api_manager)
        self.screen_manager = screen_manager
        self.current_marker = None
        self.timer = None
        self.map_view = MapView(zoom=11, lat=48.8534, lon=2.3488)  # Initialize map view
        self.add_widget(self.map_view)

        # Create a spinner
        self.spinner = Spinner(text='Loading...', values=('Loading...',), size_hint=(None, None), size=(100, 44))
        self.spinner.active = False  # Set the spinner to inactive initially
        add_comment_button = RoundedButton(text="+ Add another comment", size_hint=(0.5, None),
                                       pos_hint={'x': 0.7, 'top': 0.9},
                                       color=[0, 0, 0, 1], height=60, halign='center')
        add_comment_button.bind(on_press=self.go_back)
        self.add_widget(add_comment_button)

        # Create a BoxLayout for the search bar and button
        search_layout = BoxLayout(size_hint=(1, None), height=50)

        # Create the search bar
        self.search_bar = TextInput(hint_text='Search comments', multiline=False)
        search_layout.add_widget(self.search_bar)

        # Initialize search_results and current_result_index
        self.search_results = []
        self.current_result_index = 0
        # Create the search button
        search_button = self.create_button(text='Search',
                                           color=(0, 0, 125, 0.5), on_press_method=self.on_search_button_press)
        search_layout.add_widget(search_button)

        # Add the BoxLayout to the screen
        self.add_widget(search_layout)
        self.markers = []  # List to keep track of all markers

        # Create the "Next" and "Previous" buttons
        self.next_button = self.create_button(text='Next', color=(0, 0, 0, 1),
                                              on_press_method=self.on_next_button_press)
        self.prev_button = self.create_button(text='Previous', color=(0, 0, 0, 1),
                                              on_press_method=self.on_prev_button_press)

        # Add the buttons to the layout
        search_layout.add_widget(self.prev_button)
        search_layout.add_widget(self.next_button)

        # Disable the buttons initially
        self.next_button.disabled = True
        self.prev_button.disabled = True

    def on_enter(self):
        # Show the loading spinner
        self.spinner.active = True
        self.spinner.center_x = self.width / 2  # Center the spinner horizontally
        self.spinner.center_y = self.height / 2  # Center the spinner vertically
        self.add_widget(self.spinner)

        # Schedule the long-running operation to run after a delay
        Clock.schedule_once(self.fetch_locations_and_add_markers, 0)

    def fetch_locations_and_add_markers(self, dt):
        comments_with_locations = self.comment_manager.get_comments_with_locations()

        for (id_, user_id, topic, comment, location, lat, lon,
             is_anonymous, anonymous_username, username, timestamp) in comments_with_locations:

            # Remove 'Topic: ' from the topic string
            topic = topic.replace('Topic: ', '')
            color1 = self.colors.get(topic, '#FF0000')  # Get the color for the topic, or default to red
            marker = CommentMarker(comment=comment, is_anonymous=is_anonymous, username=username, timestamp=timestamp, lat=lat, lon=lon,
                                   color1=color1, screen_manager=self.screen_manager)
            self.markers.append(marker)
            self.map_view.add_widget(marker)
            self.map_view.center_on(lat, lon)

        # Hide the loading spinner
        self.spinner.active = False
        self.remove_widget(self.spinner)

    def create_callback(self, location, comment):
        return lambda dt: self.get_location_coordinates(location, comment)

    def on_search_button_press(self, instance):
        # Get the text from the search bar
        search_text = self.search_bar.text

        # Clear all markers from the map view
        for marker in self.markers:
            self.map_view.remove_widget(marker)
        self.current_marker = None

        # Filter comments that match the search text
        user_id = App.get_running_app().user_id
        self.search_results = [comment for comment in self.db_manager.get_comments(user_id) if search_text in comment[3]]

        # Reset the current result index
        self.current_result_index = 0

        # Display the first search result if there is one
        if self.search_results:
            self.next_button.disabled = False
            self.prev_button.disabled = False
            self.update_display()

    def update_display(self):
        # Remove old marker from map view
        if self.current_marker:
            self.map_view.remove_widget(self.current_marker)

        # Add new marker to map view
        comment = self.search_results[self.current_result_index]
        lat_lng = self.api_manager.get_location_coordinates(comment[4])
        if lat_lng:
            lat, lon = lat_lng['lat'], lat_lng['lng']

            # Ensure you're not accessing an index that doesn't exist
            username = comment[8] if len(comment) > 8 else None
            timestamp = comment[9] if len(comment) > 9 else None

            marker = CommentMarker(comment=comment[3], is_anonymous=comment[7], username=username, timestamp=timestamp, lat=lat, lon=lon,
                                   color1=self.color, screen_manager=self.screen_manager)
            self.current_marker = marker
            self.map_view.add_widget(marker)
            self.map_view.center_on(lat, lon)
            self.db_manager.close()

    def on_next_button_press(self, instance):
        # Increment the current result index and wrap around if necessary
        if self.search_results:
            self.current_result_index = (self.current_result_index + 1) % len(self.search_results)
            self.update_display()

    def on_prev_button_press(self, instance):
        # Decrement the current result index and wrap around if necessary
        if self.search_results:
            self.current_result_index = (self.current_result_index - 1) % len(self.search_results)
            self.update_display()

    def go_back(self, instance):
        self.manager.current = 'main'



