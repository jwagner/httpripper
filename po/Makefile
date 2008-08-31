all: mo
mo: *.po
	msgfmt --output-file=../share/locale/es/LC_MESSAGES/httpripper.mo es.po
	msgfmt --output-file=../share/locale/fr/LC_MESSAGES/httpripper.mo fr.po
	msgfmt --output-file=../share/locale/id/LC_MESSAGES/httpripper.mo id.po
	msgfmt --output-file=../share/locale/pt_BR/LC_MESSAGES/httpripper.mo pt_BR.po
	msgfmt --output-file=../share/locale/de/LC_MESSAGES/httpripper.mo de.po
	msgfmt --output-file=../share/locale/sr/LC_MESSAGES/httpripper.mo sr.po
*.po: httpripper.pot
	msgmerge -U es.po httpripper.pot
	msgmerge -U fr.po httpripper.pot
	msgmerge -U id.po httpripper.pot
	msgmerge -U pt_BR.po httpripper.pot
	msgmerge -U de.po httpripper.pot
	msgmerge -U sr.po httpripper.pot
httpripper.pot: ../httpripper/httpripper.py
	xgettext --language=Python --keyword=_ --output=httpripper.pot ../httpripper/httpripper.py
