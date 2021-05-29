# natinal

**N**ot  
**A**nother  
**T**wit  
**I**ssuing  
**N**otifications  
**A**bout the  
**L**ineups!<sup><a href="#footnote1">1</a></sup>

(c) 2016-21 J. W. Crockett, Jr.<sup><a href="#footnote2">2</a></sup>, [@joshcvt](http://twitter.com/joshcvt)

**natinal** is a Python 3.9 script to monitor MLB.com live gameday data feeds.  Run as a cron job, it relays certain gameday events and highlight video links to a configured set of services.

**Background**: I'm part of a long-running private chat that formed around the [Washington Nationals](http://nationals.com) during their inaugural season, which now lives on Slack.  **natinal** was created first to provide that chat links to downloadable video highlights, rather than us having to sniff JSON on MLB.com directly.  It quickly grew the ability to provide us morning announcements of the day's probables, lineup announcements and probables updates, broadcast info, and final score/standings/magic number (when relevant) announcements postgame via a [Slack webhook](https://api.slack.com/incoming-webhooks) helpfully named `natinal_bot`.  This instance runs as a cron job on a Raspberry Pi with minimal trouble as long as the power stays on.

**natinal** is invoked by `caller.py` in the root directory, and requires read/write access to the location where `persistDict` is to be stored, as configured in `config.ini`.<a href="#footnote3"><sup>3</sup></a>  To add a new service notifier, create a new class in `notifier` inheriting from `NotifierClass.Notifier` (`notifier.__init__` will automatically import it), build an appropriate section in `config.ini`, and add the section header to the `notifiers` values.  The notifier class is itself responsible for deciding which updates are appropriate for its service, possibly with help from inputs in the config file -- see `notifiers/SlackNotifier.py`.

The base application and the console and Slack notifiers can run using only the Python 2 standard libraries.  Notifiers that use Twitter (starting with  `notifiers/TFFPNotifier.py`, which tweets a hashtag after (a) a win (b) that leaves the team in first place in its division) require [python-twitter](https://github.com/bear/python-twitter), as frozen in the PIP requirements.txt.  If you have no need for Twitter, you can ignore these packages and the import for that notifier class will fail non-disruptively.

**natinal** has spawned one child project:
* [resetter](https://github.com/joshcvt/resetter/) is a Slackbot built using Chalice to let us fetch game resets, when Command-Tabbing over to the MLB.com browser window is just too much work to get a score check.

----
<a name="footnote1"/>1. Yes, the acronym's a terrible stretch. ref: http://www.uni-watch.com/2009/04/18/natinal-joke/, and 
the daily race of Nationals beat writers for who tweets the starting lineup first.

<a name="footnote2"/>2. Please note http://gdx.mlb.com/components/copyright.txt, which covers the data sources owned by MLB Advanced Media, L.P. ("MLBAM") that this application consumes. The developer of this application claims no rights to or control over these sources or the data contained within. Users of this application are themselves solely responsible for assuring that their use of this application, the sources and the data contained within complies with any and all terms and conditions set by MLBAM.</small>

<a name="footnote3"/>3. Refactoring to adhere to modern Python packaging standards is [an issue](https://github.com/joshcvt/natinal/issues/1), but not high-priority.
