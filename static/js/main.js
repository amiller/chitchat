require(["/js/jquery-1.6.2.min.js", "net"], jQueryInit);

var status = null;
var role = null;
var matches = (/\/([a-f0-9]+)\//).exec(window.location.pathname);
var userkey = '0';
if (matches != null)
  userkey = matches[1];
console.info('userkey:' + userkey)

String.prototype.capitalize = function() {
    return this.charAt(0).toUpperCase() + this.slice(1);
}

function resetProfileNames()
{
  var profiles = ['buyer', 'insurer', 'seller'];
  for (i in profiles)
    $('#' + profiles[i] + '_profile .profilename').html(profiles[i].capitalize());
}

function setCurrentProfile(person)
{
  var matches = $('#' + person + '_profile span.profilename');
  if (matches.length != 1)
    return;
  
  resetProfileNames();
  matches.html('You');
  
  $('button').addClass('notyours');
  $('button.' + person).removeClass('notyours').addClass('yours');
}

function jQueryInit()
{
    // Bind to events from the server
    events = require('net');

    events.bind('server', function(event) {
        if (event.status == 'uninvited') {
            events.abort()
            return;
        }
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

    events.bind('server:chat', function (data) {
        msgs = $('#'+data.chatbox+'_chatmessages')
        msgs.append('<div class="message '+data.from+'">' + data.message + '</div>')
        msgs[0].scrollTop = msgs[0].scrollHeight;
    })

    events.bind('server:gamestart', function (data) {
        role = data.role;
    })

    events.poll();

    // Bind to the chat box inputs
    function keydown(role) {
        return function(e) {
            var key = e.which;
            if (key == 13) {
                e.preventDefault();
                events.addEvent('chat', {'message': $(this).val(),
                                         'chatbox': role});
                $(this).val('');
            }
        }
    }
    $('#buyer_chatinput').bind('keydown', keydown('buyer'))
    $('#seller_chatinput').bind('keydown', keydown('seller'))
    
    // Bind to the approve accept button
    $('#approve').click(function() {
        // FIXME Check that the checkbox was selected
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
        // Pass
    });
}