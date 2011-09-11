import os
import hashlib

# Let this db get set by the main caller
db = None

games = []


# Call this when we receive a new qualification from mechanical turk
def add_invite():
    invite = hashlib.sha256(os.urandom(20)).hexdigest()[:10]
    db.sadd('invited_tokens', invite)
    return invite
