# -*- coding: utf-8 -*-

from skin import loadSkin
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.InfoBarGenerics import InfoBarMenu, InfoBarSeek, InfoBarNotifications, InfoBarServiceNotifications, InfoBarShowHide, InfoBarSimpleEventView, InfoBarServiceErrorPopupSupport
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Screens.Setup import SetupSummary
from Components.ActionMap import ActionMap
from Components.ServiceEventTracker import InfoBarBase
from Components.Sources.List import List
from Components.Label import Label
from Components.MultiContent import MultiContentEntryText, MultiContentEntryProgress
from Components.Pixmap import Pixmap
from Components.ConfigList import ConfigListScreen
from Components.config import config, getConfigListEntry, ConfigSubsection, ConfigText, ConfigPassword, ConfigInteger, ConfigNothing, ConfigYesNo, ConfigSelection, NoSave
from Tools.BoundFunction import boundFunction
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from downloader import TelekomSportDownloadWithProgress

from enigma import eTimer, eListboxPythonMultiContent, gFont, eEnv, eServiceReference, getDesktop, eConsoleAppContainer

import xml.etree.ElementTree as ET
import time
import urllib
import urllib2
import json
import base64
import re
import random
import string
import hashlib
from os import path
from itertools import cycle, izip
from datetime import datetime
from twisted.web.client import Agent, readBody
from twisted.internet import reactor
from twisted.web.http_headers import Headers


if getDesktop(0).size().width() <= 1280:
	loadSkin(resolveFilename(SCOPE_PLUGINS) + "Extensions/TelekomSport/skin_hd.xml")
else:
	loadSkin(resolveFilename(SCOPE_PLUGINS) + "Extensions/TelekomSport/skin_fhd.xml")

try:
	from enigma import eMediaDatabase
	telekomsport_isDreamOS = True

	import ssl
	try:
		_create_unverified_https_context = ssl._create_unverified_context
	except AttributeError:
		pass
	else:
		ssl._create_default_https_context = _create_unverified_https_context

except:
	telekomsport_isDreamOS = False

#==== workaround for TLSv1_2 with DreamOS =======
from OpenSSL import SSL
from twisted.internet.ssl import ClientContextFactory
try:
	# available since twisted 14.0
	from twisted.internet._sslverify import ClientTLSOptions
except ImportError:
	ClientTLSOptions = None
#================================================

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
# Some images like DreamOS need streams with fix quality
config.plugins.telekomsport.fix_stream_quality = ConfigYesNo(default = telekomsport_isDreamOS)
config.plugins.telekomsport.stream_quality = ConfigSelection(default = "2", choices = [("0", _("sehr gering")), ("1", _("gering")), ("2", _("mittel")), ("3", _("hoch")), ("4", _("sehr hoch"))])
config.plugins.telekomsport.conf_alarm_duration = ConfigSelection(default = "8000", choices = [("4000", "4 Sekunden"), ("6000", "6 Sekunden"), ("8000", "8 Sekunden"), ("10000", "10 Sekunden"), ("12000", "12 Sekunden")])


def encode(x):
	return base64.encodestring(''.join(chr(ord(c) ^ ord(k)) for c, k in izip(x, cycle('password protection')))).strip()

def decode(x):
	return ''.join(chr(ord(c) ^ ord(k)) for c, k in izip(base64.decodestring(x), cycle('password protection')))

def readPasswords(session):
	try:
		with open('/etc/enigma2/MagentaSport.cfg', 'rb') as f:
			p1 = decode(f.readline())
			p2 = decode(f.readline())
		return p1, p2
	except Exception as e:
		session.open(MessageBox, 'Error reading passwords' + str(e), MessageBox.TYPE_ERROR)
		print "Error reading MagentaSport.cfg", e
		return '', ''

def savePasswords(session, p1, p2):
	try:
		with open('/etc/enigma2/MagentaSport.cfg', 'wb') as f:
			f.write(encode(p1) + '\n')
			f.write(encode(p2))
		return True
	except Exception as e:
		session.open(MessageBox, 'Error writing passwords' + str(e), MessageBox.TYPE_ERROR)
		print "Error writing MagentaSport.cfg", e
		return False

def loadTelekomSportJsonData(screen, statusField, buildListFunc, data):
	try:
		jsonResult = json.loads(data)

		if statusField:
			if 'status' not in jsonResult or jsonResult['status'] != 'success':
				statusField.setText(screen + ': Fehler beim Laden der JSON Daten: "Status ist nicht success"')
				return
		buildListFunc(jsonResult)
	except Exception as e:
		statusField.setText(screen + ': Fehler beim Laden der JSON Daten "' + str(e) + '"')

def handleTelekomSportWebsiteResponse(callback, response):
	d = readBody(response)
	d.addCallback(callback)
	return d

def handleTelekomSportDownloadError(screen, statusField, err):
	if statusField:
		statusField.setText(screen + ': Fehler beim Download "' + str(err) + '"')

def downloadTelekomSportJson(url, callback, errorCallback):
	if telekomsport_isDreamOS == False:
		agent = Agent(reactor)
	else:
		class WebClientContextFactory(ClientContextFactory):
			"A SSL context factory which is more permissive against SSL bugs."

			def __init__(self):
				self.method = SSL.SSLv23_METHOD

			def getContext(self, hostname=None, port=None):
				ctx = ClientContextFactory.getContext(self)
				# Enable all workarounds to SSL bugs as documented by
				# http://www.openssl.org/docs/ssl/SSL_CTX_set_options.html
				ctx.set_options(SSL.OP_ALL)
				if hostname and ClientTLSOptions is not None: # workaround for TLS SNI
					ClientTLSOptions(hostname, ctx)
				return ctx

		contextFactory = WebClientContextFactory()
		agent = Agent(reactor, contextFactory)
	d = agent.request('GET', url, Headers({'user-agent': ['Twisted']}))
	d.addCallback(boundFunction(handleTelekomSportWebsiteResponse, callback))
	d.addErrback(errorCallback)


class TelekomSportRedirectHandler(urllib2.HTTPRedirectHandler):

	screen = None

	def __init__(self, screen):
		self.screen = screen

	def http_error_302(self, req, fp, code, msg, headers):
		location = headers.getheaders('Location')[0]
		pos = location.find('code=') + 5
		self.screen.auth_code = location[pos: pos + 8]
		return None


class TelekomSportMainScreenSummary(SetupSummary):

	def __init__(self, session, parent):
		SetupSummary.__init__(self, session, parent = parent)
		self.skinName = 'SetupSummary'
		self.onShow.append(self.addWatcher)
		self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		self.parent['list'].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def removeWatcher(self):
		self.parent['list'].onSelectionChanged.remove(self.selectionChanged)


class TelekomSportConfigScreen(ConfigListScreen, Screen):

	ts_font_str = ""
	if getDesktop(0).size().width() <= 1280:
		if not telekomsport_isDreamOS:
			ts_font_str = 'font="Regular;20"'
		skin = '''<screen position="center,center" size="680,440" flags="wfNoBorder">
					<ePixmap position="center,10" size="640,60" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="config" position="10,85" size="650,330" ''' + ts_font_str + ''' scrollbarMode="showOnDemand" />
					<widget name="buttonred" position="10,395" size="120,35" backgroundColor="red" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;20"/>
					<widget name="buttongreen" position="155,395" size="120,35" backgroundColor="green" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;20"/>
					<widget name="buttonblue" position="300,395" size="135,35" backgroundColor="blue" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;20"/>
					<widget name="HelpWindow" position="0,0" size="1,1" zPosition="1" transparent="1" alphatest="on"/>
				</screen>'''
	else:
		if not telekomsport_isDreamOS:
			ts_font_str = 'font="Regular;32"'
		skin = '''<screen position="center,center" size="1020,700" flags="wfNoBorder">
					<ePixmap position="center,15" size="980,90" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="config" position="15,120" size="990,500" ''' + ts_font_str + ''' itemHeight="42" scrollbarMode="showOnDemand" />
					<widget name="buttonred" position="15,640" size="180,50" backgroundColor="red" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;32"/>
					<widget name="buttongreen" position="225,640" size="180,50" backgroundColor="green" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;32"/>
					<widget name="buttonblue" position="435,640" size="215,50" backgroundColor="blue" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;32"/>
					<widget name="HelpWindow" position="0,0" size="1,1" zPosition="1" transparent="1" alphatest="on"/>
				</screen>'''

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

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
		self.config_fix_stream_quality = getConfigListEntry('Feste Stream Qualität verwenden', config.plugins.telekomsport.fix_stream_quality)
		self.list.append(self.config_fix_stream_quality)
		self.config_stream_quality = getConfigListEntry('Stream Qualität', config.plugins.telekomsport.stream_quality)
		self.list.append(self.config_stream_quality)
		self.config_conf_alarm_duration = getConfigListEntry('Anzeigedauer Konferenzalarm', config.plugins.telekomsport.conf_alarm_duration)
		self.list.append(self.config_conf_alarm_duration)

		ConfigListScreen.__init__(self, self.list, session)
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
		p1, p2 = readPasswords(session)
		config.plugins.telekomsport.password1.value = p1
		config.plugins.telekomsport.password2.value = p2
		config.plugins.telekomsport.default_section_chooser.value = config.plugins.telekomsport.default_section.value

		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()

		self.onLayoutFinish.append(self.setWindowTitle)

	def setWindowTitle(self):
		self.setTitle(TelekomSportMainScreen.title + ' Einstellungen')

	def save(self):
		savePasswords(self.session, config.plugins.telekomsport.password1.value, config.plugins.telekomsport.password2.value)
		config.plugins.telekomsport.password1.value = ''
		config.plugins.telekomsport.token1.value = ''
		config.plugins.telekomsport.token1_expiration_time.value = 0
		config.plugins.telekomsport.password2.value = ''
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

	# for summary
	def createSummary(self):
		from Screens.SimpleSummary import SimpleSummary
		return SimpleSummary


class TelekomSportConferenceAlarm(Screen):

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.setup_title = TelekomSportMainScreen.title
		self['list'] = List()
		self['logo_on'] = Pixmap()
		self['logo_off'] = Pixmap()
		self['logo_off'].hide()

		self.close_timer = eTimer()
		if telekomsport_isDreamOS:
			self.close_timer_conn = self.close_timer.timeout.connect(self.hide_screen)
		else:
			self.close_timer.callback.append(self.hide_screen)

		self.onShow.append(self.startTimer)
		self.onHide.append(self.stopTimer)

	def startTimer(self):
		if self.close_timer.isActive():
			self.close_timer.stop()
		self.close_timer.start(int(config.plugins.telekomsport.conf_alarm_duration.value), True)

	def stopTimer(self):
		if self.close_timer.isActive():
			self.close_timer.stop()

	def hide_screen(self):
		self.hide()
		self.shown = False


class TelekomSportMoviePlayer(Screen, InfoBarMenu, InfoBarBase, InfoBarSeek, InfoBarNotifications, InfoBarServiceNotifications, InfoBarShowHide, InfoBarSimpleEventView, InfoBarServiceErrorPopupSupport):

	conference_alarm_url = 'https://www.magentasport.de/api/v2/player/alert/history'

	def __init__(self, session, service, standings_url, schedule_url, statistics_url, boxscore_url, conference_alarm_available, league_id, video_id):
		Screen.__init__(self, session)
		self.skinName = 'MoviePlayer'
		self.title = service.getName()

		InfoBarMenu.__init__(self)
		InfoBarBase.__init__(self)
		InfoBarNotifications.__init__(self)
		InfoBarServiceNotifications.__init__(self)
		InfoBarShowHide.__init__(self)
		InfoBarSimpleEventView.__init__(self)
		InfoBarSeek.__init__(self)
		InfoBarServiceErrorPopupSupport.__init__(self)

		# disable 2nd infobar as it calls openEventView
		if hasattr(config.usage, "show_second_infobar"):
			self.saved_show_second_infobar_value = config.usage.show_second_infobar.value
			config.usage.show_second_infobar.value = '0'

		self.service = service
		self.lastservice = self.session.nav.getCurrentlyPlayingServiceReference()
		self.standings_url = standings_url
		self.schedule_url = schedule_url
		self.statistics_url = statistics_url
		self.boxscore_url = boxscore_url

		self.conference_alarm_available = conference_alarm_available
		self.league_id = league_id
		self.video_id = video_id

		self.conference_alarm_timer = eTimer()
		if telekomsport_isDreamOS:
			self.conference_alarm_timer_conn = self.conference_alarm_timer.timeout.connect(self.checkAlarmHistory)
		else:
			self.conference_alarm_timer.callback.append(self.checkAlarmHistory)
		self.conference_complete_alarm_list = []

		self.conference_alarm_dialog = self.session.instantiateDialog(TelekomSportConferenceAlarm)
		self.conference_alarm_dialog.hide_screen()

		self['actions'] = ActionMap(['MoviePlayerActions', 'ColorActions', 'OkCancelActions', 'SetupActions'],
		{
			'leavePlayer': self.leavePlayer,
			'cancel'     : self.leavePlayer,
			'leavePlayerOnExit': self.leavePlayerOnExit,
			'deleteBackward'   : self.showLastConfAlarm,
			'red'   : self.showBoxScore,
			'green' : self.showStatistics,
			'yellow': self.showSchedule,
			'blue'  : self.showStandings,
		}, -2)
		self.onFirstExecBegin.append(self.playStream)
		self.onClose.append(self.stopPlayback)
		self.onLayoutFinish.append(self.onLayoutFinished)

	def onLayoutFinished(self):
		if self.conference_alarm_available:
			self.conference_alarm_dialog.show()

	def playStream(self):
		self.session.nav.playService(self.service)

	def stopPlayback(self):
		if self.lastservice:
			self.session.nav.playService(self.lastservice)
		else:
			self.session.nav.stopService()

	def leavePlayer(self):
		if self.conference_alarm_dialog.shown:
			self.conference_alarm_dialog.hide_screen()
		else:
			self.session.openWithCallback(self.leavePlayerConfirmed, MessageBox, 'Abspielen beenden?')

	def leavePlayerOnExit(self):
		self.leavePlayer()

	def leavePlayerConfirmed(self, answer):
		if answer:
			self.session.deleteDialog(self.conference_alarm_dialog)
			self.conference_alarm_dialog = None
			# restore old 2nd infobar config value
			if hasattr(config.usage, "show_second_infobar"):
				config.usage.show_second_infobar.value = self.saved_show_second_infobar_value
			self.close()

	def openEventView(self):
		if self.conference_alarm_available and not self.conference_alarm_timer.isActive():
			self.conference_complete_alarm_list = []
			self.conference_alarm_dialog['logo_on'].hide()
			self.conference_alarm_dialog['logo_off'].hide()
			self.checkAlarmHistory(True)
			self.conference_alarm_timer.start(20000, False)
		elif self.conference_alarm_available and self.conference_alarm_timer.isActive():
			self.conference_alarm_timer.stop()
			self.conference_alarm_dialog['logo_off'].show()
			self.conference_alarm_dialog['list'].setList([])
			self.conference_alarm_dialog.show()

	def showBoxScore(self):
		if self.boxscore_url:
			self.session.open(TelekomSportBoxScoreScreen, self.boxscore_url)

	def showStatistics(self):
		if self.statistics_url:
			self.session.open(TelekomSportStatisticsScreen, self.statistics_url)

	def showSchedule(self):
		if self.schedule_url:
			self.session.open(TelekomSportScheduleScreen, self.schedule_url)

	def showStandings(self):
		if self.standings_url:
			self.session.open(TelekomSportStandingsScreen, self.standings_url)

	def showMovies(self):
		pass

	def checkAlarmHistory(self, showAll = False):
		downloadTelekomSportJson(self.conference_alarm_url, boundFunction(loadTelekomSportJsonData, 'Player', None, boundFunction(self.checkForNewAlarm, showAll)), self.checkAlarmHistoryError)

	def checkForNewAlarm(self, showAll, jsonData):
		try:
			new_alarms_list = []
			complete_list = []
			if 'leagues' in jsonData['data']:
				for league in jsonData['data']['leagues']:
					if self.league_id == league.encode('utf8'):
						leagueEvents = jsonData['data']['leagues'][league]
						for ev in leagueEvents['events']:
							title = leagueEvents['events'][ev]['title'].encode('utf8')
							text = leagueEvents['events'][ev]['text'].encode('utf8')
							if leagueEvents['events'][ev]['imageRightAlt']:
								match = leagueEvents['events'][ev]['imageLeftAlt'].encode('utf8') + ' : ' + leagueEvents['events'][ev]['imageRightAlt'].encode('utf8')
							else:
								match = leagueEvents['events'][ev]['imageLeftAlt'].encode('utf8')
							eventid = leagueEvents['events'][ev]['eventid']
							videoid = leagueEvents['events'][ev]['videoid']
							# don't show events from current stream to avoid showing events before they are visible in the stream (playback may be behind live point)
							if str(videoid) == self.video_id:
								continue

							complete_list.append((ev, match, title, text, eventid, videoid))

							if (filter(lambda x: x[0] == ev, self.conference_complete_alarm_list) == []) or showAll: # event not found in the current list or conference alarm enabled -> show all events
								new_alarms_list.append((ev, match, title, text, eventid, videoid))

						self.conference_complete_alarm_list = complete_list
			if len(new_alarms_list) > 0 or showAll:
				new_alarms_list.sort(key=lambda x: x[0], reverse=True)
				self.conference_alarm_dialog['list'].setList(new_alarms_list)
				self.conference_alarm_dialog.show()

		except Exception as e:
			print "MagentaSport error checkForNewAlarm", e
			self.conference_alarm_timer.stop()

	def checkAlarmHistoryError(self, err):
		print "MagentaSport checkAlarmHistoryError", err
		self.conference_alarm_timer.stop()

	def showLastConfAlarm(self):
		if self.conference_alarm_available and self.conference_alarm_timer.isActive():
			self.conference_alarm_dialog.show()

	# for summary
	def createSummary(self):
		from Screens.SimpleSummary import SimpleSummary
		return SimpleSummary


class TelekomSportBoxScoreScreen(Screen):

	def __init__(self, session, boxscore_url):
		Screen.__init__(self, session)
		self.session = session

		self.setup_title = TelekomSportMainScreen.title

		self['status'] = Label('Lade Daten...')
		self['title'] = Label('Ergebnis')
		self['match_home'] = Label()
		self['match_away'] = Label()
		self['endResult'] = Label()
		self['version'] = Label(TelekomSportMainScreen.version)

		self.resultList = []
		self['list'] = List(self.resultList)

		self['actions'] = ActionMap(['OkCancelActions'],
		{
			'ok': self.close,
			'cancel': self.close,
		})
		downloadTelekomSportJson(TelekomSportMainScreen.base_url + boxscore_url, boundFunction(loadTelekomSportJsonData, 'BoxScore', self['status'], self.loadBoxScore), boundFunction(handleTelekomSportDownloadError, 'BoxScore', self['status']))

	def loadBoxScore(self, jsonData):
		if not jsonData['data'] or not jsonData['data']['data'] or not jsonData['data']['data']['results'] or not jsonData['data']['type'] == 'boxScore':
			self['status'].setText('Bitte Pluginentwickler informieren:\nTelekomSportBoxScoreScreen BoxScore')
			return

		try:
			home = jsonData['data']['data']['teams']['home']['name'].encode('utf8')
			away = jsonData['data']['data']['teams']['away']['name'].encode('utf8')
			result_home = str(jsonData['data']['data']['results']['home']).encode('utf8')
			result_away = str(jsonData['data']['data']['results']['away']).encode('utf8')
			self['match_home'].setText(home)
			self['match_away'].setText(away)
			self['endResult'].setText(result_home + ' : ' + result_away)
			for period in jsonData['data']['data']['results']['periods']:
				self.resultList.append((period['name'].encode('utf8') + '  ' + period['value'].encode('utf8'), ''))
		except Exception as e:
			self['status'].setText('Bitte Pluginentwickler informieren:\nTelekomSportBoxScoreScreen BoxScore ' + str(e))
			return

		self['list'].setList(self.resultList)
		self['status'].hide()

	# for summary
	def getCurrentEntry(self):
		return self['title'].getText()

	def getCurrentValue(self):
		return self['endResult'].getText()

	def createSummary(self):
		return TelekomSportMainScreenSummary


class TelekomSportStatisticsScreen(Screen):

	def __init__(self, session, statistics_url):
		Screen.__init__(self, session)
		self.session = session

		self.setup_title = TelekomSportMainScreen.title

		self['status'] = Label('Lade Daten...')
		self['match'] = Label()
		self['title'] = Label('Spielstatistiken')
		self['version'] = Label(TelekomSportMainScreen.version)

		self.statList = []
		self['list'] = List(self.statList)

		self['actions'] = ActionMap(['OkCancelActions'],
		{
			'ok': self.close,
			'cancel': self.close,
		})
		downloadTelekomSportJson(TelekomSportMainScreen.base_url + statistics_url, boundFunction(loadTelekomSportJsonData, 'Statistic', self['status'], self.loadStatistics), boundFunction(handleTelekomSportDownloadError, 'Statistics', self['status']))

	def loadStatistics(self, jsonData):
		if not jsonData['data']:
			return

		try:
			for ev in jsonData['data']:
				self['match'].setText(jsonData['data'][ev]['name'].encode('utf8'))
				for stat in jsonData['data'][ev]['statistics']:
					stat_name = stat['name'].encode('utf8')
					if stat['data']['type'] == 'ratio':
						home_prop = stat['data']['home']['proportion']
						home_total = stat['data']['home']['total']
						away_prop = stat['data']['away']['proportion']
						away_total = stat['data']['away']['total']
						if home_total == 0:
							home_percent = 0
						else:
							home_percent = float(home_prop) / home_total * 100
						if away_total == 0:
							away_percent = 0
						else:
							away_percent = float(away_prop) / away_total * 100
						if home_percent == 0 and away_percent == 0:
							percent = 50
						else:
							percent = int(home_percent / (home_percent + away_percent) * 100)
						home_value_str = str(int(home_percent)) + '% (' + str(home_prop) + '/' + str(home_total) + ')'
						away_value_str = str(int(away_percent)) + '% (' + str(away_prop) + '/' + str(away_total) + ')'
					elif stat['data']['type'] == 'single':
						home_value = stat['data']['home']['value']
						away_value = stat['data']['away']['value']
						if home_value == 0 and away_value == 0:
							percent = 50
						else:
							percent = int(float(home_value) / (home_value + away_value) * 100)
						home_value_str = str(home_value).encode('utf8')
						away_value_str = str(away_value).encode('utf8')
					else:
						continue
					self.statList.append((home_value_str, stat_name, away_value_str, percent))
		except Exception as e:
			self['status'].setText('Bitte Pluginentwickler informieren:\nTelekomSportStatisticsScreen ' + str(e))
			return

		self['list'].setList(self.statList)
		self['status'].hide()

	# for summary
	def getCurrentEntry(self):
		return self['title'].getText()

	def getCurrentValue(self):
		return self['match'].getText()

	def createSummary(self):
		return TelekomSportMainScreenSummary


class TelekomSportScheduleScreen(Screen):

	def __init__(self, session, schedule_url):
		Screen.__init__(self, session)
		self.session = session

		self.setup_title = TelekomSportMainScreen.title

		self['title'] = Label()
		self['subtitle'] = Label('Spielplan')
		self['status'] = Label('Lade Daten...')
		self['version'] = Label(TelekomSportMainScreen.version)

		self.scheduleList = []
		self['list'] = List()

		self['actions'] = ActionMap(['SetupActions', 'DirectionActions'],
		{
			'cancel': self.close,
			'ok': self.close,
		})
		downloadTelekomSportJson(TelekomSportMainScreen.base_url + schedule_url, boundFunction(loadTelekomSportJsonData, 'Schedule', self['status'], self.loadSchedule), boundFunction(handleTelekomSportDownloadError, 'Schedule', self['status']))

	def loadSchedule(self, jsonData):
		try:
			self['title'].setText(jsonData['data']['metadata']['parent_title'].encode('utf8'))
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
			self['status'].setText('Bitte Pluginentwickler informieren:\nTelekomSportScheduleScreen ' + str(e))
			return

		self['list'].setList(self.scheduleList)
		self['status'].hide()

	# for summary
	def getCurrentEntry(self):
		return self['title'].getText()

	def getCurrentValue(self):
		return self['subtitle'].getText()

	def createSummary(self):
		return TelekomSportMainScreenSummary


class TelekomSportStandingsScreen(Screen):

	def __init__(self, session, standings_url):
		Screen.__init__(self, session)
		self.session = session

		self.setup_title = TelekomSportMainScreen.title

		self['title'] = Label()
		self['subtitle'] = Label('Tabelle')
		self['table_header_team'] = Label('Team')
		self['table_header_matches'] = Label('Spiele')
		self['table_header_wins'] = Label('S')
		self['table_header_draws'] = Label('U')
		self['table_header_losses'] = Label('N')
		self['table_header_goals'] = Label('Tore')
		self['table_header_goaldiff'] = Label('Diff')
		self['table_header_points'] = Label('Punkte')
		self['status'] = Label('Lade Daten...')
		self['version'] = Label(TelekomSportMainScreen.version)

		self.standingsList = []
		self.playoffStandingsList = []
		self['list'] = List()
		self.curr = 'standings'

		self['buttonblue'] = Label('')
		self['buttonblue'].hide()

		self['actions'] = ActionMap(['SetupActions', 'DirectionActions', 'ColorActions'],
		{
			'cancel': self.close,
			'ok': self.close,
			'blue': self.switchList,
		})
		self.toogleStandingsVisibility(False)
		downloadTelekomSportJson(TelekomSportMainScreen.base_url + standings_url, boundFunction(loadTelekomSportJsonData, 'Standings', self['status'], self.loadStandings), boundFunction(handleTelekomSportDownloadError, 'Standings', self['status']))

	def toogleStandingsVisibility(self, show):
		self['table_header_team'].setVisible(show)
		self['table_header_matches'].setVisible(show)
		self['table_header_wins'].setVisible(show)
		self['table_header_draws'].setVisible(show)
		self['table_header_losses'].setVisible(show)
		self['table_header_goals'].setVisible(show)
		self['table_header_goaldiff'].setVisible(show)
		self['table_header_points'].setVisible(show)

	def showStandings(self):
		self['status'].hide()
		self['subtitle'].setText('Tabelle')
		if self['status'].getText() == '' or self['status'].getText() == 'Lade Daten...':
			self.toogleStandingsVisibility(True)
			self['status'].hide()
			self['list'].style = 'default'
			self['list'].setList(self.standingsList)
		else:
			self['status'].show()

	def showPlayoff(self):
		self['status'].hide()
		self['subtitle'].setText('Tabelle - Playoffs')
		if self['status'].getText() == '' or self['status'].getText() == 'Lade Daten...':
			self.toogleStandingsVisibility(False)
			self['list'].style = 'playoff'
			self['list'].setList(self.playoffStandingsList)
		else:
			self['status'].show()

	def switchList(self):
		if self.curr == 'standings' and self.playoffStandingsList:
			self.curr = 'playoff'
			self['buttonblue'].setText('Tabelle')
			self.showPlayoff()
		elif self.curr == 'standings' and not self.playoffStandingsList:
			self.showStandings()
		elif self.curr == 'playoff' and self.standingsList:
			self.curr = 'standings'
			self['buttonblue'].setText('Tabelle - Playoffs')
			self.showStandings()
		elif self.curr == 'playoff' and not self.standingsList:
			self.showPlayoff()

	def loadNormalStandingsTable(self, standingsList, jsonData, table):
		for team in jsonData['ranking']:
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
			standingsList.append((str(rank), team_title, played, win, draw, loss, goals_for + ':' + goals_against, goal_diff, points, table, rank))

	def loadNormalStandings(self, jsonData):
		try:
			if len(jsonData['data']['standing']) == 1:
				self.loadNormalStandingsTable(self.standingsList, jsonData['data']['standing'][0], 1)
			else:
				self.loadNormalStandingsTable(self.standingsList, jsonData['data']['standing'][0], 1)
				self.loadNormalStandingsTable(self.standingsList, jsonData['data']['standing'][1], 2)
				# add headers for the 2 icehockey standings
				self.standingsList.append(('', 'Nord', '', '', '', '', '', '', '', 1, 0))
				self.standingsList.append(('', '', '', '', '', '', '', '', '', 2, -1))
				self.standingsList.append(('', '', '', '', '', '', '', '', '', 2, -2))
				self.standingsList.append(('', 'Süd', '', '', '', '', '', '', '', 2, 0))
			self.standingsList = sorted(self.standingsList, key = lambda entry: (entry[9], entry[10]))
			if not self.playoff_standings_url:
				self.switchList()
		except Exception as e:
			self['status'].setText('Aktuell steht die Tabelle nicht zur Verfügung. Bitte versuchen sie es später noch einmal.' + str(e))
			return

	def loadPlayoffStandings(self, jsonData):
		try:
			if 'title' in jsonData['data']:
				title = jsonData['data']['title'].encode('utf8')
			else:
				title = ''
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
			self.switchList()
		except Exception as e:
			self['status'].setText('Aktuell steht die Playoff Tabelle nicht zur Verfügung. Bitte versuchen sie es später noch einmal.' + str(e))
			return

	def loadStandings(self, jsonData):
		self.normal_standings_url = ''
		self.playoff_standings_url = ''
		try:
			self['title'].setText(jsonData['data']['metadata']['parent_title'].encode('utf8'))
			for c in jsonData['data']['content']:
				for g in c['group_elements']:
					if g['type'] == 'standings':
						self.normal_standings_url = g['data']['urls']['standings_url'].encode('utf8')
					elif g['type'] == 'playoffTree':
						self.playoff_standings_url = g['data']['url'].encode('utf8')
		except Exception as e:
			self['status'].setText('Aktuell steht die Tabelle nicht zur Verfügung. Bitte versuchen sie es später noch einmal.')
			return

		if self.normal_standings_url:
			downloadTelekomSportJson(TelekomSportMainScreen.base_url + self.normal_standings_url, boundFunction(loadTelekomSportJsonData, 'NormalStandings', self['status'], self.loadNormalStandings), boundFunction(handleTelekomSportDownloadError, 'NormalStandings', self['status']))
		if self.playoff_standings_url:
			downloadTelekomSportJson(TelekomSportMainScreen.base_url + self.playoff_standings_url, boundFunction(loadTelekomSportJsonData, 'PlayoffStandings', self['status'], self.loadPlayoffStandings), boundFunction(handleTelekomSportDownloadError, 'PlayoffStandings', self['status']))
		if self.normal_standings_url and self.playoff_standings_url:
			self['buttonblue'].show()

	# for summary
	def getCurrentEntry(self):
		return self['title'].getText()

	def getCurrentValue(self):
		return self['subtitle'].getText()

	def createSummary(self):
		return TelekomSportMainScreenSummary


class TelekomSportEventScreen(Screen):

	oauth_url = 'https://accounts.login.idm.telekom.com/oauth2/auth'
	oauth_factorx_url = 'https://accounts.login.idm.telekom.com/factorx'
	oauth_token_url = 'https://accounts.login.idm.telekom.com/oauth2/tokens'
	jwt_url = 'https://www.magentasport.de/service/auth/app/login/jwt'
	stream_access_url = 'https://www.magentasport.de/service/player/v2/streamAccess'
	auth_code = ''

	def __init__(self, session, description, starttime, match, url, standings_url, schedule_url):
		Screen.__init__(self, session)
		self.session = session
		self.starttime = starttime
		self.standings_url = standings_url
		self.schedule_url = schedule_url
		self.match = match

		self.statistics_url = ''
		self.boxscore_url = ''
		self.conference_alarm_available = False
		self.league_id = ''

		self.setup_title = TelekomSportMainScreen.title

		self['match'] = Label(match)
		self['description'] = Label(description)
		self['subdescription'] = Label('')
		self['status'] = Label('Lade Daten...')
		self['pay'] = Label('* = Abo benötigt')
		self['confalarm'] = Label('')
		self['version'] = Label(TelekomSportMainScreen.version)

		self.videoList = []
		self['list'] = List(self.videoList)

		self['actions'] = ActionMap(['MenuActions', 'SetupActions', 'DirectionActions'],
		{
			'menu': self.closeRecursive,
			'cancel': self.close,
			'ok': self.ok,
		})
		downloadTelekomSportJson(TelekomSportMainScreen.base_url + url, boundFunction(loadTelekomSportJsonData, 'Event', self['status'], self.buildScreen), boundFunction(handleTelekomSportDownloadError, 'Event', self['status']))

	def closeRecursive(self):
		self.close(True)

	def findXsrfTid(self, html):
		pos = html.find('name="xsrf')
		xsrf_name = html[pos + 6: pos + 33]
		pos = html.find('value=',pos)
		xsrf_value = html[pos + 7: pos + 29]
		pos = html.find('name="tid" value="')
		tid = html[pos + 18: pos + 54]
		return xsrf_name, xsrf_value, tid

	def login(self, account, username, password, config_token, config_token_expiration_time):
		err = ''
		# check if token is present and valid
		if config_token.value and config_token_expiration_time.value > int(time.time()):
			return ''

		nonce = ''.join(random.sample(string.ascii_letters + string.digits, 20))
		code_verifier = ''.join(random.sample(string.ascii_letters + string.digits, 20))
		code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier).digest()).split('=')[0]
		state = ''.join(random.sample(string.ascii_letters + string.digits, 20))

		data = { 'prompt': 'x-no-sso', 'nonce': nonce, 'response_type': 'code', 'scope': 'openid', 'code_challenge': code_challenge, 'code_challenge_method': 'S256', 'redirect_uri': 'sso.magentasport://web_login_callback', 'client_id': '10LIVESAM30000004901MAGENTASPORTIOS00000', 'state': state}

		try:
			response = urllib.urlopen(self.oauth_url + '?' + urllib.urlencode(data), '')
			cookies = response.info().getheaders('Set-Cookie')
			html = response.read()
			xsrf_name, xsrf_value, tid = self.findXsrfTid(html)

			# send username
			data = { xsrf_name: xsrf_value, 'tid': tid, 'x-show-cancel': 'true', 'bdata': '' , 'pw_usr': username, 'pw_submit': '', 'hidden_pwd' :''}
			req = urllib2.Request(self.oauth_factorx_url, urllib.urlencode(data))
			req.add_header('Cookie', ';'.join(cookies))
			response = urllib2.urlopen(req)
			cookies += response.info().getheaders('Set-Cookie')
			html = response.read()
			xsrf_name, xsrf_value, tid = self.findXsrfTid(html)

			# send password
			data = { xsrf_name: xsrf_value, 'tid': tid, 'bdata':'' , 'hidden_usr': username, 'pw_submit': '', 'pw_pwd': password }
			# request is redirected which needs to be prevented
			opener = urllib2.build_opener(TelekomSportRedirectHandler(self)).open
			req = urllib2.Request(self.oauth_factorx_url, urllib.urlencode(data))
			req.add_header('Cookie', ';'.join(cookies))
			try:
				response = opener(req)
			except Exception as e: # ignore redirect error we need only auth_code which is set in the handler
				pass
			if self.auth_code == '':
				return 'Fehler beim Login ' + str(account) + '. Account. Kein auth code.'

			# get auth code token
			data = { 'code': self.auth_code, 'code_verifier': code_verifier, 'client_id': '10LIVESAM30000004901MAGENTASPORTIOS00000', 'grant_type': 'authorization_code' , 'redirect_uri': 'sso.magentasport://web_login_callback'}
			response = urllib2.urlopen(urllib2.Request(self.oauth_token_url, urllib.urlencode(data)))
			jsonData= json.loads(response.read())

			# get tsm token
			data = { 'refresh_token': jsonData['refresh_token'], 'client_id': '10LIVESAM30000004901MAGENTASPORTIOS00000', 'grant_type':'refresh_token', 'redirect_uri': 'sso.magentasport://web_login_callback', 'scope':'tsm'}
			response = urllib2.urlopen(urllib2.Request(self.oauth_token_url, urllib.urlencode(data)))
			jsonData= json.loads(response.read())
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
			p1, p2 = readPasswords(self.session)
			err = self.login(1, config.plugins.telekomsport.username1.value, p1, config.plugins.telekomsport.token1, config.plugins.telekomsport.token1_expiration_time)
			if err:
				return err
			else:
				if config.plugins.telekomsport.username2.value:
					err = self.login(2, config.plugins.telekomsport.username2.value, p2, config.plugins.telekomsport.token2, config.plugins.telekomsport.token2_expiration_time)
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
		except urllib2.URLError as e2:
			if 'CERTIFICATE_VERIFY_FAILED' in str(e2.reason):
				return '', -2
			return '', -1

	def readExtXStreamInfLine(self, line, attributeListPattern):
		line = line.replace('#EXT-X-STREAM-INF:', '')
		for param in attributeListPattern.split(line)[1::2]:
			if param.startswith('BANDWIDTH='):
				return param.strip().split('=')[1]
		return ''

	def getFixQualtiyStreamUrl(self, m3u8_url):
		try:
			attributeListPattern = re.compile(r'''((?:[^,"']|"[^"]*"|'[^']*')+)''')
			streams = []
			req = urllib2.Request(m3u8_url)
			req.add_header('User-Agent', 'Enigma2 HbbTV/1.1.1 (PVRRTSPDL;OpenPLi;;;)')
			response = urllib2.urlopen(req)
			self.cookies = response.info().getheaders('Set-Cookie')
			lines = response.readlines()
			if len(lines) > 0 and lines[0] == '#EXTM3U\n':
				i = 1
				count_lines = len(lines)
				while i < len(lines) - 1:
					if lines[i].startswith('#EXT-X-STREAM-INF:'):
						bandwith = self.readExtXStreamInfLine(lines[i], attributeListPattern)
						if bandwith and i + 1 < count_lines:
							streams.append((int(bandwith), lines[i+1].strip()))
					i += 1
				if streams:
					streams.sort(key = lambda x: x[0])
					if len(streams) <> 5:
						print 'Warning: %d streams in m3u8. 5 expected' % len(streams)
						if int(config.plugins.telekomsport.stream_quality.value) < 3:
							return streams[0][1]
						else:
							return streams[len(streams)-1][1]
					return streams[int(config.plugins.telekomsport.stream_quality.value)][1]
			return ''
		except:
			return ''

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
		elif errorCode == -2:
			self['status'].setText('Bitte stellen sie das Datum ein!')
			self['status'].show()
			return
		elif errorCode == -1:
			self['status'].setText('Es ist ein Fehler aufgetreten. Der Stream kann nicht abgespielt werden!')
			self['status'].show()
			return

		if config.plugins.telekomsport.fix_stream_quality.value:
			url = self.getFixQualtiyStreamUrl(playlisturl)
			if url:
				playlisturl = url + "#User-Agent=Enigma2 HbbTV/1.1.1 (PVRRTSPDL;OpenPLi;;;)&Cookie=" + ";".join(self.cookies)

		ref = eServiceReference(4097, 0, playlisturl)
		ref.setName(title)

		self.session.open(TelekomSportMoviePlayer, ref, self.standings_url, self.schedule_url, self.statistics_url, self.boxscore_url, self.conference_alarm_available, self.league_id, videoid)

	def buildPreEventScreen(self, jsonData):
		pay = ''
		for content in jsonData['data']['content']:
			if content['group_elements']:
				for element in content['group_elements']:
					if element['type'] == 'noVideo':
						if 'pay' in element['data']['metadata'] and element['data']['metadata']['pay']:
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
					if element['type'] in ('eventVideos', 'player'):
						if element['type'] == 'eventVideos':	# remove all previous player videolist entries. This is needed for Bayern.TV
							self.videoList = []
						for videos in element['data']:
							title = videos['title'].encode('utf8')
							if videos['pay']:
								title += ' *'
							self.videoList.append((title, self.match + ' - ' + videos['title'].encode('utf8'), str(videos['videoID']), str(videos['pay'])))
					elif element['type'] == 'statistics':
						self.statistics_url = element['data']['url'].encode('utf8')
					elif element['type'] == 'boxScore':
						self.boxscore_url = element['data_url'].encode('utf8')

	def buildLiveEventScreen(self, jsonData):
		self['subdescription'].setText('Übertragung vom ' + self.starttime.strftime('%d.%m.%Y %H:%M') + '\n\nVideos:')
		if 'has_alerts' in jsonData['data']['metadata']['event_metadata']:
			self.conference_alarm_available = jsonData['data']['metadata']['event_metadata']['has_alerts'] == True
			if self.conference_alarm_available:
				self['confalarm'].setText('Konferenzalarm ist verfügbar. Bitte Info/EPG Taste drücken um ihn zu aktivieren.')
		if 'league_id' in jsonData['data']['metadata']['event_metadata']:
			self.league_id = str(jsonData['data']['metadata']['event_metadata']['league_id'])
		for content in jsonData['data']['content']:
			if content['group_elements']:
				for element in content['group_elements']:
					if element['type'] == 'player':
						title = 'Live Stream'
						if element['data'][0]['pay']:
							title += ' *'
						self.videoList.append((title, element['data'][0]['title'].encode('utf8'), str(element['data'][0]['videoID']), str(element['data'][0]['pay'])))
					elif element['type'] == 'statistics':
						self.statistics_url = element['data']['url'].encode('utf8')
					elif element['type'] == 'boxScore':
						self.boxscore_url = element['data_url'].encode('utf8')

	def buildScreen(self, jsonData):
		self.videoList = []

		if not jsonData['data'] or not jsonData['data']['content'] or not jsonData['data']['metadata']:
			self['status'].setText('Bitte Pluginentwickler informieren:\nTelekomSportEventScreen')
			return

		try:
			if jsonData['data']['metadata']['state'] == 'pre':
				self.buildPreEventScreen(jsonData)
			elif jsonData['data']['metadata']['state'] == 'post':
				self.buildPostEventScreen(jsonData)
			elif jsonData['data']['metadata']['state'] == 'live':
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

	# for summary
	def getCurrentEntry(self):
		if self['list'].getCurrent():
			return self['list'].getCurrent()[1]
		return self['match'].getText()

	def getCurrentValue(self):
		return ' '

	def createSummary(self):
		return TelekomSportMainScreenSummary


class TelekomSportEventLaneScreen(Screen):

	def __init__(self, session, main_title, title, url, epg_url, standings_url, schedule_url):
		Screen.__init__(self, session)
		self.session = session
		self.standings_url = standings_url
		self.schedule_url = schedule_url

		self.setup_title = TelekomSportMainScreen.title

		self['title'] = Label(main_title)
		self['subtitle'] = Label(title)
		self['status'] = Label('Lade Daten...')
		self['version'] = Label(TelekomSportMainScreen.version)

		self.eventList = []
		self['list'] = List(self.eventList)

		self['actions'] = ActionMap(['MenuActions', 'SetupActions', 'DirectionActions'],
		{
			'menu': self.closeRecursive,
			'cancel': self.close,
			'ok': self.ok,
		})
		if url != '':
			downloadTelekomSportJson(TelekomSportMainScreen.base_url + url, boundFunction(loadTelekomSportJsonData, 'EventLane', self['status'], self.buildList), boundFunction(handleTelekomSportDownloadError, 'EventLane', self['status']))
		elif epg_url != '':
			downloadTelekomSportJson(TelekomSportMainScreen.base_url + epg_url, boundFunction(loadTelekomSportJsonData, 'EventLane', self['status'], self.buildEpgList), boundFunction(handleTelekomSportDownloadError, 'EventLane', self['status']))

	def closeRecursive(self):
		self.close(True)

	def addEventToList(self, events):
		if 'target_type' in events and events['target_type'] == 'event' and (events['target_playable'] or not config.plugins.telekomsport.hide_unplayable.value):
			description = events['metadata']['description_bold'].encode('utf8')
			subdescription = events['metadata']['description_regular'].encode('utf8')
			original = events['metadata']['scheduled_start']['original'].encode('utf8')
			starttime = datetime.strptime(original, '%Y-%m-%d %H:%M:%S')
			starttime_str = starttime.strftime('%d.%m.%Y %H:%M')
			urlpart = events['target'].encode('utf8')
			if subdescription:
				description = description + ' - ' + subdescription
			if 'home' in events['metadata']['details'] and 'name_full' in events['metadata']['details']['home'] and events['metadata']['details']['home']['name_full'].encode('utf8') <> '':
				home = events['metadata']['details']['home']['name_full'].encode('utf8')
				away = events['metadata']['details']['away']['name_full'].encode('utf8')
				self.eventList.append((description, starttime_str, home + ' - ' + away, urlpart, starttime))
			else:
				title = events['metadata']['title'].encode('utf8')
				self.eventList.append((description, starttime_str, title, urlpart, starttime))

	def buildList(self, jsonData):
		try:
			if 'panels' in jsonData['data']['data']:
				jsonData = jsonData['data']['data']['panels']
			else:
				jsonData = jsonData['data']['data']
			for events in jsonData:
				if 'event' in events:
					events = events['event']
				self.addEventToList(events)
		except Exception as e:
			self['status'].setText('Bitte Pluginentwickler informieren:\nTelekomSportEventLaneScreen ' + str(e))
			return

		self['list'].setList(self.eventList)
		self['status'].hide()

	def buildEpgList(self, jsonData):
		try:
			for element in jsonData['data']['elements']:
				for slot in element['slots']:
					for events in slot['events']:
						self.addEventToList(events)
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
			self.session.openWithCallback(self.recursiveClose, TelekomSportEventScreen, description, starttime, match, urlpart, self.standings_url, self.schedule_url)

	def recursiveClose(self, *retVal):
		if retVal:
			self.close(True)

	# for summary
	def getCurrentEntry(self):
		if self['list'].getCurrent():
			return self['list'].getCurrent()[0]
		else:
			return ' '

	def getCurrentValue(self):
		if self['list'].getCurrent():
			return self['list'].getCurrent()[2]
		else:
			return ' '

	def createSummary(self):
		return TelekomSportMainScreenSummary


class TelekomSportSportsTypeScreen(Screen):

	def __init__(self, session, title, url):
		Screen.__init__(self, session)
		self.session = session
		self.main_title = title
		self.standings_url = ''
		self.schedule_url = ''

		self.setup_title = TelekomSportMainScreen.title

		# for update
		self.telekomSportMainScreen = session.current_dialog

		self['title'] = Label(title)
		self['subtitle'] = Label('')
		self['status'] = Label('Lade Daten...')
		self['version'] = Label(TelekomSportMainScreen.version)

		self.eventLaneList = []
		self['list'] = List(self.eventLaneList)

		self['buttonblue'] = Label('')
		self['buttonblue'].hide()
		self['buttongreen'] = Label('Update')
		if self.telekomSportMainScreen.update_exist == False:
			self['buttongreen'].hide()

		self['actions'] = ActionMap(['MenuActions', 'SetupActions', 'DirectionActions', 'ColorActions'],
		{
			'menu': self.closeRecursive,
			'cancel': self.close,
			'ok': self.ok,
			'blue': self.showTableResults,
			'green': self.update,
		})
		downloadTelekomSportJson(TelekomSportMainScreen.base_url + url, boundFunction(loadTelekomSportJsonData, 'SportsType', self['status'], self.buildList), boundFunction(handleTelekomSportDownloadError, 'SportsType', self['status']))

	def update(self):
		if self.telekomSportMainScreen.update_exist:
			self.session.openWithCallback(self.telekomSportMainScreen.updateConfirmed, MessageBox, 'Ein Update ist verfügbar. Wollen sie es installieren?\nInformationen:\n' + self.telekomSportMainScreen.updateText, MessageBox.TYPE_YESNO, default = False)

	def closeRecursive(self):
		self.close(True)

	def buildList(self, jsonData):
		try:
			title = ''
			for content in jsonData['data']['content']:
				if content['title'] and content['title'] != '':
					title = content['title'].encode('utf8')
				for group_element in content['group_elements']:
					if group_element['type'] == 'eventLane' or group_element['type'] == 'editorialLane' or group_element['type'] == 'teaserGrid':
						subtitle = group_element['title'].encode('utf8')
						urlpart = group_element['data_url'].encode('utf8')
						if content['title'] != '' and subtitle == '':
							self.eventLaneList.append((title, subtitle, title, urlpart, ''))
						elif content['title'] != '' and subtitle != '':
							self.eventLaneList.append((title, '', title, '', ''))
							self.eventLaneList.append(('', subtitle, title + ' - ' + subtitle, urlpart, ''))
						elif content['title'] == '' and subtitle != '':
							self.eventLaneList.append(('', subtitle, subtitle, urlpart, ''))
						else:
							self.eventLaneList.append(('Aktuelles', subtitle, 'Aktuelles', urlpart, ''))
					if group_element['type'] == 'teaserGrid': # read epg data to get all matches
						content_id = group_element['content_id']
						self.eventLaneList.append(('Spielplan', '', 'Spielplan', '', '/epg/content/' + str(content_id)))
			if 'navigation' in jsonData['data'] and 'header' in jsonData['data']['navigation']:
				for header in jsonData['data']['navigation']['header']:
					if header['target_type'] == 'standings':
						self.standings_url = header['target'].encode('utf8')
						self['buttonblue'].setText('Tabelle')
						self['buttonblue'].show()
					if header['target_type'] == 'schedule':
						self.schedule_url = header['target'].encode('utf8')
		except Exception as e:
			self['status'].setText('Bitte Pluginentwickler informieren:\nTelekomSportSportsTypeScreen ' + str(e))
			return

		self['list'].setList(self.eventLaneList)
		self['status'].hide()

	def ok(self):
		if self['list'].getCurrent():
			title = self['list'].getCurrent()[2]
			urlpart = self['list'].getCurrent()[3]
			epg_urlpart = self['list'].getCurrent()[4]
			if urlpart != '' or epg_urlpart != '':
				self.session.openWithCallback(self.recursiveClose, TelekomSportEventLaneScreen, self.main_title, title, urlpart, epg_urlpart, self.standings_url, self.schedule_url)

	def recursiveClose(self, *retVal):
		if retVal:
			self.close(True)

	def showTableResults(self):
		if self.standings_url:
			self.session.open(TelekomSportStandingsScreen, self.standings_url)

	# for summary
	def getCurrentEntry(self):
		return self['title'].getText()

	def getCurrentValue(self):
		if self['list'].getCurrent():
			return self['list'].getCurrent()[2]
		else:
			return ' '

	def createSummary(self):
		return TelekomSportMainScreenSummary


class TelekomSportMainScreen(Screen):

	version = 'v2.9.6'

	base_url = 'https://www.magentasport.de/api/v2/mobile'
	main_page = '/navigation'
	title = 'Magenta Sport'

	def __init__(self, session, args = None):
		Screen.__init__(self, session)
		self.session = session

		self.updateUrl = ''
		self.updateText = ''
		self.filename = ''

		self.setup_title = TelekomSportMainScreen.title

		self['title'] = Label('')
		self['subtitle'] = Label('')
		self['status'] = Label('Lade Daten...')
		self['version'] = Label(self.version)

		self.sportslist = []
		self['list'] = List(self.sportslist)

		self['buttonblue'] = Label('Einstellungen')
		self['buttongreen'] = Label('Update')
		self['buttongreen'].hide()

		self['actions'] = ActionMap(['SetupActions', 'DirectionActions', 'ColorActions'],
		{
			'cancel': self.close,
			'ok': self.ok,
			'blue': self.showSetup,
			'green': self.update,
		})
		downloadTelekomSportJson(self.base_url + self.main_page, boundFunction(loadTelekomSportJsonData, 'Main', self['status'], self.buildList), boundFunction(handleTelekomSportDownloadError, 'Main', self['status']))
		self.onLayoutFinish.append(self.checkForUpdate)
		self.migrate_timer = eTimer()
		if telekomsport_isDreamOS:
			self.migrate_timer_conn = self.migrate_timer.timeout.connect(self.checkNewPasswordFileIsUsed)
		else:
			self.migrate_timer.callback.append(self.checkNewPasswordFileIsUsed)
		self.migrate_timer.start(200, True)

	def buildList(self, jsonData):
		default_section_choicelist = [('', 'Default')]

		self.sportslist.append(('MagentaSport Hauptseite', '', 'MagentaSport Hauptseite', '/page/1'))
		default_section_choicelist.append(('MagentaSport Hauptseite', 'MagentaSport Hauptseite'))

		try:
			for sports in jsonData['data']['league_filter']:
				title = sports['title'].encode('utf8')
				if title != "":
					self.sportslist.append((title, '', title, sports['target'].encode('utf8')))
					default_section_choicelist.append((title, title))
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
			self.session.openWithCallback(self.recursiveClose, TelekomSportSportsTypeScreen, title, urlpart)

	def recursiveClose(self, *retVal):
		if retVal:
			self.close()

	def selectDefaultSportsType(self):
		if config.plugins.telekomsport.default_section.value:
			items = filter(lambda x: x[0] == config.plugins.telekomsport.default_section.value or x[1] == config.plugins.telekomsport.default_section.value, self.sportslist)
			if items:
				self.selectSportsType(items[0])

	def selectSportsType(self, item):
		if item:
			title = item[2]
			urlpart = item[3]
			self.session.openWithCallback(self.recursiveClose, TelekomSportSportsTypeScreen, title, urlpart)

	def showSetup(self):
		self.session.open(TelekomSportConfigScreen)

	# for summary
	def getCurrentEntry(self):
		if self['list'].getCurrent():
			return self['list'].getCurrent()[2]
		else:
			return ' '

	def getCurrentValue(self):
		return ' '

	def createSummary(self):
		return TelekomSportMainScreenSummary

	# for update
	def checkForUpdate(self):
		url = 'https://api.github.com/repos/E2OpenPlugins/e2openplugin-TelekomSport/releases'
		header = { 'Accept' : 'application/vnd.github.v3+json' }
		req = urllib2.Request(url, None, header)
		self.update_exist = False
		try:
			response = urllib2.urlopen(req)
			jsonData = json.loads(response.read())

			for rel in jsonData:
				if rel['target_commitish'] != 'master':
					continue
				if self.version < rel['tag_name']:
					self.updateText = rel['body'].encode('utf8')
					for asset in rel['assets']:
						if telekomsport_isDreamOS and asset['name'].endswith('.deb'):
							self.updateUrl = asset['browser_download_url'].encode('utf8')
							self.filename = '/tmp/enigma2-plugin-extensions-telekomsport.deb'
							self['buttongreen'].show()
							self.update_exist = True
							break
						elif (not telekomsport_isDreamOS) and asset['name'].endswith('.ipk'):
							self.updateUrl = asset['browser_download_url'].encode('utf8')
							self.filename = '/tmp/enigma2-plugin-extensions-telekomsport.ipk'
							self['buttongreen'].show()
							self.update_exist = True
							break
				if self.version >= rel['tag_name'] or self.updateUrl != '':
					break

		except Exception as e:
			pass

	def update(self):
		if self.updateUrl:
			self.session.openWithCallback(self.updateConfirmed, MessageBox, 'Ein Update ist verfügbar. Wollen sie es installieren?\nInformationen:\n' + self.updateText, MessageBox.TYPE_YESNO, default = False)

	def updateConfirmed(self, answer):
		if answer:
			self.downloader = TelekomSportDownloadWithProgress(self.updateUrl, self.filename)
			self.downloader.addError(self.updateFailed)
			self.downloader.addEnd(self.downloadFinished)
			self.downloader.start()

	def downloadFinished(self):
		self.downloader.stop()
		self.container = eConsoleAppContainer()
		if telekomsport_isDreamOS:
			self.container.appClosed_conn = self.container.appClosed.connect(self.updateFinished)
			self.container.execute('dpkg -i ' + self.filename)
		else:
			self.container.appClosed.append(self.updateFinished)
			self.container.execute('opkg update; opkg install ' + self.filename)

	def updateFailed(self, reason, status):
		self.updateFinished(1)

	def updateFinished(self, retval):
		self['buttongreen'].hide()
		self.updateUrl = ''
		if retval == 0:
			self.session.openWithCallback(self.restartE2, MessageBox, 'Das Magenta Sport Plugin wurde erfolgreich installiert!\nSoll das E2 GUI neugestartet werden?', MessageBox.TYPE_YESNO, default = False)
		else:
			self.session.open(MessageBox, 'Bei der Installation ist ein Problem aufgetreten.', MessageBox.TYPE_ERROR)

	def restartE2(self, answer):
		if answer:
			self.session.open(TryQuitMainloop, 3)

	def checkNewPasswordFileIsUsed(self):
		if not path.isfile('/etc/enigma2/MagentaSport.cfg'):
			print 'Migrating passwords'
			if savePasswords(self.session, decode(config.plugins.telekomsport.password1.value), decode(config.plugins.telekomsport.password2.value)):
				config.plugins.telekomsport.password1.value = ''
				config.plugins.telekomsport.password1.save()
				config.plugins.telekomsport.password2.value = ''
				config.plugins.telekomsport.password2.save()


def main(session, **kwargs):
	session.open(TelekomSportMainScreen)

def Plugins(**kwargs):
	return PluginDescriptor(name='Magenta Sport', description=_('Magenta Sport Plugin'), where = PluginDescriptor.WHERE_PLUGINMENU, icon='plugin.png', fnc=main)
