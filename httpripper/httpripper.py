"""
Author: Jonas Wagner

HTTPRipper a generic ripper for the web
Copyright (C) 2008-2010 Jonas Wagner

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import datetime
import logging
import os
from os import path
import shutil
import socket
import SocketServer
import sys
import tempfile
import threading
import time
from urlparse import urlparse


# configure gettext
import locale
locale.setlocale(locale.LC_ALL, "")

import gettext
try:
    PREFIX = path.abspath(path.join(path.dirname(sys.modules["__main__"].__file__), os.pardir))
except AttributeError:
    # frozen
    PREFIX = path.abspath(".")
LANGUAGES = [locale.getdefaultlocale()[0] or "en_US", "en_US"]
LOCALE_PATH = os.path.join(PREFIX, "share", "locale")
gettext.bindtextdomain('httpripper', LOCALE_PATH)
gettext.textdomain('httpripper')
gettext.translation('httpripper', LOCALE_PATH,
        languages=LANGUAGES, fallback = True).install(unicode=1)


import gtk, gobject, pango

# always enable button images
gtk.settings_get_default().set_long_property("gtk-button-images", True, "main")


from x29a import mygtk
from x29a.utils import byteformat
mygtk.install()

import prox as proxpy

try:
    __file__
except NameError:
    # frozen
    sys.stderr.write = lambda *x: None

try:
    import gconf
except ImportError:
    logging.debug("disabling proxy configuration")
    def get_proxy():
        return None, None, False, None
    def set_proxy(host, port, on):
        pass
else:
    logging.debug("enabling proxy configuration")
    gconf_client = gconf.client_get_default()
    def get_proxy():
        proxy = (
                gconf_client.get_string("/system/http_proxy/host"),
                gconf_client.get_int("/system/http_proxy/port"),
                gconf_client.get_bool("/system/http_proxy/use_http_proxy"),
                gconf_client.get_string("/system/proxy/mode")
        )
        logging.debug("get_proxy() -> %r", proxy)
        return proxy

    def set_proxy(host, port, enabled, mode="manual"):
        logging.debug("set_proxy(%r, %r, %r, %r)", host, port, enabled, mode)
        gconf_client.set_string("/system/http_proxy/host", host),
        gconf_client.set_int("/system/http_proxy/port", port),
        gconf_client.set_bool("/system/http_proxy/use_http_proxy", enabled)
        gconf_client.set_string("/system/proxy/mode", mode)

NAME = "HTTP Ripper"
VERSION = "1.1.1"
WEBSITE = "http://29a.ch/httpripper/"

def llabel(s):
    """a left aligned label"""
    l = gtk.Label(s)
    l.set_property("xalign", 0.0)
    return l

def byteformatdatafunc(column, cell, model, treeiter):
    n = int(cell.get_property('text'))
    cell.set_property('text', byteformat(n))

def get_unused_filename(name):
    if path.exists(name):
        root, ext = path.splitext(name)
        i = 1
        while path.exists(root + str(i) + ext):
            i += 1
        return root + str(i) + ext
    return name

class ContentTypeFilter(gtk.ComboBox):
    """A combobox to choose a prefix to filter mimetypes"""
    content_types = [
            ("text-x-generic", _("Any"), ""),
            ("audio-x-generic", _("Audio"), "audio"),
            ("image-x-generic", _("Image"), "image"),
            ("video-x-generic", _("Video"), "video"),
    ]
    def __init__(self):
        self.model = mygtk.ListStore(icon=gtk.gdk.Pixbuf, name=str, prefix=str)
        for icon, name, prefix in self.content_types:
            self.model.append(icon=mygtk.iconfactory.get_icon(icon, 16), name=name, prefix=prefix)
        gtk.ComboBox.__init__(self, self.model)
        pixbuf_cell = gtk.CellRendererPixbuf()
        self.pack_start(pixbuf_cell, False)
        self.add_attribute(pixbuf_cell, 'pixbuf', self.model.columns.icon)
        text_cell = gtk.CellRendererText()
        self.pack_start(text_cell, True)
        self.add_attribute(text_cell, 'text', self.model.columns.name)
        self.set_active(0)

    @property
    def prefix(self):
        i = self.get_active()
        return self.model.get_value(self.model.get_iter(self.get_active()),
                self.model. columns.prefix)


class MainWindow(gtk.Window):
    """the main window of httpripper"""
    def __init__(self):
        gtk.Window.__init__(self)
        self.port = 8080
        while True:
            try:
                self.server = HTTPProxyServer(self)
                break
            except socket.error:
                self.port += 1
        self.server.start()
        self.set_title(NAME)
        self.set_icon(mygtk.iconfactory.get_icon("httpripper", 32))
        self.set_default_size(600, 600)
        self.vbox = gtk.VBox()
        self.add(self.vbox)
        self.info = gtk.Label(
                _("HTTPRipper is running on localhost: %i") % self.port)
        self.vbox.pack_start(self.info, False, False)
        self.model = mygtk.ListStore(date=str, url=str, size=int, path=str,
                icon=str, content_type=str)
        self.model_filtered = self.model.filter_new()
        self.model_filtered.set_visible_func(self.row_visible)
        self.model_sort = gtk.TreeModelSort(self.model_filtered)
        self.treeview = gtk.TreeView(self.model_sort)
        self.treeview.set_rules_hint(True)
        self.treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.treeview.connect("row-activated", self.save_file)
        self.treeview.set_search_column(self.model.columns.url)

        # add rows
        col = self.treeview.insert_column_with_attributes(0, _("Time"),
                gtk.CellRendererText(), text=self.model.columns.date)
        col.set_sort_column_id(self.model.columns.date)

        col = self.treeview.insert_column_with_attributes(1, _("Size"),
                gtk.CellRendererText(), text=self.model.columns.size)
        col.set_cell_data_func(col.get_cell_renderers()[0], byteformatdatafunc)
        col.set_sort_column_id(self.model.columns.size)

        renderer = gtk.CellRendererText()
        col = self.treeview.insert_column_with_attributes(2, _("Content-Type"),
                renderer, text=self.model.columns.content_type)
        renderer.set_property("ellipsize", pango.ELLIPSIZE_END)
        renderer.set_property("width", 100)
        col.set_sort_column_id(self.model.columns.content_type)

        col = self.treeview.insert_column_with_attributes(3, _("URL"),
                gtk.CellRendererText(), text=self.model.columns.url)
        col.set_expand(True)
        col.set_sort_column_id(self.model.columns.url)

        col = self.treeview.insert_column_with_attributes(0, "",
                gtk.CellRendererPixbuf(),
                **({"icon_name": self.model.columns.icon}))

        self.vbox.pack_start(mygtk.scrolled(self.treeview))
        #self.treeview.set_fixed_height_mode(True) # makes it a bit faster

        # filtering
        self.filter_content_type = ContentTypeFilter()
        self.filter_size = gtk.Entry()
        self.filter_size.connect("changed", lambda entry: self.model_filtered.refilter())
        self.filter_content_type.connect("changed", lambda combobox: self.model_filtered.refilter())
        self.filter_expander = gtk.Expander(label=_("Filter"))
        self.filter_expander.add(
                mygtk.make_table([
                    (llabel(_("Content-Type")), llabel(_("is")), self.filter_content_type),
                    (llabel(_("Size")), llabel(_("at least (KiB)")), self.filter_size),
                ])
        )
        self.vbox.pack_start(self.filter_expander, False, False)

        # buttons at the buttom
        self.buttonbox = gtk.HButtonBox()
        self.vbox.pack_end(self.buttonbox, False, False)

        self.button_record = gtk.ToggleButton(gtk.STOCK_MEDIA_RECORD)
        self.button_record.set_use_stock(True)
        self.button_record.connect("clicked", self.record)
        self.buttonbox.pack_start(self.button_record)

        self.button_save = gtk.Button(stock=gtk.STOCK_SAVE_AS)
        self.button_save.connect("clicked", self.save)
        self.buttonbox.pack_start(self.button_save)

        self.button_clear = gtk.Button(stock=gtk.STOCK_CLEAR)
        self.button_clear.connect("clicked", self.clear)
        self.buttonbox.pack_start(self.button_clear)

        self.button_about = gtk.Button(stock=gtk.STOCK_ABOUT)
        self.button_about.connect("clicked", self.about)
        self.buttonbox.pack_start(self.button_about)

        self.connect("destroy", self.clear)
        self.connect("destroy", lambda *args: self.server.shutdown())
        self.connect("destroy", gtk.main_quit)

        host, port, enabled, mode = get_proxy()
        if host == "localhost" and port == self.port and enabled:
            self.button_record.set_active(True)

    def save(self, sender):
        """save the selected files"""
        model, rows = self.treeview.get_selection().get_selected_rows()
        if len(rows) == 1:
            self.save_file(self.treeview, rows[0], None)
        elif len(rows) > 1:
            self.save_files(model, rows)

    def save_files(self, model, rows):
        """called to save multiple selected files"""
        dialog = gtk.FileChooserDialog(
                title=_("Save As"),
                parent=self,
                action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                buttons=(# ugly pygtk problem
                    _("Cancel").encode("utf8"), gtk.RESPONSE_CANCEL,
                    _("Save").encode("utf8"), gtk.RESPONSE_OK
                )
        )
        if dialog.run() == gtk.RESPONSE_OK:
            for row in map(model.get_iter, rows):
                filepath = model.get_value(row, self.model.columns.path)
                url = model.get_value(row, self.model.columns.url)
                name = path.basename(url).split("?")[0]
                dest = get_unused_filename(path.join(dialog.get_filename(), name))
                shutil.copy(filepath, dest)
        dialog.destroy()

    def save_file(self, treeview, treepath, view_column):
        """called to save a single file"""
        model = treeview.get_model()
        row = model.get_iter(treepath)
        filepath = model.get_value(row, self.model.columns.path)
        url = model.get_value(row, self.model.columns.url)
        name = urlparse(url).path.split("/")[-1]
        dialog = gtk.FileChooserDialog(
                title=_("Save As"),
                parent=self,
                action=gtk.FILE_CHOOSER_ACTION_SAVE,
                buttons=( # ugly pygtk problem
                    _("Cancel").encode("utf8"), gtk.RESPONSE_CANCEL,
                    _("Save").encode("utf8"), gtk.RESPONSE_OK
                )
        )
        dialog.set_current_name(name)
        if dialog.run() == gtk.RESPONSE_OK:
            shutil.copy(filepath, dialog.get_filename())
        dialog.destroy()

    def row_visible(self, model, iter_):
        content_type = self.model.get_value(iter_, self.model.columns.content_type)
        prefix = self.filter_content_type.prefix
        if prefix:
            if not content_type:
                return False
            if not content_type.startswith(prefix):
                return False
        try:
            size = int(self.filter_size.get_text())*1024
        except ValueError:
            size = 0
        if size and size > self.model.get_value(iter_, self.model.columns.size):
            return False
        return True

    def new_file(self, url, filepath, content_type):
        """called by the proxy where there is a new file"""
        self.model.append(
                date=datetime.datetime.now().time().strftime("%H:%M:%S"),
                url=url,
                size=path.getsize(filepath),
                icon="gtk-save",
                path=filepath,
                content_type=content_type
        )

    def clear(self, sender):
        """clear the model and remove all files"""
        for row in self.model:
            filepath = row[self.model.columns.path]
            os.remove(filepath)
        self.model.clear()
        self.treeview.columns_autosize()

    def record(self, sender=None):
        self.server.record = sender.get_active()
        if self.server.record:
            self.old_proxy = get_proxy()
            set_proxy("localhost", self.port, True)
        elif self.old_proxy:
            host, port, enabled, mode = get_proxy()
            if host == "localhost" and port == self.port and enabled:
                set_proxy(host, port, False)
            else:
                set_proxy(*self.old_proxy)


    def about(self, sender):
        """show an about dialog"""
        about = gtk.AboutDialog()
        about.set_transient_for(self)
        about.set_logo(mygtk.iconfactory.get_icon("httpripper", 128))
        about.set_name(NAME)
        about.set_version(VERSION)
#        about.set_comments("")
        about.set_authors(["Jonas Wagner"])
        about.set_translator_credits(_("translator-credits"))
        about.set_copyright("Copyright (c) 2008-2010 Jonas Wagner")
        about.set_website(WEBSITE)
        about.set_website_label(WEBSITE)
        about.set_license("""
Copyright (C) 2008-2010 Jonas Wagner
This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
""")
        about.run()
        about.destroy()

class Tee(object):
    """A filelike that writes it's data to two others"""
    def __init__(self, f1, f2):
        self.f1 = f1
        self.f2 = f2

    def write(self, data):
        self.f1.write(data)
        self.f2.write(data)

class HTTPProxyHandler(proxpy.HTTPProxyHandler):
    """handles a single request to the proxy"""
    def forward_response_body(self, f1, f2, contentlength):
        """forwardes the content to the client and (if record is true) logs it"""
        if self.server.record:
            fd, name = tempfile.mkstemp(dir=self.server.tempdir)
            f3 = os.fdopen(fd, "w+b", 0)
            f2 = Tee(f2, f3)
        self.forward(f1, f2, contentlength)
        if self.server.record:
            content_type = self.responseheaders.get("Content-Type")
            if content_type:
                content_type = content_type[0]
            self.server.on_new_file(self.url, name, content_type)

class HTTPProxyServer(proxpy.HTTPProxyServer, threading.Thread):
    """accepts client connections, deletes all files on shutdown"""
    def __init__(self, mainwin):
        threading.Thread.__init__(self)
        proxpy.HTTPProxyServer.__init__(self, ("127.0.0.1", mainwin.port), HTTPProxyHandler)
        self.skip_headers.append("If-")
        self.tempdir = tempfile.mkdtemp(prefix="httpripper")
        self.record = False
        self.setDaemon(True)
        self.mainwin = mainwin

    def run(self):
        self.serve_forever()

    def shutdown(self):
        shutil.rmtree(self.tempdir)
        self.socket.close()

    def on_new_file(self, url, filepath, content_type):
        gobject.idle_add(self.mainwin.new_file, url, filepath, content_type)

def main():
    """the entry point"""
    level = "DEBUG" in sys.argv and logging.DEBUG or logging.ERROR
    if sys.platform == "win32":
        def release_gil_on_stupid_operating_system():
            """fix for a stupid problem with threads and gtk on windows!"""
            time.sleep(0.001)
            return True
        gobject.timeout_add(25, release_gil_on_stupid_operating_system)
        logging.basicConfig(filename="httpripper.log", level=level)
    else:
        logging.basicConfig(level=level)
        gtk.gdk.threads_init()
    win = MainWindow()
    win.show_all()
    old_proxy = get_proxy()
    try:
        gtk.main()
    finally:
        set_proxy(*old_proxy)

if __name__ == "__main__":
    main()
