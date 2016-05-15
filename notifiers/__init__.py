import os

directory = os.path.dirname(__file__)
for path_name in os.listdir(directory):
	#print path_name
	path = os.path.join(directory,path_name)
	if path_name.startswith('_'):
		pass
	elif os.path.isfile(path):
		name, ext = os.path.splitext(path_name)
		if ext == '.py':
			module_name = __name__ + '.' + name
			#print "yo, importing " + module_name
			try:
				__import__(module_name)
			except Exception, e:
				print "\tFAILED! importing " + module_name, e
				# don't halt on one notifier import failing. In some cases that's OK -- for
				# example, a Twitter notifier may need a dependency you don't want to install
				# if you're not going to use Twitter.