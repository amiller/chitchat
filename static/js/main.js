require(["/js/jquery-1.6.2.min.js", "net"], jQueryInit);

var game_started = false;
var status = null;
var condition = null;
var role = null;
var matches = (/\/([a-f0-9]+)\//).exec(window.location.pathname);
var userkey = '0';
if (matches != null)
  userkey = matches[1];
console.info('userkey:' + userkey)

var tmpl_instructions = null;

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
    var matches = $('#' + person + '_profile');
    if (matches.length != 1)
        return;
    
    resetProfileNames();
    matches.find('span.profilename').html('You');
    matches.effect('highlight', {}, 750);
    
    if (person == 'buyer')
        $('#seller_chatbox').addClass('disabled');
    else if (person == 'seller')
        $('#buyer_chatbox').addClass('disabled');
    
    $('#buyer_token').attr('src', '/img/no_token.png');
    $('#seller_token').attr('src', '/img/token.png');
    
    $('button').addClass('notyours').unbind('click');
    $('button.' + person).removeClass('notyours').addClass('yours');
    
    $('#instructions_role .title').addClass(person);
    $('#instructions_role').addClass(person).slideDown();
}

function setButtonPressed(buttons)
{
    buttons.each(function (k, button) {
        button = $(button);
        button.addClass('pressed');
        
        if (button.hasClass('button_give'))
            button.html('25&cent;<br />Given');
        else if (button.hasClass('button_take'))
            button.html('25&cent;<br />Taken');
    });
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
    resetProfileNames();
    $('button').addClass('notyours');
    
    // Bind to events from the server
    events = require('net');

    events.bind('server', function(event) {
        if (event.name == 'uninvited' || event.name == 'gameover') {
            events.abort()
            return;
        }
        $('#eventlog').append(JSON.stringify(event));
    });

    events.bind('server:prequeue', function (data) {
        // Show the 'accept' message
    });

    events.bind('server:queued', function (data) {
        // Hide the accept message if it's still shown
        // Show the 'waiting for people' information
        // Show the countdown timer
    });

    events.bind('server:chat', function (data) {
        msgs = $('#'+data.chatbox+'_chatmessages')
        msgs.append('<div class="message '+data.from+(data.from==role?' yours':'')+'">' + data.message + '</div>')
        msgs[0].scrollTop = msgs[0].scrollHeight;
    });

    events.bind('server:gamestart', function (data) {
        if (game_started || data.role == undefined)
            return;
        game_started = true;
        
        role = data.role;
        condition = data.condition;
        
        setCurrentProfile(role);
        $('#content').removeClass('disabled').addClass('enabled');
        $('#tmpl_instructions').tmpl(data).appendTo('#instructions_role .body');
        $('#instructions_role .title span').html(role.capitalize());
        
        var buy_info = 'Chat between ' + (role == 'buyer' ? 'you' : 'buyer') +
            ' and ' + (role == 'insurer' ? 'you' : 'insurer') + '.';
        var sell_info = 'Chat between ' + (role == 'seller' ? 'you' : 'seller') +
            ' and ' + (role == 'insurer' ? 'you' : 'insurer') + '.';
        
        $('#buyer_chatinput').attr('placeholder', buy_info);
        $('#seller_chatinput').attr('placeholder', sell_info);
        
        $('.chatinput[placeholder]').placeholder();
        
        switch (role)
        {
        case 'buyer':
            $('#buyer_chatinput').removeAttr('disabled');
            break;
        
        case 'seller':
            $('#seller_chatinput').removeAttr('disabled');
            break;
        
        case 'insurer':
            $('.chatinput').removeAttr('disabled');
            break;
        }
        
    });
    
    events.bind('send_money_buyer_seller', function () {
        setButtonPressed($('#buyer_send_seller'));
    });
    
    events.bind('send_money_seller_insurer', function () {
        setButtonPressed($('#seller_send_insurer'));
    });
    
    events.bind('send_money_buyer_insurer', function () {
        setButtonPressed($('#buyer_send_insurer'));
    });
    
    events.bind('send_money_insurer_buyer', function () {
        setButtonPressed($('#insurer_send_buyer'));
    });
    
    events.bind('send_money_insurer_seller', function () {
        setButtonPressed($('#insurer_send_seller'));
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
    
    require(["/js/jquery-ui-1.8.14.min.js", "/js/jquery.tmpl.min.js", "/js/jConf-1.2.0.js"], function ()
    {
        // Start polling only when we have all the templates

        events.poll();
    });
    
    $(window).unload(function ()
    {
        // Pass
    });
}