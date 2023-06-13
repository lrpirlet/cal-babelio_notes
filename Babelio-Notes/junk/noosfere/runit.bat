rem see https://manual.calibre-ebook.com/creating_plugins.html#id14 goto Debugging plugins...
rem click runit from from the directory where the plugin is developed...

rem this will kill any running calibre, push a new plugin.zip where appropriate and start calibre again
rem see results of calibre-debug -h
calibre-debug -s

rem this will execute what is needed to get the modified/new noosfere sources into calibre (do not forget the .)
rem see results of calibre-customize -h
calibre-customize -b .

rem this will create a terminal (start /b) and inside it run calibre
start /b calibre
