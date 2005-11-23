
#
# gPodder
# Copyright (c) 2005 Thomas Perl <thp@perli.net>
# Released under the GNU General Public License (GPL)
#

#
#  librssreader.py -- xml reader functionality
#  thomas perl <thp@perli.net>   20051029
#
#

from xml.sax.saxutils import DefaultHandler
from xml.sax.handler import ErrorHandler
from xml.sax import make_parser
from string import strip

from libpodcasts import podcastChannel
from libpodcasts import podcastItem

class rssErrorHandler( ErrorHandler):
    def __init__( self):
        None

    def error( self, exception):
        print exception

    def fatalError( self, exception):
        print "FATAL ERROR: ", exception

    def warning( self, exception):
        print "warning: ", exception

class rssReader( DefaultHandler):
    channel_url = ""
    channel = None
    current_item = None
    current_element_data = ""

    def __init__( self):
        None
    
    def parseXML( self, url, filename):
        self.channel_url = url
        parser = make_parser()
	parser.returns_unicode = True
        parser.setContentHandler( self)
	parser.setErrorHandler( rssErrorHandler())
        parser.parse( filename)
    
    def startElement( self, name, attrs):
        self.current_element_data = ""

        if name == "channel":
            self.channel = podcastChannel( self.channel_url)
        if name == "item":
            self.current_item = podcastItem()
        
        if name == "enclosure" and self.current_item != None:
            self.current_item.url = attrs.get( "url", "")
            self.current_item.length = attrs.get( "length", "")
            self.current_item.mimetype = attrs.get( "type", "")

        if name == "itunes:image":
            self.channel.image = attrs.get( "href", "")
    
    def endElement( self, name):
        if self.current_item == None:
            if name == "title":
                self.channel.title = self.current_element_data
            if name == "link":
                self.channel.link = self.current_element_data
            if name == "description":
                self.channel.description = self.current_element_data
        
        if self.current_item != None:
            if name == "title":
                self.current_item.title = self.current_element_data
            if name == "link":
                self.current_item.link = self.current_element_data
            if name == "description":
                self.current_item.description = self.current_element_data
            if name == "guid":
                self.current_item.guid = self.current_element_data
            if name == "item":
                self.channel.addItem( self.current_item)
                self.current_item = None
    
    def characters( self, ch):
        self.current_element_data = self.current_element_data + ch


