#!/bin/sh
gksu -u root python setup.py install
zenity --info --text "HTTP Ripper has been installed"
