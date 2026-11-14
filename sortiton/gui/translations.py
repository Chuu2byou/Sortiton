"""Language-aware GUI text and lifetime-bound notifications."""

from __future__ import annotations

import tkinter as tk
from weakref import WeakSet

from .. import i18n as _i18n

_listeners: WeakSet = WeakSet()


def __getattr__(name):
    return getattr(_i18n, name)


class Text(str):
    """A text value with a function to retranslate it."""

    def __new__(cls, render):
        obj = super().__new__(cls, render())
        obj.render = render
        return obj

    def upper(self):
        return Text(lambda: self.render().upper())

    def strip(self, chars=None):
        return Text(lambda: self.render().strip(chars))

    def __add__(self, other):
        return Text(lambda: self.render() + resolve(other))

    def __radd__(self, other):
        return Text(lambda: resolve(other) + self.render())


def resolve(value):
    return value.render() if isinstance(value, Text) else str(value)


def t(key, **kwargs):
    return Text(lambda: _i18n.t(key, **{k: resolve(v) if isinstance(v, Text) else v
                                       for k, v in kwargs.items()}))


def t_count(key, count, *, lang=None, **kwargs):
    return Text(lambda: _i18n.t_count(key, count, lang=lang,
                                      **{k: resolve(v) if isinstance(v, Text) else v
                                         for k, v in kwargs.items()}))


def subscribe(widget, slot, callback):
    """Register a callback only for the lifetime of the widget."""
    callbacks = getattr(widget, "_language_callbacks", None)
    if callbacks is None:
        if callback is None:
            return
        callbacks = widget._language_callbacks = {}
        _listeners.add(widget)

        def destroyed(event):
            if event.widget is widget:
                _listeners.discard(widget)
                callbacks.clear()

        widget.bind("<Destroy>", destroyed, add="+")
    if callback is None:
        callbacks.pop(slot, None)
    else:
        callbacks[slot] = callback


def notify(root):
    """Update only widgets belonging to the affected main window."""
    for widget in list(_listeners):
        try:
            if widget._root() is root and widget.winfo_exists():
                for callback in list(widget._language_callbacks.values()):
                    callback()
        except tk.TclError:
            _listeners.discard(widget)


class StringVar(tk.StringVar):
    """A text variable with an optional re-translatable value."""

    def __init__(self, *args, **kwargs):
        self._translated_value = None
        super().__init__(*args, **kwargs)

    def set(self, value):
        self._translated_value = value if isinstance(value, Text) else None
        super().set(resolve(value))

    def refresh(self):
        """Render the stored key in the active language."""
        if self._translated_value is not None:
            super().set(resolve(self._translated_value))


def bind_title(window, text):
    window.title(resolve(text))
    subscribe(window, "title", lambda: window.title(resolve(text)))


class Label(tk.Label):
    """A label whose translatable text follows language changes."""

    def __init__(self, master=None, cnf=None, **kwargs):
        text = kwargs.get("text")
        super().__init__(master, cnf or {}, **kwargs)
        if isinstance(text, Text):
            self._bind_text(text)

    def _bind_text(self, text):
        subscribe(self, "text", lambda: tk.Label.configure(self, text=resolve(text)))

    def configure(self, cnf=None, **kwargs):
        options = dict(cnf) if isinstance(cnf, dict) else {}
        options.update(kwargs)
        if "text" in options and hasattr(self, "tk"):
            text = options["text"]
            if isinstance(text, Text):
                self._bind_text(text)
            elif hasattr(self, "_language_callbacks"):
                subscribe(self, "text", None)
        return super().configure(cnf, **kwargs)

    config = configure
