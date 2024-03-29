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

QUEUE_TIMELIMIT = 10*60
GAME_TIMELIMIT = 7*60


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
    # Generate a 16 character user string (8 bytes)
    return hashlib.sha256(os.urandom(20)).hexdigest()[:16]


def events_for_user(userkey, since=None):
    # Get all the events visible to the user
    status = user_status(userkey)

    # Bounce if not invited
    if status['status'] == 'uninvited':
        return [{'name': 'uninvited', 'timestamp': repr(time.time())}]

    # Bounce if game is already over or they're queued
    if status['status'] == 'gameover':
        return [{'name': 'gameover', 'timestamp': repr(time.time())}]

    if status['status'] == 'overqueued':
        return [{'name': 'overqueued', 'timestamp': repr(time.time())}]

    # Get all the user events
    since = '(' + since if since else '-inf'
    user_events = db.zrangebyscore('events_user:%s' % userkey,
                                   since, float('+inf'), withscores=True)
    user_events = [(json.loads(k),v) for (k,v) in user_events]

    if status['status'] == 'playing':
        gamekey = status['gamekey']
        game_events = db.zrangebyscore('events_game:%s' % gamekey,
                                       since, float('+inf'), withscores=True)
        game_events = [(json.loads(k),v) for (k,v) in game_events]
        role = status['role']
        game = Game(gamekey)
        game_events = [_ for _ in game_events if game.filter_event(role, _[0])]
    else:
        game_events = []

    # Sort the combined events
    events = user_events + game_events
    events = map(lambda x: x[0], sorted(events, key=lambda k: k[1]))
    return events


def events_for_game(gamekey, since=None):
    # Get all the events for a game
    since = '(' + since if since else '-inf'
    events = db.zrangebyscore('events_game:%s' % gamekey, since, float('+inf'))
    return [json.loads(_) for _ in events]


def queue_user(userkey):
    # Add the user to the queue
    while 1:
        with db.pipeline() as pipe:
            try:
                pipe.watch('user_status:%s' % userkey)
                pipe.watch('queue')

                status = json.loads(pipe['user_status:%s' % userkey])
                if status['status'] != 'prequeue':
                    return

                pipe.multi()
                queuetime = repr(time.time())
                pipe['user_status:%s' % userkey] = \
                                      json.dumps({'status': 'queued',
                                                  'time': queuetime,
                                                  'lastseen': queuetime})
                pipe.zadd('queue', **{userkey: queuetime})
                pipe.execute()
                print 'queued:', userkey
            except redis.WatchError:
                continue
            break

    user_event(userkey, 'queued')
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
    while 1:
        with db.pipeline() as pipe:
            try:
                pipe.watch('user_status:%s' % userkey)
                status = pipe.get('user_status:%s' % userkey)
                if not status:
                    pipe.multi()
                    # Set the status to 'prequeue'
                    status = json.dumps({'status': 'prequeue'})
                    pipe['user_status:%s' % userkey] = status

                    # Add 'prequeue' to the event
                    timestamp = repr(time.time())
                    event = {'name': 'prequeue', 'data': {}, 'time': timestamp}
                    pipe.zadd('events_user:%s' % userkey,
                              **{json.dumps(event): timestamp})

                elif json.loads(status)['status'] == 'playing':
                    pipe.multi()
                    # Timeout the game after 5 minutes
                    if time.time() - float(json.loads(status)['starttime']) > \
                           GAME_TIMELIMIT:
                        role = json.loads(status)['role']
                        status = json.dumps({'status': 'gameover',
                                             'role': role})
                        pipe['user_status:%s' % userkey] = status
                elif json.loads(status)['status'] == 'queued':
                    # Timeout the queue after 15 minutes
                    if time.time() - float(json.loads(status)['time']) > \
                           QUEUE_TIMELIMIT:
                        pipe.watch('queue')
                        pipe.multi()
                        status = json.dumps({'status': 'overqueued'})
                        pipe['user_status:%s' % userkey] = status
                        pipe.zrem('queue', userkey)

                status = json.loads(status)
                pipe.execute()
                return status
            except redis.WatchError:
                continue


def process_user_event(userkey, event):
    status = user_status(userkey)
    if event['name'] == 'approve' and status['status'] == 'prequeue':
        queue_user(userkey)
        return

    if event['name'] == 'unload' and status['status'] == 'queued':
        db.zrem('queue', userkey)
        db['userkey:%s' % userkey] = json.dumps({'status': 'prequeue'})
        return

    # Refresh in the queue
    if event['name'] == 'refresh':
        pass

    if status['status'] == 'playing':
        gamekey = status['gamekey']
        with db.lock('lock:game:%s' % gamekey):
            game = Game(gamekey)
            try:
                game.play_event(status['role'], event)
            except AssertionError, e:
                print 'Event error:', e
            game.commit_state()
            game.commit_events()


def handle_queue():
    # Can we break three people into a group?
    # Does anyone need to be refreshed
    while 1:
        with db.pipeline() as pipe:
            pipe.watch('queue')
            try:
                if pipe.zcard('queue') < 3:
                    return
                users = pipe.zrange('queue', 0, 2)

                pipe.watch('user_status:%s' % users[0])
                pipe.watch('user_status:%s' % users[1])
                pipe.watch('user_status:%s' % users[2])

                hadtobail = False
                for u in users:
                    # Squash the user if he's stale
                    status = json.loads(pipe.get('user_status:%s' % u))
                    diff = time.time() - float(status['lastseen'])
                    if diff > 60:
                        print 'unqueueing a user: %s' % u
                        pipe.multi()
                        pipe['user_status:%s' % u] = \
                                              json.dumps({'status':'prequeue'})
                        pipe.zrem('queue', u)
                        pipe.execute()
                        print 'unqueued'
                        hadtobail = True
                        break
                if hadtobail:
                    print 'skipping queue attempt'
                    continue


                # Create a fresh game
                next_condition = None
                game = Game(users=users, condition=next_condition)
                state = bunch.bunchify(game.state)
                gamekey = state['gamekey']
                pipe.watch('game:%s' % gamekey)

                # Update user status with their role and gamekey
                buyer = state.buyer.userkey
                seller = state.seller.userkey
                insurer = state.insurer.userkey

                pipe.multi()
                pipe.zremrangebyrank('queue', 0, 2)
                pipe['game:%s'%gamekey] = json.dumps(state)

                d = {'status': 'playing',
                     'gamekey': state.gamekey,
                     'starttime': state.starttime}

                d['role'] = 'buyer'
                pipe['user_status:%s'%buyer] = json.dumps(d)
                d['role'] = 'seller'
                pipe['user_status:%s'%seller] = json.dumps(d)
                d['role'] = 'insurer'
                pipe['user_status:%s'%insurer] = json.dumps(d)

                pipe.execute()
            except redis.WatchError:
                continue
            game.commit_events()


class Game(object):
    def __init__(self, gamekey=None, users=None, condition=None):
        self.events = []

        if gamekey:
            self.state = json.loads(db['game:%s' % gamekey])
        else:
            # Randomly select game condition
            if condition is None:
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
                          'starttime': repr(time.time()),
                                      }
            # Game start event
            self.event('gamestart')

            # User info events
            d = {'condition': condition,
                 'starttime': self.state['starttime']}
            d['role'] = 'buyer'; user_event(buyer, 'gamestart', d)
            d['role'] = 'seller'; user_event(seller, 'gamestart', d)
            d['role'] = 'insurer'; user_event(insurer, 'gamestart', d)

    def commit_state(self):
        gamekey = self.state['gamekey']
        db['game:%s'%gamekey] = json.dumps(self.state)

    def commit_events(self):
        # Store any new events in the db, and clear the events
        for event in self.events:
            gamekey = self.state['gamekey']
            e = {json.dumps(event): repr(event['time'])}
            db.zadd('events_game:%s'%gamekey, **e)
        self.events = []

    def event(self, name, data={}):
        self.events.append({'name':name, 'data': data,
                            'time': time.time()})

    def play_event(self, role, event):
        if event['name'] == 'chat':
            message = event['data']['message']
            chatbox = event['data']['chatbox']
            if chatbox == 'buyer':
                assert role in ['insurer', 'buyer'], 'Wrong chat'
            if chatbox == 'seller':
                assert role in ['insurer', 'seller'], 'Wrong chat'
            self.event('chat', {'from': role, 'chatbox': chatbox,
                                'message': message})

        elif event['name'] == 'send_money_insurer_seller':
            # Insurer can send money to the seller anytime
            assert role == 'insurer'
            assert not 'insurer_sent_seller' in self.state
            assert self.state['insurer']['items']['money'] >= 0.25
            self.state['insurer']['items']['money'] -= 0.25
            self.state['insurer_sent_seller'] = True
            self.event(event['name'], event['data'])
        elif event['name'] == 'send_money_insurer_buyer':
            # Insurer can send money to the buyer anytime
            assert role == 'insurer'
            assert not 'insurer_sent_buyer' in self.state
            assert self.state['insurer']['items']['money'] >= 0.25
            self.state['insurer']['items']['money'] -= 0.25
            self.state['insurer_sent_buyer'] = True
            self.event(event['name'], event['data'])
        else:
            # Dispatch to the condition specific logic
            {1:self.escrow_play,
             2:self.guarantor_play,
             3:self.arbitrator_play}[
                self.state['condition']](role, event)

    def escrow_play(self, role, event):
        if event['name'] == 'send_money_buyer_insurer':
            # First the buyer has to send insurer money
            assert role == 'buyer'
            assert not 'buyer_sent' in self.state, 'buyer sends money once'
            self.state['buyer_sent'] = True
        elif event['name'] == 'send_token':
            # Seller can send token to buyer
            assert role == 'seller'
            assert 'buyer_sent' in self.state
            assert not 'token_sent' in self.state
            self.state['token_sent'] = True
        else:
            assert False, 'unexpected event: %s' % event
        self.event(event['name'], event['data'])

    def guarantor_play(self, role, event):
        if event['name'] == 'send_money_buyer_seller':
            # First the buyer has to send the seller money
            assert role == 'buyer'
            assert not 'buyer_sent' in self.state
            self.state['buyer_sent'] = True
        elif event['name'] == 'send_token':
            # Seller can send token to buyer
            assert role == 'seller'
            assert 'buyer_sent' in self.state
            assert not 'token_sent' in self.state
            self.state['token_sent'] = True
        elif event['name'] == 'send_money_seller_insurer':
            # Seller can send money to insurer
            assert role == 'seller'
            assert 'buyer_sent' in self.state
            assert not 'seller_sent' in self.state
            self.state['insurer']['items']['money'] += 0.25
            self.state['seller_sent'] = True
        else:
            assert False, 'unexpected event: %s' % event
        self.event(event['name'], event['data'])

    def arbitrator_play(self, role, event):
        if event['name'] == 'send_money_buyer_seller':
            # First the buyer has to send the seller money
            assert role == 'buyer'
            assert not 'buyer_sent' in self.state
            self.state['buyer_sent'] = True
        elif event['name'] == 'send_token':
            # Seller can send token to buyer
            assert role == 'seller'
            assert 'buyer_sent' in self.state
            assert not 'token_sent' in self.state
            self.state['token_sent'] = True
        elif event['name'] == 'send_money_seller_insurer':
            # Insurer can seize money from seller
            assert role == 'insurer'
            assert 'buyer_sent' in self.state
            assert not 'seller_sent' in self.state
            self.state['insurer']['items']['money'] += 0.25
            self.state['seller_sent'] = True
        else:
            assert False, 'unexpected event: %s' % event
        self.event(event['name'], event['data'])

    def filter_event(self, role, event):
        # Only show the events that each role should see
        if event['name'] == 'chat':
            return (role == 'insurer' or
                    event['data']['chatbox'] == role)

        # Buyer and insurer never see the token sent
        if event['name'] == 'send_token':
            if role == 'buyer': return False

        # Insurer can't see buyer to seller transactions
        #if event['name'] == 'send_money_buyer_seller':
            #if role == 'insurer': return False

        return True
