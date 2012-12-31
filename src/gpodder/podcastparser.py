# -*- coding: utf-8 -*-
#
# gPodder - A media aggregator and podcast client
# Copyright (c) 2005-2012 Thomas Perl and the gPodder Team
#
# gPodder is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# gPodder is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# gpodder.podcastparser - Simplified, fast RSS parser
# Thomas Perl <thp@gpodder.org>; 2012-12-29

from xml import sax

from gpodder import util
from gpodder import youtube
from gpodder import vimeo

import re
import os
import time
import urlparse

class Target:
    WANT_TEXT = False

    def __init__(self, key=None, filter_func=lambda x: x.strip()):
        self.key = key
        self.filter_func = filter_func

    def start(self, handler, attrs): pass
    def end(self, handler, text): pass

class RSS(Target):
    def start(self, handler, attrs):
        handler.set_base(attrs.get('xml:base'))

class PodcastItem(Target):
    def end(self, handler, text):
        handler.data['episodes'].sort(key=lambda entry: entry.get('published'), reverse=True)
        if handler.max_episodes:
            handler.data['episodes'] = handler.data['episodes'][:handler.max_episodes]

class PodcastAttr(Target):
    WANT_TEXT = True

    def end(self, handler, text):
        handler.set_podcast_attr(self.key, self.filter_func(text))

class PodcastAttrFromHref(Target):
    def start(self, handler, attrs):
        value = attrs.get('href')
        if value:
            handler.set_podcast_attr(self.key, self.filter_func(value))

class PodcastAttrFromPaymentHref(PodcastAttrFromHref):
    def start(self, handler, attrs):
        if attrs.get('rel') == 'payment':
            PodcastAttrFromHref.start(self, handler, attrs)

class EpisodeItem(Target):
    def start(self, handler, attrs):
        handler.episodes.append({
            # title
            'description': '',
            # url
            'published': 0,
            # guid
            'link': '',
            'file_size': -1,
            'mime_type': 'application/octet-stream',
            'total_time': 0,
            'payment_url': None,
            'enclosures': [],
            '_guid_is_permalink': False,
        })

    def end(self, handler, text):
        entry = handler.episodes[-1]

        # No enclosures for this item
        if len(entry['enclosures']) == 0:
            if (youtube.is_video_link(entry['link']) or
                    vimeo.is_video_link(entry['link'])):
                entry['enclosures'].append({
                    'url': entry['link'],
                    'file_size': -1,
                    'mime_type': 'video/mp4',
                })
            else:
                handler.episodes.pop()
                return

        # Here we could pick a good enclosure
        entry.update(entry['enclosures'][0])
        del entry['enclosures']

        if 'guid' not in entry:
            # Maemo bug 12073
            entry['guid'] = entry['url']

        if 'title' not in entry:
            entry['title'] = entry['url']

        if not entry.get('link') and entry.get('_guid_is_permalink'):
            entry['link'] = entry['guid']

        del entry['_guid_is_permalink']

class EpisodeAttr(Target):
    WANT_TEXT = True

    def end(self, handler, text):
        handler.set_episode_attr(self.key, self.filter_func(text))

class EpisodeGuid(EpisodeAttr):
    def start(self, handler, attrs):
        if attrs.get('isPermaLink', 'true').lower() == 'true':
            handler.set_episode_attr('_guid_is_permalink', True)
        else:
            handler.set_episode_attr('_guid_is_permalink', False)

    def end(self, handler, text):
        def filter_func(guid):
            guid = guid.strip()
            if handler.base is not None:
                return urlparse.urljoin(handler.base, guid)
            return guid

        self.filter_func = filter_func
        EpisodeAttr.end(self, handler, text)

class EpisodeAttrFromHref(Target):
    def start(self, handler, attrs):
        value = attrs.get('href')
        if value:
            handler.set_episode_attr(self.key, self.filter_func(value))

class EpisodeAttrFromPaymentHref(EpisodeAttrFromHref):
    def start(self, handler, attrs):
        if attrs.get('rel') == 'payment':
            EpisodeAttrFromHref.start(self, handler, attrs)

class Enclosure(Target):
    def start(self, handler, attrs):
        url = attrs.get('url')
        if url is None:
            return

        url = parse_url(urlparse.urljoin(handler.url, url))
        file_size = parse_length(attrs.get('length'))
        mime_type = parse_type(attrs.get('type'))

        handler.add_enclosure(url, file_size, mime_type)


def squash_whitespace(text):
    return re.sub('\s+', ' ', text.strip())

def parse_duration(text):
    return util.parse_time(text.strip())

def parse_url(text):
    return util.normalize_feed_url(text.strip())

def parse_length(text):
    if text is None:
        return -1

    try:
        return long(text.strip()) or -1
    except ValueError:
        return -1

def parse_type(text):
    if not text or '/' not in text:
        # Maemo bug 10036
        return 'application/octet-stream'

    return text

def parse_pubdate(text):
    return util.parse_date(text)


MAPPING = {
    'rss': RSS(),
    'rss/channel': PodcastItem(),
    'rss/channel/title': PodcastAttr('title', squash_whitespace),
    'rss/channel/link': PodcastAttr('link'),
    'rss/channel/description': PodcastAttr('description', squash_whitespace),
    'rss/channel/image/url': PodcastAttr('cover_url'),
    'rss/channel/itunes:image': PodcastAttrFromHref('cover_url'),
    'rss/channel/atom:link': PodcastAttrFromPaymentHref('payment_url'),

    'rss/channel/item': EpisodeItem(),
    'rss/channel/item/guid': EpisodeGuid('guid'),
    'rss/channel/item/title': EpisodeAttr('title', squash_whitespace),
    'rss/channel/item/link': EpisodeAttr('link'),
    'rss/channel/item/description': EpisodeAttr('description', squash_whitespace),
    # Alternatives for description: itunes:summary, itunes:subtitle, content:encoded
    'rss/channel/item/itunes:duration': EpisodeAttr('total_time', parse_duration),
    'rss/channel/item/pubDate': EpisodeAttr('published', parse_pubdate),
    'rss/channel/item/atom:link': EpisodeAttrFromPaymentHref('payment_url'),

    'rss/channel/item/enclosure': Enclosure(),
}

class PodcastHandler(sax.handler.ContentHandler):
    def __init__(self, url, max_episodes):
        self.url = url
        self.max_episodes = max_episodes
        self.base = None
        self.text = None
        self.episodes = []
        self.data = {
            'title': '',
            'episodes': self.episodes
        }
        self.path_stack = []

    def set_base(self, base):
        self.base = base

    def set_podcast_attr(self, key, value):
        self.data[key] = value

    def set_episode_attr(self, key, value):
        self.episodes[-1][key] = value

    def add_enclosure(self, url, file_size, mime_type):
        self.episodes[-1]['enclosures'].append({
            'url': url,
            'file_size': file_size,
            'mime_type': mime_type,
        })

    def startElement(self, name, attrs):
        self.path_stack.append(name)

        target = MAPPING.get('/'.join(self.path_stack))
        if target is not None:
            target.start(self, attrs)
            if target.WANT_TEXT:
                self.text = []

    def characters(self, chars):
        if self.text is not None:
            self.text.append(chars)

    def endElement(self, name):
        target = MAPPING.get('/'.join(self.path_stack))
        if target is not None:
            target.end(self, ''.join(self.text) if self.text is not None else '')
            self.text = None

        self.path_stack.pop()


def parse(url, stream, max_episodes=0):
    handler = PodcastHandler(url, max_episodes)
    sax.parse(stream, handler)
    return handler.data
