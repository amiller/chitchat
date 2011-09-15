require(["/js/jquery-1.6.2.min.js", "net"], jQueryInit);

var game_started = false;
var start_time = 0;
var queued = false;
var seller_got_money = false;

var status = null;
var condition = null;
var role = null;
var matches = (/\/([a-f0-9]+)\//).exec(window.location.pathname);
var userkey = '0';
if (matches != null)
  userkey = matches[1];

var tmpl_instructions = null;

String.prototype.capitalize = function() {
    return this.charAt(0).toUpperCase() + this.slice(1);
}

function resetProfileNames()
{
    var profiles = ['buyer', 'insurer', 'seller'];
    var names = ['Buyer', 'Mediator', 'Seller'];
    for (i in profiles)
        $('#' + profiles[i] + '_profile .profilename').html(names[i]);
}

function handleButton(evtname)
{
    return function(evt) {
        if ($(this).hasClass('pressed') || $(this).hasClass('notyours'))
            return false;
        
        var buttons = $(this);
        $(this).jConf({
            sText: $(this).prev('.button_explanation').html(),
            okBtn: 'Okay',
            noBtn: 'Cancel',
            evt: evt,
            callResult: function(data) {
                if (data.btnVal == 'Okay')
                {
                    events.addEvent(evtname, {});
                    setButtonPressed(buttons)
                }
            }
        });
        
    }
}

function setToken(role, state)
{
    var name = {'no': 'no_token', 'has': 'has_token', 'missing': 'token_missing'}[state];
    $('#' + role + '_token').removeClass('no_token has_token token_missing').addClass(name);
}

function setCurrentProfile(role)
{
    var matches = $('#' + role + '_profile');
    if (matches.length != 1)
        return;
    
    resetProfileNames();
    matches.find('span.profilename').html('You');
    matches.effect('highlight', {}, 750);
    
    if (role == 'buyer')
        $('#seller_chatbox').addClass('disabled');
    else if (role == 'seller')
        $('#buyer_chatbox').addClass('disabled');
    
    $('button').addClass('notyours').unbind('click');
    $('button.' + role).removeClass('notyours').addClass('yours');
    
    $('#instructions_role .title').addClass(role);
    $('#instructions_role').addClass(role).slideDown();
    
    setToken('buyer', 'no');
    setToken('seller', 'has');
        
    switch (role)
    {
    case 'buyer':
        $('#buyer_chatinput').removeAttr('disabled');
        $('#buyer_send_seller').bind('click', handleButton('send_money_buyer_seller'));
        $('#buyer_send_insurer').bind('click', handleButton('send_money_buyer_insurer'));
        $('.profilebox .profiletokenlink').addClass('pointer');
        
        $('#chat_info_buyer_insurer').css('display', 'block');
        break;
    
    case 'seller':
        $('#seller_chatinput').removeAttr('disabled');
        $('#seller_send_insurer').bind('click', handleButton('send_money_seller_insurer'));
        $('.profilebox.buyer .profiletokenlink').addClass('pointer');
        $('#seller_send_buyer').bind('click', function (evt) {
            if ($('#seller_token').hasClass('has_token'))
            {
                if (!seller_got_money)
                    $(this).jConf({
                        sText: 'You must wait until the buyer sends you money.',
                        okBtn: 'Okay',
                        evt: evt
                    });
                
                $(this).jConf({
                    sText: $(this).prev('.button_explanation').html(),
                    okBtn: 'Okay',
                    noBtn: 'Cancel',
                    evt: evt,
                    callResult: function(data) {
                        if (data.btnVal == 'Okay')
                            events.addEvent('send_token', {});
                    }
                });
            }
        })
        $('#chat_info_seller_insurer').css('display', 'block');
        break;
    
    case 'insurer':
        $('.chatinput').removeAttr('disabled');
        $('#insurer_send_buyer').bind('click', handleButton('send_money_insurer_buyer'));
        $('#insurer_take_buyer').bind('click', handleButton('send_money_buyer_insurer'));
        $('#insurer_send_seller').bind('click', handleButton('send_money_insurer_seller'));
        $('#insurer_take_seller').bind('click', handleButton('send_money_seller_insurer'));
        $('.profilebox .profiletokenlink').addClass('pointer');
        
        $('#seller_token_info').css('display', 'block');
        $('#chat_info_insurer_buyer').css('display', 'block');
        $('#chat_info_insurer_seller').css('display', 'block');
        break;
    }
}

function setButtonPressed(buttons)
{
    buttons.each(function (k, button) {
        var what = '25&cent;';
        if (button.id == 'seller_send_buyer')
            what = 'Token';
        
        button = $(button);
        button.addClass('pressed');
        
        if (button.hasClass('button_give'))
            button.find('span.action').html(what + ' Given');
        else if (button.hasClass('button_take'))
            button.find('span.action').html(what + ' Taken');
    });
}

function setTimer(seconds)
{
    var str_sec = '' + (seconds % 60);
    if (str_sec.length == 1)
        str_sec = '0' + str_sec;
    
    $('#timer').html(parseInt(seconds / 60) + ':' + str_sec);
}

function setCurrentWait(sec_diff)
{
    if (!queued)
        window.timeleft = 0;
    else if (game_started)
        window.timeleft = 5*60 - sec_diff;
    else
        window.timeleft = 15*60 - sec_diff;
    setTimer(window.timeleft);
}

wallets = {
    buyer: 0.25,
    seller: 0.25,
    insurer: 0.25,
};
function setWallet(role, amount)
{
    if (wallets[role] == undefined)
        wallets[role] = 0.0;
    
    wallets[role] += amount;
    $('#' + role + '_profile .profilewallet').html('$' + wallets[role].toFixed(2))
        .effect('highlight', 1000);
    
    if (wallets[role] == 0)
        $('button.' + role + '.yours:not(.pressed):not(.disabled)').addClass('notyours').removeClass('yours');
    else
        $('button.' + role + ':not(.pressed):not(.disabled)').removeClass('notyours').addClass('yours');
}

function jQueryInit()
{
    (function($){
      var ph = "PLACEHOLDER-INPUT";
      var phl = "PLACEHOLDER-LABEL";
      var boundEvents = false;
      var default_options = {
        labelClass: 'placeholder'
      };
      
      //check for native support for placeholder attribute, if so stub methods and return
      var input = document.createElement("input");
      if ('placeholder' in input) {
        $.fn.placeholder = $.fn.unplaceholder = function(){}; //empty function
        delete input; //cleanup IE memory
        return;
      };
      delete input;

      $.fn.placeholder = function(options) {
        bindEvents();

        var opts = $.extend(default_options, options)

        this.each(function(){
          var rnd=Math.random().toString(32).replace(/\./,'')
            ,input=$(this)
            ,label=$('<label style="position:absolute;display:none;top:0;left:0;"></label>');

          if (!input.attr('placeholder') || input.data(ph) === ph) return; //already watermarked

          //make sure the input tag has an ID assigned, if not, assign one.
          if (!input.attr('id')) input.attr('id') = 'input_' + rnd;

          label	.attr('id',input.attr('id') + "_placeholder")
              .data(ph, '#' + input.attr('id'))	//reference to the input tag
              .attr('for',input.attr('id'))
              .addClass(opts.labelClass)
              .addClass(opts.labelClass + '-for-' + this.tagName.toLowerCase()) //ex: watermark-for-textarea
              .addClass(phl)
              .text(input.attr('placeholder'));

          input
            .data(phl, '#' + label.attr('id'))	//set a reference to the label
            .data(ph,ph)		//set that the field is watermarked
            .addClass(ph)		//add the watermark class
            .after(label);		//add the label field to the page

          //setup overlay
          itemIn.call(this);
          itemOut.call(this);
        });
      };

      $.fn.unplaceholder = function(){
        this.each(function(){
          var	input=$(this),
            label=$(input.data(phl));

          if (input.data(ph) !== ph) return;
            
          label.remove();
          input.removeData(ph).removeData(phl).removeClass(ph);
        });
      };


      function bindEvents() {
        if (boundEvents) return;

        //prepare live bindings if not already done.
        $('.' + ph)
          .live('click',itemIn)
          .live('focusin',itemIn)
          .live('focusout',itemOut);
        bound = true;

        boundEvents = true;
      };

      function itemIn() {
        var input = $(this)
          ,label = $(input.data(phl));

        label.css('display', 'none');
      };

      function itemOut() {
        var that = this;

        //use timeout to let other validators/formatters directly bound to blur/focusout work first
        setTimeout(function(){
          var input = $(that);
          $(input.data(phl))
            .css('top', input.position().top + 'px')
            .css('left', input.position().left + 'px')
            .css('display', !!input.val() ? 'none' : 'block');
        }, 200);
      };

    }(jQuery));

    // Set the UI to the default blanked out state
    $(function() {
        resetProfileNames();
        $('button').addClass('notyours');
    });
    
    // Bind to events from the server
    events = require('net');

    events.bind('server', function(event) {
        if (event.name == 'uninvited' || event.name == 'gameover') {
            events.abort()
            location.href = '/quest/' + userkey + '/';
            return;
        }
        if (event.name == 'overqueued') {
            events.abort()
            location.href = '/overqueued/' + userkey + '/';
            return;
        }

        $('#eventlog').append(JSON.stringify(event));
        
        if (event.name == 'gamestart' && event.data.starttime != undefined)
        {
            start_time = parseInt(event.data.starttime);
            game_started = true;
            setCurrentWait(0);
            
            $('#timer').addClass('gamestart');
            
            function gameTimer()
            {
                if (--window.timeleft <= 0)
                    return;
                else
                    window.timer = window.setTimeout(gameTimer, 1000);
                
                setTimer(window.timeleft);
                if (window.timeleft % 60 == 0)
                    $('#timer').effect('highlight', 750);
            }
            
            clearTimeout(window.timer);
            window.timer = window.setTimeout(gameTimer, 1000);
        }
        else if (event.name == 'time')
            setCurrentWait(parseInt(event.time) - start_time);
        else if (event.name == 'queued')
        {
            start_time = parseInt(event.time);
            queued = true;
            setCurrentWait(0);
            
            function timerFunc()
            {
                if (--window.timeleft <= 0 || game_started)
                    return;
                else
                    window.timer = window.setTimeout(timerFunc, 1000);
                
                setTimer(window.timeleft);
                if (window.timeleft % 60 == 0)
                    $('#timer').effect('highlight', 750);
            }
            
            window.timer = window.setTimeout(timerFunc, 1000);
        }
    });

    events.bind('server:prequeue', function (data) {
        // Show the accept message
    });

    events.bind('server:queued', function (data) {
        // Hide the accept message if it's still shown
        
        $('#waiting_note').css('display', 'block');
        $('#approve_check').attr('checked', 'checked');
    });

    events.bind('server:chat', function (data) {
        msgs = $('#'+data.chatbox+'_chatmessages')
        msgs.append('<div class="message '+data.from+(data.from==role?' yours':'')+'">' + data.message + '</div>')
        msgs.scrollTop(msgs[0].scrollHeight - msgs.height());
    });

    events.bind('server:gamestart', function (data) {
        if (data.role == undefined)
            return;
        
        $('#waiting_note').css('display', 'none');
        
        role = data.role;
        condition = data.condition;
        
        setCurrentProfile(role);
        $('#content').show();
        $('#content').removeClass('disabled').addClass('enabled');
        $('#tmpl_instructions').tmpl(data).appendTo('#instructions_role .body');
        $('#instructions_role .title span').html(role == 'insurer' ? 'Mediator' : role.capitalize());
        
        var buy_info = 'Chat between ' + (role == 'buyer' ? 'you' : 'buyer') +
            ' and ' + (role == 'insurer' ? 'you' : 'mediator') + '.';
        var sell_info = 'Chat between ' + (role == 'seller' ? 'you' : 'seller') +
            ' and ' + (role == 'insurer' ? 'you' : 'mediator') + '.';
        
        $('#buyer_chatinput').attr('placeholder', buy_info);
        $('#seller_chatinput').attr('placeholder', sell_info);
        
        $('.chatinput[placeholder]').placeholder();
        
        switch (condition)
        {
        case 1:
            $('#buyer_send_seller').addClass('disabled');
            $('#seller_send_insurer').addClass('disabled');
            $('#insurer_take_seller').addClass('disabled');
            $('#insurer_take_buyer').addClass('disabled');
            break;
        
        case 2:
            $('#buyer_send_insurer').addClass('disabled');
            $('#insurer_take_seller').addClass('disabled');
            $('#insurer_take_buyer').addClass('disabled');
            
            $('#seller_send_insurer').addClass('notyours').removeClass('yours');
            break;
        
        case 3:
            $('#seller_send_insurer').addClass('disabled');
            $('#buyer_send_insurer').addClass('disabled');
            $('#insurer_take_buyer').addClass('disabled');
            
            $('#insurer_take_seller').addClass('notyours').removeClass('yours');
            break;
        }
    });
    
    events.bind('server:send_money_buyer_seller', function () {
        setButtonPressed($('#buyer_send_seller'));
        setWallet('buyer', -0.25);
        setWallet('seller', 0.25);
        
        seller_got_money = true;
        
        if (condition == 3 && role == 'insurer')
            $('#insurer_take_seller').addClass('yours').removeClass('notyours');
        else if (condition == 2 && role == 'seller')
            $('#seller_send_insurer').addClass('yours').removeClass('notyours');
    });
    
    events.bind('server:send_money_seller_insurer', function () {
        setButtonPressed($('#seller_send_insurer'));
        setWallet('seller', -0.25);
        setWallet('insurer', 0.25);
    });
    
    events.bind('server:send_money_buyer_insurer', function () {
        setButtonPressed($('#buyer_send_insurer'));
        setWallet('buyer', -0.25);
        setWallet('insurer', 0.25);
        
        if (condition == 1)
            seller_got_money = true;
    });
    
    events.bind('server:send_money_insurer_buyer', function () {
        setButtonPressed($('#insurer_send_buyer'));
        setWallet('insurer', -0.25);
        setWallet('buyer', 0.25);
    });
    
    events.bind('server:send_money_insurer_seller', function () {
        setButtonPressed($('#insurer_send_seller'));
        setWallet('insurer', -0.25);
        setWallet('seller', 0.25);
    });
    
    events.bind('server:send_token', function () {
        if (role == 'insurer')
        {
            setToken('buyer', 'missing');
            setToken('seller', 'missing');
        }
        else
        {
            setToken('buyer', 'has');
            setToken('seller', 'no');
        }
        
        if (role == 'seller')
            setButtonPressed($('#seller_send_buyer'))
    });

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
    
    $(function() {
        $('#buyer_chatinput').bind('keydown', keydown('buyer'))
        $('#seller_chatinput').bind('keydown', keydown('seller'))
        
        $('.chatinput').focus(function() {
            if (this.value === this.defaultValue)
                this.value = '';
        })
        .blur(function() {
            if (this.value === '')
                this.value = this.defaultValue;
        });
        
        // Bind to the approve accept button
        $('#approve').click(function() {
            // FIXME Check that the checkbox was selected
            events.addEvent('approve');
            // Hide the "Accept" message
        })
    });
    
    require(["/js/jquery.tmpl.min.js", "/js/jConf-1.2.0.js", "/js/jquery-ui-1.8.14.min.js"], function ()
    {
        // Start polling only when we have all the templates
        events.poll();
    });
    
    $(window).unload(function ()
    {
        // Pass
    });
}