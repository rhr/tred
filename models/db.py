ct = local_import("clienttools")
page = ct.PageManager(globals())
event = ct.EventManager(page)
js = ct.ScriptManager(page) # javascript helpers
jq = ct.JQuery # don't instantiate, just to shorten

page.google_load("jquery", "1.7.2")
