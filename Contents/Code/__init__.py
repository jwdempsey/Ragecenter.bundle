import datetime
import re
from dateutil import parser
from dateutil import tz

ART            = 'art-default.jpg'
ICON           = 'icon-default.png'
SEARCH_ICON    = 'icon-search.png'
PREFS_ICON     = 'icon-prefs.png'
NHL_ICON       = 'NHL.png'
PREFIX         = '/video/ragecenter'
TITLE          = 'NHL Ragecenter'
BASE_URL       = 'https://www.ragecenter.com'
TITLE_FORMAT   = '{0} at {1}'
SUMMARY_FORMAT = 'Game time: {0}. {1}'
STATUS_FORMAT  = 'Game time: {0}. Status: {1}.'
ARCHIVE_FORMAT = '{0}'
LOGIN          = BASE_URL + '/api/auth'
GAMES_BY_DATE  = BASE_URL + '/api/json-for-day/{0}'
GAME_URLS      = BASE_URL + '/api/url-for-game/{0}'

################################################################################
def Start():
    ObjectContainer.art = R(ART)
    ObjectContainer.title1 = TITLE
    DirectoryObject.thumb = R(ICON)

################################################################################
def ValidatePrefs():
    return True

################################################################################
@handler(PREFIX, TITLE, art=ART, thumb=ICON)
def MainMenu():
    authenticate()
    oc = ObjectContainer(title2=TITLE)
    oc.add(DirectoryObject(title="Today's Games", summary="Watch live games for today", key=Callback(GamesByDate, title='Live Games')))
    oc.add(DirectoryObject(title="Archived Games", summary="Watch archived games as far back as the 2011-2012 season", key=Callback(ArchivedGames)))
    oc.add(PrefsObject(title='Preferences', thumb=R(PREFS_ICON)))
    return oc

################################################################################
@route(PREFIX + '/gamesbydate')
def GamesByDate(title, date=None):
    if not date:
        date = (datetime.datetime.now(tz.gettz("EST5EDT")) - datetime.timedelta(hours=3)).strftime("%Y/%m/%d")

    oc = ObjectContainer(title2=title)
    games = request(GAMES_BY_DATE.format(date))

    if len(games) == 0:
        return ObjectContainer(header='Live Games', message='No games today!')

    for game in games:
        away = game['away_team']
        home = game['home_team']
        title = TITLE_FORMAT.format(away['team_name'], home['team_name'])
        summary = get_summary(game)

        do = DirectoryObject(title=title, thumb=R(NHL_ICON), summary=summary)
        if game['gamestate'] != 1:
            do.key=Callback(GameURLs, title=title, summary=summary, id=game['game_id'], away=away, home=home)
        else:
            do.key=Callback(NotStarted)

        oc.add(do)
    return oc

################################################################################
@route(PREFIX + '/archivedgames')
def ArchivedGames():
    oc = ObjectContainer(title2="Archived Games")

    now = Datetime.Now()
    offset = 0
    if now.month < 9:
        offset = -1

    for i in range(now.year + offset, 2010, -1):
        s = "%d%d" % (i, i+1)
        title = "%d-%s Season" % (i, str(i+1)[-2:])
        oc.add(DirectoryObject(key = Callback(ArchivedSeason, season=s, title=title), title=title))

    return oc

################################################################################
@route(PREFIX + '/archivedseason')
def ArchivedSeason(season, title):
    now = Datetime.Now()
    current_year = str(now.year)

    cacheTime = CACHE_1DAY * 120
    if current_year in season:
        cacheTime = 0

    schedule = JSON.ObjectFromURL('http://live.nhl.com/GameData/SeasonSchedule-%s.json' % season, cacheTime=cacheTime)

    sortedGames = {}
    for d in schedule:
        key = str(d['est'][:8])
        current_date = datetime.datetime.strptime(key, '%Y%m%d')
        if current_date >= now:
            continue

        if key in sortedGames:
            games = sortedGames[key]
        else:
            games = []
        games.append(d)
        sortedGames[key] = games

    oc = ObjectContainer(title2=title)
    for i in sorted(sortedGames, reverse=True):
        date = '%s/%s/%s' % (i[:4], i[4:6], i[6:])
        title = datetime.datetime.strptime(date, '%Y/%m/%d').strftime("%B %d, %Y")
        oc.add(DirectoryObject(key = Callback(GamesByDate, title=title, date=date), title=title))

    return oc

################################################################################
@route(PREFIX + '/gameurls', home=dict, away=dict)
def GameURLs(title, summary, id, home, away):
    oc = ObjectContainer(title2=TITLE)
    urls = request(GAME_URLS.format(id))

    isLive = urls['game_urls']['isLive']
    home_url = urls['game_urls']['home'][0]['url']
    away_url = urls['game_urls']['away'][0]['url']

    if '.mp4' in home_url:
        if isLive:
            oc.add(LiveVideoObject(
                url = home_url,
                title = 'Full Game Recap',
                thumb = R(NHL_ICON),
                summary = summary
            ))
        else:
          oc.add(RecapVideoObject(
              url = home_url,
              title = 'Full Game Recap',
              thumb = R(NHL_ICON),
              summary = summary
          ))
    else:
       oc.add(LiveVideoObject(
           url = home_url,
           title = 'Home Stream: ' + home['team_name'],
           thumb = R(home['abbreviation'] + '.png'),
           summary = summary
       ))

       oc.add(LiveVideoObject(
           url = away_url,
           title = 'Away Stream: ' + away['team_name'],
           thumb = R(away['abbreviation'] + '.png'),
           summary = summary
       ))

    return oc

################################################################################
@route(PREFIX + '/notstarted')
def NotStarted():
    return ObjectContainer(header='Not Started', message='This game has not started yet. Please check back 20 minutes before game time.')

################################################################################
@route(PREFIX + '/livevideoobject')
def LiveVideoObject(url, title, summary, thumb, include_container=False):
    vo = VideoClipObject(
        key = Callback(LiveVideoObject, url=url, title=title, summary=summary, thumb=thumb, include_container=True),
        rating_key = url,
        title = title,
        summary = summary,
        thumb = thumb,
        items = [
            MediaObject(
                protocol = 'hls',
                container = 'mpegts',
                video_codec = VideoCodec.H264,
                parts = [PartObject(key=Callback(PlayVideo, url=url, ext='m3u8'))]
            )
        ]
    )

    if include_container:
        return ObjectContainer(objects=[vo])
    return vo

################################################################################
@route(PREFIX + '/recapvideoobject')
def RecapVideoObject(url, title, summary, thumb, include_container=False):
    vo = VideoClipObject(
        key = Callback(RecapVideoObject, url=url, title=title, summary=summary, thumb=thumb, include_container=True),
        rating_key = url,
        title = title,
        summary = summary,
        thumb = thumb,
        items = [
            MediaObject(
                container = Container.MP4,
                video_codec = VideoCodec.H264,
                parts = [PartObject(key=Callback(PlayRecapVideo, url=url, ext='mp4'))]
            )
        ]
    )

    if include_container:
        return ObjectContainer(objects=[vo])
    return vo

################################################################################
@indirect
@route(PREFIX + '/playvideo')
def PlayVideo(url):
    url = url.replace('hd_ipad', 'hd_4500_ipad')

    if Client.Platform == ClientPlatform.Roku:
        return IndirectResponse(VideoClipObject, key=HTTPLiveStreamURL(url))
    else:
        cookies = ''
        req_m3u8 = HTTP.Request(url, cacheTime=0)
        cookies = req_m3u8.headers['Set-Cookie']
        m = re.search('.*EXT-X-KEY.*URI="(.*)".*', req_m3u8.content)
        if m:
            key_uri = m.group(1)
            try:
                cookies += "; " + HTTP.Request(key_uri, headers = {'Cookie': cookies}).headers['Set-Cookie']
            except Exception, e:
                cookies = ''

        return IndirectResponse(VideoClipObject, key=HTTPLiveStreamURL(url), http_cookies = cookies)

################################################################################
@route(PREFIX + '/playrecapvideo')
def PlayRecapVideo(url):
    return Redirect(url)

################################################################################
def request(url, parameters=None):
    return JSON.ObjectFromURL(url, values=parameters)

def authenticate():
    parameters = {'username': Prefs['username'], 'password': Prefs['password']}
    data = request(LOGIN, parameters=parameters)
    HTTP.Headers['Cookie'] = HTTP.CookiesForURL(BASE_URL)

def get_local_date(date):
    local = tz.tzlocal()
    eastern = tz.gettz("EST5EDT")
    current_day = (datetime.datetime.now(eastern) - datetime.timedelta(hours=3)).strftime("%Y/%m/%d")

    time = datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S').strftime('%I:%M %p')
    naive = parser.parse(current_day + " " + time)
    start = naive.replace(tzinfo=eastern)
    return start.astimezone(local).strftime("%I:%M %p")

def get_summary(game):
    date = get_local_date(game['start_time_est'])
    if game['gamestate'] in [1, 2]:
        summary = SUMMARY_FORMAT.format(date, game['preview'])
    elif game['gamestate'] in [3,4,5]:
        summary = STATUS_FORMAT.format(date, game['status_tag'])
    elif game['gamestate'] == 6:
        summary = STATUS_FORMAT.format(date, game['status'])
    else:
        summary = ARCHIVE_FORMAT.format(game['recap'])

    if not summary:
        return SUMMARY_FORMAT.format(date, '')
    else:
        return summary