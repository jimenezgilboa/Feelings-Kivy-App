from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.graphics import RoundedRectangle, Color
from kivy.app import App
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.bubble import Bubble
from datetime import datetime
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image


class UserLabel(Button):
    def __init__(self, text, id, user_list_screen, **kwargs):
        super(UserLabel, self).__init__(**kwargs)
        self.text = text
        self.id = id
        self.user_list_screen = user_list_screen
        self.bind(on_release=lambda instance: self.user_list_screen.user_selected(self.id))


class MessageBubble(Bubble):
    def __init__(self, message_id, sender, message, timestamp, delete_callback, **kwargs):
        super(MessageBubble, self).__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (360, 90)
        self.arrow_pos = 'bottom_left' if sender == "You" else 'bottom_right'
        self.padding = "8dp"
        self.pos_hint = {'x': 0} if sender == "You" else {'right': 1}
        self.background_color = [1, 1, 1, 1]
        self.border = [10, 10, 10, 10]
        self.bubble_border = [15, 15, 15, 15]
        self.color = [0, 0, 0, 1]

        self.lbl = Label(text=f"{message}", color=self.color, text_size=(self.width * .9, None), size_hint_y=None, halign='center', valign='middle')
        self.lbl.bind(texture_size=self.adjust_size)
        self.timestamp_lbl = Label(text=f"{timestamp.strftime('%H:%M')} {timestamp.strftime('%d/%m/%Y')}", font_size='10sp', halign='right', valign='bottom', color=self.color)  # Align to the right
        self.timestamp_lbl.bind(texture_size=self.adjust_size)
        self.delete_button = Button(text='Delete', size_hint=(None, None), size=(50, 50))
        self.delete_button.bind(on_release=lambda x: delete_callback(message_id, self))

        box_layout = BoxLayout(orientation='vertical', padding=(10, 10), spacing=20)
        box_layout.add_widget(self.lbl)

        bottom_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, padding=[0, 10, 0, 0])
        bottom_layout.add_widget(self.delete_button)
        bottom_layout.add_widget(self.timestamp_lbl)

        box_layout.add_widget(bottom_layout)

        layout = AnchorLayout(anchor_x='left' if sender == "You" else 'right', padding=(15, 15))
        layout.add_widget(box_layout)

        with layout.canvas.before:
            Color(1, 1, 1, 1)
            self.rect = RoundedRectangle(pos=layout.pos, size=layout.size)

        self.add_widget(layout)
        layout.bind(size=self.update_rect, pos=self.update_rect)

    def adjust_size(self, instance, value):
        # Set the height of the bubble to be the sum of the heights of the labels and the padding
        self.height = self.lbl.height + self.timestamp_lbl.height + 20

    def update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size


class MessageScreen(Screen):
    def __init__(self, user_id, username, message_manager, database_manager, receiver_id=None, **kwargs):
        super(MessageScreen, self).__init__(**kwargs)
        self.bg = Image(source='images/stars.jpg', pos_hint={'center_x': 0.5, 'center_y': 0.5},
                        size_hint=(1, 1), fit_mode='fill')
        self.add_widget(self.bg)
        self.database_manager = database_manager
        self.message_manager = message_manager
        self.user_id = App.get_running_app().user_id
        self.username = App.get_running_app().username
        self.receiver_id = receiver_id
        self.sender_id = self.user_id
        self.is_loading = False
        self.has_new_messages = False
        self.messages = []
        self.thread_id = None
        self.layout = BoxLayout(orientation='vertical')
        self.message_list = BoxLayout(orientation='vertical', size_hint_y=None)
        self.message_list.bind(minimum_height=self.message_list.setter('height'))
        self.scroll_view = ScrollView()
        self.scroll_view.add_widget(self.message_list)
        self.scroll_view.bind(scroll_y=self.check_scroll)
        send_layout = BoxLayout(size_hint=(1, None), height=60)
        self.message_input = TextInput(hint_text='Enter your message', size_hint=(4 / 5, None), size_hint_y=None,
                                       height=60)
        send_layout.add_widget(self.message_input)
        send_button = Button(text='Send', size_hint=(1 / 5, None), size_hint_y=None, height=60)
        send_layout.add_widget(send_button)
        send_button.bind(on_release=self.send_message)
        go_back_button = Button(text="Go back", size_hint=(0.2, None), pos_hint={'x': 0.1, 'top': 0.9},
                                color=[0, 0, 0, 1], height=60, on_release=self.go_back)
        self.layout.add_widget(go_back_button)
        self.layout.add_widget(self.scroll_view)
        self.layout.add_widget(send_layout)
        self.add_widget(self.layout)

    def check_scroll(self, instance, value):
        if value <= 0 and not self.is_loading and self.has_new_messages:
            self.is_loading = True
            thread_id = self.database_manager.get_thread_id(self.sender_id, self.receiver_id)
            self.update_messages(self.sender_id, self.receiver_id, thread_id)

    def send_message(self, instance):
        message = self.message_input.text
        if message:
            timestamp = datetime.now()
            sender = "You"
            thread_id = self.database_manager.get_thread_id(self.sender_id, self.receiver_id)
            if thread_id is None:
                thread_id = self.database_manager.create_new_thread_id()
            self.message_manager.send_message(self.sender_id, self.receiver_id, message, thread_id)
            self.message_input.text = ''
            self.update_messages(self.sender_id, self.receiver_id, thread_id)  # Update messages after sending
            self.has_new_messages = True

    def update_messages(self, sender_id, receiver_id, thread_id):
        self.messages.clear()
        self.message_list.clear_widgets()
        thread_id = self.database_manager.get_thread_id(self.sender_id, self.receiver_id)
        messages = self.message_manager.get_messages(self.thread_id, self.sender_id, self.receiver_id)
        new_messages = [msg for msg in messages if msg not in self.messages]
        self.messages = messages

        for message in new_messages:
            sender = "You" if message[1] == self.user_id else self.database_manager.fetch_username(message[1])
            timestamp = datetime.strptime(message[3], '%Y-%m-%d %H:%M:%S.%f')
            message_bubble = MessageBubble(message_id=message[0], sender=sender, message=message[2],
                                           timestamp=timestamp, delete_callback=self.message_manager.delete_message)
            self.message_list.add_widget(message_bubble)
        self.is_loading = False
        self.has_new_messages = False

    def open_new_chat(self, sender_id, receiver_id):
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.thread_id = None
        self.clear_messages()
        self.update_messages(sender_id, receiver_id, self.thread_id)

    def clear_messages(self):
        self.messages.clear()
        self.message_list.clear_widgets()
        self.thread_id = None

    def go_back(self, instance):
        self.manager.current = 'UserList'


class UserListScreen(Screen):
    def __init__(self, message_manager, screen_manager, database_manager, **kwargs):
        super(UserListScreen, self).__init__(**kwargs)
        self.message_manager = message_manager
        self.screen_manager = screen_manager
        self.database_manager = database_manager
        self.current_user_id = App.get_running_app().user_id
        self.thread_id = None
        self.layout = BoxLayout(orientation='vertical')
        go_back_button = Button(text="Go back", size_hint=(0.2, None), pos_hint={'x': 0.1, 'top': 0.9},
                                color=[0, 0, 0, 1], height=60)
        go_back_button.bind(on_press=self.go_back)
        self.layout.add_widget(go_back_button)
        refresh_button = Button(text="Refresh", size_hint=(0.2, None), pos_hint={'x': 0.8, 'top': 0.8})
        refresh_button.bind(on_press=self.refresh)
        self.layout.add_widget(refresh_button)
        self.user_list = BoxLayout(orientation='vertical', size_hint_y=None)
        self.user_list.bind(minimum_height=self.user_list.setter('height'))
        scroll_view = ScrollView()
        scroll_view.add_widget(self.user_list)
        self.layout.add_widget(scroll_view)
        self.user_list.data = [{'text': user[1], 'id': user[0]} for user in self.database_manager.get_users(
            current_user_id=self.current_user_id)]
        self.add_widget(self.layout)

    def on_pre_enter(self):
        self.update_user_list()

    def refresh(self, instance):
        self.update_user_list()

    def update_user_list(self):
        users = self.database_manager.get_users(current_user_id=self.current_user_id)
        self.user_list.clear_widgets()
        for user in users:
            label = UserLabel(user[1], user[0], self)
            self.user_list.add_widget(label)

    def user_selected(self, user_id):
        message_screen = self.screen_manager.get_screen('message_screen')
        message_screen.receiver_id = user_id
        self.thread_id = self.database_manager.get_thread_id(self.current_user_id, user_id)
        if self.thread_id is None:
            self.thread_id = self.database_manager.create_new_thread_id()
        message_screen.thread_id = self.thread_id
        message_screen.sender_id = self.current_user_id
        message_screen.update_messages(message_screen.sender_id, message_screen.receiver_id, self.thread_id)
        self.screen_manager.current = 'message_screen'

    def go_back(self, instance):
        self.manager.current = 'main'

