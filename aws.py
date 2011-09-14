#!/usr/bin/env python

# Import libraries
import time
import hmac
import sha
import base64
import urllib
import xml.dom.minidom
import game

# Define constants
REDIS_PORT = 9201
game.setup_redis(REDIS_PORT)

SANDBOX = True
if SANDBOX:
    HITTYPEID = "2XLNTL0XULRGRMCPCTDD05FP7PLO2I"
else:
    HITTYPEID = "none"

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
        hittypeid = hit.getElementsByTagName('HITTypeId')[0].childNodes[0].data
        if hittypeid == HITTYPEID:
            hitids.append(hitid)
    return hitids

def notify_worker(workerid, invite):
    url = 'http://studyvj9ht.vps.soc1024.com/%s/' % invite
    results_xml = request('NotifyWorkers',
                          Subject='[Research Study] Peer-to-Peer Trading Game URL invitation',
                          MessageText="""You are receiving this notification because you have completed the pre-questionnaire for the Peer-to-Peer Trading Game assignment on Mechanical Turk.

In order to finish the assignment, please visit the following URL and play the game: %s

The game will take exactly 5 minutes, but you may have to wait for (no longer than) 15 minutes for other players to join.

This game is part of research conducted by the University of Central Florida. For more information about this study, go here: https://s3.amazonaws.com/ucfuserstudy/tradeconsentform.doc""" % url,
                          WorkerId=workerid)
    print results_xml.toxml()


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
