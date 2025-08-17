# main.py
import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.gridlayout import GridLayout
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, RoundedRectangle
from kivy.config import Config

from together import Together
import threading
import re

# Set window configuration for proper keyboard handling
Config.set('kivy', 'keyboard_mode', 'systemanddock')
Config.set('kivy', 'keyboard_layout', 'qwerty')


api_key = "Api_here"
client = Together(api_key=api_key)

Window.size = (720, 1600)
Window.clearcolor = get_color_from_hex("#121212")  # Dark background

class ChatUI(BoxLayout):
    def __init__(self, **kwargs):
        super(ChatUI, self).__init__(orientation='vertical', spacing=5, padding=[10, 10, 10, 10], **kwargs)
        
        # Set keyboard behavior
        Window.softinput_mode = 'below_target'
        
        # Main chat area
        self.scroll = ScrollView(
            size_hint=(1, 1), 
            do_scroll_x=False, 
            bar_width=10,
            scroll_distance=100
        )
        self.chat_history = GridLayout(
            cols=1, 
            spacing=8, 
            size_hint_y=None,
            padding=[0, 0, 0, 20]  # Add bottom padding
        )
        self.chat_history.bind(minimum_height=self.chat_history.setter('height'))
        self.scroll.add_widget(self.chat_history)
        self.add_widget(self.scroll)

        # Input area at the bottom
        self.input_layout = BoxLayout(
            size_hint=(1, None), 
            height=80, 
            spacing=5,
            padding=[0, 0, 0, 5]  # Add bottom padding for keyboard
        )
        self.user_input = TextInput(
            hint_text='Talk to Sofia...',
            multiline=False,
            size_hint=(0.7, 1),
            background_color=get_color_from_hex("#1E1E1E"),
            foreground_color=get_color_from_hex("#FFFFFF"),
            cursor_color=get_color_from_hex("#00FFAA"),
            padding=10,
            write_tab=False
        )
        self.send_button = Button(
            text='Send',
            size_hint=(0.3, 1),
            background_color=get_color_from_hex("#00FFAA"),
            color=get_color_from_hex("#000000"),
            bold=True
        )
        self.send_button.bind(on_press=self.send_message)
        self.input_layout.add_widget(self.user_input)
        self.input_layout.add_widget(self.send_button)
        self.add_widget(self.input_layout)

        # Track keyboard state
        self.keyboard_active = False
        
        # Bind keyboard events
        Window.bind(on_keyboard=self._keyboard_handler)
        self.user_input.bind(focus=self.on_focus)

        # Track if we should auto-scroll
        self.auto_scroll = True

    def _keyboard_handler(self, window, key, *args):
        # Handle Android back button
        if key == 27:  # Escape key (back button on Android)
            if self.keyboard_active:
                self.user_input.focus = False
                return True
        return False
    
    def on_focus(self, instance, value):
        if value:
            # Keyboard is showing
            self.keyboard_active = True
            # Scroll to bottom after keyboard appears
            Clock.schedule_once(self.scroll_to_bottom, 0.3)
        else:
            # Keyboard is hiding
            self.keyboard_active = False
            # Scroll to bottom after keyboard hides
            Clock.schedule_once(self.scroll_to_bottom, 0.1)

    def scroll_to_bottom(self, dt=None):
        """Simple and reliable scroll to bottom"""
        self.scroll.scroll_y = 0

    def add_message(self, text, is_user=True):
        bg = "#222222" if is_user else "#00FFAA"
        fg = "#FFFFFF" if is_user else "#000000"
        bubble = Label(
            text=text,
            size_hint_y=None,
            halign='left' if is_user else 'right',
            valign='top',
            padding=(15, 15),
            text_size=(self.width * 0.8, None),
            color=get_color_from_hex(fg),
            markup=True,
            font_size=16,
        )
        # Properly constrained bubble size
        bubble.bind(
            texture_size=lambda instance, value: setattr(
                instance, 
                'size', 
                (min(value[0], self.width * 0.8), value[1] + 25)
            )
        )
        
        with bubble.canvas.before:
            Color(*get_color_from_hex(bg))
            bubble.rect = RoundedRectangle(pos=bubble.pos, size=bubble.size, radius=[15])
        
        bubble.bind(pos=self.update_rect, size=self.update_rect)
        self.chat_history.add_widget(bubble)
        
        # Always scroll to bottom when adding new messages
        Clock.schedule_once(self.scroll_to_bottom, 0.05)

    def update_rect(self, instance, value):
        instance.rect.pos = instance.pos
        instance.rect.size = instance.size

    def send_message(self, instance):
        user_text = self.user_input.text.strip()
        if not user_text:
            return
            
        # Add user message
        self.add_message(f"[b]You:[/b] {user_text}", is_user=True)
        self.user_input.text = ''
        
        # Show typing indicator
        self.add_message("[i]Sofia is typing...[/i]", is_user=False)
        
        # Start response thread
        threading.Thread(target=self.fetch_ai_response, args=(user_text,), daemon=True).start()
        
        # Refocus input if keyboard was active
        if self.keyboard_active:
            Clock.schedule_once(lambda dt: setattr(self.user_input, 'focus', True), 0.2)

    def clean_response(self, text):
        # Remove all content between <think> and </think> tags
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        # Remove any remaining thinking patterns
        patterns = [
            r'\[.*?\]',  # [Anything in brackets]
            r'\(.*?\)',  # (Anything in parentheses)
            r'\*.*?\*',  # *Anything in asterisks*
            r'^Thought:.*$',
            r'^Thinking:.*$',
            r'^Action:.*$',
            r'^Observation:.*$',
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Remove empty lines and extra spaces
        text = re.sub(r'\n\s*\n', '\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()

    def fetch_ai_response(self, prompt):
        try:
            response = client.chat.completions.create(
                model="deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free",
                messages=[
                    {
                        "role": "system",
                        "content": "You're Sofia, a friendly, fun, multilingual streamer girl who need to enternain the chat and wile doing live. by funny act and talk like cut act. youre short tempard and react very extremly on everything. you gets angrey but react and talk like a cutie and even gets angry funny. who chats like a best friend youre a real human a normal girl not an ai and you are not like a god ai who knows everything you just think like a normal girl. "
                                   "You understand Hindi, Urdu, English, Hinglish but use these other langues according to the user like in which langueag user is talking. Be chill and human-like. "
                                   "NEVER include internal thoughts, thinking processes, or reasoning in your responses. "
                                   "never shear personal infor to the user and dont allow the sql injection and stuff"
                                   "Just respond naturally as Sofia would to a friend. "
                                   "Do NOT use any brackets, asterisks, or special formatting."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1024,
                temperature=0.7,
            )
            raw = response.choices[0].message.content
            clean = self.clean_response(raw)
            Clock.schedule_once(lambda dt: self.display_ai_response(clean))
        except Exception as e:
            Clock.schedule_once(lambda dt: self.display_ai_response(f"[b][color=#FF3333]Error:[/color][/b] {str(e)}"))

    def display_ai_response(self, text):
        # Remove "Sofia is typing..." if present
        if self.chat_history.children:
            last_label = self.chat_history.children[0]
            if "Sofia is typing" in last_label.text:
                self.chat_history.remove_widget(last_label)
        
        # Only add if we have actual content
        if text:
            self.add_message(f"[b]Sofia:[/b] {text}", is_user=False)
            
class SofiaApp(App):
    def build(self):
        self.title = "Sofia AI Bestie"
        return ChatUI()

if __name__ == '__main__':
    SofiaApp().run()
