import os
from glob import glob

print "all: mo"
print "mo: *.po"

for po in glob('*.po'):
    code = po.replace("httpripper-", "").replace(".po", "")
    mo = "../share/locale/%s/LC_MESSAGES/httpripper.mo" % code
    if not os.path.exists(os.path.dirname(mo)):
        os.makedirs(mo)
    print "\tmsgfmt --output-file=%s %s" % (mo, po)

print "*.po: httpripper.pot"
for po in glob('*.po'):
    print "\tmsgmerge -U %s httpripper.pot" % po
    
print "httpripper.pot: ../httpripper/httpripper.py"
print "xgettext --language=Python --keyword=_ --output=httpripper.pot ../httpripper/httpripper.py"
