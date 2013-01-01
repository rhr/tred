import re, shlex

# max upload file size (I think this is 5 megs)
BUFSIZE = 1024*5000

NEXUS_TRANSPAT = re.compile(r'\btranslate\s+([^;]+);',
                            re.IGNORECASE | re.MULTILINE)
NEXUS_TREEPAT = re.compile(r'\btree\s+([_.\w]+)\s*=[^(]+(\([^;]+;)',
                           re.IGNORECASE | re.MULTILINE)

def get_trees_from_nexus(infile):
    s = infile.read(BUFSIZE)
    ttable = NEXUS_TRANSPAT.findall(s) or None
    if ttable:
        items = [ shlex.split(line) for line in ttable[0].split(",") ]
        ttable = dict([ (k, v.replace(" ", "_")) for k, v in items ])
    trees = NEXUS_TREEPAT.findall(s)
    for i, t in enumerate(trees):
        t = list(t)
        if ttable:
            t[1] = "".join(
                [ ttable.get(x, "_".join(x.split()).replace("'", ""))
                  for x in shlex.shlex(t[1]) ]
                )
        trees[i] = t
    return trees

NEWICKPAT = re.compile(r'(\([^;]+;)', re.IGNORECASE | re.MULTILINE)

def extract_newicks_from_buffer(buf):
    #lines = [ x for x in s.split("\n") if not x.strip().startswith("#") ]
    v = get_trees_from_nexus(buf)
    if not v:
        buf.seek(0)
        v = [ ("tree_%s" % i, x)
              for i, x in enumerate(NEWICKPAT.findall(buf.read(BUFSIZE))) ]
    if len(v) > 10:
        v = v[:10]
    return v

if __name__ == "__main__":
    from cStringIO import StringIO
    buf = StringIO("""
(a,(b,(c,(d,(e,f)))));
(a,(b,(c,(d,(e,f)))));
(a,(b,(c,(d,(e,f)))));
    """)
    #buf = file("/home/rree/src/som/apg20020928.nex")
    buf = file("/home/rree/Projects/corydalis-phylogeny/2009-Apr/combined/combined.garli.run00.boot.tre")
    v = extract_newicks_from_buffer(buf)
    print v
