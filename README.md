# natinal

**N**ot  
**A**nother  
**T**wit  
**I**ssuing  
**N**otifications  
**A**bout the  
**L**ineups!<sup><a href="#footnote1">1</a></sup>

(c) 2016 J. W. Crockett, Jr.<sup><a href="#footnote2">2</a></sup>

**natinal** is a Python 2 script to monitor MLB.com live gameday data feeds.  Run as a cron job, it relays certain gameday events and highlight video links to a configured set of services.

**Background**: I'm part of a long-running private chat that formed around the [Washington Nationals](http://nationals.com) (no, you may
not have an invitation) and, in the way of most interesting chats, migrated to Slack around 2015.
One of the members is a notorious video-hound, and most of the rest of us at least want to see what's
going on in the current game -- and maybe be reminded each morning of the schedule and probables,
then hear if anything relevant happens between then and first pitch (rain, expected starter scratched
after his pitching arm is severed in a horrifying Metro accident, etc.).

Meanwhile, I had been looking for an excuse to buy a Raspberry Pi, and [uBlock Origin](https://github.com/gorhill/uBlock) had
offered me a very convenient view into the nature and volume of requests going back and forth in my [MLB.com](http://mlb.com) Gameday 
Audio tab.  A few weeks later, **natinal** was born (as was its accompanying [Slack webhook](https://api.slack.com/incoming-webhooks) natinal_bot).

**natinal** is invoked by `caller.py` in the root directory, and requires read/write access to the location where `persistDict` is to be stored, as configured in `config.ini`.<a href="#footnote3"><sup>3</sup></a>  To add a new service notifier, create a new class in `notifier` inheriting from `NotifierClass.Notifier` (`notifier.__init__` will automatically import it), build an appropriate section in `config.ini`, and add the section header to the `notifiers` values.  The notifier class is itself responsible for deciding which updates are appropriate for its service, possibly with help from inputs in the config file -- see `notifiers/SlackNotifier.py`.

----
<a name="footnote1"/>1. Yes, the acronym's a terrible stretch. ref: http://www.uni-watch.com/2009/04/18/natinal-joke/, and 
the daily race of Nationals beat writers for who tweets the starting lineup first.

<a name="footnote2"/>2. Please note http://gdx.mlb.com/components/copyright.txt, which covers the data sources owned by MLB Advanced Media, L.P. ("MLBAM") that this application consumes. The developer of this application claims no rights to or control over these sources or the data contained within. Users of this application are themselves solely responsible for assuring that their use of this application, the sources and the data contained within complies with any and all terms and conditions set by MLBAM.</small>

<a name="footnote3"/>3. Adherence to modern Python packaging standards is [an issue](#1), but not high-priority.
