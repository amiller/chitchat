import os
import hashlib
import redis
import json
import random
import bunch
import time
import sys

db = None
pubsub = None


def setup_redis(port):
    global db, pubsub
    db = redis.Redis(port=port)
    pubsub = db.pubsub()


# Call this when we receive a new qualification from mechanical turk
def add_invite():
    invite = random_userkey()
    db.sadd('invited_userkeys', invite)
    return invite


def random_userkey():
    # 16 character user string (8 bytes)
    return hashlib.sha256(os.urandom(20)).hexdigest()[:16]


def events_for_user(userkey, since=None):
    # Get all the events visible to the user
    status = user_status(userkey)

    # Bounce if not invited
    if status['status'] == 'uninvited':
        return [{'name': 'uninvited', 'timestamp': repr(time.time())}]

    # Bounce if game is already over
    if status['status'] == 'gameover':
        return [{'name': 'gameover', 'timestamp': repr(time.time())}]

    # Get all the user events
    since = '(' + since if since else '-inf'
    user_events = db.zrangebyscore('events_user:%s' % userkey,
                                   since, float('+inf'), withscores=True)

    if status['status'] == 'playing':
        gamekey = status['gamekey']
        game_events = db.zrangebyscore('events_game:%s' % gamekey,
                                       since, float('+inf'), withscores=True)
    else:
        game_events = []

    # Sort the combined events
    events = user_events + game_events
    events = map(lambda x: x[0], sorted(events, key=lambda k: k[1]))

    # TODO filter events by user visibility
    return [json.loads(_) for _ in events]


def events_for_game(gamekey, since=None):
    # Get all the events for a game
    since = '(' + since if since else '-inf'
    events = db.zrangebyscore('events_game:%s' % gamekey, since, float('+inf'))
    return [json.loads(_) for _ in events]


def queue_user(userkey):
    # Add the user to the queue
    with db.lock('lock:user_status:%s' % userkey, 2):
        db['user_status:%s' % userkey] = json.dumps({'status': 'queued'})
        user_event(userkey, 'queued')
        print 'queued:', userkey

    with db.lock('lock:queue', 2):
        db.zadd('queue', **{userkey:1})

    # Process the queue
    handle_queue()


def user_event(userkey, name, data={}, timestamp=None):
    # Add this user event to the user queue
    if timestamp is None:
        timestamp = time.time()
    timestamp = repr(timestamp)
    event = {'name': name, 'data': data, 'time': timestamp}
    db.zadd('events_user:%s' % userkey, **{json.dumps(event): timestamp})


def user_status(userkey):
    # Return uninvited if they aren't known
    if not db.sismember('invited_userkeys', userkey):
        return {'status':'uninvited'}

    # Preapprove them if they have no status yet
    with db.lock('lock:user_status:%s' % userkey, 2):
        status = db.get('user_status:%s' % userkey)
        if not status:
            # Set the status to 'prequeue'
            status = json.dumps({'status': 'prequeue'})
            db['user_status:%s' % userkey] = status

            # Add 'prequeue' to the event
            user_event(userkey, 'prequeue')
        status = json.loads(status)
    return status


def handle_queue():
    # Can we break three people into a group?
    # Does anyone need to be refreshed
    while 1:
        with db.lock('lock:queue', 2):
            if db.zcard('queue') < 3:
                return
            users = db.zrange('queue', 0, 2)
            db.zremrangebyrank('queue', 0, 2)

        # Create a fresh game
        game = Game(users=users)
        game.commit_events()
        game.commit_state()
        state = bunch.bunchify(game.state)

        # Update user status with their role and gamekey
        buyer = state.buyer.userkey
        seller = state.seller.userkey
        insurer = state.insurer.userkey

        db['user_status:%s'%buyer] = json.dumps({'status': 'playing',
                                                 'gamekey': state.gamekey,
                                                 'role': 'buyer'})
        db['user_status:%s'%seller] = json.dumps({'status': 'playing',
                                                  'gamekey': state.gamekey,
                                                  'role': 'seller'})
        db['user_status:%s'%insurer] = json.dumps({'status': 'playing',
                                                   'gamekey': state.gamekey,
                                                   'role': 'insurer'})


class Game(object):
    def __init__(self, state=None, users=None):
        self.state = state
        self.events = []
        if not state:
            # Randomly select game condition
            condition = random.choice([1,2,3])

            # Initialize the game
            random.shuffle(users)
            buyer, seller, insurer = users
            self.state = {'buyer': {'userkey': buyer,
                                    'items':
                                    {'money': 0.25, 'tokens': 0}},
                          'seller': {'userkey': seller,
                                     'items':
                                     {'money': 0.25, 'tokens': 1}},
                          'insurer': {'userkey': insurer,
                                      'items':
                                      {'money': 0.25, 'tokens': 0}},
                          'gamekey': random_userkey(),
                          'condition': condition,
                                      }
            # Game start event
            self.event('gamestart')

            # User info events
            user_event(buyer, 'gamestart', {'role': 'buyer',
                                            'condition': condition})
            user_event(seller, 'gamestart', {'role': 'seller',
                                             'condition': condition})
            user_event(insurer, 'gamestart', {'role': 'insurer',
                                              'condition': condition})

    def commit_state(self):
        gamekey = self.state['gamekey']
        db['game:%s'%gamekey] = self.state

    def commit_events(self):
        # Store any new events in the db, and clear the events
        for event in self.events:
            gamekey = self.state['gamekey']
            e = {json.dumps(event): repr(event['time'])}
        self.events = []

    def event(self, name, data={}):
        self.events.append({'name':name, 'data': data, 'time': time.time()})


class Condition1(Game):
    # Dispute resolver (insurer can take Escrow agent
    pass


class Condition2(Game):
    pass


class Condition3(Game):
    pass
