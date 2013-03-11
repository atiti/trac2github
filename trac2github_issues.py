#!/usr/bin/env python

DBFILE = 'mobius.db'
CREDENTIALS_FILE = '.creds'
GITHUBURL = "https://api.github.com"
TO_USER = 'atiti'
TO_PROJECT = 'testproject'


from getpass import getuser, getpass
import github3
import sqlite3, sys, string, time
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

### END OF CONFIG ###

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
	def getTickets(self):
		cursor = self.db.cursor()
		where = ""
		sql = "select id, type, summary, description, milestone, component, reporter, owner from ticket %s order by id" % where
		cursor.execute(sql)
		# Fetch all the tickets
		tickets = []
		for id, type, summary, description, milestone, component, reporter, owner in cursor:
			if not id:
				continue
#			print id, "|", milestone, "|", component, "|", reporter, "|", owner, "|",summary
#			if milestone:
#				milestone = milestone.replace(' ', '_')
#			if component:
#				component = component.replace(' ', '_')
			if owner:
				owner = owner.replace(' ', '_')
			if reporter:
				reporter = reporter.replace(' ', '_')

			# Now we got the basics of a ticket
			ticket = {
				'id': id,
				'summary': summary,
				'type' : type,
				'description': description,
				'milestone': milestone,
				'component': component,
				'reporter': reporter,
				'owner': owner,
				'history': []
			}
			# Let's collect all the comments too
			cursor2 = self.db.cursor()
			sql = 'select author, time, newvalue from ticket_change where (ticket = %s) and (field = "comment")' % id
			cursor2.execute(sql)
			for author, time, newvalue in cursor2:
				change = {
					'author': author,
					'time': time,
					'comment': newvalue
				}
				ticket['history'].append(change)

			tickets.append(ticket)


		return tickets

class GitHubWrapper:
	gh = None
	labels = None
	milestones = None
	issues = None
	comments_issues = {}
	def __init__(self):
		token = id = ''
		try:
			with open(CREDENTIALS_FILE, 'r') as fd:
                        	token = fd.readline().strip()
                        	id = fd.readline().strip()
        	except IOError:
                	print "No token found. Requesting new."
                	user = getuser()
                	password = ''
                	while not password:
                        	password = getpass('Password for {0}: '.format(user))
        
                	note = 'Trac2Github app'
                	note_url = 'https://www.github.com/atiti/trac2github'
                	scopes = ['user', 'repo']
        
                	auth = github3.authorize(user, password, scopes, note, note_url)
                	with open(CREDENTIALS_FILE, 'w') as fd:
                        	fd.write(auth.token + '\n')
                        	fd.write(str(auth.id))

                	token = auth.token
                	id = str(auth.id)

        	self.gh = github3.login(token=token)
        	print "We are in!"

	def getRepo(self, user, repo):
		return self.gh.repository(user, repo)

	def getMilestoneOrCreate(self, repo, title):
		if not self.milestones:
			self.milestones = [m.refresh(True) for m in repo.iter_milestones()]
		print title, repr(self.milestones)
		for ms in self.milestones:
			if ms.title == title:
				return ms
		print "hmm no ms"
		ms = repo.create_milestone(title)
		self.milestones.append(ms)
		return ms

	def getLabelOrCreate(self, repo, label):
		if not self.labels:
			self.labels = [l.refresh(True) for l in repo.iter_labels()]
		for l in self.labels:
			if l.name == label:
				return l
		l = repo.create_label(label, self.random_color())
		self.labels.append(l)
		return l
	
	def getIssueOrCreate(self, repo, title, body=None, assignee=None, milestone=None, labels=None):
		if not self.issues:
			self.issues = [i.refresh(True) for i in repo.iter_issues()]
		for i in self.issues:
			if i.title == title:
				return i	
		i = repo.create_issue(title=title, body=body, assignee=assignee, milestone=milestone, labels=labels)
		self.issues.append(i)
		return i
	
	def getCommentOrCreate(self, issue, body):
		if not self.comments_issues.has_key(issue.title):
			self.comments_issues[issue.title] = [c.refresh(True) for c in issue.iter_comments()]

		coms = self.comments_issues[issue.title]
		for c in coms:
			if c.body == body:
				return c
		c = issue.create_comment(body)
		self.comments_issues[issue.title].append(c);
		return c

	def hsv_to_rgb(self, h, s, v):
    		h, s, v = [float(x) for x in (h, s, v)]

		hi = (h / 60) % 6
		hi = int(round(hi))

		f = (h / 60) - (h / 60)
		p = v * (1 - s)
		q = v * (1 - f * s)
		t = v * (1 - (1 - f) * s)

		if hi == 0:
			return v, t, p
		elif hi == 1:
			return q, v, p
		elif hi == 2:
			return p, v, t
		elif hi == 3:
			return p, q, v
		elif hi == 4:
			return t, p, v
		elif hi == 5:
			return v, p, q

	def random_color(self):
		h = randint(0, 255)
		s = uniform(0.2, 1)
		v = uniform(0.3, 1)

		r, g, b = self.hsv_to_rgb(h, s, v)
		r, g, b = [int(x*255) for x in (r, g, b)]

		return hex((r<<16)+(g<<8)+b).replace("0x", "")
				

if __name__ == "__main__":
	# Getting tickets from track with history
	t = Trac(DBFILE)
	tickets = t.getTickets()

	g = GitHubWrapper()
	
	# Get the destination repo
	repo = g.getRepo(TO_USER, TO_PROJECT)

	for ti in tickets:
		print "Rate left: "+str(g.gh.ratelimit_remaining)
		print repr(ti)
		# Preparing milestones and labels for use to create the issue
		milestone = ti["milestone"]
		if milestone and len(milestone) > 0:
			ms = g.getMilestoneOrCreate(repo, milestone)
			msnum = ms.number
		else:
			msnum = None

		component = ti["component"]
		if component and len(component) > 0:
			cp = g.getLabelOrCreate(repo, component)
			component = [component]
		else:
			component = None			
	
		type = ti["type"]
		if len(type) > 0:
			tp = g.getLabelOrCreate(repo, type)
			if component: component.append(type)
			else:
				component = [type]

	
		# Map trac to github users
		assignee = map_users(ti["owner"])

		# Create a new issue
		# TODO: the assignee needs to be set once the trac -> github user mapping is known
		issue = g.getIssueOrCreate(repo, ti["summary"], ti["description"], assignee, msnum, component)

		# Add all the comments!
		for c in ti["history"]:
			if len(c["comment"]) > 0:
				if c['author'] and len(c['author']) == 0:
					c['author'] = 'None'
				author = str(c['author'])+" (GH: "+str(map_users(c['author']))+")"
				date = time.ctime(long(c['time'])/1000000)
				comment = '**From:** '+author+' **Date:** '+date+'\n\n'+c["comment"]
				g.getCommentOrCreate(issue, comment)				

		
