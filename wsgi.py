##############################################################################
#
# Copyright (c) 2004 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""A WSGI Application wrapper for zope

$Id$
"""

from zope.interface import implements
from zope.publisher.publish import publish
from zope.publisher.http import HTTPRequest
from zope.publisher.interfaces.http import IHeaderOutput
from zope.publisher.browser import BrowserRequest
from zope.publisher.xmlrpc import XMLRPCRequest

class WsgiOutput(object):
    """This class handles the output generated by
    the publisher. It is used to collect the headers
    and as an outstream to output the response body.

    When write is first called by the response, it initiates
    the reponse by invoking the WSGI start_response callable.

    Create a mock implementation of the wsgi write callable
    >>> from StringIO import StringIO
    >>> data = StringIO('')
    >>> def start_response(status, headers):
    ...     data.write('status and headers.')
    ...     return data.write
    ...

    create an instance
    >>> output = WsgiOutput(start_response)

    Set the response status
    >>> output.setResponseStatus("200", "OK")
    >>> output._statusString
    '200 OK'
    
    Set the headers as a mapping
    >>> output.setResponseHeaders({'a':'b', 'c':'d'})

    They must be returned as a list of tuples
    >>> output.getHeaders()
    [('a', 'b'), ('c', 'd')]
    
    calling setResponseHeaders again adds new values 
    >>> output.setResponseHeaders({'x':'y', 'c':'d'})
    >>> h = output.getHeaders()
    >>> h.sort()
    >>> h
    [('a', 'b'), ('c', 'd'), ('x', 'y')]

    Headers that can potentially repeat are added using
    appendResponseHeaders
    >>> output.appendResponseHeaders(['foo: bar'])
    >>> h = output.getHeaders()
    >>> h.sort()
    >>> h    
    [('a', 'b'), ('c', 'd'), ('foo', ' bar'), ('x', 'y')]
    >>> output.appendResponseHeaders(['foo: bar'])
    >>> h = output.getHeaders()
    >>> h.sort()
    >>> h    
    [('a', 'b'), ('c', 'd'), ('foo', ' bar'), ('foo', ' bar'), ('x', 'y')]

    Headers containing a colon should also work
    >>> output.appendResponseHeaders(['my: brain:hurts'])
    >>> h = output.getHeaders()
    >>> h.sort()
    >>> h    
    [('a', 'b'), ('c', 'd'), ('foo', ' bar'), \
('foo', ' bar'), ('my', ' brain:hurts'), ('x', 'y')]

    The headers should not be written to the output
    >>> output.wroteResponseHeader()
    False
    >>> data.getvalue()
    ''
    
    now write something
    >>> output.write('Now for something')

    The headers should be sent and the data written to the stream
    >>> output.wroteResponseHeader()
    True
    >>> data.getvalue()
    'status and headers.Now for something'

    calling write again the headers should not be sent again
    >>> output.write(' completly different!')
    >>> data.getvalue()
    'status and headers.Now for something completly different!'
    """

    def __init__(self, start_response):
        self._headers = {}
        self._accumulatedHeaders = []
        self._statusString = ""
        self._headersSent = False

        self.wsgi_write = None
        self.start_response = start_response

    def setResponseStatus(self,status, reason):
        """Sets the status code and the accompanying message.
        """
        self._statusString = str(status)+' '+reason

    def setResponseHeaders(self, mapping):
        """Sets headers.  The headers must be Correctly-Cased.
        """
        self._headers.update(mapping)

    def appendResponseHeaders(self, lst):
        """Sets headers that can potentially repeat.

        Takes a list of strings.
        """
        self._accumulatedHeaders.extend(lst)

    def wroteResponseHeader(self):
        """Returns a flag indicating whether the response

        header has already been sent.
        """
        return self._headersSent

    def setAuthUserName(self, name):
        """Sets the name of the authenticated user so the name can be logged.
        """
        pass

    def getHeaders(self):
        """return the response headers as a list of tuples according
        to the WSGI spec
        """
        response_headers = self._headers.items()

        accum = [ tuple(line.split(':',1)) for line in self._accumulatedHeaders]
            
        response_headers.extend(accum)
        return response_headers


    def write(self, data):
        """write the response.
        If the reponse has not begun, call the wsgi servers
        'start_reponse' callable to begin the response
        """
        if not self._headersSent:
            self.wsgi_write = self.start_response(self._statusString,
                                         self.getHeaders())
            self._headersSent = True

        self.wsgi_write(data)


class PublisherApp(object):
    """A WSGI application implemenation for the zope publisher

    Instances of this class can be used as a WSGI application
    object.

    The class relies on a properly initialized request factory.
    
    """
    

    def __init__(self, publication):
        self.publication = publication

    def __call__(self, env, start_response,
                 _browser_methods = ('GET', 'POST', 'HEAD'),
                 ):
        """makes instances a WSGI callable application object
        """
        
        wsgi_output = WsgiOutput(start_response)
        input_stream = env['wsgi.input']

        method = env.get('REQUEST_METHOD', 'GET').upper()
        if method in _browser_methods:
            if (method == 'POST' and
                env.get('CONTENT_TYPE', '').startswith('text/xml')
                ):
                request = XMLRPCRequest(input_stream, wsgi_output, env)
            else:
                request = BrowserRequest(input_stream, wsgi_output, env)
        else:
            request = HTTPRequest(input_stream, wsgi_output, env)

        request.setPublication(self.publication)
        request.response.setHeaderOutput(wsgi_output)

        publish(request)

        request.close()

        # since the response is written using the WSGI write callable
        # return an empty iterable (see 
        return ""
