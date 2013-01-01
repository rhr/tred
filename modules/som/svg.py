import newick, layout, svgfig
from pprint import pprint

def getsize(fig, w, h):
    "use inkscape to calculate the width and height of fig"
    import tempfile, commands, os, sys
    fname = tempfile.mktemp(suffix=".svg")
    svg = fig.SVG()
    vb = "%s %s %s %s" % (0, 0, w, h)
    svgfig.canvas(svg, width=w, height=h, viewBox=vb).save(fname)
    #svg.save(fname)
    width = float(commands.getoutput("inkscape -W '%s'" % fname))
    height = float(commands.getoutput("inkscape -H '%s'" % fname))
    os.remove(fname)
    return width, height

w = 400.0
h = 800.0

r = newick.parse(file("test.newick").read())
r.order_subtrees_by_size()
n2c = layout.calc_node_positions(r, w, h, scaled=True)

ntips = float(len(r.leaves()))
fontsize = h/ntips

## bbox = svgfig.Rect(1,1,w-1,h-1)
branches = []
labels = []
for n, c in n2c.items():
    if n.parent:
        pc = n2c[n.parent]
        d = ((c.x, c.y), (pc.x, c.y), (pc.x, pc.y))
        line = svgfig.Poly(d)
        branches.append(line)

    if n.label:
        label = svgfig.Text(c.x, c.y, n.label, font_size=fontsize)
        label.attr["text-anchor"] = "start"
        # this should vertically align the point to the middle of the
        # text, but doesn't:
        # label.attr["alignment-baseline"] ="middle"
        # so shift y down
        label.y += fontsize/3
        labels.append(label)

fig = svgfig.Fig(svgfig.Fig(*branches),svgfig.Fig(*labels))
w = getwidth(fig, w, h)

svg = fig.SVG()
vb = "%s %s %s %s" % (-10, -10, w+10,h+10)
## print svgfig.canvas(svg, width=w, height=h, viewBox=vb).xml()
## svgfig.canvas(svg, width=w, height=h, viewBox=vb).save()
svgfig.canvas(svg, width=w, height=h, viewBox=vb).inkscape()
## svgfig.canvas(svg, width=w, height=h, viewBox=vb).firefox()
