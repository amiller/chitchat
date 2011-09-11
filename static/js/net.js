define(["/js/jquery-ui-1.8.14.min.js"], function()
{
    /**
     * This class keeps a queue of events that need to be sent to the server.
     * The queue of events gets sent when the queue reaches `max_queue` events,
     * or if `max_seconds` passes, whichever comes first. This is to cut down on
     * server load and for clients where internets is terrible.
     */
    function EventPoster()
    {
        this.queue = [];
        this._queue = [];
        this.urlid = null;
        
        this.max_queue = 20;
        this.max_seconds = 30; // Every 30 seconds
        
        /* Make sure we have a URL ID */
        var rgx = /\/play\/([a-f0-9]+)\//;
        var uri = window.location.pathname;
        if (window.location.pathname != window.parent.location.pathname)
            uri = window.parent.location.pathname;
        
        var match = rgx.exec(uri)
        if (match != null)
            this.urlid = match[1];
        else
            return;

        var self = this;
        this.timer = setTimeout(function () { 
            self.sendQueue(); 
        }, this.max_seconds * 1000);
    }
    
    EventPoster.prototype.sendQueue = function(redirect)
    {
        function do_redirect() {
            setTimeout(function()
                       {
                           if (window.location.href != window.parent.location.href)
                               window.parent.location.href = redirect;
                           else
                               window.location.href = redirect;
                       }, 5*1000);
        }

        if (this.urlid == null) {
            if (redirect) do_redirect();
            return false;
        }
        
        if (this.queue.length == 0) {
            if (redirect) do_redirect();
            return false;
        }
        
        // Copy the queue to a temporary one, so if the request fails, we can
        // re-add them to the queue.
        this._queue = this.queue.slice();
        this.queue = [];
        
        var events = this;
        
        var data = {
            'events': JSON.stringify(this._queue),
            'id': this.urlid
        };
        
        jQuery.post('/post/', data, function()
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
            });
        
        return true;
    }
    
    EventPoster.prototype.addEvent = function(name, data)
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
    
    var poster = new EventPoster();
    return poster;
});