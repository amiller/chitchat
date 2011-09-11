require(["/js/jquery-1.6.2.min.js", "game", "net"], jQueryInit);


/* Finishes the game and sends the user to the end page */
function endGame()
{
    game.end();
    addNotification('Game over! Thanks for playing.');
    window.localStorage['wallet'] = game.wallet;
    window.localStorage['urlid'] = events.urlid;
    
    $('#timer').css('background-color', '#CD2626');
    $('#timer').effect('highlightnobgchange', {}, 1000);
    
    events.addEvent('EndGame', {'wallet': game.wallet});
    // Send anything left in the queue
    events.sendQueue('/end.htm');
}

function jQueryInit()
{
    try {
        window.localStorage.test = 'TEST123';
        if (!window.localStorage.test == 'TEST123') {
            throw("No local storage");
        }
    } catch (e) {
        alert("HTML5 local storage isn't supported in your browser. This game won't work.");
        return;
    }
    
    events = require('net');
     
    require(["/js/jquery-ui-1.8.14.min.js", "/js/jquery.tmpl.min.js", "/js/jConf-1.2.0.js"], function ()
    {
        $.get('/js/templates/transaction.htm', {}, function (data) {
            $.template('transaction', data);
            // Initial transaction
            addTransaction({
                description: 'Began game.',
                net: 0.0,
                balance: game.wallet
            });
        });
                        
        game.bind('AchievementUnlocked', function(m) {
            if (m.name.substring(0,4) == 'Cash')
            {
                var amount = m.name.substring(4);
                addAchievement('Reached <span class="money">$' + currency(new Number(amount)) +
                               '</span> in your wallet!');
            }
        });
        // Setup the timer
        setTimer(_timeLeft);
        var timer = setInterval(function() {
            if (_timeLeft <= 0) {
                clearInterval(timer);
                endGame();
            }
            
            setTimer(_timeLeft--);
        }, 1000);
            
        // Send a "began game" event to the server
        events.addEvent("Began game", {});
    });
    
    $(window).unload(function ()
    {
        game.save();
    });
}