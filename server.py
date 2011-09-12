# <Trading Game>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import os
import os.path
import urlparse
from binascii import crc32
from time import time
import sys
import argparse
import flask
from gevent.wsgi import WSGIServer
import gevent
import redis
from werkzeug import SharedDataMiddleware

import game
reload(game)

app = None
db = None
base = os.path.dirname(__file__)

ADMIN_KEY = 'adminueqytMXDDS'


def all_events():
    ids = db.smembers('used_url_ids')
    events = dict([(id, db.lrange('%s:log' % id, 0, -1)) for id in ids])
    return events


def startapp(args):
    global app, db
    global get_next_url, add_next_url, add_urls, gen_url_csv, clear_urls
    
    app = flask.Flask(__name__, static_url_path='/')

    # Turn Debug on
    app.debug = True
    app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {
        '/': os.path.join(base, 'static')})

    db = redis.Redis(port=args.redis_port)
    game.setup_redis(args.redis_port)

    @app.route('/')
    def index(**kwargs):
        return "Error message. Only access this page with a session"

    # Main page for a session
    @app.route('/<userkey>/')
    def default(userkey=None, **kwargs):
        if userkey == ADMIN_KEY:
            return "Wow! You are an admin"

        # Return an error if they are not a valid user
        if not db.sismember('invited_userkeys', userkey):
            return 'This user key is not invited', 403

        # Render the main page
        with open(os.path.join(base, 'static', 'game.htm'), 'r') as fp:
            return fp.read()

    @app.route('/post/<userkey>/', methods=['POST'])
    def post(userkey, **kwargs):
        events = json.loads(flask.request.form['events'])
        status = game.user_status(userkey)

        for event in events:
            # Deal with the event
            if event['name'] == 'approve' and status['status'] == 'prequeue':
                game.queue_user(userkey)
                
        return 'OK'

    @app.route('/events/<userkey>/', methods=['POST'])
    def events(userkey):
        def response(events):
            rv = flask.make_response()
            rv.mimetype = 'text/json'
            rv.data = json.dumps(events)
            return rv
            
        status = game.user_status(userkey)
        if status['status'] == 'uninvited':
            return response([status])

        for i in range(10):
            since = None
            if 'since' in flask.request.form:
                since = flask.request.form['since']
            events = game.events_for_user(userkey, since)

            # Return if there are some events
            if events: return response(events)

            # Otherwise wait and poll
            gevent.sleep(2)

        return response([])

    @app.route('/adminueqytMXDDS/newuser')
    def admin_newuser():
        # Create a new random string
        userkey = game.add_invite()
        return flask.redirect('/' + userkey)

    @app.route('/adminueqytMXDDS/table')
    def admin_table():
        if not app.debug:
            return '', 404
        
        html = '<link rel="stylesheet" href="/css/other-screen.css" />'
        ids = db.smembers('used_url_ids')
        for id in ids:
            events = db.lrange('%s:log' % id, 0, -1)
            html += '''\
<div style="margin-bottom: 3em;">
  <h2>%s</h2>
  <ul>
    <li>%s</li>
  </ul>
</div>
''' % (id, '    </li>\n    <li>'.join(events) or 'No events')
        
        return html


if __name__ == '__main__':
    parser = argparse.ArgumentParser('<Trading Game>')
    parser.add_argument('--port', type=int, default=9202)
    parser.add_argument('--redis-port', type=int, default=9201)
    args = parser.parse_args()
    
    startapp(args)

    print 'Serving on port', args.port
    if app.debug and 0:  # Use gevent?
        app.run('0.0.0.0', args.port)
    else:
        http_server = WSGIServer(('', args.port), app)
        http_server.serve_forever()
