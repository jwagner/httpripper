all: mo
mo: *.po
	msgfmt --output-file=../share/locale/de/LC_MESSAGES/httpripper.mo de.po
*.po: httpripper.pot
	 msgmerge -U de.po httpripper.pot
httpripper.pot: ../httpripper/httpripper.py
	xgettext --language=Python --keyword=_ --output=httpripper.pot ../httpripper/httpripper.py
