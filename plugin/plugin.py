# -*- coding: utf-8 -*-

from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.InfoBarGenerics import InfoBarMenu, InfoBarSeek, InfoBarNotifications, InfoBarServiceNotifications, InfoBarShowHide, InfoBarSimpleEventView, InfoBarServiceErrorPopupSupport
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Components.ActionMap import ActionMap
from Components.ServiceEventTracker import InfoBarBase
from Components.Sources.List import List
from Components.Label import Label
from Components.MultiContent import MultiContentEntryText, MultiContentEntryProgress
from Components.ConfigList import ConfigListScreen
from Components.config import config, getConfigListEntry, ConfigSubsection, ConfigText, ConfigPassword, ConfigInteger, ConfigNothing, ConfigYesNo, ConfigSelection, NoSave
from Tools.BoundFunction import boundFunction
from downloader import TelekomSportDownloadWithProgress

from enigma import eTimer, eListboxPythonMultiContent, gFont, eEnv, eServiceReference, getDesktop, eConsoleAppContainer

import xml.etree.ElementTree as ET
import time
import urllib
import urllib2
import json
import base64
import re
from itertools import cycle, izip
from datetime import datetime
from twisted.web.client import getPage
import twisted.web.error as twistedWebError
import twisted.python.failure as twistedFailure


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
config.plugins.telekomsport.stream_quality = ConfigSelection(default = "1000000", choices = [("350000", _("sehr gering")), ("600000", _("gering")), ("1000000", _("mittel")), ("1700000", _("hoch")), ("3000000", _("sehr hoch"))])


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

	ts_font_str = ""
	if getDesktop(0).size().width() <= 1280:
		if not telekomsport_isDreamOS:
			ts_font_str = 'font="Regular;20"'
		skin = '''<screen position="center,center" size="470,370" flags="wfNoBorder">
					<ePixmap position="center,10" size="450,45" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="config" position="10,70" size="460,250" ''' + ts_font_str + ''' scrollbarMode="showOnDemand" />
					<widget name="buttonred" position="10,330" size="120,35" backgroundColor="red" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;20"/>
					<widget name="buttongreen" position="165,330" size="120,35" backgroundColor="green" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;20"/>
					<widget name="buttonblue" position="320,330" size="135,35" backgroundColor="blue" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;20"/>
				</screen>'''
	else:
		if not telekomsport_isDreamOS:
			ts_font_str = 'font="Regular;32"'
		skin = '''<screen position="center,center" size="670,600" flags="wfNoBorder">
					<ePixmap position="center,15" size="640,59" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="config" position="15,100" size="650,420" ''' + ts_font_str + ''' itemHeight="42" scrollbarMode="showOnDemand" />
					<widget name="buttonred" position="15,540" size="180,50" backgroundColor="red" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;32"/>
					<widget name="buttongreen" position="225,540" size="180,50" backgroundColor="green" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;32"/>
					<widget name="buttonblue" position="440,540" size="215,50" backgroundColor="blue" valign="center" halign="center" zPosition="2"  foregroundColor="white" font="Regular;32"/>
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
		self.config_fix_stream_quality = getConfigListEntry('Feste Stream Qualität verwenden', config.plugins.telekomsport.fix_stream_quality)
		self.list.append(self.config_fix_stream_quality)
		self.config_stream_quality = getConfigListEntry('Stream Qualität', config.plugins.telekomsport.stream_quality)
		self.list.append(self.config_stream_quality)

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


class TelekomSportMoviePlayer(Screen, InfoBarMenu, InfoBarBase, InfoBarSeek, InfoBarNotifications, InfoBarServiceNotifications, InfoBarShowHide, InfoBarSimpleEventView, InfoBarServiceErrorPopupSupport):

	def __init__(self, session, service, standings_url, schedule_url, statistics_url, boxscore_url):
		Screen.__init__(self, session)
		self.skinName = 'MoviePlayer'

		InfoBarMenu.__init__(self)
		InfoBarBase.__init__(self)
		InfoBarNotifications.__init__(self)
		InfoBarServiceNotifications.__init__(self)
		InfoBarShowHide.__init__(self)
		InfoBarSimpleEventView.__init__(self)
		InfoBarSeek.__init__(self)
		InfoBarServiceErrorPopupSupport.__init__(self)

		self.service = service
		self.lastservice = self.session.nav.getCurrentlyPlayingServiceReference()
		self.standings_url = standings_url
		self.schedule_url = schedule_url
		self.statistics_url = statistics_url
		self.boxscore_url = boxscore_url

		self['actions'] = ActionMap(['MoviePlayerActions', 'ColorActions'],
		{
			'leavePlayer' : self.leavePlayer,
			'leavePlayerOnExit' : self.leavePlayerOnExit,
			'red'    : self.openEventView,
			'green'  : self.showStatistics,
			'yellow' : self.openEventView,
			'blue'   : self.openEventView,
		}, -2)
		self.onFirstExecBegin.append(self.playStream)
		self.onClose.append(self.stopPlayback)

	def playStream(self):
		self.session.nav.playService(self.service)

	def stopPlayback(self):
		if self.lastservice:
			self.session.nav.playService(self.lastservice)
		else:
			self.session.nav.stopService()

	def leavePlayer(self):
		self.session.openWithCallback(self.leavePlayerConfirmed, MessageBox, 'Abspielen beenden?')

	def leavePlayerOnExit(self):
		if config.usage.leave_movieplayer_onExit.value != 'no':
			self.leavePlayer()

	def leavePlayerConfirmed(self, answer):
		if answer:
			self.close()

	def openEventView(self):
		if self.standings_url:
			self.session.open(TelekomSportStandingsResultsScreen, '', self.standings_url, self.schedule_url)

	def showStatistics(self):
		if self.statistics_url:
			self.session.open(TelekomSportStatisticsScreen, self.statistics_url)

	def showMovies(self):
		pass


class TelekomSportStatisticsScreen(Screen):

	if getDesktop(0).size().width() <= 1280:
		skin = '''<screen position="center,center" size="820,680" flags="wfNoBorder">
					<ePixmap position="center,25" size="700,87" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="10,140" size="800,40" font="Regular;34" zPosition="1" />
					<widget name="match" position="10,190" size="800,40" noWrap="1" halign="center" font="Regular;32" zPosition="1" />
					<widget source="list" render="Listbox" position="10,260" size="800,355" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (50,[
									MultiContentEntryText(pos = (20, 0), size = (130, 28), font=0, flags = RT_HALIGN_CENTER|RT_VALIGN_CENTER, text = 0), # home
									MultiContentEntryText(pos = (0, 0), size = (800, 28), font=0, flags = RT_HALIGN_CENTER|RT_VALIGN_CENTER, text = 1), # stat name
									MultiContentEntryText(pos = (630, 0), size = (130, 28), font=0, flags = RT_HALIGN_CENTER|RT_VALIGN_CENTER, text = 2), # away
									MultiContentEntryProgress(pos = (10, 32), size = (780, 10), percent = -3), # percent
								]),
								},
								"fonts": [gFont("Regular", 24)],
								"itemHeight": 50
							}
						</convert>
					</widget>
					<widget name="status" position="10,370" size="800,250" font="Regular;25" halign="center" zPosition="1" />
					<widget foregroundColor="white" font="Regular;20" position="640,630" render="Label" size="200,35" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''
	else:
		skin = '''<screen position="center,center" size="1230,1020" flags="wfNoBorder">
					<ePixmap position="center,25" size="1070,134" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="15,210" size="1200,50" font="Regular;45" zPosition="1" />
					<widget name="match" position="15,280" size="1200,65" noWrap="1" halign="center" font="Regular;42" zPosition="1" />
					<widget source="list" render="Listbox" position="40,380" size="1150,570" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (80,[
									MultiContentEntryText(pos = (50, 0), size = (200, 40), font=0, flags = RT_HALIGN_CENTER|RT_VALIGN_CENTER, text = 0), # home
									MultiContentEntryText(pos = (0, 0), size = (1150, 40), font=0, flags = RT_HALIGN_CENTER|RT_VALIGN_CENTER, text = 1), # stat name
									MultiContentEntryText(pos = (900, 0), size = (200, 40), font=0, flags = RT_HALIGN_CENTER|RT_VALIGN_CENTER, text = 2), # away
									MultiContentEntryProgress(pos = (25, 40), size = (1100, 15), percent = -3), # percent
								]),
								},
								"fonts": [gFont("Regular", 32)],
								"itemHeight": 75
							}
						</convert>
					</widget>
					<widget name="status" position="15,500" size="1200,400" font="Regular;35" halign="center" zPosition="1" />
					<widget foregroundColor="white" font="Regular;32" position="920,955" render="Label" size="270,50" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''

	def __init__(self, session, statistics_url):
		Screen.__init__(self, session)
		self.session = session

		self['status'] = Label('Lade Daten...')
		self['match'] = Label()
		self['title'] = Label('Spielstatistiken')
		self.statList = []
		self['list'] = List(self.statList)

		self['actions'] = ActionMap(['OkCancelActions'],
		{
			'ok' : self.close,
			'cancel' : self.close,
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


class TelekomSportStandingsResultsScreen(Screen):

	if getDesktop(0).size().width() <= 1280:
		skin = '''<screen position="center,center" size="820,680" flags="wfNoBorder">
					<ePixmap position="center,25" size="700,87" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
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
									MultiContentEntryText(pos = (3, 0), size = (25, 25), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0), # rank
									MultiContentEntryText(pos = (30, 0), size = (370, 25), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1), # team
									MultiContentEntryText(pos = (400, 0), size = (50, 25), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 2), # count matches
									MultiContentEntryText(pos = (440, 0), size = (30, 25), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 3), # count wins
									MultiContentEntryText(pos = (475, 0), size = (30, 25), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 4), # count draws
									MultiContentEntryText(pos = (510, 0), size = (30, 25), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 5), # count losses
									MultiContentEntryText(pos = (555, 0), size = (95, 25), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 6), # goals
									MultiContentEntryText(pos = (650, 0), size = (50, 25), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 7), # goal diff
									MultiContentEntryText(pos = (710, 0), size = (60, 25), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 8), # points
									MultiContentEntryText(pos = (0, 0), size = (800, 25), border_width=1, border_color=0x424242, font=0, text = ""), # border
								]),
								"playoff": (65,[
									MultiContentEntryText(pos = (20, 0), size = (500, 28), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0), # title
									MultiContentEntryText(pos = (20, 30), size = (750, 30), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1), # teams + wins
									MultiContentEntryText(pos = (0, 0), size = (800, 65), border_width=1, border_color=0x424242, font=0, text = ""), # border
								]),
								"schedule": (65,[
									MultiContentEntryText(pos = (20, 0), size = (500, 28), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0), # description
									MultiContentEntryText(pos = (620, 0), size = (240, 28), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1), # start time
									MultiContentEntryText(pos = (20, 30), size = (750, 30), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 2), # teams + result
									MultiContentEntryText(pos = (0, 0), size = (800, 65), border_width=1, border_color=0x424242, font=0, text = ""), # border
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
					<ePixmap position="center,25" size="1070,134" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="15,185" size="1200,50" font="Regular;42" zPosition="1" />
					<widget name="subtitle" position="15,235" size="1200,50" font="Regular;38" zPosition="1" />
					<widget name="table_header_team" position="60,300" size="100,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_matches" position="585,300" size="80,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_wins" position="690,300" size="25,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_draws" position="740,300" size="25,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_losses" position="785,300" size="25,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_goals" position="865,300" size="70,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_goaldiff" position="1005,300" size="60,40" font="Regular;30" zPosition="1" />
					<widget name="table_header_points" position="1065,300" size="100,40" font="Regular;30" zPosition="1" />
					<widget source="list" render="Listbox" position="15,340" size="1200,610" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (40,[
									MultiContentEntryText(pos = (2, 0), size = (40, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0), # rank
									MultiContentEntryText(pos = (45, 0), size = (555, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1), # team
									MultiContentEntryText(pos = (600, 0), size = (50, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 2), # count matches
									MultiContentEntryText(pos = (650, 0), size = (50, 40), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 3), # count wins
									MultiContentEntryText(pos = (700, 0), size = (50, 40), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 4), # count draws
									MultiContentEntryText(pos = (755, 0), size = (50, 40), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 5), # count losses
									MultiContentEntryText(pos = (835, 0), size = (150, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 6), # goals
									MultiContentEntryText(pos = (990, 0), size = (50, 40), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 7), # goal diff
									MultiContentEntryText(pos = (1060, 0), size = (80, 40), font=0, flags = RT_HALIGN_RIGHT|RT_VALIGN_CENTER, text = 8), # points
									MultiContentEntryText(pos = (0, 0), size = (1200, 40), border_width=1, border_color=0x424242, font=0, text = ""), # border
								]),
								"playoff": (90,[
									MultiContentEntryText(pos = (20, 0), size = (1150, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0), # title
									MultiContentEntryText(pos = (20, 42), size = (1150, 42), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1), # teams + wins
									MultiContentEntryText(pos = (0, 0), size = (1200, 90), border_width=1, border_color=0x424242, font=0, text = ""), # border
								]),
								"schedule": (90,[
									MultiContentEntryText(pos = (20, 0), size = (1150, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0), # description
									MultiContentEntryText(pos = (925, 0), size = (360, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1), # start time
									MultiContentEntryText(pos = (20, 42), size = (1150, 42), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 2), # teams + result
									MultiContentEntryText(pos = (0, 0), size = (1200, 90), border_width=1, border_color=0x424242, font=0, text = ""), # border
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
					<ePixmap position="center,25" size="700,87" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
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
					<ePixmap position="center,25" size="1070,134" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
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

		self.statistics_url = ''
		self.boxscore_url = ''

		self['match'] = Label(match)
		self['description'] = Label(description)
		self['subdescription'] = Label('')
		self['status'] = Label('Lade Daten...')
		self['pay'] = Label('* = Abo benötigt')

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
			lines = urllib2.urlopen(m3u8_url).readlines()
			if len(lines) > 0 and lines[0] == '#EXTM3U\n':
				i = 1
				count_lines = len(lines)
				while i < len(lines) - 1:
					if lines[i].startswith('#EXT-X-STREAM-INF:'):
						bandwith = self.readExtXStreamInfLine(lines[i], attributeListPattern)
						if bandwith and i + 1 < count_lines:
							streams.append((bandwith, lines[i+1].strip()))
					i += 1
				if streams:
					# return stream URL which bandwidth is closest to the user chosen bandwidth
					return min(streams, key=lambda x:abs(int(x[0]) - int(config.plugins.telekomsport.stream_quality.value)))[1]
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
				playlisturl = url

		ref = eServiceReference(4097, 0, playlisturl)
		ref.setName(title)

		self.session.open(TelekomSportMoviePlayer, ref, self.standings_url, self.schedule_url, self.statistics_url, self.boxscore_url)

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
					if element['type'] == 'eventVideos':
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
			if jsonData['data']['metadata']['title'].startswith('Event Page Pre'):
				self.buildPreEventScreen(jsonData)
			elif jsonData['data']['metadata']['title'].startswith('Event Page Post'):
				self.buildPostEventScreen(jsonData)
			elif jsonData['data']['metadata']['title'].startswith('Event Page Live'):
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
					<ePixmap position="center,25" size="700,87" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="10,125" size="800,40" font="Regular;30" zPosition="1" />
					<widget name="subtitle" position="10,165" size="800,35" font="Regular;25" zPosition="1" />
					<widget source="list" render="Listbox" position="10,200" size="800,420" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (65,[
									MultiContentEntryText(pos = (20, 0), size = (500, 28), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
									MultiContentEntryText(pos = (620, 0), size = (240, 28), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1),
									MultiContentEntryText(pos = (20, 30), size = (750, 30), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 2),
									MultiContentEntryText(pos = (0, 0), size = (800, 65), border_width=1, border_color=0x424242, font=0, text = ""),
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
					<ePixmap position="center,25" size="1070,134" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="15,185" size="1200,50" font="Regular;42" zPosition="1" />
					<widget name="subtitle" position="15,235" size="1200,45" font="Regular;38" zPosition="1" />
					<widget source="list" render="Listbox" position="15,300" size="1200,630" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (90,[
									MultiContentEntryText(pos = (20, 0), size = (1150, 40), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
									MultiContentEntryText(pos = (925, 0), size = (360, 40), font=1, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1),
									MultiContentEntryText(pos = (20, 42), size = (1150, 42), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 2),
									MultiContentEntryText(pos = (0, 0), size = (1180, 90), border_width=1, border_color=0x424242, font=0, text = ""),
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

		self['actions'] = ActionMap(['MenuActions', 'SetupActions', 'DirectionActions'],
		{
			'menu': self.closeRecursive,
			'cancel': self.close,
			'ok': self.ok,
		})
		downloadTelekomSportJson(TelekomSportMainScreen.base_url + url, boundFunction(loadTelekomSportJsonData, 'EventLane', self['status'], self.buildList), boundFunction(handleTelekomSportDownloadError, 'EventLane', self['status']))

	def closeRecursive(self):
		self.close(True)

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
					if 'home' in events['metadata']['details'] and events['metadata']['details']['home']['name_full'].encode('utf8') <> '':
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
			self.session.openWithCallback(self.recursiveClose, TelekomSportEventScreen, description, starttime, match, urlpart, self.standings_url, self.schedule_url)

	def recursiveClose(self, *retVal):
		if retVal:
			self.close(True)


class TelekomSportSportsTypeScreen(Screen):

	if getDesktop(0).size().width() <= 1280:
		skin = '''<screen position="center,center" size="820,680" flags="wfNoBorder">
					<ePixmap position="center,25" size="700,87" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="10,125" size="800,40" font="Regular;30" zPosition="1" />
					<widget name="subtitle" position="10,165" size="800,35" font="Regular;25" zPosition="1" />
					<widget source="list" render="Listbox" position="10,200" size="800,420" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (30,[
									MultiContentEntryText(pos = (5, 0), size = (750, 28), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
									MultiContentEntryText(pos = (50, 0), size = (750, 28), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1),
									MultiContentEntryText(pos = (0, 0), size = (800, 30), border_width=1, border_color=0x424242, font=0, text = ""),
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
					<ePixmap position="center,25" size="1070,134" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="title" position="15,185" size="1200,50" font="Regular;42" zPosition="1" />
					<widget name="subtitle" position="15,235" size="1200,45" font="Regular;38" zPosition="1" />
					<widget source="list" render="Listbox" position="15,300" size="1200,630" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (45,[
									MultiContentEntryText(pos = (5, 0), size = (1180, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
									MultiContentEntryText(pos = (50, 0), size = (1140, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1),
									MultiContentEntryText(pos = (0, 0), size = (1180, 45), border_width=1, border_color=0x424242, font=0, text = ""),
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

		self['actions'] = ActionMap(['MenuActions', 'SetupActions', 'DirectionActions', 'ColorActions'],
		{
			'menu': self.closeRecursive,
			'cancel': self.close,
			'ok': self.ok,
			'blue': self.showTableResults,
		})
		downloadTelekomSportJson(TelekomSportMainScreen.base_url + url, boundFunction(loadTelekomSportJsonData, 'SportsType', self['status'], self.buildList), boundFunction(handleTelekomSportDownloadError, 'SportsType', self['status']))

	def closeRecursive(self):
		self.close(True)

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
				self.session.openWithCallback(self.recursiveClose, TelekomSportEventLaneScreen, self.main_title, title, urlpart, self.standings_url, self.schedule_url)

	def recursiveClose(self, *retVal):
		if retVal:
			self.close(True)

	def showTableResults(self):
		if self.standings_url or self.schedule_url:
			self.session.open(TelekomSportStandingsResultsScreen, self.main_title, self.standings_url, self.schedule_url)


class TelekomSportMainScreen(Screen):

	version = 'v2.2.0'

	base_url = 'https://www.telekomsport.de/api/v2/mobile'
	main_page = '/navigation'

	if getDesktop(0).size().width() <= 1280:
		skin = '''<screen position="center,center" size="820,680" flags="wfNoBorder">
					<ePixmap position="center,25" size="700,87" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="version" position="760,89" size="75,20" font="Regular;18" zPosition="2" />
					<widget name="title" position="10,125" size="800,40" font="Regular;30" zPosition="1" />
					<widget name="subtitle" position="10,165" size="800,35" font="Regular;25" zPosition="1" />
					<widget source="list" render="Listbox" position="10,200" size="800,420" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (30,[
									MultiContentEntryText(pos = (5, 0), size = (750, 28), border_width=0, font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
									MultiContentEntryText(pos = (50, 0), size = (750, 28), border_width=0, font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1),
									MultiContentEntryText(pos = (0, 0), size = (800, 30), border_width=1, border_color=0x424242, font=0, text = ""),
								]),
								},
								"fonts": [gFont("Regular", 20)],
								"itemHeight": 30
							}
						</convert>
					</widget>
					<widget name="status" position="10,200" size="800,420" font="Regular;25" halign="center" zPosition="1" />
					<widget name="buttonblue" position="15,630" size="140,35" backgroundColor="blue" valign="center" halign="center" zPosition="2" foregroundColor="white" font="Regular;20"/>
					<widget name="buttongreen" position="180,630" size="140,35" backgroundColor="green" valign="center" halign="center" zPosition="2" foregroundColor="white" font="Regular;20"/>
					<widget foregroundColor="white" font="Regular;20" position="640,630" render="Label" size="200,35" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''
	else:
		skin = '''<screen position="center,center" size="1230,1020" flags="wfNoBorder">
					<ePixmap position="center,25" size="1070,134" scale="1" pixmap="''' + eEnv.resolve('${libdir}/enigma2/python/Plugins/Extensions/TelekomSport/TelekomSport-Logo.png') + '''" alphatest="blend" zPosition="1"/>
					<widget name="version" position="1150,127" size="90,35" font="Regular;26" zPosition="2" />
					<widget name="title" position="15,185" size="1200,50" font="Regular;42" zPosition="1" />
					<widget name="subtitle" position="15,235" size="1200,45" font="Regular;38" zPosition="1" />
					<widget source="list" render="Listbox" position="15,300" size="1200,630" scrollbarMode="showOnDemand">
						<convert type="TemplatedMultiContent">
							{"templates":
								{"default": (45,[
									MultiContentEntryText(pos = (5, 0), size = (1180, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 0),
									MultiContentEntryText(pos = (50, 0), size = (1140, 40), font=0, flags = RT_HALIGN_LEFT|RT_VALIGN_CENTER, text = 1),
									MultiContentEntryText(pos = (0, 0), size = (1180, 45), border_width=1, border_color=0x424242, font=0, text = ""),
								]),
								},
								"fonts": [gFont("Regular", 32)],
								"itemHeight": 45
							}
						</convert>
					</widget>
					<widget name="status" position="15,300" size="1200,630" font="Regular;35" halign="center" zPosition="1" />
					<widget name="buttonblue" position="35,955" size="220,50" backgroundColor="blue" valign="center" halign="center" zPosition="2" foregroundColor="white" font="Regular;32"/>
					<widget name="buttongreen" position="300,955" size="220,50" backgroundColor="green" valign="center" halign="center" zPosition="2" foregroundColor="white" font="Regular;32"/>
					<widget foregroundColor="white" font="Regular;32" position="920,955" render="Label" size="270,50" valign="center" source="global.CurrentTime">
						<convert type="ClockToText">
							Format:%d.%m.%Y %H:%M
						</convert>
					</widget>
				</screen>'''

	def __init__(self, session, args = None):
		Screen.__init__(self, session)
		self.session = session

		self.updateUrl = ''
		self.updateText = ''
		self.filename = ''

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
			self.session.openWithCallback(self.recursiveClose, TelekomSportSportsTypeScreen, title, urlpart)

	def recursiveClose(self, *retVal):
		if retVal:
			self.close()

	def selectDefaultSportsType(self):
		if config.plugins.telekomsport.default_section.value:
			items =  filter(lambda x: x[0] == config.plugins.telekomsport.default_section.value or x[1] == config.plugins.telekomsport.default_section.value, self.sportslist)
			if items:
				self.selectSportsType(items[0])

	def selectSportsType(self, item):
		if item:
			title = item[2]
			urlpart = item[3]
			self.session.openWithCallback(self.recursiveClose, TelekomSportSportsTypeScreen, title, urlpart)

	def showSetup(self):
		self.session.open(TelekomSportConfigScreen)

	def checkForUpdate(self):
		url = 'https://api.github.com/repos/E2OpenPlugins/e2openplugin-TelekomSport/releases'
		header = { 'Accept' : 'application/vnd.github.v3+json' }
		req = urllib2.Request(url, None, header)
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
							break
						elif (not telekomsport_isDreamOS) and asset['name'].endswith('.ipk'):
							self.updateUrl = asset['browser_download_url'].encode('utf8')
							self.filename = '/tmp/enigma2-plugin-extensions-telekomsport.ipk'
							self['buttongreen'].show()
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
		self.container.appClosed.append(self.updateFinished)
		if telekomsport_isDreamOS:
			self.container.execute('dpkg -i ' + self.filename)
		else:
			self.container.execute('opkg update; opkg install ' + self.filename)

	def updateFailed(self, reason, status):
		self.updateFinished(1)

	def updateFinished(self, retval):
		self['buttongreen'].hide()
		self.updateUrl = ''
		if retval == 0:
			self.session.openWithCallback(self.restartE2, MessageBox, 'Das Telekom Sport Plugin wurde erfolgreich installiert!\nSoll das E2 GUI neugestartet werden?', MessageBox.TYPE_YESNO, default = False)
		else:
			self.session.open(MessageBox, 'Bei der Installation ist ein Problem aufgetreten.', MessageBox.TYPE_ERROR)

	def restartE2(self, answer):
		if answer:
			self.session.open(TryQuitMainloop, 3)


def main(session, **kwargs):
	session.open(TelekomSportMainScreen)

def Plugins(**kwargs):
	return PluginDescriptor(name='Telekom Sport', description=_('Telekom Sport Plugin'), where = PluginDescriptor.WHERE_PLUGINMENU, icon='plugin.png', fnc=main)
