# natinal

**N**ot
**A**nother
**T**wit
**I**ssuing
**N**otifications
**A**bout the
**L**ineups!

(c) 2016 J. W. Crockett, Jr.

(Yes, the acronym's a terrible stretch. ref: http://www.uni-watch.com/2009/04/18/natinal-joke/, and 
the daily race of Nationals beat writers for who tweets the starting lineup first.)

I'm part of a long-running private chat that formed around the Washington Nationals (no, you may
not have an invitation) and, in the way of most interesting chats, migrated to Slack around 2015.
One of the members is a notorious video-hound, and most of the rest of us at least want to see what's
going on in the current game -- and maybe be reminded each morning of the schedule and probables,
then hear if anything relevant happens between then and first pitch (rain, expected starter scratched
after his pitching arm is severed in a horrifying Metro accident, etc.).

Meanwhile, I had been looking for an excuse to buy and play with a Raspberry Pi, and uBlock Origin had
offered me a view into the nature and volume of requests going back and forth in my MLB.com Gameday 
Audio tab.  A few weeks later, natinal (and his accompanying Slack webhook natinal_bot) was born.

It's started as a simple cron-ready script that only relies on the Python 2 standard library, invoked by
`caller.py`. Adherence to modern Python packaging standards is on hold.  The notifier architecture is 
fairly simple -- if you'd like to add a new service, create a new class in `notifier` inheriting from 
`NotifierClass.Notifier`.  Deciding which status updates are appropriate for the service is the service
notifier class's job.
