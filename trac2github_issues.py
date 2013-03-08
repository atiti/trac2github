#!/usr/bin/env python

DBFILE = 'mobius.db'
CREDENTIALS_FILE = '.creds'
GITHUBURL = "https://api.github.com"

from getpass import getuser, getpass
import github3
import sqlite3, sys, string
import requests, json
from random import randint, uniform

user_map = { "dmz" : "dmzimmerman",
	     "nobody" : None,
	     "" : None }

# Map trac usernames to github
def map_users(inp):
	if user_map.has_key(inp):
		return user_map[inp]
	else:
		return inp

# Handle the trac database
class Trac:
	db = None
	def __init__(self, dbfile):
		self.db = sqlite3.connect(dbfile)
	def getTickets(self):
		cursor = self.db.cursor()
		where = ""
		sql = "select id, summary, description, milestone, component, reporter, owner from ticket %s order by id" % where
		cursor.execute(sql)
		# Fetch all the tickets
		tickets = []
		for id, summary, description, milestone, component, reporter, owner in cursor:
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
	labels = []
	milestones = []
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
		self.milestones = [m.refresh() for m in repo.iter_milestones()]
		print title, repr(self.milestones)
		for ms in self.milestones:
			if ms.title == title:
				return ms
		print "hmm no ms"
		ms = repo.create_milestone(title)
		return ms

	def getLabelOrCreate(self, repo, label):
		self.labels = [l.refresh() for l in repo.iter_labels()]
		for l in self.labels:
			if l.name == label:
				return l
		l = repo.create_label(label, self.random_color())
		return l
	
	def getIssueOrCreate(self, repo, title, body=None, assignee=None, milestone=None, labels=None):
		issues = [i.refresh() for i in repo.iter_issues()]
		for i in issues:
			if i.title == title:
				return i	
		i = repo.create_issue(title=title, body=body, assignee=assignee, milestone=milestone, labels=labels)
		return i
	
	def getCommentOrCreate(self, issue, body):
		comments = [c.refresh() for c in issue.iter_comments()]
		for c in comments:
			if c.body == body:
				return c
		c = issue.create_comment(body)
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
	repo = g.getRepo('atiti', 'testproject')

	for ti in tickets:
		# Preparing milestones and labels for use to create the issue
		milestone = ti["milestone"]
		if len(milestone) > 0:
			ms = g.getMilestoneOrCreate(repo, milestone)
			msnum = ms.number
		else:
			msnum = None

		component = ti["component"]
		if len(component) > 0:
			cp = g.getLabelOrCreate(repo, component)
			component = [component]
		else:
			component = None			
		
		# Map trac to github users
		assignee = map_users(ti["owner"])

		# Create a new issue
		# TODO: the assignee needs to be set once the trac -> github user mapping is known
		issue = g.getIssueOrCreate(repo, ti["summary"], ti["description"], None, msnum, component)

		# Add all the comments!
		for c in ti["history"]:
			if len(c["comment"]) > 0:
				g.getCommentOrCreate(issue, c["comment"])				

		
