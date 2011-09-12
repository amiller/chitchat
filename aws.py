#!/usr/bin/env python

# Import libraries
import time
import hmac
import sha
import base64
import urllib
import xml.dom.minidom

# Define constants
SANDBOX = True

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


def get_assignments(hit):
    results_xml = request('GetAssignmentsForHIT',
                          HITId=hit,
                          AssignmentStatus='Submitted',
                          PageSize=100)
    return results_xml.toxml()


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

#print get_balance()
print get_assignments(get_first_hit_id())


def main():
    # Every so often, poll
    while 1:
        time.sleep(10000)  # Ten seconds

        # Grab a list of all completed assignments with turkid
        # Grab a list of all the already-sent turkid tokens
        # For each assignment, if it's not in the turkid list:
        #   then send them a worker notification including the url
        #   update the redis so that we know they're available
