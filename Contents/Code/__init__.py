import urlparse
import re
import time
from datetime import datetime

NAME = 'Ragecenter'
ART  = 'NHL-bg.png'
NHLICON  = 'NHL.png'
ICON = 'icon-default.png'
PREFIX = '/video/ragecenter'
UA = [
	'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Trident/6.0; Xbox; Xbox One)',
	'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0; Xbox)',
	'Roku/DVP-4.3 (024.03E01057A), Mozilla/5.0(iPad; U; CPU iPhone OS 3_2 like Mac OS X; en-us) AppleWebKit/531.21.10 (KHTML, like Gecko) Version/4.0.4 Mobile/7B314 Safari/531.21.10'
]
CODE_FIX = {"PHX":"ARI"}
API_URL = 'https://www.ragecenter.com/api/url-for-game/'
FEED_HOME = "home"
FEED_AWAY = "away"

####################################################################################################

def Start():
	Dict.Reset()
	ObjectContainer.title1 = NAME
	ObjectContainer.art = R(ART)
	ObjectContainer.no_cache = True
	DirectoryObject.thumb = R(NHLICON)
	DirectoryObject.art = R(ART)
	HTTP.Headers['User-Agent'] = Util.RandomItemFromList(UA)

@handler(PREFIX, NAME, thumb=ICON, art=ART)
def MainMenu():
	oc = ObjectContainer(title2=NAME)
	Authenticate()
	if 'auth' in Dict:
		oc.add(DirectoryObject(key = Callback(LiveGames), title="Live Games", summary="Watch live games for today."))
		oc.add(DirectoryObject(key = Callback(ArchivedGames), title="Archived Games", summary="Watch archived games as far back as the 2011-2012 season."))

	oc.add(PrefsObject(title="Preferences", summary="Configure the channel.", thumb=R("icon-prefs.png")))
	return oc

@route(PREFIX + '/archivedgames')
def ArchivedGames():
	oc = ObjectContainer(title2="Archived Games")

	now = Datetime.Now()
	offset = 0
	if now.month < 9:
		offset = -1

	for i in range(now.year + offset, 2010, -1):
		s = "%d%d" % (i, i+1)
		title = "%d-%d Season" % (i, i+1)
		oc.add(DirectoryObject(key = Callback(ArchivedSeason, season=s), title=title))

	return oc

@route(PREFIX + '/archivedseason')
def ArchivedSeason(season):
	now = Datetime.Now()
	current_year = str(now.year)

	cacheTime = CACHE_1DAY * 30
	if current_year in season:
		cacheTime = 0

	schedule = JSON.ObjectFromURL('http://live.nhl.com/GameData/SeasonSchedule-%s.json' % season, cacheTime=cacheTime)

	sortedGames = {}
	for d in schedule:
		key = str(d['est'][:8])
		current_date = datetime.strptime(key, '%Y%m%d')
		if current_date >= now:
			continue

		if key in sortedGames:
			games = sortedGames[key]
		else:
			games = []
		games.append(d)
		sortedGames[key] = games

	oc = ObjectContainer(title2=season)
	for i in sorted(sortedGames, reverse=True):
		oc.add(DirectoryObject(key = Callback(ArchivedGamesForDate, season=season, date=i), title="%s-%s-%s" % (i[:4], i[4:6], i[6:])))

	return oc

@route(PREFIX + '/archivedgamesfordate')
def ArchivedGamesForDate(season, date):
	now = str(Datetime.Now().year)
	cacheTime = CACHE_1DAY * 30
	if now in season:
		cacheTime = 0

	schedule = JSON.ObjectFromURL('http://live.nhl.com/GameData/SeasonSchedule-%s.json' % season, cacheTime=cacheTime)
	oc = ObjectContainer(title2="%s-%s-%s" % (date[:4], date[4:6], date[6:]))
	for g in schedule:
		if g['est'].startswith(date):
			id = g['id']
			a = g['a']
			h = g['h']
			title = "%s vs %s" % (a, h)
			oc.add(DirectoryObject(key = Callback(ArchivedGameMenu, id=id, away=a, home=h), title=title))

	return oc

@route(PREFIX + '/archivedgamemenu')
def ArchivedGameMenu(id, away, home):
	title = "%s vs %s" % (away, home)
	oc = ObjectContainer(title2=title)

	oc.add(CreateGameObject(
		url = API_URL + '%(id)s?feed=%(feed)s' % {'id': id, 'feed': FEED_HOME},
		title = title + ' - Home',
		team = home,
		summary = 'Full game replay - Home Feed',
		feed = FEED_HOME
	))

	oc.add(CreateGameObject(
		url = API_URL + '%(id)s?feed=%(feed)s' % {'id': id, 'feed': FEED_AWAY},
		title = title + ' - Away',
		team = away,
		summary = 'Full game replay - Away Feed',
		feed = FEED_AWAY
	))

	return oc

@route(PREFIX + '/livegames')
def LiveGames():
	oc = ObjectContainer(title2="Live Games", no_cache=True)
	today = Datetime.Now()

	console = XML.ElementFromURL('http://gamecenter.nhl.com/nhlgc/servlets/simpleconsole?format=xml&app=true', cacheTime=0)
	date = console.xpath("//currentDate/text()")[0].replace('T', ' ')
	date = Datetime.ParseDate(date)

	if today >= date:
		today = date

	url = today.strftime('http://f.nhl.com/livescores/nhl/leagueapp/20142015/scores/%Y-%m-%d_O2T1.json')
	schedule = JSON.ObjectFromURL(url)

	for g in schedule['games']:
		gameInformation = g['gameInformation']
		title = '%s vs. %s' % (gameInformation['awayTeam']['teamName'], gameInformation['homeTeam']['teamName'])
		summary = gameInformation['easternGameTime'] if gameInformation['gs'] < 3 else gameInformation['currentGameTime']
		thumb = g['gameStory']['storyThumbnail'] if 'gameStory' in g else None

		oc.add(DirectoryObject(key = Callback(LiveGameFeeds, game=g), title=title, summary=summary, thumb=thumb))

	return oc

@route(PREFIX + '/livegamefeeds', game=dict)
def LiveGameFeeds(game):
	title = '%s vs %s' % (game['gameInformation']['awayTeam']['teamName'], game['gameInformation']['homeTeam']['teamName'])
	oc = ObjectContainer(title2=title)
	if 'gameStory' in game:
		gameStory = game['gameStory']

		oc.add(CreateVideoObject(
			url = 'http://video.nhl.com/videocenter/servlets/playlist?format=json&ids=%d' % gameStory['storyVideoId'],
			format = None,
			title = gameStory['storyTitle'],
			thumb = gameStory['storyThumbnail'],
			summary = gameStory['storyDesc']
		))

	gs = game['gameInformation']['gs']
	gameLiveVideo = game['gameLiveVideo']
	if gs > 1 and gs < 6:
		oc.add(CreateGameObject(
			url = API_URL + '%(id)d?feed=%(feed)s' % {'id': game['gameInformation']['gameId'], 'feed': FEED_HOME},
			title = title + ' - Home',
			summary = 'Home Feed',
			team = game['gameInformation']['homeTeam']['teamAbb'],
			feed = FEED_HOME
		))
		oc.add(CreateGameObject(
			url = API_URL + '%(id)d?feed=%(feed)s' % {'id': game['gameInformation']['gameId'], 'feed': FEED_AWAY},
			title = title + ' - Away',
			summary = 'Away Feed',
			team = game['gameInformation']['awayTeam']['teamAbb'],
			feed = FEED_AWAY
		))

	elif gs > 5:
		oc.add(CreateGameObject(
			url = API_URL + '%(id)d?feed=%(feed)s' % {'id': game['gameInformation']['gameId'], 'feed': FEED_HOME},
			title = title + ' - Home',
			team = game['gameInformation']['homeTeam']['teamAbb'],
			summary = 'Full game replay - Home Feed',
			feed = FEED_HOME
		))
		oc.add(CreateGameObject(
			url = API_URL + '%(id)d?feed=%(feed)s' % {'id': game['gameInformation']['gameId'], 'feed': FEED_AWAY},
			title = title + ' - Away',
			team = game['gameInformation']['awayTeam']['teamAbb'],
			summary = 'Full game replay - Away Feed',
			feed = FEED_AWAY
		))
	return oc

@route(PREFIX + '/creategameobject')
def CreateGameObject(url, title, summary, team, feed, include = False):
	bitrate = Prefs['bitrate']
	if bitrate == 'Auto':
		bitrate = 5000

	for key in CODE_FIX:
		if team == key:
			team = CODE_FIX[key]

	v = VideoClipObject(
			key = Callback(CreateGameObject, url=url, title=title, summary=summary, team=team, feed=feed, include=True),
			rating_key = url,
			title = title,
			summary = summary,
			thumb = R(team + '.png'),
			art = R(team + '-bg.png'),
			items = [
				MediaObject(
					optimized_for_streaming=True,
					protocol = 'hls',
					container = 'mpegts',
					video_codec = VideoCodec.H264,
					parts = [PartObject(key=Callback(PlayEncryptedVideo, url=url, feed=feed, bitrate=bitrate))]
				)
			]
		)

	if include:
		return ObjectContainer(objects=[v])
	return v

@route(PREFIX + '/createvideoobject')
def CreateVideoObject(url, format, title, summary, thumb, include = False):
	v = VideoClipObject(
			key = Callback(CreateVideoObject, url=url, format=format, title=title, summary=summary, thumb=thumb, include=True),
			rating_key = url,
			title = title,
			summary = summary,
			thumb = thumb,
			items = [
				MediaObject(
					optimized_for_streaming = True,
					parts = [PartObject(key = Callback(PlayVideo, format=format, url=url))]
				)
			]
		)

	if include:
		return ObjectContainer(objects=[v])
	return v

@indirect
@route(PREFIX + '/playvideo')
def PlayVideo(format, url):
	if url.startswith('http://video.nhl.com/videocenter/servlets/playlist'):
		video = JSON.ObjectFromString(HTTP.Request(url=url).content.replace("\\'", ""))
		format = video[0]['formats']
		url = video[0]['publishPoint']

	format = int(format)
	if '/s/' in url:
		url = url.replace('/s/', '/u/')
	if format == 1:
		url = url.replace('.mp4', '_sd.mp4')
	elif format == 2:
		url = url.replace('.mp4', '_sh.mp4')
	elif format != 0:
		url = url.replace('.mp4', '_hd.mp4')

	return IndirectResponse(VideoClipObject, key=HTTPLiveStreamURL(url))

@indirect
@route(PREFIX + '/playencryptedvideo')
def PlayEncryptedVideo(url, feed, bitrate):
	cookies = ''
	path = JSON.ObjectFromURL(url, headers = {'User-Agent': Util.RandomItemFromList(UA), 'Cookie': 'sessionid=' + Dict['auth']}, cacheTime=0)
	isLive = path['game_urls']['isLive']
	streams = path['game_urls'][feed]
	path = streams[0]['url']
	for stream in streams:
		if str(stream['quality']) == str(bitrate):
			path = stream['url']

	if isLive:
		tempRate = str(bitrate)
		if tempRate == '5000':
			tempRate = '4500'

		tempPath = path.replace('hd_ipad', 'hd_4500_ipad')
		if Prefs['bitrate'] != 'Auto':
			tempPath = path.replace('hd_ipad', 'hd_' + tempRate + '_ipad')
			path = tempPath

		req_m3u8 = HTTP.Request(tempPath, cacheTime=0)
		cookies = req_m3u8.headers['Set-Cookie']
		m = re.search('.*EXT-X-KEY.*URI="(.*)".*', req_m3u8.content)
		if m:
			key_uri = m.group(1)
			cookies += "; " + HTTP.Request(key_uri, headers = {'Cookie': cookies}).headers['Set-Cookie']

	return IndirectResponse(VideoClipObject, key=HTTPLiveStreamURL(path), http_cookies = cookies)

def Authenticate():
	parameters = {'username': Prefs['username'], 'password': Prefs['password']}
	data = JSON.ObjectFromURL('https://ragecenter.com/api/auth', values=parameters)
	sessionid = HTTP.CookiesForURL('https://ragecenter.com').split('sessionid=')[1]
	Dict['auth'] = sessionid

def ValidatePrefs():
	Authenticate()