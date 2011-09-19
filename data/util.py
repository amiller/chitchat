import redis
import json

class Util(object):
    __slots__ = ['db', 'mturk_users', 'notified_workers', 'games']
    
    def __init__(self, db=None, port=9201):
        if db is None:
            db = redis.Redis(port=port)
        self.db = db
        
        self.refresh_data()
    
    def refresh_data(self):
        '''Grab new data about users and games from the DB'''
        self.notified_workers = self.db.hgetall('notified_workers')
        self.mturk_users = dict(zip(self.notified_workers.values(),
            self.notified_workers.keys()))
        self.games = [self.gamekey(game) for game in self.db.keys('game:*')]
    
    def is_mturk(self, userkey):
        '''Whether a user is from mturk'''
        return userkey in self.mturk_users
    
    def userstate(self, userkey):
        '''Returns the entire user state dict'''
        if not self.db.exists('user_status:' + userkey):
            return None
        return json.loads(self.db['user_status:' + userkey])
    
    def userstatus(self, userkey):
        '''Returns just the user status from their state dict'''
        if not self.db.exists('user_status:' + userkey):
            return None
        state = self.userstate(userkey)
        return state.get('status', None)
    
    def usergameover(self, userkey):
        '''Whether the user has the "gameover" status'''
        return self.userstatus(userkey) == 'gameover'
    
    def get_game_players(self, gamekey):
        '''Returns all the userkeys for the players in a game'''
        if not self.db.exists('game:' + gamekey):
            return []
        
        state = json.loads(self.db['game:' + gamekey])
        return [state[role]['userkey'] for role in ('buyer', 'seller', 'insurer')]
    
    def is_game_mturk(self, gamekey):
        '''Whether a game contains all mturk players'''
        return all(map(self.is_mturk, self.get_game_players(gamekey)))
    
    def gamekey(self, key):
        '''Strips "game:" from a full redis key to produce a gamekey'''
        return key.split(':')[-1]
    
    def gamestate(self, gamekey):
        '''Returns the entire game state dict'''
        if not self.db.exists('game:' + gamekey):
            return None
        return json.loads(self.db['game:' + gamekey])
    
    def gamecond(self, gamekey):
        '''Returns the game condition'''
        if not self.db.exists('game:' + gamekey):
            return None
        return self.gamestate(gamekey)['condition']
    
    def is_game_complete(self, gamekey):
        '''Whether the game is over (all users in gameover state)'''
        return all(map(self.usergameover, self.get_game_players(gamekey)))
    
    def get_completed_games(self):
        '''Returns the gamekeys for all the completed games'''
        return filter(self.is_game_complete, self.games)
    
    def get_completed_mturk_games(self):
        '''Returns the gamekeys for all the completed games'''
        return filter(self.is_game_mturk, filter(self.is_game_complete, self.games))
    
    def get_completed_game_conds(self, mturk=True):
        '''Returns a dict with keys for the condition numbers and a list of
        gamekeys as values'''
        conds = {1: [], 2: [], 3: []}
        games = self.get_completed_mturk_games() if mturk else self.get_completed_games()
        for key,cond in zip(games, map(self.gamecond, games)):
            conds[cond].append(key)
        return conds
    
    def get_completed_game_conds_num(self):
        '''Returns the number of completed games separated into their conds'''
        conds = self.get_completed_game_conds()
        return dict(zip(conds.keys(), map(len, conds.values())))
