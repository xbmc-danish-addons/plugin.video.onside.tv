#
#      Copyright (C) 2014 Tommy Winther
#      http://tommy.winther.nu
#
#  This Program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This Program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this Program; see the file LICENSE.txt.  If not, write to
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#  http://www.gnu.org/copyleft/gpl.html
#
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib2
import re
import os
import sys
import urlparse
import buggalo

BASE_URL = 'http://onside.dk'


def listVideos(page=0):
    url = BASE_URL + '/onside_tv/arkiv'
    if page > 0:
        url += '?page=%d' % page

    html = downloadUrl(url)
    for m in re.finditer('field-created">(.*?)<a href="([^"]+)"><span class="Video">([^<]+)<', html, re.DOTALL):
        path = m.group(2)
        title = m.group(3).replace('&#039;', "'")

        item = xbmcgui.ListItem(title, iconImage=ICON, thumbnailImage=ICON)
        item.setProperty('IsPlayable', 'true')
        item.setProperty('Fanart_Image', FANART)
        item.setInfo(type='video', infoLabels={
            'studio': ADDON.getAddonInfo('name'),
            'title': title,
        })
        xbmcplugin.addDirectoryItem(HANDLE, PATH + '?play=' + path, item)

    if ADDON.getSetting('show.load.next.page') == 'true':
        if -1 != html.find('<a href="/onside_tv/arkiv?page=' + str(page + 1) + '"'):
            item = xbmcgui.ListItem(ADDON.getLocalizedString(30000), iconImage=ICON)
            item.setProperty('Fanart_Image', FANART)
            xbmcplugin.addDirectoryItem(HANDLE, PATH + '?page=' + str(page + 1), item, True)

    xbmcplugin.endOfDirectory(HANDLE)


def playProgram(path):
    url = BASE_URL + path
    html = downloadUrl(url)

    m = re.search('<iframe src="([^"]+)"', html)

    embedUrl = m.group(1)
    html = downloadUrl(embedUrl, url)

    m = re.search('@videoPlayer" value="([^"]+)"', html)
    playerId = m.group(1)

    # inspired by
    # https://github.com/markhoney/plugin.video.nz.ondemand/blob/master/resources/channels/tvnz.py
    import pyamf
    from pyamf import AMF3
    from pyamf.remoting.client import RemotingService

    gateway = RemotingService(
        'http://c.brightcove.com/services/messagebroker/amf?playerKey=AQ~~%2CAAAB3OVQl2k~%2CoSHJMRP9QYplfaGrVZpNjWVXyHUIiqtG',
        amf_version=AMF3)

    pyamf.register_class(ViewerExperienceRequest, 'com.brightcove.experience.ViewerExperienceRequest')
    pyamf.register_class(ContentOverride, 'com.brightcove.experience.ContentOverride')

    req = ViewerExperienceRequest(embedUrl, [ContentOverride(int(playerId))], None,
                                  'AQ~~%2CAAAB3OVQl2k~%2CoSHJMRP9QYplfaGrVZpNjWVXyHUIiqtG')

    facade = gateway.getService('com.brightcove.experience.ExperienceRuntimeFacade')
    response = facade.getDataForExperience('2c72cad0c1734e5dd4360759814e199d07e1ca21', req)

    videoUrl = None
    encodingRate = 0
    for rendition in response['programmedContent']['videoPlayer']['mediaDTO']['IOSRenditions']:
        if rendition['encodingRate'] > encodingRate:
            videoUrl = rendition['defaultURL']
            encodingRate = rendition['encodingRate']

    item = xbmcgui.ListItem(path=videoUrl)
    xbmcplugin.setResolvedUrl(HANDLE, True, item)


def downloadUrl(url, referrer=None):
    try:
        req = urllib2.Request(url)
        if referrer:
            req.add_header('Referer', referrer)
        u = urllib2.urlopen(req)
        data = u.read()
        u.close()
        return data
    except Exception, ex:
        raise OnsideException(ex)


def showError(message):
    heading = buggalo.getRandomHeading()
    line1 = ADDON.getLocalizedString(30900)
    line2 = ADDON.getLocalizedString(30901)
    xbmcgui.Dialog().ok(heading, line1, line2, message)


class OnsideException(Exception):
    pass


class ViewerExperienceRequest(object):
    def __init__(self, URL, contentOverrides, experienceId, playerKey, TTLToken=""):
        self.URL = URL
        self.deliveryType = float(0)
        self.contentOverrides = contentOverrides
        self.experienceId = experienceId
        self.playerKey = playerKey
        self.TTLToken = TTLToken


class ContentOverride(object):
    def __init__(self, contentId, contentType=0, target='videoPlayer'):
        self.contentType = contentType
        self.contentId = contentId
        self.target = target
        self.contentIds = None
        self.contentRefId = None
        self.contentRefIds = None
        self.featureId = float(0)
        self.featuredRefId = None


if __name__ == '__main__':
    ADDON = xbmcaddon.Addon()
    PATH = sys.argv[0]
    HANDLE = int(sys.argv[1])
    PARAMS = urlparse.parse_qs(sys.argv[2][1:])

    FANART = os.path.join(ADDON.getAddonInfo('path'), 'fanart.jpg')
    ICON = os.path.join(ADDON.getAddonInfo('path'), 'icon.png')

    buggalo.SUBMIT_URL = 'http://tommy.winther.nu/exception/submit.php'
    try:
        if 'play' in PARAMS:
            playProgram(PARAMS['play'][0])
        elif 'page' in PARAMS:
            listVideos(int(PARAMS['page'][0]))
        else:
            listVideos()

    except OnsideException, ex:
        showError(str(ex))
    except Exception:
        buggalo.onExceptionRaised()
