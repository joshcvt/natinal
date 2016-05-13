import os

"""
yamanote:pyclassing joshc$ python
Python 2.7.10 (default, Oct 23 2015, 19:19:21) 
[GCC 4.2.1 Compatible Apple LLVM 7.0.0 (clang-700.0.59.5)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>> import subs
>>> subs.ParentClass.Parent.__subclasses__
<built-in method __subclasses__ of type object at 0x7f9839e31b30>
>>> subs.ParentClass.Parent.__subclasses__()
[<class 'subs.SubOne.SubOne'>]
>>> subs.ParentClass.Parent.__subclasses__()[0].__name__
'SubOne'
>>> whatever = subs.ParentClass.Parent.__subclasses__()[0]()
called Parent.__init__()
>>> whatever
<subs.SubOne.SubOne object at 0x1021b69d0>
>>> 

subs/ParentClass.py:
class Parent(object):
	def __init__(self): pass

subs/SubOne.py: 
from ParentClass import Parent
class SubOne(Parent):
	pass

"""

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
