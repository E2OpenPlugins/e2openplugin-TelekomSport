# -*- coding: utf-8 -*-

from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.InfoBar import MoviePlayer
from Screens.MessageBox import MessageBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Components.ActionMap import ActionMap
from Components.Sources.List import List
from Components.Label import Label
from Components.MultiContent import MultiContentEntryText
from Components.ConfigList import ConfigListScreen
from Components.config import config, getConfigListEntry, ConfigSubsection, ConfigText, ConfigPassword, ConfigInteger, ConfigNothing, ConfigYesNo, ConfigSelection, NoSave
from Tools.BoundFunction import boundFunction

from enigma import eTimer, eListboxPythonMultiContent, gFont, eEnv, eServiceReference, getDesktop

import xml.etree.ElementTree as ET
import time
import urllib
import urllib2
import json
import base64
from itertools import cycle, izip
from datetime import datetime
from twisted.web.client import getPage
import twisted.web.error as twistedWebError
import twisted.python.failure as twistedFailure


config.plugins.telekomsport = ConfigSubsection()
config.plugins.telekomsport.username1 = ConfigText(default = '', fixed_size = False)
config.plugins.telekomsport.password1 = ConfigPassword(default = '', fixed_size = False)
config.plugins.telekomsport.token1 = ConfigText(default = '')
config.plugins.telekomsport.token1_expiration_time = ConfigInteger(default = 0)
config.plugins.telekomsport.username2 = ConfigText(default = '', fixed_size = False)
config.plugins.telekomsport.password2 = ConfigPassword(default = '', fixed_size = False)
config.plugins.telekomsport.token2 = ConfigText(default = '')
config.plugins.telekomsport.token2_expiration_time = ConfigInteger(default = 0)
config.plugins.telekomsport.hide_unplayable = ConfigYesNo(default=False)
# Use 2 config variables as workaround as empty ConfigSelection is not initialized with the stored value after e2 restart
config.plugins.telekomsport.default_section = ConfigText(default = '', fixed_size = False)
config.plugins.telekomsport.default_section_chooser = NoSave(ConfigSelection([], default = None))


def encode(x):
	return base64.encodestring(''.join(chr(ord(c) ^ ord(k)) for c, k in izip(x, cycle('password protection')))).strip()

def decode(x):
	return ''.join(chr(ord(c) ^ ord(k)) for c, k in izip(base64.decodestring(x), cycle('password protection')))

def loadTelekomSportJsonData(screen, statusField, buildListFunc, data):
	try:
		jsonResult = json.loads(data)

		if 'status' not in jsonResult or jsonResult['status'] != 'success':
			statusField.setText(screen + ': Fehler beim Laden der JSON Daten: "Status ist nicht success"')
			return
		buildListFunc(jsonResult)
	except Exception as e:
		statusField.setText(screen + ': Fehler beim Laden der JSON Daten "' + str(e) + '"')

def handleTelekomSportDownloadError(screen, statusField, err):
	try:
		err.trap(twistedWebError.Error)
		statusField.setText(screen + ': Fehler beim Download "' + err.getErrorMessage() + '"')
	except twistedFailure.Failure as e:
		statusField.setText(screen + ': Fehler beim Download "' + e.getErrorMessage() + '"')
	except Exception as e:
		statusField.setText(screen + ': Fehler beim Download "' + str(e) + '"')

def downloadTelekomSportJson(url, callback, errorCallback):
	d = getPage(url)
	d.addCallback(callback)
	d.addErrback(errorCallback)


class TelekomSportConfigScreen(ConfigListScreen, Screen):

	if getDesktop(0).size().width() <= 1280:
		skin = '''<screen position="center,center" size="470,320" flags="wfNoBorder">
					<ePixmap position="center,10" size="450,45" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="config" position="10,70" size="460,200" font="Regular;20" scrollbarMode="showOnDemand" />
					<widget name="buttonred" position="10,280" size="120,35" backgroundColor="red" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;20"/>
					<widget name="buttongreen" position="165,280" size="120,35" backgroundColor="green" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;20"/>
					<widget name="buttonblue" position="320,280" size="135,35" backgroundColor="blue" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;20"/>
				</screen>'''
	else:
		skin = '''<screen position="center,center" size="670,520" flags="wfNoBorder">
					<ePixmap position="center,15" size="640,59" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="config" position="15,100" size="650,340" font="Regular;32" itemHeight="42" scrollbarMode="showOnDemand" />
					<widget name="buttonred" position="15,460" size="180,50" backgroundColor="red" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;32"/>
					<widget name="buttongreen" position="225,460" size="180,50" backgroundColor="green" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;32"/>
					<widget name="buttonblue" position="440,460" size="215,50" backgroundColor="blue" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;32"/>
				</screen>'''

	def __init__(self, session):
		Screen.__init__(self, session)

		self.list = []
		self.config_account1_text = getConfigListEntry('1. Account', ConfigNothing())
		self.list.append(self.config_account1_text)
		self.config_username1 = getConfigListEntry('Benutzername', config.plugins.telekomsport.username1)
		self.list.append(self.config_username1)
		self.config_password1 = getConfigListEntry('Passwort', config.plugins.telekomsport.password1)
		self.list.append(self.config_password1)
		self.config_account2_text = getConfigListEntry('2. Account', ConfigNothing())
		self.list.append(self.config_account2_text)
		self.config_username2 = getConfigListEntry('Benutzername', config.plugins.telekomsport.username2)
		self.list.append(self.config_username2)
		self.config_password2 = getConfigListEntry('Passwort', config.plugins.telekomsport.password2)
		self.list.append(self.config_password2)
		self.config_hide_unplayable = getConfigListEntry('Unspielbares ausblenden', config.plugins.telekomsport.hide_unplayable)
		self.list.append(self.config_hide_unplayable)
		self.config_default_section_chooser = getConfigListEntry('Default Abschnitt', config.plugins.telekomsport.default_section_chooser)
		self.list.append(self.config_default_section_chooser)

		ConfigListScreen.__init__(self, self.list)
		self['buttonred'] = Label(_('Cancel'))
		self['buttongreen'] = Label(_('Ok'))
		self['buttonblue'] = Label('virt. Tastatur')
		self['setupActions'] = ActionMap(['SetupActions', 'VirtualKeyboardActions', 'ColorActions'],
		{
			'green': self.save,
			'red': self.cancel,
			'blue': self.virtualKeyboard,
			'save': self.save,
			'cancel': self.cancel,
			'ok': self.save,
			'showVirtualKeyboard': self.virtualKeyboard,
		}, -2)
		config.plugins.telekomsport.password1.value = decode(config.plugins.telekomsport.password1.value)
		config.plugins.telekomsport.password2.value = decode(config.plugins.telekomsport.password2.value)
		config.plugins.telekomsport.default_section_chooser.value = config.plugins.telekomsport.default_section.value
		self.onLayoutFinish.append(self.setWindowTitle)

	def setWindowTitle(self):
		self.setTitle('Setup Telekom Sport Accounts')

	def save(self):
		config.plugins.telekomsport.password1.value = encode(config.plugins.telekomsport.password1.value)
		config.plugins.telekomsport.token1.value = ''
		config.plugins.telekomsport.token1_expiration_time.value = 0
		config.plugins.telekomsport.password2.value = encode(config.plugins.telekomsport.password2.value)
		config.plugins.telekomsport.token2.value = ''
		config.plugins.telekomsport.token2_expiration_time.value = 0
		config.plugins.telekomsport.default_section.value = config.plugins.telekomsport.default_section_chooser.value
		config.plugins.telekomsport.default_section.save()
		for x in self['config'].list:
			x[1].save()
		self.close()

	def cancel(self):
		for x in self['config'].list:
			x[1].cancel()
		self.close()

	def virtualKeyboard(self):
		if self['config'].getCurrent() in (self.config_username1, self.config_username2, self.config_password1, self.config_password2):
			self.session.openWithCallback(self.virtualKeyBoardCallback, VirtualKeyBoard, title = self['config'].getCurrent()[0], text = self['config'].getCurrent()[1].value)

	def virtualKeyBoardCallback(self, callback = None):
		if callback is not None:
			self['config'].getCurrent()[1].value = callback
			self['config'].invalidate(self['config'].getCurrent())


class TelekomSportMoviePlayer(MoviePlayer):

	def __init__(self, session, service, standings_url, schedule_url):
		MoviePlayer.__init__(self, session, service)
		self.skinName = 'MoviePlayer'
		self.standings_url = standings_url
		self.schedule_url = schedule_url

	def leavePlayer(self):
		self.session.openWithCallback(self.leavePlayerConfirmed, MessageBox, 'Abspielen beenden?')

	def leavePlayerConfirmed(self, answer):
		if answer:
			self.close()

	def openEventView(self):
		if self.standings_url:
			self.session.open(TelekomSportStandingsResultsScreen, '', self.standings_url, self.schedule_url)

	def showMovies(self):
		pass


class TelekomSportStandingsResultsScreen(Screen):

	if getDesktop(0).size().width() <= 1280:
		skin = '''<screen position="center,center" size="820,680" flags="wfNoBorder">
					<ePixmap position="center,25" size="800,100" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="10,125" size="800,40" font="Regular;30" zPosition="1" />
					<widget name="subtitle" position="10,165" size="800,35" font="Regular;25" zPosition="1" />
					<widget name="table_header_team" position="40,200" size="100,20" font="Regular;18" zPosition="1" />
					<widget name="table_header_matches" position="395,200" size="60,20" font="Regular;18" zPosition="1" />
					<widget name="table_header_wins" position="460,200" size="30,20" font="Regular;18" zPosition="1" />
					<widget name="table_header_draws" position="495,200" size="30,20" font="Regular;18" zPosition="1" />
					<widget name="table_header_losses" position="530,200" size="30,20" font="Regular;18" zPosition="1" />
					<widget name="table_header_goals" position="570,200" size="70,20" font="Regular;18" zPosition="1" />
					<widget name="table_header_goaldiff" position="685,200" size="70,20" font="Regular;18" zPosition="1" />
					<widget name="table_header_points" position="730,200" size="100,20" font="Regular;18" zPosition="1" />
					<widget source="list" render="Listbox" position="10,230" size="800,390" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (25,[
									MultiContentEntryText(pos = (0, 0), size = (25, 25), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0), # rank
									MultiContentEntryText(pos = (30, 0), size = (370, 25), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1), # team
									MultiContentEntryText(pos = (400, 0), size = (50, 25), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 2), # count matches
									MultiContentEntryText(pos = (440, 0), size = (30, 25), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 3), # count wins
									MultiContentEntryText(pos = (475, 0), size = (30, 25), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 4), # count draws
									MultiContentEntryText(pos = (510, 0), size = (30, 25), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 5), # count losses
									MultiContentEntryText(pos = (555, 0), size = (95, 25), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 6), # goals
									MultiContentEntryText(pos = (650, 0), size = (50, 25), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 7), # goal diff
									MultiContentEntryText(pos = (720, 0), size = (50, 25), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 8), # points
								]),
								"playoff": (65,[
									MultiContentEntryText(pos = (20, 0), size = (500, 28), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0), # title
									MultiContentEntryText(pos = (20, 30), size = (750, 30), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1), # teams + wins
								]),
								"schedule": (65,[
									MultiContentEntryText(pos = (20, 0), size = (500, 28), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0), # description
									MultiContentEntryText(pos = (620, 0), size = (240, 28), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1), # start time
									MultiContentEntryText(pos = (20, 30), size = (750, 30), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 2), # teams + result
								]),
								},
								"fonts": [gFont("Regular", 20), gFont("Regular", 24)],
								"itemHeight": 65
							}
						</convert>
					</widget>
					<widget name="status_standings" position="10,230" size="800,400" font="Regular;25" halign="center" zPosition="1" />
					<widget name="status_schedule" position="10,230" size="800,400" font="Regular;25" halign="center" zPosition="1" />
					<widget name="buttonblue" position="15,630" size="160,35" backgroundColor="blue" valign="center" halign="center" zPosition="2" foregroundColor="white" font="Regular;20"/>
					<widget foregroundColor="white" font="Regular;20" position="640,630" render="Label" size="200,35" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''
	else:
		skin = '''<screen position="center,center" size="1230,1020" flags="wfNoBorder">
					<ePixmap position="center,25" size="1200,150" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="15,185" size="1200,50" font="Regular;42" zPosition="1" />
					<widget name="subtitle" position="15,235" size="1200,50" font="Regular;38" zPosition="1" />
					<widget name="table_header_team" position="60,300" size="100,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_matches" position="580,300" size="80,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_wins" position="690,300" size="25,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_draws" position="740,300" size="25,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_losses" position="785,300" size="25,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_goals" position="855,300" size="70,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_goaldiff" position="995,300" size="60,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_points" position="1055,300" size="100,40" font="Regular;30" zPosition="1" />
					<widget source="list" render="Listbox" position="15,340" size="1200,610" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (40,[
									MultiContentEntryText(pos = (0, 0), size = (40, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0), # rank
									MultiContentEntryText(pos = (45, 0), size = (555, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1), # team
									MultiContentEntryText(pos = (600, 0), size = (50, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 2), # count matches
									MultiContentEntryText(pos = (650, 0), size = (50, 40), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 3), # count wins
									MultiContentEntryText(pos = (700, 0), size = (50, 40), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 4), # count draws
									MultiContentEntryText(pos = (755, 0), size = (50, 40), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 5), # count losses
									MultiContentEntryText(pos = (835, 0), size = (150, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 6), # goals
									MultiContentEntryText(pos = (990, 0), size = (50, 40), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 7), # goal diff
									MultiContentEntryText(pos = (1060, 0), size = (50, 40), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 8), # points
								]),
								"playoff": (90,[
									MultiContentEntryText(pos = (20, 0), size = (1150, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0), # title
									MultiContentEntryText(pos = (20, 42), size = (1150, 42), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1), # teams + wins
								]),
								"schedule": (90,[
									MultiContentEntryText(pos = (20, 0), size = (1150, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0), # description
									MultiContentEntryText(pos = (925, 0), size = (360, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1), # start time
									MultiContentEntryText(pos = (20, 42), size = (1150, 42), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 2), # teams + result
								]),
								},
								"fonts": [gFont("Regular", 32), gFont("Regular", 36)],
								"itemHeight": 40
							}
						</convert>
					</widget>
					<widget name="status_standings" position="15,340" size="1200,600" font="Regular;35" halign="center" zPosition="1" />
					<widget name="status_schedule" position="15,340" size="1200,600" font="Regular;35" halign="center" zPosition="1" />
					<widget name="buttonblue" position="35,955" size="240,50" backgroundColor="blue" valign="center" halign="center" zPosition="2" foregroundColor="white" font="Regular;32"/>
					<widget foregroundColor="white" font="Regular;32" position="920,955" render="Label" size="270,50" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''

	def __init__(self, session, title, standings_url, schedule_url):
		Screen.__init__(self, session)
		self.session = session

		self['title'] = Label(title)
		self['subtitle'] = Label('Tabelle')
		self['table_header_team'] = Label('Team')
		self['table_header_matches'] = Label('Spiele')
		self['table_header_wins'] = Label('S')
		self['table_header_draws'] = Label('U')
		self['table_header_losses'] = Label('N')
		self['table_header_goals'] = Label('Tore')
		self['table_header_goaldiff'] = Label('Diff')
		self['table_header_points'] = Label('Punkte')
		self['status_standings'] = Label('Lade Daten...')
		self['status_schedule'] = Label('')
		self['status_schedule'].hide()

		self.standingsList = []
		self.playoffStandingsList = []
		self.scheduleList = []
		self['list'] = List()
		self.curr = 'schedule'

		self['buttonblue'] = Label('')

		self['actions'] = ActionMap(['SetupActions', 'DirectionActions', 'ColorActions'],
		{
			'cancel': self.close,
			'ok': self.close,
			'blue': self.switchList,
		})
		self.toogleStandingsVisibility(False)
		downloadTelekomSportJson(TelekomSportMainScreen.base_url + schedule_url, boundFunction(loadTelekomSportJsonData, 'Schedule', self['status_schedule'], self.loadSchedule), boundFunction(handleTelekomSportDownloadError, 'Schedule', self['status_schedule']))
		downloadTelekomSportJson(TelekomSportMainScreen.base_url + standings_url, boundFunction(loadTelekomSportJsonData, 'Standings', self['status_standings'], self.loadStandings), boundFunction(handleTelekomSportDownloadError, 'Standings', self['status_standings']))

	def toogleStandingsVisibility(self, show):
		self['table_header_team'].setVisible(show)
		self['table_header_matches'].setVisible(show)
		self['table_header_wins'].setVisible(show)
		self['table_header_draws'].setVisible(show)
		self['table_header_losses'].setVisible(show)
		self['table_header_goals'].setVisible(show)
		self['table_header_goaldiff'].setVisible(show)
		self['table_header_points'].setVisible(show)

	def showSchedule(self):
		self['status_standings'].hide()
		self.toogleStandingsVisibility(False)
		self['subtitle'].setText('Spielplan')
		if self['status_schedule'].getText() == '':
			self['list'].style = 'schedule'
			self['list'].setList(self.scheduleList)
		else:
			self['status_schedule'].show()

	def showStandings(self):
		self['status_schedule'].hide()
		self['subtitle'].setText('Tabelle')
		if self['status_standings'].getText() == '' or self['status_standings'].getText() == 'Lade Daten...':
			self.toogleStandingsVisibility(True)
			self['status_standings'].hide()
			self['list'].style = 'default'
			self['list'].setList(self.standingsList)
		else:
			self['status_standings'].show()

	def showPlayoff(self):
		self['status_schedule'].hide()
		self['subtitle'].setText('Tabelle - Playoffs')
		if self['status_standings'].getText() == '' or self['status_standings'].getText() == 'Lade Daten...':
			self.toogleStandingsVisibility(False)
			self['list'].style = 'playoff'
			self['list'].setList(self.playoffStandingsList)
		else:
			self['status_standings'].show()

	def switchList(self):
		if self.curr == 'standings' and self.playoffStandingsList:
			self.curr = 'playoff'
			self['buttonblue'].setText('Spielplan')
			self.showPlayoff()
		elif self.curr == 'standings' and not self.playoffStandingsList:
			self.curr = 'schedule'
			self['buttonblue'].setText('Tabelle')
			self.showSchedule()
		elif self.curr == 'playoff':
			self.curr = 'schedule'
			self['buttonblue'].setText('Tabelle')
			self.showSchedule()
		elif self.curr == 'schedule':
			self.curr = 'standings'
			if self.playoffStandingsList:
				self['buttonblue'].setText('Tabelle - Playoffs')
			else:
				self['buttonblue'].setText('Spielplan')
			self.showStandings()

	def loadNormalStandings(self, jsonData):
		try:
			for team in jsonData['data']['standing'][0]['ranking']:
				rank = team['rank']
				team_title = team['team_title'].encode('utf8')
				played = str(team['played'])
				win = str(team['win'])
				draw = str(team['draw'])
				loss = str(team['loss'])
				goals_for = str(team['goals_for'])
				goals_against = str(team['goals_against'])
				goal_diff = str(team['goal_diff'])
				points = str(team['points'])
				self.standingsList.append((str(rank), team_title, played, win, draw, loss, goals_for + ':' + goals_against, goal_diff, points, rank))
			self.standingsList = sorted(self.standingsList, key = lambda entry: entry[9])
			self.switchList()
		except Exception as e:
			self['status_standings'].setText('Aktuell steht die Tabelle nicht zur Verfügung. Bitte versuchen sie es später noch einmal.')
			return False
		return True

	def loadPlayoffStandings(self, jsonData):
		try:
			title = jsonData['data']['title'].encode('utf8')
			for round in jsonData['data']['rounds']:
				subtitle = round['title'].encode('utf8')
				for enc in round['encounters']:
					if not enc:
						continue
					home_team = enc['home']['title_mini'].encode('utf8')
					home_wins = str(enc['home']['wins'])
					away_team = enc['away']['title_mini'].encode('utf8')
					away_wins = str(enc['away']['wins'])
					if home_wins == 'None':
						home_wins = ' '
					if away_wins == 'None':
						away_wins = ' '
					encounters = home_team + '  ' + home_wins + ' - ' + away_wins + ' ' + away_team
					self.playoffStandingsList.append((subtitle, encounters))
		except Exception as e:
			self['status_standings'].setText('Aktuell steht die Playoff Tabelle nicht zur Verfügung. Bitte versuchen sie es später noch einmal.'+str(e))
			return False
		return True

	def loadStandings(self, jsonData):
		normal_standings_url = ''
		playoff_standings_url = ''
		try:
			for g in jsonData['data']['content'][0]['group_elements']:
				if g['type'] == 'standings':
					normal_standings_url = g['data']['urls']['standings_url'].encode('utf8')
				elif g['type'] == 'playoffTree':
					playoff_standings_url = g['data']['url'].encode('utf8')
		except Exception as e:
			self['status_standings'].setText('Aktuell steht die Tabelle nicht zur Verfügung. Bitte versuchen sie es später noch einmal.')
			return False

		if normal_standings_url:
			downloadTelekomSportJson(TelekomSportMainScreen.base_url + normal_standings_url, boundFunction(loadTelekomSportJsonData, 'NormalStandings', self['status_standings'], self.loadNormalStandings), boundFunction(handleTelekomSportDownloadError, 'NormalStandings', self['status_standings']))
		if playoff_standings_url:
			downloadTelekomSportJson(TelekomSportMainScreen.base_url + playoff_standings_url, boundFunction(loadTelekomSportJsonData, 'PlayoffStandings', self['status_standings'], self.loadPlayoffStandings), boundFunction(handleTelekomSportDownloadError, 'PlayoffStandings', self['status_standings']))

	def loadSchedule(self, jsonData):
		try:
			for c in jsonData['data']['content']:
				for g in c['group_elements']:
					for d in g['data']['days']:
						for ev in d['events']:
							if ev['type'] in ('skyConferenceEvent', 'conferenceEvent'):
								continue
							description = ev['metadata']['description_bold'].encode('utf8')
							sub_description = ev['metadata']['description_regular'].encode('utf8')
							if sub_description:
								description = description + ' - ' + sub_description
							original = ev['metadata']['scheduled_start']['original']
							starttime = datetime.strptime(original, '%Y-%m-%d %H:%M:%S')
							starttime_str = starttime.strftime('%d.%m.%Y %H:%M')
							home_team = ev['metadata']['details']['home']['name_full'].encode('utf8')
							away_team = ev['metadata']['details']['away']['name_full'].encode('utf8')
							if 'result' in ev['metadata']['details']['encounter']:
								home_goals = str(ev['metadata']['details']['encounter']['result']['home']).encode('utf8')
								away_goals = str(ev['metadata']['details']['encounter']['result']['away']).encode('utf8')
							else:
								home_goals = ' '
								away_goals = ' '
							match = home_team + '  ' + home_goals + ' - ' + away_goals + '  ' + away_team

							self.scheduleList.append((description, starttime_str, match))
		except Exception as e:
			self['status_schedule'].setText('Bitte Pluginentwickler informieren:\nTelekomSportStandingsResultsScreen ' + str(e))
			return False
		return True


class TelekomSportEventScreen(Screen):

	if getDesktop(0).size().width() <= 1280:
		skin = '''<screen position="center,center" size="820,680" flags="wfNoBorder">
					<ePixmap position="center,25" size="800,100" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="description" position="10,150" size="800,40" font="Regular;25" zPosition="1" />
					<widget name="match" position="10,200" size="800,45" noWrap="1" halign="center" font="Regular;35" zPosition="1" />
					<widget name="subdescription" position="10,270" size="800,90" font="Regular;25" zPosition="1" />
					<widget source="list" render="Listbox" position="10,370" size="800,250" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (30,[
									MultiContentEntryText(pos = (20, 0), size = (750, 28), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
								]),
								},
								"fonts": [gFont("Regular", 24),gFont("Regular", 20)],
								"itemHeight": 30
							}
						</convert>
					</widget>
					<widget name="status" position="10,370" size="800,250" font="Regular;25" halign="center" zPosition="1" />
					<widget name="pay" position="15,630" size="200,35" valign="center" halign="center" zPosition="2" font="Regular;20"/>
					<widget foregroundColor="white" font="Regular;20" position="640,630" render="Label" size="200,35" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''
	else:
		skin = '''<screen position="center,center" size="1230,1020" flags="wfNoBorder">
					<ePixmap position="center,25" size="1200,150" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="description" position="15,230" size="1200,50" font="Regular;35" zPosition="1" />
					<widget name="match" position="15,290" size="1200,65" noWrap="1" halign="center" font="Regular;50" zPosition="1" />
					<widget name="subdescription" position="15,370" size="1200,130" font="Regular;35" zPosition="1" />
					<widget source="list" render="Listbox" position="15,500" size="1200,400" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (45,[
									MultiContentEntryText(pos = (20, 0), size = (1100, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
								]),
								},
								"fonts": [gFont("Regular", 32)],
								"itemHeight": 45
							}
						</convert>
					</widget>
					<widget name="status" position="15,500" size="1200,400" font="Regular;35" halign="center" zPosition="1" />
					<widget name="pay" position="35,955" size="250,50" valign="center" halign="center" zPosition="2" font="Regular;32"/>
					<widget foregroundColor="white" font="Regular;32" position="920,955" render="Label" size="270,50" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''

	oauth_url = 'https://accounts.login.idm.telekom.com/oauth2/tokens'
	jwt_url = 'https://www.telekomsport.de/service/auth/app/login/jwt'
	stream_access_url = 'https://www.telekomsport.de/service/player/streamAccess'

	def __init__(self, session, description, starttime, match, url, standings_url, schedule_url):
		Screen.__init__(self, session)
		self.session = session
		self.starttime = starttime
		self.standings_url = standings_url
		self.schedule_url = schedule_url
		self.match = match

		self['match'] = Label(match)
		self['description'] = Label(description)
		self['subdescription'] = Label('')
		self['status'] = Label('Lade Daten...')
		self['pay'] = Label('* = Abo benötigt')

		self.videoList = []
		self['list'] = List(self.videoList)

		self['actions'] = ActionMap(['SetupActions', 'DirectionActions'],
		{
			'cancel': self.close,
			'ok': self.ok,
		})
		downloadTelekomSportJson(TelekomSportMainScreen.base_url + url, boundFunction(loadTelekomSportJsonData, 'Event', self['status'], self.buildScreen), boundFunction(handleTelekomSportDownloadError, 'Event', self['status']))

	def login(self, account, username, password, config_token, config_token_expiration_time):
		err = ''
		# check if token is present and valid
		if config_token.value and config_token_expiration_time.value > int(time.time()):
			return ''

		data = { "claims": "{'id_token':{'urn:telekom.com:all':null}}", "client_id": "10LIVESAM30000004901TSMAPP00000000000000", "grant_type": "password", "scope": "tsm offline_access", "username": username, "password": password }

		try:
			response = urllib.urlopen(self.oauth_url + '?' + urllib.urlencode(data), '').read()
			jsonData = json.loads(response)
			if 'access_token' not in jsonData:
				if 'error_description' in jsonData:
					return jsonData['error_description'].encode('utf8')
				else:
					return 'Fehler beim Login ' + str(account) + '. Account. Kein access_token.'

			response = urllib2.urlopen(urllib2.Request(self.jwt_url, json.dumps({'token': jsonData['access_token']}), {'Content-Type': 'application/json'})).read()
			jsonResult = json.loads(response)
			if 'data' not in jsonResult or 'token' not in jsonResult['data']:
				return 'Fehler beim Login ' + str(account) + '. Account. Kein Token.'

			config_token.value = jsonResult['data']['token']
			config_token.save()
			config_token_expiration_time.value = jsonResult['data']['expiration_time']
			config_token_expiration_time.save()
			return ''
		except Exception as e:
			return 'Fehler beim Login ' + str(account) + '. Account. ' + str(e)

	def loginAllAccounts(self):
		if config.plugins.telekomsport.username1.value:
			err = self.login(1, config.plugins.telekomsport.username1.value, decode(config.plugins.telekomsport.password1.value), config.plugins.telekomsport.token1, config.plugins.telekomsport.token1_expiration_time)
			if err:
				return err
			else:
				if config.plugins.telekomsport.username2.value:
					err = self.login(2, config.plugins.telekomsport.username2.value, decode(config.plugins.telekomsport.password2.value), config.plugins.telekomsport.token2, config.plugins.telekomsport.token2_expiration_time)
				return err
		return 'Account bitte in den Einstellungen hinterlegen.'

	def getStreamUrl(self, videoid, token):
		try:
			response = urllib2.urlopen(urllib2.Request(self.stream_access_url, json.dumps({'videoId': videoid}), {'xauthorization': token, 'Content-Type': 'application/json'}, {'label': '2780_hls'})).read()
			jsonResult = json.loads(response)
			if 'status' not in jsonResult or jsonResult['status'] != 'success':
				self['status'].setText('Fehler beim streamAccess')
				self['status'].show()
				return '', -1

			url = 'https:' + jsonResult['data']['stream-access'][0]
			response = urllib.urlopen(url).read()
			xmlroot = ET.ElementTree(ET.fromstring(response))
			playlisturl = xmlroot.find('token').get('url') + "?hdnea=" + xmlroot.find('token').get('auth')
			return playlisturl, 0
		except urllib2.HTTPError as e:
			return '', e.code

	def playVideo(self, videoid, pay, title):
		# login if necessary
		if pay:
			err = self.loginAllAccounts()
			if err:
				self['status'].setText('Bezahlinhalt kann nicht angezeigt werden.\n' + err)
				self['status'].show()
				return

		# for non pay content you pass a random token -> token1 is also a valid token
		playlisturl, errorCode = self.getStreamUrl(videoid, config.plugins.telekomsport.token1.value)
		if (errorCode == 403 or not playlisturl) and config.plugins.telekomsport.username2.value:
			playlisturl, errorCode = self.getStreamUrl(videoid, config.plugins.telekomsport.token2.value)
		if errorCode == 403:
			self['status'].setText('Es wird ein Abo benötigt um den Inhalt anzuzeigen!')
			self['status'].show()
			return

		ref = eServiceReference(4097, 0, playlisturl)
		ref.setName(title)

		self.session.open(TelekomSportMoviePlayer, ref, self.standings_url, self.schedule_url)

	def buildPreEventScreen(self, jsonData):
		pay = ''
		for content in jsonData['data']['content']:
			if content['group_elements']:
				for element in content['group_elements']:
					if element['type'] == 'noVideo':
						if element['data']['metadata']['pay']:
							pay = ' *'
		if self.starttime.date() == datetime.today().date():
			self['subdescription'].setText('Die Übertragung startet heute um ' + self.starttime.strftime('%H:%M') + pay)
		else:
			self['subdescription'].setText('Die Übertragung startet am ' + self.starttime.strftime('%d.%m.%Y') + ' um ' + self.starttime.strftime('%H:%M') + pay)

	def buildPostEventScreen(self, jsonData):
		self['subdescription'].setText('Übertragung vom ' + self.starttime.strftime('%d.%m.%Y %H:%M') + '\n\nVideos:')
		for content in jsonData['data']['content']:
			if content['group_elements']:
				for element in content['group_elements']:
					if element['type'] == 'eventVideos':
						for videos in element['data']:
							title = videos['title'].encode('utf8')
							if videos['pay']:
								title += ' *'
							self.videoList.append((title, self.match + ' - ' + videos['title'].encode('utf8'), str(videos['videoID']), str(videos['pay'])))

	def buildLiveEventScreen(self, jsonData):
		self['subdescription'].setText('Übertragung vom ' + self.starttime.strftime('%d.%m.%Y %H:%M') + '\n\nVideos:')
		for content in jsonData['data']['content']:
			if content['group_elements']:
				for element in content['group_elements']:
					if element['type'] == 'player':
						title = 'Live Stream'
						if element['data'][0]['pay']:
							title += ' *'
						self.videoList.append((title, element['data'][0]['title'].encode('utf8'), str(element['data'][0]['videoID']), str(element['data'][0]['pay'])))

	def buildScreen(self, jsonData):
		self.videoList = []

		if not jsonData['data'] or not jsonData['data']['content'] or not jsonData['data']['metadata']:
			self['status'].setText('Bitte Pluginentwickler informieren:\nTelekomSportEventScreen')
			return

		try:
			if jsonData['data']['metadata']['title'] == 'Event Page Pre':
				self.buildPreEventScreen(jsonData)
			elif jsonData['data']['metadata']['title'] == 'Event Page Post':
				self.buildPostEventScreen(jsonData)
			elif jsonData['data']['metadata']['title'] == 'Event Page Live':
				self.buildLiveEventScreen(jsonData)
		except Exception as e:
			self['status'].setText('Bitte Pluginentwickler informieren:\nTelekomSportEventScreen ' + str(e))
			return

		self['list'].setList(self.videoList)
		self['status'].hide()

	def ok(self):
		if self['list'].getCurrent():
			title = self['list'].getCurrent()[1]
			videoid = self['list'].getCurrent()[2]
			pay = self['list'].getCurrent()[3]
			self.playVideo(videoid, pay == 'True', title)


class TelekomSportEventLaneScreen(Screen):

	if getDesktop(0).size().width() <= 1280:
		skin = '''<screen position="center,center" size="820,680" flags="wfNoBorder">
					<ePixmap position="center,25" size="800,100" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="10,125" size="800,40" font="Regular;30" zPosition="1" />
					<widget name="subtitle" position="10,165" size="800,35" font="Regular;25" zPosition="1" />
					<widget source="list" render="Listbox" position="10,200" size="800,420" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (65,[
									MultiContentEntryText(pos = (20, 0), size = (500, 28), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
									MultiContentEntryText(pos = (620, 0), size = (240, 28), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1),
									MultiContentEntryText(pos = (20, 30), size = (750, 30), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 2),
								]),
								},
								"fonts": [gFont("Regular", 24),gFont("Regular", 20)],
								"itemHeight": 65
							}
						</convert>
					</widget>
					<widget name="status" position="10,200" size="800,420" font="Regular;25" halign="center" zPosition="1" />
					<widget foregroundColor="white" font="Regular;20" position="640,630" render="Label" size="200,35" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''
	else:
		skin = '''<screen position="center,center" size="1230,1020" flags="wfNoBorder">
					<ePixmap position="center,25" size="1200,150" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="15,185" size="1200,50" font="Regular;42" zPosition="1" />
					<widget name="subtitle" position="15,235" size="1200,45" font="Regular;38" zPosition="1" />
					<widget source="list" render="Listbox" position="15,300" size="1200,630" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (90,[
									MultiContentEntryText(pos = (20, 0), size = (1150, 40), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
									MultiContentEntryText(pos = (925, 0), size = (360, 40), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1),
									MultiContentEntryText(pos = (20, 42), size = (1150, 42), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 2),
								]),
								},
								"fonts": [gFont("Regular", 36),gFont("Regular", 32)],
								"itemHeight": 90
							}
						</convert>
					</widget>
					<widget name="status" position="15,300" size="1200,630" font="Regular;35" halign="center" zPosition="1" />
					<widget foregroundColor="white" font="Regular;32" position="920,955" render="Label" size="270,50" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''

	def __init__(self, session, main_title, title, url, standings_url, schedule_url):
		Screen.__init__(self, session)
		self.session = session
		self.standings_url = standings_url
		self.schedule_url = schedule_url

		self['title'] = Label(main_title)
		self['subtitle'] = Label(title)
		self['status'] = Label('Lade Daten...')

		self.eventList = []
		self['list'] = List(self.eventList)

		self['actions'] = ActionMap(['SetupActions', 'DirectionActions'],
		{
			'cancel': self.close,
			'ok': self.ok,
		})
		downloadTelekomSportJson(TelekomSportMainScreen.base_url + url, boundFunction(loadTelekomSportJsonData, 'EventLane', self['status'], self.buildList), boundFunction(handleTelekomSportDownloadError, 'EventLane', self['status']))

	def buildList(self, jsonData):
		try:
			for events in jsonData['data']['data']:
				if events['target_type'] and events['target_type'] == 'event' and (events['target_playable'] or not config.plugins.telekomsport.hide_unplayable.value):
					description = events['metadata']['description_bold'].encode('utf8')
					subdescription = events['metadata']['description_regular'].encode('utf8')
					original = events['metadata']['scheduled_start']['original'].encode('utf8')
					starttime = datetime.strptime(original, '%Y-%m-%d %H:%M:%S')
					starttime_str = starttime.strftime('%d.%m.%Y %H:%M')
					urlpart = events['target'].encode('utf8')
					if subdescription:
						description = description + ' - ' + subdescription
					if 'home' in events['metadata']['details']:
						home = events['metadata']['details']['home']['name_full'].encode('utf8')
						away = events['metadata']['details']['away']['name_full'].encode('utf8')
						self.eventList.append((description, starttime_str, home + ' - ' + away, urlpart, starttime))
					else:
						title = events['metadata']['title'].encode('utf8')
						self.eventList.append((description, starttime_str, title, urlpart, starttime))
		except Exception as e:
			self['status'].setText('Bitte Pluginentwickler informieren:\nTelekomSportEventLaneScreen ' + str(e))
			return

		self['list'].setList(self.eventList)
		self['status'].hide()

	def ok(self):
		if self['list'].getCurrent():
			description = self['list'].getCurrent()[0]
			match = self['list'].getCurrent()[2]
			urlpart = self['list'].getCurrent()[3]
			starttime = self['list'].getCurrent()[4]
			self.session.open(TelekomSportEventScreen, description, starttime, match, urlpart, self.standings_url, self.schedule_url)


class TelekomSportSportsTypeScreen(Screen):

	if getDesktop(0).size().width() <= 1280:
		skin = '''<screen position="center,center" size="820,680" flags="wfNoBorder">
					<ePixmap position="center,25" size="800,100" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="10,125" size="800,40" font="Regular;30" zPosition="1" />
					<widget name="subtitle" position="10,165" size="800,35" font="Regular;25" zPosition="1" />
					<widget source="list" render="Listbox" position="10,200" size="800,420" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (30,[
									MultiContentEntryText(pos = (0, 0), size = (750, 28), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
									MultiContentEntryText(pos = (50, 0), size = (750, 28), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1),
								]),
								},
								"fonts": [gFont("Regular", 20)],
								"itemHeight": 30
							}
						</convert>
					</widget>
					<widget name="status" position="10,200" size="800,420" font="Regular;25" halign="center" zPosition="1" />
					<widget name="buttonblue" position="15,630" size="160,35" backgroundColor="blue" valign="center" halign="center" zPosition="2" foregroundColor="white" font="Regular;20"/>
					<widget foregroundColor="white" font="Regular;20" position="640,630" render="Label" size="200,35" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''
	else:
		skin = '''<screen position="center,center" size="1230,1020" flags="wfNoBorder">
					<ePixmap position="center,25" size="1200,150" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="15,185" size="1200,50" font="Regular;42" zPosition="1" />
					<widget name="subtitle" position="15,235" size="1200,45" font="Regular;38" zPosition="1" />
					<widget source="list" render="Listbox" position="15,300" size="1200,630" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (45,[
									MultiContentEntryText(pos = (0, 0), size = (1180, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
									MultiContentEntryText(pos = (50, 0), size = (1140, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1),
								]),
								},
								"fonts": [gFont("Regular", 32)],
								"itemHeight": 45
							}
						</convert>
					</widget>
					<widget name="status" position="15,300" size="1200,630" font="Regular;35" halign="center" zPosition="1" />
					<widget name="buttonblue" position="35,955" size="240,50" backgroundColor="blue" valign="center" halign="center" zPosition="2" foregroundColor="white" font="Regular;32"/>
					<widget foregroundColor="white" font="Regular;32" position="920,955" render="Label" size="270,50" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''

	def __init__(self, session, title, url):
		Screen.__init__(self, session)
		self.session = session
		self.main_title = title
		self.standings_url = ''
		self.schedule_url = ''

		self['title'] = Label(title)
		self['subtitle'] = Label('')
		self['status'] = Label('Lade Daten...')

		self.eventLaneList = []
		self['list'] = List(self.eventLaneList)

		self['buttonblue'] = Label('')
		self['buttonblue'].hide()

		self['actions'] = ActionMap(['SetupActions', 'DirectionActions', 'ColorActions'],
		{
			'cancel': self.close,
			'ok': self.ok,
			'blue': self.showTableResults,
		})
		downloadTelekomSportJson(TelekomSportMainScreen.base_url + url, boundFunction(loadTelekomSportJsonData, 'SportsType', self['status'], self.buildList), boundFunction(handleTelekomSportDownloadError, 'SportsType', self['status']))

	def buildList(self, jsonData):
		try:
			title = ''
			for content in jsonData['data']['content']:
				if content['title'] and content['title'] != '':
					title = content['title'].encode('utf8')
				for group_element in content['group_elements']:
					if group_element['type'] == 'eventLane' or group_element['type'] == 'editorialLane':
						subtitle = group_element['title'].encode('utf8')
						urlpart = group_element['data_url'].encode('utf8')
						if content['title'] != '' and subtitle == '':
							self.eventLaneList.append((title, subtitle, title, urlpart))
						elif content['title'] != '' and subtitle != '':
							self.eventLaneList.append((title, '', title, ''))
							self.eventLaneList.append(('', subtitle, title + ' - ' + subtitle, urlpart))
						else:
							self.eventLaneList.append(('', subtitle, title + ' - ' + subtitle, urlpart))
			if 'navigation' in jsonData['data'] and 'header' in jsonData['data']['navigation']:
				for header in jsonData['data']['navigation']['header']:
					if header['target_type'] == 'standings':
						self.standings_url = header['target'].encode('utf8')
					if header['target_type'] == 'schedule':
						self.schedule_url = header['target'].encode('utf8')
				if self.standings_url or self.schedule_url:
					self['buttonblue'].setText('Tabelle/Spielplan')
					self['buttonblue'].show()
		except Exception as e:
			self['status'].setText('Bitte Pluginentwickler informieren:\nTelekomSportSportsTypeScreen ' + str(e))
			return

		self['list'].setList(self.eventLaneList)
		self['status'].hide()

	def ok(self):
		if self['list'].getCurrent():
			title = self['list'].getCurrent()[2]
			urlpart = self['list'].getCurrent()[3]
			if urlpart != '':
				self.session.open(TelekomSportEventLaneScreen, self.main_title, title, urlpart, self.standings_url, self.schedule_url)

	def showTableResults(self):
		if self.standings_url or self.schedule_url:
			self.session.open(TelekomSportStandingsResultsScreen, self.main_title, self.standings_url, self.schedule_url)


class TelekomSportMainScreen(Screen):

	base_url = 'https://www.telekomsport.de/api/v2'
	main_page = '/navigation'

	if getDesktop(0).size().width() <= 1280:
		skin = '''<screen position="center,center" size="820,680" flags="wfNoBorder">
					<ePixmap position="center,25" size="800,100" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="10,125" size="800,40" font="Regular;30" zPosition="1" />
					<widget name="subtitle" position="10,165" size="800,35" font="Regular;25" zPosition="1" />
					<widget source="list" render="Listbox" position="10,200" size="800,420" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (30,[
									MultiContentEntryText(pos = (0, 0), size = (750, 28), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
									MultiContentEntryText(pos = (50, 0), size = (750, 28), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1),
								]),
								},
								"fonts": [gFont("Regular", 20)],
								"itemHeight": 30
							}
						</convert>
					</widget>
					<widget name="status" position="10,200" size="800,420" font="Regular;25" halign="center" zPosition="1" />
					<widget name="buttonblue" position="15,630" size="140,35" backgroundColor="blue" valign="center" halign="center" zPosition="2" foregroundColor="white" font="Regular;20"/>
					<widget foregroundColor="white" font="Regular;20" position="640,630" render="Label" size="200,35" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''
	else:
		skin = '''<screen position="center,center" size="1230,1020" flags="wfNoBorder">
					<ePixmap position="center,25" size="1200,150" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="15,185" size="1200,50" font="Regular;42" zPosition="1" />
					<widget name="subtitle" position="15,235" size="1200,45" font="Regular;38" zPosition="1" />
					<widget source="list" render="Listbox" position="15,300" size="1200,630" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (45,[
									MultiContentEntryText(pos = (0, 0), size = (1180, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
									MultiContentEntryText(pos = (50, 0), size = (1140, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1),
								]),
								},
								"fonts": [gFont("Regular", 32)],
								"itemHeight": 45
							}
						</convert>
					</widget>
					<widget name="status" position="15,300" size="1200,630" font="Regular;35" halign="center" zPosition="1" />
					<widget name="buttonblue" position="35,955" size="220,50" backgroundColor="blue" valign="center" halign="center" zPosition="2" foregroundColor="white" font="Regular;32"/>
					<widget foregroundColor="white" font="Regular;32" position="920,955" render="Label" size="270,50" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''

	def __init__(self, session, args = None):
		Screen.__init__(self, session)
		self.session = session

		self['title'] = Label('')
		self['subtitle'] = Label('')
		self['status'] = Label('Lade Daten...')

		self.sportslist = []
		self['list'] = List(self.sportslist)

		self['buttonblue'] = Label('Einstellungen')

		self['actions'] = ActionMap(['SetupActions', 'DirectionActions', 'ColorActions'],
		{
			'cancel': self.close,
			'ok': self.ok,
			'blue': self.showSetup,
		})
		downloadTelekomSportJson(self.base_url + self.main_page, boundFunction(loadTelekomSportJsonData, 'Main', self['status'], self.buildList), boundFunction(handleTelekomSportDownloadError, 'Main', self['status']))

	def buildList(self, jsonData):
		default_section_choicelist = [('', 'Default')]

		try:
			for sports in jsonData['data']['filter']:
				title = sports['title'].encode('utf8')
				self.sportslist.append((title, '', title, sports['target'].encode('utf8')))
				default_section_choicelist.append((title, title))
				if sports['children']:
					for subsport in sports['children']:
						subtitle = subsport['title'].encode('utf8')
						self.sportslist.append(('', subtitle, title + ' - ' + subtitle, subsport['target'].encode('utf8')))
						default_section_choicelist.append((subtitle, subtitle))
		except Exception as e:
			self['status'].setText('Bitte Pluginentwickler informieren:\nTelekomSportMainScreen ' + str(e))
			return

		config.plugins.telekomsport.default_section_chooser.setChoices(default_section_choicelist, '')

		self['list'].setList(self.sportslist)
		self['status'].hide()
		self.selectDefaultSportsType()

	def ok(self):
		if self['list'].getCurrent():
			title = self['list'].getCurrent()[2]
			urlpart = self['list'].getCurrent()[3]
			self.session.open(TelekomSportSportsTypeScreen, title, urlpart)

	def selectDefaultSportsType(self):
		if config.plugins.telekomsport.default_section.value:
			items =  filter(lambda x: x[0] == config.plugins.telekomsport.default_section.value or x[1] == config.plugins.telekomsport.default_section.value, self.sportslist)
			if items:
				self.selectSportsType(items[0])

	def selectSportsType(self, item):
		if item:
			title = item[2]
			urlpart = item[3]
			self.session.open(TelekomSportSportsTypeScreen, title, urlpart)

	def showSetup(self):
		self.session.open(TelekomSportConfigScreen)


def main(session, **kwargs):
	session.open(TelekomSportMainScreen)

def Plugins(**kwargs):
	return PluginDescriptor(name='Telekom Sport', description=_('Telekom Sport Plugin'), where = PluginDescriptor.WHERE_PLUGINMENU, icon='plugin.png', fnc=main)
