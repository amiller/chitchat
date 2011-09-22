#!/usr/bin/env python

# Import libraries
import time
import hmac
import sha
import base64
import urllib
import xml.dom.minidom
import game
import json

# Define constants
REDIS_PORT = 9201
game.setup_redis(REDIS_PORT)

SANDBOX = False
if SANDBOX:
    HITTYPEID = "2XLNTL0XULRGRMCPCTDD05FP7PLO2I"
else:
    HITTYPEID = "2R59KSSZVXX2UX603RHO2GNIWBF4M9"

from aws_credentials import AWS_ACCESS_KEY_ID
from aws_credentials import AWS_SECRET_ACCESS_KEY
SERVICE_NAME = 'AWSMechanicalTurkRequester'
SERVICE_VERSION = '2008-08-02'


# Define authentication routines
def generate_timestamp(gmtime):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", gmtime)


def generate_signature(service, operation, timestamp, secret_access_key):
    my_sha_hmac = hmac.new(secret_access_key,
                           service + operation + timestamp, sha)
    my_b64_hmac_digest = base64.encodestring(my_sha_hmac.digest()).strip()
    return my_b64_hmac_digest


# Make the request

def request(operation, **kwargs):
    url = 'http://mechanicalturk.amazonaws.com/onca/xml?'
    if SANDBOX:
        url = 'http://mechanicalturk.sandbox.amazonaws.com/onca/xml?'

    # Calculate the request authentication parameters
    timestamp = generate_timestamp(time.gmtime())
    signature = generate_signature('AWSMechanicalTurkRequester',
                                   operation, timestamp, AWS_SECRET_ACCESS_KEY)

    # Construct the request
    parameters = {
        'Service': SERVICE_NAME,
        'Version': SERVICE_VERSION,
        'AWSAccessKeyId': AWS_ACCESS_KEY_ID,
        'Timestamp': timestamp,
        'Signature': signature,
        'Operation': operation,
    }
    parameters.update(kwargs)

    result_xmlstr = urllib.urlopen(url, urllib.urlencode(parameters)).read()
    result_xml = xml.dom.minidom.parseString(result_xmlstr)

    # Check for and print results and errors
    errors_nodes = result_xml.getElementsByTagName('Errors')
    if errors_nodes:
        print 'There was an error processing your request:'
        for errors_node in errors_nodes:
            for error_node in errors_node.getElementsByTagName('Error'):
                print '  Error code:    ' + error_node.getElementsByTagName('Code')[0].childNodes[0].data
                print '  Error message: ' + error_node.getElementsByTagName('Message')[0].childNodes[0].data

    return result_xml


def get_balance():
    result_xml = request('GetAccountBalance')
    availbalance_nodes = result_xml.getElementsByTagName('AvailableBalance')
    if availbalance_nodes:
        print "Available balance: " + availbalance_nodes[0].getElementsByTagName('FormattedPrice')[0].childNodes[0].data


def extend_time(hit, time=3600):
    request('ExtendHIT', HITId=hit, ExpirationIncrementInSeconds=time)


def extend_assignments(hit, count=3):
    result_xml = request('ExtendHIT', HITId=hit, MaxAssignmentsIncrement=count)
    return result_xml.toxml()


def force_expire(hit):
    request('ForceExpireHIT', HITId=hit)


def get_first_hit_id():
    results_xml = request('SearchHITs', SortDirection='Descending')
    print results_xml.toxml()
    return results_xml.getElementsByTagName('HITId')[0].childNodes[0].data


def get_all_hitids():
    results_xml = request('SearchHITs', SortDirection='Descending')
    hitids = []
    for hit in results_xml.getElementsByTagName('HIT'):
        hitid = hit.getElementsByTagName('HITId')[0].childNodes[0].data
        #hittypeid = hit.getElementsByTagName('HITTypeId')[0].childNodes[0].data
        title = hit.getElementsByTagName('Title')[0].childNodes[0].data
        if title == 'Peer-to-Peer Trading Game':
            hitids.append(hitid)
    return hitids


def notify_worker(workerid, invite):
    url = 'http://studyvj9ht.vps.soc1024.com/%s/' % invite
    results_xml = request('NotifyWorkers',
                          Subject='[Research Study] Peer-to-Peer Trading Game URL invitation',
                          MessageText="""You are receiving this notification because you have completed the pre-questionnaire for the Peer-to-Peer Trading Game assignment on Mechanical Turk.

In order to finish the assignment, please visit the following URL and play the game: %s
You must go to this url within the next hour, that is in between 5:00pm-6:00pm EDT (2:30am and 3:30pm IST)

The game will take exactly 7 minutes, but you may have to wait for (no longer than) 10 minutes for other players to join.

This game is part of research conducted by the University of Central Florida. For more information about this study, go here: https://s3.amazonaws.com/ucfuserstudy/tradeconsentform.doc""" % url,
                          WorkerId=workerid)
    print results_xml.toxml()


def grant_bonus(workerid, assid, amount=0.50, reason='Thanks!'):
    d = {'Reward.1.Amount':str(amount), 'Reward.1.CurrencyCode':'USD'}
    result = request('GrantBonus',
                     WorkerId=workerid,
                     AssignmentId=assid,
                     Reason=reason,
                     **d)
    print result.toxml()


def get_assignments():
    for hitid in get_all_hitids():
        results_xml = request('GetAssignmentsForHIT',
                              HITId=hitid,
                              AssignmentStatus='Submitted',
                              PageSize=100) 
        assignments = results_xml.getElementsByTagName('Assignment')
        for ass in assignments:
            # TODO Check that the assignment is legit?
            workerid = ass.getElementsByTagName('WorkerId')[0].childNodes[0].data
            answer = ass.getElementsByTagName('Answer')[0].childNodes[0].data
            result_xml = xml.dom.minidom.parseString(answer)
            answers = result_xml.getElementsByTagName('Answer')
            d = {}
            for ans in answers:
                tag = ans.getElementsByTagName('QuestionIdentifier')[0].childNodes[0].data
                try:
                    answer = ans.getElementsByTagName('FreeText')[0].childNodes[0].data
                except IndexError:
                    answer = ''
                d[tag] = answer
            d = json.dumps(d)
            game.db.hset('presurvey', workerid, d)


def do_bonuses():
    for hitid in get_all_hitids():
        results_xml = request('GetAssignmentsForHIT',
                              HITId=hitid,
                              PageSize=100)
        assignments = results_xml.getElementsByTagName('Assignment')
        for ass in assignments:
            # TODO Check that the assignment is legit?
            workerid = ass.getElementsByTagName('WorkerId')[0].childNodes[0].data
            assid = ass.getElementsByTagName('AssignmentId')[0].childNodes[0].data
            code = game.db.hget('notified_workers', workerid)
            status = game.db.get('user_status:%s' % code)
            bonus_text = """
            Thank you for taking part in our study. In the game you played,
            there was a deliberate problem where the buyer wouldn't get the
            token even if the seller sent it. This was so we could collect
            data about the techniques and language used during a disagreement.
            
            So, regardless of the outcome of your game, all parties get the
            50 cent bonus.

            Thank you again for participating.
            Andrew Miller, University of Central Florida
            amiller@cs.ucf.edu
            """
            if status and 'gameover' in status and not workerid in ('AIQ1I6ODSIO56', 'A3GPGSHQY2JGPY'):
                print workerid, assid
                #grant_bonus(workerid, assid, 0.5, bonus_text)


def get_all_assignments():
    # Grab a list of all completed assignments with turkid
    # Grab a list of all the already-sent turkid tokens
    # For each assignment, if it's not in the turkid list:
    #   then send them a worker notification including the url
    #   update the redis so that we know they're available
    for hitid in get_all_hitids():
        results_xml = request('GetAssignmentsForHIT',
                          HITId=hitid,
                          AssignmentStatus='Submitted',
                          PageSize=100)
        assignments = results_xml.getElementsByTagName('Assignment')
        for ass in assignments:
            # TODO Check that the assignment is legit?
            workerid = ass.getElementsByTagName('WorkerId')[0].childNodes[0].data
            if not game.db.hexists('notified_workers', workerid):
                print 'workerid:', workerid, ' has not yet been notified'
                invite = game.add_invite()
                notify_worker(workerid, invite)
                game.db.hset('notified_workers', workerid, invite)


def main():
    # Every so often, poll
    while 1:
        print 'polling:', time.time()
        get_all_assignments()
        time.sleep(10)  # Ten seconds

if __name__ == '__main__':
    main()
