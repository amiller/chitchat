define(["/js/jquery-ui-1.8.14.min.js", "/js/microevent.js"], function()
{
    /**
     * These are custom to the particular server configuration. Change them as needed
     */
    var url_regex = /\/([a-f0-9]+)\//;

    /**
     * This class keeps a queue of events that need to be sent to the server.
     * The queue of events gets sent when the queue reaches `max_queue` events,
     * or if `max_seconds` passes, whichever comes first. This is to cut down on
     * server load and for clients where internets is terrible.
     */
    function EventManager()
    {
        this.queue = [];
        this._queue = [];
        this.urlid = null;
        
        this.max_queue = 1;
        this.max_seconds = 30; // Every 30 seconds
        
        /* Make sure we have a URL ID */
        var uri = window.location.pathname;
        if (window.location.pathname != window.parent.location.pathname)
            uri = window.parent.location.pathname;
        
        var match = url_regex.exec(uri)
        if (match != null)
            this.urlid = match[1];
        else
            return;

        var self = this;
        this.timer = setTimeout(function () { 
            self.sendQueue(); 
        }, this.max_seconds * 1000);

        this.polltimer = null;
        this.pollXHR = null;
        this.since = null;
        this.aborting = false;

        this.polldone = false;
        this.senddone= false;
    }

    EventManager.prototype.poll = function() {
        data = {};
        if (this.since) data.since = this.since;

        var self = this;

        this.pollXHR = $.ajax({
            url: '/events/' + this.urlid + '/',
            type: 'post',
            data: data,
            //timeout: 10000,  // 10 second timeout
            success: function (events) {
                for (var i in events) {
                    var event = events[i];
                    self.trigger('server:' + event.name, event.data); 
                    self.trigger('server', event);
                    if (event.name == 'time') return;
                    self.since = event.time;
                }
            },
            error: function (xhr, status, error) {
                if (status != 'timeout')
                    if (typeof console != undefined)
                        console.error('poll: ' + status);
            },
            complete: function (xhr, reason) {
                if (self.aborting) {
                    self.polldone = true;
                    self.finish();
                    return;
                }

                // Go around again right away
                clearTimeout(self.polltimer);
                self.polltimer = setTimeout(function() {
                    self.poll();
                }, 2000)
            }
        })
    }

    EventManager.prototype.abort = function () {
        this.aborting = true;
        this.finish = function () {
            if (this.senddone && this.polldone) {

            }
        }
        clearTimeout(this.polltimer);
        clearTimeout(this.timer);
    }

    EventManager.prototype.sendQueue = function(redirect)
    {
        if (this.urlid == null) {
            return false;
        }
        
        if (this.queue.length == 0) {
            return false;
        }

        if (this.xhr) {
            return false;
        }
        
        // Copy the queue to a temporary one, so if the request fails, we can
        // re-add them to the queue.
        this._queue = this.queue.slice();
        this.queue = [];
        
        var events = this;
        
        var data = {'events': JSON.stringify(this._queue)};
        
        this.xhr = jQuery.post('/post/'+this.urlid+'/', data, function()
            {
                clearTimeout(events.timer);
                
                if (redirect)
                    do_redirect();
                else
                    events.timer = setTimeout(function () { events.sendQueue() },
                        events.max_seconds * 1000);
            })
        .error(function()
            {
                // Prepend _queue to queue
                events._queue.concat(events.queue);
                events.queue = events._queue;
                events._queue = [];
            })
        .complete(function()
            {
                events.xhr = null;
                events.sendQueue();
            })
        
        return true;
    }
    
    EventManager.prototype.addEvent = function(name, data)
    {
        if (this.urlid == null)
            return false;
        
        this.queue.push({
            'name': name,
            'data': data,
            'time': parseInt(new Date().getTime() / 1000)
        });
        
        if (this.queue.length >= this.max_queue)
            this.sendQueue();
        
        return true;
    }

    MicroEvent.mixin(EventManager);
    var events = new EventManager();
    return events;
});