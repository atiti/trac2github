#!/usr/bin/env python

DBFILE = 'mobius.db'
FOLDER = 'testproject.wiki'
WIKI_REPO_URL = 'git@github.com:atiti/testproject.wiki.git'
BASE_URL = "https://github.com/atiti/testproject/wiki/"
TMP_PATH = 'tmp/'
CHECKPOINT_FILE = '.chkpoint'
DEBUG = 1


from getpass import getuser, getpass
import github3
import sqlite3, sys, string, time, os, re
import requests, json
from random import randint, uniform

user_map = { "dmz" : "dmzimmerman",
	     "nobody" : None,
	     "Eva" : "EvkaD",
	     "Eva_,_Fintan" : "EvkaD",
	     "Eva,_Fintan" : "EvkaD",
	     "None" : None,
	     "dcochran" : "dcochran",
	     "kiniry" : "kiniry",
	     "rgrig" : "rgrig",
	     "evka" : "EvkaD",
	     "jcharles" : "kiniry",
	     "fintan" : "fintanf" }

dont_do_pages = ["Trac"]

### END OF CONFIG ###

# Checkpointing functions to be able to resume
def checkpoint_load():
	global CHECKPOINT_FILE
	try:
		fh = open(CHECKPOINT_FILE, "r")
		buff = fh.read().strip()
		fh.close()
		return int(buff)
	except:
		return 0

def checkpoint_save(tcnt):
	global CHECKPOINT_FILE
	fh = open(CHECKPOINT_FILE, "w")
	fh.write(str(tcnt))
	fh.close()

# Map trac usernames to github
def map_users(inp):
	return None
	if user_map.has_key(inp):
		return user_map[inp]
	else:
		return None

# Handle the trac database
class Trac:
	db = None
	def __init__(self, dbfile):
		self.db = sqlite3.connect(dbfile)
	def getWikis(self):
		global dont_do_pages	
		cursor = self.db.cursor()
		where = ""
		sql = "select name, version, time, author, ipnr, text, comment, readonly from wiki %s order by version asc" % where
		cursor.execute(sql)
		# Fetch all the wikis
		wikis = []
		for name, version, time1, author, ipnr, text, comment, readonly in cursor:
			skip = 0
			for f in dont_do_pages:
				if name.startswith(f):
					skip = 1
					break
			if skip:
				continue
			# Now we got the basics of a ticket
			wiki = {
				'name': name,
				'version': version,
				'time' : time1,
				'author': author,
				'ipnr': ipnr.encode('utf-8'),
				'text': text.encode('utf-8'),
				'comment': comment,
				'readonly': readonly,
				'history': []
			}
			# Let's collect all the comments too
			#cursor2 = self.db.cursor()
			#sql = 'select author, time, newvalue from ticket_change where (ticket = %s) and (field = "comment")' % id
			#cursor2.execute(sql)
			#for author, time, newvalue in cursor2:
			#	change = {
			#		'author': author,
			#		'time': time,
			#		'comment': newvalue
			#	}
			#	ticket['history'].append(change)
			#
			#tickets.append(ticket)
			wikis.append(wiki)

		return wikis

class GitHubWikis:
	def __init__(self, url):
		global TMP_PATH
		self.runcmd("git clone "+url)		
	def runcmd(self, cmd, subdir=''):
		global TMP_PATH
		print "Running: cd "+TMP_PATH+"/"+subdir+"; "+cmd
		os.system("cd "+TMP_PATH+"/"+subdir+"; "+cmd)
	def format_text(self, text):
		global BASE_URL

                # Manually process tables
                outtext = ""
                lines = text.split("\n")
                table_start = 0
                for l in lines:
                        if l.startswith("||"):
                                if not table_start:
                                        outtext += "<table>\n"
                                        table_start = 1

                                outtext += "<tr>"
                                elements = l.split("||")
                                elements = elements[1:len(elements)-1]
                                for e in elements:
                        		e = re.sub(r"'''(.+)'''", "<b>\\1</b>", e) # Bold in HTML
					e = re.sub(r"''(.+)''", "<i>\\1</i>", e) # Italic
					e = re.sub(r'\[(http[^\s\[\]]+)\s([^\[\]]+)\]', '<a href="\\1">\\2</a>', e) # URL handling
					e = re.sub(r'\[wiki:([^\s\[\]]+)\s([^\[\]]+)\]', '[\\2]('+BASE_URL+'\\1)', e)
					e = re.sub(r'\[wiki:([^\s\[\]]+)\]', '[\\1]('+BASE_URL+'\\1)', e)
			                outtext += "<td>"+e+"</td>"
                                outtext += "</tr>\n"
                        else:
                                if table_start:
                                        outtext += "</table>\n"
                                        table_start = 0
                                outtext += l+"\n"


		newtext = re.sub(r'\{\{\{([^\n]+?)\}\}\}', '`\\1`', outtext) # Code?
		newtext = re.sub(r'\=\=\=\=\s(.+?)\s\=\=\=\=', '### \\1', newtext) # headlines
		newtext = re.sub(r'\=\=\=\s(.+?)\s\=\=\=', '## \\1', newtext)
		newtext = re.sub(r'\=\=\s(.+?)\s\=\=', '# \\1', newtext)
		newtext = re.sub(r'\=\s(.+?)\s\=[\s\n]*', '', newtext)
		newtext = re.sub(r'\[(http[^\s\[\]]+)\s([^\[\]]+)\]', '[\\2](\\1)', newtext) # urls
		newtext = re.sub(r'\[wiki:([^\s\[\]]+)\s([^\[\]]+)\]', '[\\2]('+BASE_URL+'\\1)', newtext) # Wiki links with title
		newtext = re.sub(r'\[wiki:([^\s\[\]]+)\]', '[\\1]('+BASE_URL+'\\1)', newtext) # Wiki links without title
		newtext = re.sub(r'\!(([A-Z][a-z0-9]+){2,})', '\\1', newtext)
		newtext = re.sub(r"'''(.+)'''", '*\\1*', newtext)
		newtext = re.sub(r"''(.+)''", '_\\1_', newtext)
		newtext = re.sub(r'^\s\*', '*', newtext)
		newtext = re.sub(r'^\s\d\.', '\\1.', newtext)
		#newtext = re.sub(r'\|\|\s(.+?)\s\|\|', '| \\1 |', newtext)
		#newtext = newtext.replace("||", "|") # FIXME: this can f*ck up the or operator in conditions
		newtext = newtext.replace("{{{", "```").replace("}}}", "```")

		return newtext

	def new_page(self, w):
		global TMP_PATH, FOLDER

		fname = w["name"].replace("/", "-").replace(" ", "_")+".md"

		fd = open(TMP_PATH+"/"+FOLDER+"/"+fname, "w")
		text = self.format_text(w["text"])
		text += "\n\n"
		text += "***Version:*** "+str(w["version"])+"\n"
		text += "***Time:*** "+time.ctime(long(w["time"])/1000000)+"\n"
		text += "***Author:*** "+w["author"].encode("utf-8")+"("+str(map_users(w["author"]))+")\n"
		text += "***IP:*** "+w["ipnr"]+"\n"
		fd.write(text)
		fd.close()
		print text

		# Add change to repo
		self.runcmd("git add "+fname, FOLDER);
		# Do a commit
		self.runcmd("git commit -m 'Wiki page \""+w["name"]+"\" update, rev "+str(w["version"])+" by "+w["author"]+" at "+time.ctime(long(w["time"])/1000000)+"'", FOLDER)

if __name__ == "__main__":
	# Getting tickets from track with history
	t = Trac(DBFILE)
	wikis = t.getWikis()

	g = GitHubWikis(WIKI_REPO_URL)
	
	wcnt = 0
	#for w in wikis:
	while wcnt < len(wikis):
		w = wikis[wcnt]
		print w["name"], w["version"]	
		g.new_page(w)
		wcnt += 1
