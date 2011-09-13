require(["/js/jquery-1.6.2.min.js", "net"], jQueryInit);

var status = null;
var role = null;
var userkey = (/\/([a-f0-9]+)\//).exec(window.location.pathname)[1];
console.info('userkey:' + userkey)

function jQueryInit()
{
    // Bind to events from the server
    events = require('net');

    events.bind('server', function(event) {
        $('#eventlog').append(JSON.stringify(event));
    })

    events.bind('server:prequeue', function (data) {
        // Show the 'accept' message
    })

    events.bind('server:queued', function (data) {
        // Hide the accept message if it's still shown
        // Show the 'waiting for people' information
        // Show the countdown timer
    })

    events.bind('server:gamestart', function (data) {
        role = data.role;
    })

    events.poll();
    
    $('#approve').click(function() {
        events.addEvent('approve');
        // Hide the "Accept" message
    })
    
    require(["/js/jquery-ui-1.8.14.min.js", "/js/jquery.tmpl.min.js", "/js/jConf-1.2.0.js"], function ()
    {
        // Start polling only when we have all the templates
            
        // Send a "began game" event to the server
    });
    
    $(window).unload(function ()
    {
        confirm("Are you sure you want to quit");
    });
}