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

import argparse
import flask
from gevent.wsgi import WSGIServer
import redis
from werkzeug import SharedDataMiddleware

import game
reload(game)

app = None
db = None
base = os.path.dirname(__file__)


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
    game.db = db

    # Generate the secret key if it hasn't been already
    if not db.exists('secretkey'):
        db.set('secretkey', os.urandom(36))
    app.secret_key = db.get('secretkey')
    
    # Setup the user ID counter
    if not db.exists('id_counter'):
        db.set('id_counter', 1)
        
    # Returns a URL ID based on a counter stored in the database
    def get_next_url():
        if not db.exists('next_url_id'):
            db.set('next_url_id', 0)
        url_id = db.get('next_url_id')
        db.incr('next_url_id')
        
        return ('%08x' % crc32(app.secret_key + url_id)).replace('-', '')
    
    # Adds, or generates and adds, an ID to the list of unactivated IDs
    def add_next_url(id=None):
        if id is None:
            id = get_next_url()
        db.sadd('url_ids', id)
    
    # Adds a certain amount of URLs
    def add_urls(n=100):
        for x in xrange(n):
            add_next_url()
    
    # Clear the URL IDs from the URL ID lists. If `used_only` is True, only the
    # activated URL IDs are removed.
    def clear_urls(used_only=True):
        if not used_only:
            db.sdiffstore('url_ids', 'url_ids', 'url_ids')
        db.sdiffstore('used_url_ids', 'used_url_ids', 'used_url_ids')
    
    def gen_url_csv():
        if not db.exists('url_ids'):
            return None
        
        return ','.join('/play/%s/' % s for s in db.smembers('url_ids'))
    
    @app.route('/csv/')
    def csv(filename='urls.csv'):
        if app.debug is False:
            return '',404

        return gen_url_csv()

    @app.route('/')
    def index(**kwargs):
        return "Error message. Only access this page with a session"

    # Main page for a session
    @app.route('/<session>')
    def session(session=None, **kwargs):
        if session == 'adminueqytMXDDS':
            return "Wow! You are an admin"

        print 'session:' + session
        url = get_next_url()
        add_next_url(url)
        return flask.redirect('/play/'+url)

    # Return all the chat events for a given channel (buyer or seller)
    @app.route('/chat/<session>/<type>', methods=['POST'])
    def get_chat_since(session, type, **kwargs):
        pass
    
    @app.route('/post/<session>/', methods=['POST'])
    def post():
        if (not 'events' in flask.request.form or
            not 'id' in flask.request.form):
            return 'BAD',500
        
        id = flask.request.form['id']
        events = json.loads(flask.request.form['events'])
        for event in events:
            db.lpush('%s:log' % id, json.dumps(event))
        
        return 'OK'
        
    @app.route('/play/<id>/')
    def play(id):
        log = '%s:log' % id
        if not db.sismember('url_ids', id) and not db.exists(log):
            return '', 404
        
        if not db.exists(log):
            db.srem('url_ids', id)
            db.sadd('used_url_ids', id)
            
            db.set('%s:id', db.get('id_counter'))
            db.incr('id_counter')
            
            # Add activated URL event to initialize list
            db.lpush(log,
                     '{"name":"Activated URL","data":{"id":"%s"},"time":%s}'
                     % (id, int(time())))
        
        with open(os.path.join(base, 'static', 'index.htm'), 'r') as fp:
            return fp.read()

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
