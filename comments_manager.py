from kivy.uix.bubble import Bubble
from kivy.utils import get_color_from_hex
from kivy_garden.mapview import MapMarkerPopup
from kivy.uix.boxlayout import BoxLayout
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import RoundedRectangle, Color
from cryptography.fernet import Fernet
import sqlite3
import datetime
import logging
from encryption_manager import EncryptionManager
import os


# Get the key from the environment variable
key = os.getenv("ENCRYPTION_KEY")
# Create an instance of EncryptionManager
encryption_manager = EncryptionManager(key)


class MessageManager:
    def __init__(self, user_id, username, key):
        self.user_id = user_id
        self.username = username
        self.key = key
        self.cipher_suite = Fernet(self.key)
        self.conn = self.open_conn()
        self.cursor = self.conn.cursor()

    def open_conn(self):
        return sqlite3.connect("comments.db")

    def send_message(self, sender_id, receiver_id, message, thread_id):
        if isinstance(message, str) and thread_id is not None:
            encrypted_message = self.cipher_suite.encrypt(message.encode())  # Encrypt the message
            timestamp = datetime.datetime.utcnow()
            self.cursor.execute(
                "INSERT INTO messages (sender_id, receiver_id, message, timestamp, thread_id) VALUES (?, ?, ?, ?, ?)",
                (sender_id, receiver_id, encrypted_message, timestamp, thread_id))
            self.conn.commit()
            return True
        else:
            print("Error: message is not a string or thread_id is None")
            return False

    def get_messages(self, thread_id, sender_id, receiver_id):
        if thread_id is not None:
            self.cursor.execute(
                "SELECT id, sender_id, message, timestamp FROM messages WHERE thread_id=? AND ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)) ORDER BY timestamp ASC",
                (thread_id, sender_id, receiver_id, receiver_id, sender_id,))
            messages = self.cursor.fetchall()
            decrypted_messages = [(msg[0], msg[1], self.cipher_suite.decrypt(msg[2]).decode(), msg[3]) for msg in
                                  messages]  # Decrypt the message
            return decrypted_messages
        else:
            return []

    def delete_message(self, message_id, message_bubble):
        try:
            self.cursor.execute("DELETE FROM messages WHERE id=?", (message_id,))
            self.conn.commit()
            message_bubble.parent.remove_widget(message_bubble)  # Remove the message bubble from the UI
            return True
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            return False

    def get_user_id(self, username):
        self.cursor.execute("SELECT id FROM users WHERE username=?", (username,))
        user_id = self.cursor.fetchone()
        return user_id[0] if user_id else None

    def get_threads_messages(self, user_id, thread_id):
        self.cursor.execute("""
            SELECT message, timestamp FROM messages 
            WHERE (sender_id=? OR receiver_id=?) AND thread_id=?
            ORDER BY timestamp DESC
        """, (user_id, user_id, thread_id))
        messages = self.cursor.fetchall()
        decrypted_messages = [(self.cipher_suite.decrypt(msg[0]).decode(), msg[1]) for msg in messages]
        return decrypted_messages if messages else []

    def close(self):
        self.conn.close()


class CommentManager:
    def __init__(self, db_manager, api_manager):
        self.db_manager = db_manager
        self.api_manager = api_manager

    def get_comments_with_locations(self):
        user_id = App.get_running_app().user_id
        comments = self.db_manager.get_comments(user_id)
        comments_with_locations = []

        for id_, user_id, topic, comment, location, is_encrypted, is_anonymous, anonymous_username, username, timestamp in comments:
            lat_lng = self.api_manager.get_location_coordinates(location)
            if lat_lng:
                lat, lon = lat_lng['lat'], lat_lng['lng']
                if is_anonymous:
                    anonymous_username = 'Anonymous'
                else:
                    anonymous_username = username
                comments_with_locations.append(
                    (id_, user_id, topic, comment, location, lat, lon, is_anonymous, anonymous_username, username,
                     timestamp))

        return comments_with_locations


class CommentBubble(Bubble):
    def __init__(self, comment, is_anonymous, user_id, timestamp, screen_manager, **kwargs):
        super(CommentBubble, self).__init__(**kwargs)
        self.screen_manager = screen_manager
        self.size_hint = (None, None)
        self.size = (240, 180)
        self.orientation = "vertical"
        self.padding = "8dp"
        self.arrow_pos = "bottom_mid"
        self.user_id = user_id

        box = BoxLayout(orientation='vertical', size_hint_y=None)
        with box.canvas.before:
            Color(1, 1, 1, 1)
            self.rect = RoundedRectangle(size=box.size, pos=box.pos)

        if is_anonymous:
            lbl = Label(text="(Posted by: Anonymous)", color=(0, 0, 0, 1),
                        size_hint_y=None)
        else:
            lbl = Label(text=f"Posted by: {user_id}", bold=True, color=(0, 0, 0, 1), size_hint_y=None)
        box.add_widget(lbl)

        lbl = Label(text=comment, color=(0, 0, 0, 1), size_hint_y=None)

        lbl.text_size = (self.width * .9, None)
        lbl.halign = 'center'
        lbl.valign = 'middle'
        lbl.bind(texture_size=lbl.setter('size'))
        box.add_widget(lbl)

        # Create a new BoxLayout for the timestamp and the 'Message' button
        bottom_box = BoxLayout(orientation='horizontal', size_hint_y=None, height="30dp", spacing=10, padding=[5, 15, 5, 5])

        if not is_anonymous:
            self.message_button = Button(text='Message', size_hint_x=None, width="60dp", height=25)
            self.message_button.bind(on_release=self.go_to_message_screen)
            bottom_box.add_widget(self.message_button)

        timestamp_lbl = Label(text=timestamp, color=(0, 0, 0, 0.5), size_hint_x=None, width="60dp", font_size='10sp')
        bottom_box.add_widget(timestamp_lbl)

        box.add_widget(bottom_box)


        self.add_widget(box)

        box.bind(size=self.update_rect, pos=self.update_rect)

    def update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

    def go_to_message_screen(self, instance):
        from main import DatabaseManager
        # Fetch the receiver_id from the database
        database_manager = DatabaseManager("comments.db")
        receiver_id = database_manager.fetch_user_id(self.user_id)

        # Set the receiver_id in MessageScreen
        message_screen = self.screen_manager.get_screen('message_screen')
        sender_id = message_screen.sender_id
        message_screen.receiver_id = receiver_id
        thread_id = database_manager.get_thread_id(sender_id, receiver_id)
        if thread_id is None:
            thread_id = database_manager.create_new_thread_id()
        message_screen.thread_id = thread_id  # Set thread_id before calling update_messages
        message_screen.update_messages(sender_id, receiver_id, thread_id)
        self.screen_manager.current = 'message_screen'


class CommentMarker(MapMarkerPopup):
    def __init__(self, comment, is_anonymous, username, timestamp, color1, screen_manager, **kwargs):
        super(CommentMarker, self).__init__(**kwargs)
        self.color = get_color_from_hex(color1)
        self.comment = comment
        # Create a bubble and add it to the marker
        self.bubble = CommentBubble(comment, is_anonymous, username,timestamp, screen_manager)
        self.add_widget(self.bubble)
        # Initially make the bubble invisible
        self.bubble.opacity = 0
        self.bind(on_release=self.show_comment)

    def show_comment(self, *args):
        if self.bubble.opacity == 0:
            # Show the bubble
            self.bubble.opacity = 1
        else:
            # Hide the bubble
            self.bubble.opacity = 0
