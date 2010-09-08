#!/usr/bin/env python
import sys
import os

from distutils.core import setup

def ls_r(dir):
    def do_reduce(a, b):
        files = []
        for f in b[2]:
            files.append(os.path.join(b[0], f))
        a.append((b[0], files))
        return a
    return reduce(do_reduce, os.walk(dir), [])

kwargs = {
      'name': 'httpripper',
      'version': "1.1.1",
      'description': 'A generic ripper for the web implemented as a http proxy',
      'author': 'Jonas Wagner',
      'author_email': 'veers@gmx.ch',
      'url': 'http://29a.ch/httpripper/',
      'packages': ['x29a', 'httpripper'],
      'scripts': ['bin/httpripper'],
      'options': {'py2exe':{
          'packages': 'encodings',
          'includes': 'cairo, pango, pangocairo, atk, gobject',
          'dist_dir': 'dist/win32',
          'optimize': 2,
          }},
      'data_files': ls_r('share'),
      'license': 'GNU GPL v3',
      'classifiers': ['Development Status :: 4 - Beta',
        'Environment :: X11 Applications :: GTK',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Operating System :: Microsoft',
        'Programming Language :: Python',
        ]
}

try:
    import py2exe
    kwargs['windows'] = [{'script': 'bin/httpripper',
          'icon_resources': [(1, 'httpripper.ico')],
          'dest_base': 'httpripper'}]
except ImportError:
    pass

setup(**kwargs)
