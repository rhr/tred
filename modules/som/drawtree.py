#!/usr/bin/env python
import sys, os, re, math, copy, pprint, shlex, datetime
from cStringIO import StringIO
import reportlab.pdfgen.canvas
import reportlab.lib.pagesizes
from reportlab.lib.units import inch, cm
import reportlab.graphics.widgetbase
from reportlab.graphics.widgetbase import Widget
from reportlab.graphics import shapes
from reportlab.pdfbase import pdfmetrics
from reportlab.graphics import renderPDF, renderPS, renderSVG
from reportlab.lib import colors
from reportlab.graphics.charts.textlabels import Label
import newick, phylo, layout
import optparse
from pyPdf import PdfFileWriter, PdfFileReader
letter = reportlab.lib.pagesizes.letter
A4 = reportlab.lib.pagesizes.A4
PG_SIZE = (letter[0], letter[1]*1)

name2size = {
    "letter": letter, "A4": A4
    }

class Storage(dict):

    """
    A Storage object is like a dictionary except `obj.foo` can be used
    in addition to `obj['foo']`.
    
        >>> o = Storage(a=1)
        >>> print o.a
        1
        >>> o['a']
        1
        >>> o.a = 2
        >>> print o['a']
        2
        >>> del o.a
        >>> print o.a
        None
    
    """

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError, k:
            return None

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError, k:
            raise AttributeError, k

    def __repr__(self):
        return '<Storage ' + dict.__repr__(self) + '>'

    def __getstate__(self):
        return dict(self)

    def __setstate__(self, value):
        for (k, v) in value.items():
            self[k] = v

    def copy(self):
        return Storage(self)


class Treestyle:
    cladogram = 0
    phylogram = 1

class NodeLabel(Label):
    pass

class DrawingNode(Widget):
    """
    A node on a phylogeny that knows how to render itself, by drawing a
    line to its parent (if it has one) and drawing any associated
    labels, e.g., tiplabel, length, and support.  The position, size,
    font, etc. of these labels are specified in the node's XXX_render
    dictionaries (these are stored in the node's render_info
    dictionary).  If the 'visible' flag is set to 0, the label is not
    drawn.
    """
    base_render = Storage({
        "visible": 1,
        "x_offset": 0.5,
        "y_offset": -0.33,
        "offset_relative": "self",
        "format": "%s",
        "font": "Times-Roman",
        "font_size": 1.0,
        "font_color": colors.black,
        "text_anchor": "start",
        })
    
    def __init__(self, baseheight=12):
        self.children = []
        self.parent = None
        self.tiplabel = None
        self.intlabel = None
        self.label_SW = None
        self.length = None
        self.depth = 0  # number of internodes from root

        self.drawables = []

        self.thicken = False
        self.x = 0.0
        self.y = 0.0

        # baseheight: the 'base' point size of the rendered node,
        # against which other attributes are rendered (labels etc.)
        self.baseheight = baseheight or 12

        length_render = self.base_render.copy()
        length_render.update(
            {"visible": 0,
             "x_offset": 0,
             "y_offset": 0.25,
             "offset_relative": "edge",
             "format": "%0.2f",
             "font": "Helvetica",
             "font_size": 0.75,
             "text_anchor": "middle"}
            )

        intlabel_render = self.base_render.copy()
        intlabel_render.update(
            {"visible": 0,
             "x_offset": -0.25,
             "y_offset": 0.25,
             "offset_relative": "self",
             "format": "%s",
             "font": "Helvetica",
             "font_size": 0.75,
             "text_anchor": "end"}
            )
        support_render = self.base_render.copy()
        support_render.update(
            {"visible": 0,
             "x_offset": 0,
             "y_offset": 0.25,
             "offset_relative": "edge",
             "format": "%0.2f",
             "font": "Helvetica",
             "font_size": 0.75,
             "text_anchor": "middle"}
            )
        dsdn_render = self.base_render.copy()
        dsdn_render.update(
            {"visible": 0,
             "x_offset": 0,
             "y_offset": 0.2,
             "offset_relative": "edge",
             "format": "%s",
             "font": "Helvetica",
             "font_size": 0.75,
             "text_anchor": "middle"}
            )

        label_SW_render = self.base_render.copy()
        label_SW_render.update(
            {"visible": 0,
             "x_offset": -0.5,
             "y_offset": 0.2,
             "offset_relative": "self",
             "format": "%s",
             "font": "Helvetica",
             "font_size": 0.75,
             "text_anchor": "middle"}
            )

        self.render_info = Storage({
            "tiplabel": self.base_render.copy(),
            "length": length_render,
            "intlabel": intlabel_render,
            "support": support_render,
            "dsdn": dsdn_render,
            "label_SW": dsdn_render,
            })

        # vpad: proportion of label font size that separates ('pads')
        # terminal nodes
        # TODO: allow for multiline labels?
        self.vpad = 1.1

        # stroke_width: line thickness of drawn branches, as a
        # proportion of baseheight
        self.stroke_width = 0.1
        self.stroke_color = colors.black

    def iternodes(self, v=None):
        """
        returns a list of nodes descendant from self - including self
        """
        yield self
        for child in self.children:
            for d in child.iternodes():
                yield d

    def set_attr(self, key, value, recurse=1):
        setattr(self, key, value)
        if recurse:
            for c in self.children:
                c.set_attr(key, value, recurse)

    def foreach(self, func):
        "call func with self as arg and recurse"
        func(self)
        for c in self.children:
            c.foreach(func)

    def set_render_attr(self, key, attr, value, recurse=1):
        self.render_info[key][attr] = value
        if recurse:
            for c in self.children:
                c.set_render_attr(key, attr, value, recurse)

    def calc_tiplabel_font_size(self):
        return self.baseheight * \
               self.render_info["tiplabel"]["font_size"]
    
    def calc_vpad(self):
        return max(self.baseheight * self.vpad,
                   self.calc_tiplabel_font_size() * self.vpad)

    def calc_strokewidth(self):
        return self.baseheight * self.stroke_width

    def calc_length_to_root(self):
        v = 0.0; n = self
        while n.parent is not None:
            v += n.length
            n = n.parent
        return v

    def translate(self, dx=0.0, dy=0.0, func=None):
        if func is not None:
            dx, dy = func(self)
        self.x += dx
        self.y += dy

        for d in self.drawables:
            d.translate(dx, dy)

        for c in self.children:
            c.translate(dx, dy, func)

    def add_child(self, child):
        self.children.append(child)
        child.x = self.x

    def get_height(self):
        if self.children:
            return sum([ c.get_height() for c in self.children ])
        else:
            return self.calc_vpad()

    def leaves(self, lvs = []):
        if self.children:
            for c in self.children:
                c.leaves(lvs)
        else:
            lvs.append(self)
        return lvs

    def sort(self):
        if self.children:
            data = sorted([ c.sort() for c in self.children ])
            if not filter(lambda x:x[0] != data[0][0], data):
                data.reverse()
            self.children[:] = [d[2] for d in data]
            return [reduce(lambda x,y:x+y, [d[0] for d in data]),
                    reduce(lambda x,y:x+y, [d[1] for d in data]),
                    self]
        else:
            return [1, [self.tiplabel], self]

    def intlabel2support(self):
        try:
            self.support = float(self.intlabel)
        except:
            pass

    def draw(self):
        g = shapes.Group()

        for attr, info in filter(lambda x:x[1]["visible"],
                                 self.render_info.items()):
            if hasattr(self, attr):
                val = getattr(self, attr)
                if val is not None:
                    fs = info["font_size"] * self.baseheight
                    rel = info["offset_relative"]
                    y = self.y
                    if rel == "self":
                        x = self.x
                    elif rel == "edge" and self.parent:
                        x = self.x - (self.x-self.parent.x)*0.5
                    dx = info["x_offset"] * fs
                    dy = info["y_offset"] * fs
                    label = shapes.String(
                        x + dx, y + dy,
                        info["format"] % val,
                        fontName = info["font"],
                        fontSize = fs,
                        fillColor = info["font_color"],
                        textAnchor = info["text_anchor"]
                    )
                    g.add(label)

        if self.parent:
            pl = shapes.PolyLine(
                [self.x, self.y,
                 self.parent.x, self.y,
                 self.parent.x, self.parent.y],
                strokeWidth = max(self.calc_strokewidth(), 1.0),
                strokeColor = self.stroke_color,
                fillColor = None
                )
            g.add(pl)

            ## thicken strongly supported branches
            if self.thicken:
                pl = shapes.PolyLine(
                    [self.x, self.y,
                     self.parent.x - self.parent.calc_strokewidth()/2.0,
                     self.y],
                    strokeWidth = max(self.calc_strokewidth(), 1.0)*4,
                    strokeColor = self.stroke_color,
                    fillColor = None
                    )
                g.add(pl)

        for d in self.drawables:
            g.add(d)
        return g

def traverse(node, opts, parent_gnode=None, mapping={}):
    """take a tree of nodes and return a tree of widget DrawingNodes"""
    if parent_gnode is None:
        parent_gnode = DrawingNode()
        parent_gnode.x = parent_gnode.y = 0.0
        parent_gnode.depth = 0
    else:
        n = DrawingNode(baseheight=opts.baseheight)
        mapping[node] = n
        n.depth = parent_gnode.depth + 1
        n.parent = parent_gnode
        if node.label:
            if node.istip:
                n.tiplabel = node.label
            else:
                n.intlabel = node.label
        else:
            n.render_info["tiplabel"]["visible"] = 0
        n.length = node.length

        parent_gnode.add_child(n)
        parent_gnode = n

    if node and not node.istip:
        for child in node.children:
            traverse(child, opts, parent_gnode, mapping)

    return parent_gnode, mapping

def set_terminal_ypos(node, v = [None]):
    if node.children:
        for c in node.children:
            set_terminal_ypos(c, v)
    else:
        if v[0]:
            node.y = v[0].y + v[0].get_height()/2.0 + node.get_height()/2.0
        else:
            node.y = node.get_height()/2.0
        v[0] = node

def calc_internal_ypos(node):
    if node.children:
        map(calc_internal_ypos, node.children)
        
        node.y = (node.children[-1].y + node.children[0].y)*0.5

def calc_xpos(node, maxdepth, unitwidth):
    if node.parent:
        node.x = node.parent.x + unitwidth
    if node.children:
        for c in node.children:
            calc_xpos(c, maxdepth, unitwidth)
        node.x = min([n.x for n in node.children]) - unitwidth
    else:
        node.x += (maxdepth-node.depth)*unitwidth

def smooth_xpos(node):
    for c in node.children:
        smooth_xpos(c)
        
    if node.parent and node.children:
        px = node.parent.x
        cx = min([c.x for c in node.children])
        dxp = node.x - px
        cxp = cx - node.x
        node.x = px + (cx - px)*0.5
        

def scale_branches(node, scalefactor):
    if node.parent:
        node.x = node.parent.x + (node.length * scalefactor)
    for c in node.children:
        scale_branches(c, scalefactor)

def draw(tree, opts):
    for attr in opts.visible:
        tree.set_render_attr(attr, "visible", 1, 1)

    leaves = tree.leaves()

    maxdepth = max([ leaf.depth for leaf in leaves ])
    width = opts.unitwidth * maxdepth

    set_terminal_ypos(tree)
    calc_internal_ypos(tree)

    maxleaf = leaves[-1]
    maxy = maxleaf.y
    minleaf = leaves[0]
    miny = minleaf.y

    height = sum([ x.get_height() for x in leaves ])

    max_labelwidth = max(
        [ pdfmetrics.stringWidth(str(l.tiplabel),
                                 l.render_info["tiplabel"]["font"],
                                 l.calc_tiplabel_font_size()) \
          + (l.render_info["tiplabel"]["x_offset"] * l.baseheight)
          for l in leaves ]
        )

    #unitwidth = (height*((avail_w-max_labelwidth)/avail_h)) / maxdepth

    calc_xpos(tree, maxdepth, opts.unitwidth)
    for i in range(10):
        smooth_xpos(tree)

    ## tree.translate(tree.calc_strokewidth()/2.0,
    ##                tree.calc_tiplabel_font_size()/2.0)

    ## width = (maxdepth * unitwidth) + \
    ##         max_labelwidth + (tree.calc_strokewidth() * 0.5)
    #width *= 1.2

    # if fill: width = avail_w

    if opts.lengths_are_support:
        def func(n):
            if n.length is not None:
                n.support = n.length
                n.length = None
                if not n.children:
                    n.support = None
        tree.foreach(func)

    if opts.thicken is not None:
        def func(n):
            try:
                if n.support >= opts.thicken:
                    n.thicken = 1
            except AttributeError:
                pass
        tree.foreach(func)

    if opts.draw_phylogram:
        if opts.scale:
            brlen_transform = opts.scale
        else:
            brlen_transform = (maxdepth * opts.unitwidth) * \
                              1.0/max([l.calc_length_to_root() for l in leaves])
        scale_branches(tree, brlen_transform)
        if opts.verbose:
            print "%s: brlen_transform=%s" % (opts.outfile, brlen_transform)

        # draw scalebar
        max_length_to_root = max([n.calc_length_to_root() for n in leaves])
        max_x = max([n.x for n in leaves])
        scalebar = shapes.Group()
        font_size = tree.calc_tiplabel_font_size()*0.9
##         scalebar.add(shapes.String(max_x, tree.baseheight-font_size*(1.0/3.0),
##                                    " %g" % max_length_to_root,
##                                    textAnchor="start", fontSize=font_size))
        scalebar.add(shapes.String(tree.x, 1, "0.0",
                                   textAnchor="middle", fontSize=font_size))
        scalebar.add(
            shapes.Line(tree.x, tree.baseheight, max_x, tree.baseheight,
                        strokeColor = colors.black, strokeWidth = 1.0)
            )
        scalebar.add(
            shapes.Line(tree.x, tree.baseheight*1.2, tree.x, tree.baseheight*0.8,
                        strokeColor = colors.black, strokeWidth = 1.0)
            )
        scalebar.add(
            shapes.Line(max_x, tree.baseheight*1.2, max_x, tree.baseheight*0.8,
                        strokeColor = colors.black, strokeWidth = 1.0)
            )

        interval = 10**(math.floor(math.log10(float(max_length_to_root))))
        nintervals = int(math.modf(max_length_to_root/interval)[1])
        if nintervals == 1:
            interval = interval/4.0
        x = interval
        while x < max_length_to_root:
            scalebar.add(shapes.Line(x * brlen_transform, tree.baseheight*1.2,
                                     x * brlen_transform, tree.baseheight*0.8,
                                     strokeColor = colors.black, strokeWidth = 0.5))
            scalebar.add(shapes.String(x * brlen_transform, 1, str(x),
                                       textAnchor="middle", fontSize=font_size))
            x += interval
            
        
        height += tree.baseheight*3
        tree.translate(0, tree.baseheight*3)
        tree.drawables.append(scalebar)
                      
    font_size = tree.calc_tiplabel_font_size()
    if opts.title:
        title = shapes.Group()
        title.add(shapes.String(0, tree.x + height + font_size*2,
                                opts.title, fontSize=font_size))
        now = datetime.datetime.now().ctime()
        title.add(shapes.String(width+max_labelwidth,
                                tree.x + height + font_size*2,
                                now, fontSize=font_size,
                                textAnchor="end"))
        tree.drawables.append(title)
        height += font_size*2
                  
    #print list(tree.iternodes())[0].draw().getBounds()
    ## boxes = [ n.draw().getBounds() for n in tree.iternodes() ]
    ## minx = min([ b[0] for b in boxes ])
    ## maxx = max([ b[2] for b in boxes ])
    ## miny = min([ b[1] for b in boxes ])
    ## maxy = max([ b[3] for b in boxes ])
    ## tree.translate(dx=-minx,dy=-miny)
    ## boxes = [ n.draw().getBounds() for n in tree.iternodes() ]
    ## minx = min([ b[0] for b in boxes ])
    ## maxx = max([ b[2] for b in boxes ])
    ## miny = min([ b[1] for b in boxes ])
    ## maxy = max([ b[3] for b in boxes ])
    ## width = maxx; height = maxy

    drawing = shapes.Drawing(width, height)
    for node in tree.iternodes():
        ## x1, y1, x2, y2 = node.getBounds()
        ## if x2 > width:
        ##     print node.tiplabel, x2
        drawing.add(node.draw())

    x1, y1, x2, y2 = drawing.getBounds()
    drawing.width = x2 - x1
    drawing.height = y2 - y1
    return drawing

def render_svg(drawing, opts, outbuf=None):
    if opts.pagesize in name2size:
        pagesize = name2size[opts.pagesize]
    else:
        pagesize = opts.pagesize or letter
    border = opts.border or 1*cm
    landscape = opts.landscape or False
    pgwidth, pgheight = pagesize if not landscape \
                        else (pagesize[1], pagesize[0])
    #print "drawing width, height:", drawing.width/inch, drawing.height/inch
    if drawing.width > pgwidth - 2*border:
        scalefact = (pgwidth - 2*border)/float(drawing.width)
        drawing.scale(scalefact, scalefact)
    else:
        scalefact = 1.0
    #border *= scalefact
    dwidth = drawing.width*scalefact
    dheight = drawing.height*scalefact

    buf = StringIO()
    renderSVG.drawToFile(drawing, buf)
    return buf.getvalue()

def render_multipage(drawing, opts, outbuf=None):
    if opts.pagesize in name2size:
        pagesize = name2size[opts.pagesize]
    else:
        pagesize = opts.pagesize or letter
    border = opts.border or 1*cm
    landscape = opts.landscape or False
    pgwidth, pgheight = pagesize if not landscape \
                        else (pagesize[1], pagesize[0])
    #print "drawing width, height:", drawing.width/inch, drawing.height/inch
    if drawing.width > pgwidth - 2*border:
        scalefact = (pgwidth - 2*border)/float(drawing.width)
        drawing.scale(scalefact, scalefact)
    else:
        scalefact = 1.0
    #border *= scalefact
    dwidth = drawing.width*scalefact
    dheight = drawing.height*scalefact

    output = PdfFileWriter()
    if not outbuf:
        outfile = file(opts.outfile, "wb")
    else:
        outfile = outbuf

    buf = StringIO()
    renderPDF.drawToFile(drawing, buf)
    lower = dheight
    pgnum = 0
    while lower >= 0:
        if pgnum == 0:
            delta = 0.0
        else:
            delta = 2*border*pgnum
        buf.seek(0)
        tmp = PdfFileReader(buf)
        page = tmp.getPage(0)
        box = page.mediaBox
        uly = box.getUpperLeft_y() * scalefact
        upper = uly+border+delta-pgnum*pgheight
        #lower = uly+border+delta-(pgnum+1)*pgheight
        lower = upper-pgheight
        box.setUpperRight((pgwidth-border, upper))
        box.setUpperLeft((-border, upper))
        box.setLowerRight((pgwidth-border, lower))
        box.setLowerLeft((-border, lower))
        output.addPage(page)
        pgnum += 1

    output.write(outfile)
    return pgnum, scalefact

def render_pdf(drawing, opts):
    width = drawing.width
    height = drawing.height
    border = opts.border or 1*cm
    drawing.width += 2*border
    drawing.height += 2*border
    drawing.translate(border, border)
    #avail_w = size[0] - 2*border; avail_h = size[1] - 2*border
    #scalefact = min(avail_w/float(width), avail_h/float(height))
    #drawing.scale(scalefact, scalefact)
    ## size = (width+2*border, height+2*border)
    ## canvas = reportlab.pdfgen.canvas.Canvas(opts.outfile, size)
    ## canvas.setFont("Times-Roman", 10)
    ## drawing.drawOn(canvas, border, border)
    ## canvas.showPage()
    ## canvas.save()
    buf = StringIO()
    renderPDF.drawToFile(drawing, buf)
    return buf

TRANSPAT = re.compile(r'\btranslate\s+([^;]+);',
                      re.IGNORECASE | re.MULTILINE)
TREEPAT = re.compile(r'\btree\s+([_.\w]+)\s+=[^(]+(\([^;]+;)',
                     re.IGNORECASE | re.MULTILINE)
def get_trees_from_nexus(infile):
    s = infile.read()
    ttable = TRANSPAT.findall(s) or None
    if ttable:
        items = [ shlex.split(line) for line in ttable[0].split(",") ]
        ttable = dict([ (k, v.replace(" ", "_")) for k, v in items ])
    trees = TREEPAT.findall(s)
    for i, t in enumerate(trees):
        t = list(t)
        if ttable:
            t[1] = "".join(
                [ ttable.get(x, x) for x in shlex.shlex(t[1]) ]
                )
        trees[i] = t
    return trees

def get_input_tree(infile, opts=None):
    pos = infile.tell()
    line = infile.readline()
    infile.seek(pos)
    if line.upper().startswith("#NEXUS"):
        newick_trees = get_trees_from_nexus(infile)

    else:
        if opts.dsdn:
            opts.S, opts.N = map(float, infile.readline().split())
        newick_trees = infile.read().split(";")

    tree = newick.parse(newick_trees[0])
##     reroot(tree, ["ptheirospermum_tenuisec_28207", "seymeria_pectinata"])

    node, mapping = traverse(tree)
    node.sort()

    if opts.dsdn:
        def func(n):
            try:
                n.dS = n.length
                n.length = None
            except AttributeError: pass
        node.foreach(func)
        
        dN_newick = newick_trees[1].strip()
        assert dN_newick

        dN = newick.parse(dN_newick)
        labelset2treenode = tree_compare.set_labels(tree)
        labelset2dNnode = tree_compare.set_labels(dN)

        for labelset, dNnode in labelset2dNnode.items():
            treenode = labelset2treenode.get(labelset)
            if treenode:
                try:
                    gnode = mapping[treenode]
                    gnode.dN = dNnode.length
##                     gnode.dsdn = "%0.1f/%0.1f" % (gnode.dS*opts.S,
##                                                   gnode.dN*opts.N)
                    try:
                        if gnode.dN > 0.0:
                            gnode.dsdn = "%f" % (gnode.dN/gnode.dS)
                        else:
                            gnode.dsdn = ""
                    except ZeroDivisionError:
                        gnode.dsdn = ""
                except KeyError:
                    pass
        return node

    try:
        support_newick = newick_trees[1].strip()
        if support_newick:
            support = newick.parse(support_newick)
            labelset2treenode = tree_compare.set_labels(tree)
            labelset2supportnode = tree_compare.set_labels(support)

            for labelset, supportnode in labelset2supportnode.items():
                treenode = labelset2treenode.get(labelset)
                if treenode:
                    try:
                        gnode = mapping[treenode]
                        gnode.support = supportnode.length
                    except KeyError:
                        pass
    except IndexError:
        pass
        
    # add parsing for other file formats here

    return node

class Options(Storage):
    def __init__(self, **kwargs):
        self.pagesize = None
        self.visible = ""
        self.lengths_are_support = False
        self.thicken = False
        self.draw_phylogram = False
        self.scale = False
        self.title = None
        self.format = "pdf"
        self.verbose = False
        self.baseheight = 12
        self.unitwidth = self.baseheight*3.0
        self.border = cm
        for k, v in kwargs:
            setattr(self, k, v)

if __name__ == "__main__":
    opts = Options()
    opts.outfile = "/tmp/tmp.pdf"
    opts.title = "Corydalis trnTL April 2009"
    opts.pagesize = A4
    opts.baseheight = 10
    opts.unitwidth *= 0.5
    opts.draw_phylogram = 1
    s = "(Lamprocapnos_spectabilis_AY328204:0.08538233,Adl_asiatica_ML2007.10.04:0.0049816,(Dicentra_eximia_AY145361:0.03572868,((((Dac_torulosa_ML2007.10.05:1e-08,Dac_roylei_ML2007.10.37:0.00124039):0.00123638,Dac_lichiangensis_ML2007.10.35:0.00249241):0.00558662,(Dac_macrocapnos_ML2007.10.06:0.00269334,Dac_scandens_ML2007.10.33:0.00150651):0.01478759):0.01038187,((Cor_semenovii_ML2007.10.08:0.02001658,(((Cor_rupestris_RUP:1e-08,Cor_rupestris_330513:0.00379922):0.00380251,Cor_grubovii_GRU:0.00260068):0.00013505,Cor_adunca_yw28:0.00476175):0.01282934):0.00558306,((((Cor_Peng21464:1e-08,Cor_ophiocarpa_CKY1680:1e-08):0.0055592,Cor_racemosa_YWHN001:1e-08):0.02091717,(((Cor_latiloba_ML2007.10.42:0.00630165,((Cor_edulis_ML2008.04.11:1e-08,Cor_edulis_EDU:2e-08):0.0012276,Cor_tomentella_TOM:0.00485597):0.00245174):0.0097641,((Cor_foetida_330515:1e-08,Cor_brevipedunculata_ML2006.15:1e-08):0.00446044,(Cor_tashiroi_Chen03353:1e-08,Cor_tashiroi_BB6201:1e-08):0.00257344):0.00604045):0.01097774,Cor_orthopoda_RR080606.01:0.02944005):0.01459268):0.00830524,(((((Cor_brevirostrata_330528:0.01196655,((Cor_nudicaulis_ML060414:0.00407589,Cor_schanginii_ssp_ainae_ML060408:0.00160085):0.00780903,((Cor_repens_ML060402:1e-08,(Cor_watanabei_ML060407:0.00126891,Corydalis_ambigua_DQ912916:0.00460318):0.00120624):0.0125281,Cor_henrikii_ML060405:0.02888342):0.00109279):0.00315426):0.00309794,(Cor_1642:0.05908923,Cor_sigmantha_mix_ellipticarpa_06.5_ML2006.16:0.00256113):0.00118435):1e-08,Cor_alpestris_308:0.02739746):0.00127047,(((Cor_anthriscifolia_ML2006.2b:0.00122948,Cor_anthriscifolia_ML2006.2a:1e-08):0.01562389,(Cor_cheilosticta_33051:1e-08,Cor_livida_330525:1e-08):0.01111376):1e-08,(Cor_blanda_ssp_oxelmannii_ML060404:0.00257888,Cor_cava_ML2008.04.27:0.00261892):0.01177337):0.0017093):1e-08,((((Cor_buschii_yw05:1e-08,Cor_nobilis_NOB:2e-08):1e-08,Cor_nobilis_ML060418:1e-08):0.01554237,((((Cor_davidii_ML2006.67:0.01734853,Cor_inopinata_330547:0.02151837):0.00355606,Cor_gracillima_ML2007.10.49:0.01909226):0.00255662,Cor_pygmaea_Dickore10838:0.0130424):1e-08,(((Cor_wuzhengyiana_Miehe05.104.32:1e-08,Cor_hookeri_330575:0.00136099):0.00620547,((Cor_raddeana_YW0702.06:0.01033424,Cor_laucheana_31398:0.00574416):0.00509468,(Cor_pseudoimpatiens_check_ML2006.30:0.00521817,(Cor_impatiens_YW0702.10:0.00518875,(Cor_zhongdianensis_33056:0.01170718,(Cor_sect_Fasciculatae_32063:1e-08,(Cor_pseudosibirica_ML2006.45:0.00125863,(Cor_pseudosibirica_yw27:1e-08,Cor_pseudosibirica_ML2006.48:1e-08):1e-08):0.0012534):0.0127861):1e-08):0.00125238):0.00314432):0.01487106):0.00399348,(((((Cor_fissibracteata_yw14:0.00288596,Cor_jiulongensis_ML2006.65:1e-08):1e-08,((Cor_nubicola_31129:0.00123745,(Cor_chamdoensis_x_31459:1e-08,(Cor_calcicola_yw13:1e-08,Cor_sect_Trachycarpae_hybrid_32279:1e-08):1e-08):1e-08):0.00408618,(((Cor_polygalina_ML2008.04.03:0.00527158,Cor_linarioides_32465:0.00102956):0.00100923,(Cor_31855:0.00188791,Cor_densispica_330564:0.00155833):0.00902629):0.00111501,((Cor_sect_Trachycarpae_31946:1e-08,(((Cor_linarioides_group_ML2006.42:1e-08,Cor_scaberula_31750:1e-08):1e-08,Cor_scaberula_31947:1e-08):1e-08,(Cor_prattii_yw16:1e-08,Cor_atuntsuensis_linarioides_complex_31103:0.00128435):1e-08):1e-08):0.00134431,Cor_milarepa_ML2008.04.08:1e-08):0.0026783):1e-08):1e-08):0.0045528,Cor_delavayi_yw18:0.00497383):0.01261367,Cor_drakeana_yw09:0.014088):0.00467194,((Corydalis_falconeri_EU326049:1e-08,Cor_meifolia_330511:1e-08):0.00274417,((Cor_dasyptera_31945:0.00362938,Cor_nana_330530:0.00462978):1e-08,Cor_pachypoda_ML2007.10.23:1e-08):0.00153103):0.00694293):0.0015815):0.0020075):0.0187199):0.00148112,(Cor_bungeana_yw10:0.04327289,(((((Cor_ML2007.10.13:1e-08,Cor_mucronata_YW0701.40:1e-08):0.03297057,(Corydalis_incisa_DQ912917:0.00583286,Cor_incisa_Chen02507:0.00553014):0.02445205):0.00484969,(Cor_ternatifolia_ML2008.04.20:0.004217,(Corydalis_temulifolia_AY328202:0.00263566,Cor_temulifolia_TEM:1e-08):0.00268836):0.00988548):0.00137759,((((Cor_duclouxii_ML2007.10.34:0.00252616,(Cor_duclouxii_ML2007.10.07:1e-08,Cor_duclouxii_ML2007.10.31:1e-08):1e-08):1e-08,(Cor_shimienensis_330526:1e-08,Cor_shimienensis_ML2006.68:1e-08):0.00239198):0.00963243,((Cor_leptocarpa_potentillifolia_ML2007.10.12:1e-08,(Cor_leptocarpa_potentillifolia_ML2007.10.58:1e-08,Cor_leptocarpa_ML2007.10.10:1e-08):1e-08):0.01405754,Cor_bulleyana_ML2007.10.40:0.00374755):0.00687011):0.00655341,(Cor_capnoides_ML2007.10.09:0.01106581,Cor_brevirostrata_33664:0.01543107):0.00545768):0.00116684):0.00282419,((Cor_petrophila_ML2008.04.05:1e-08,Cor_petrophila_ML2007.10.39:1e-08):0.00395927,(Cor_kiukiangensis_ML2007.10.55:0.00278589,(((Cor_polyphylla_ML2008.04.04:1e-08,Cor_polyphylla_ML2007.10.52:1e-08):0.00264586,(((Cor_melanochlora_ML2006.54:0.00125728,Cor_omeiana_330570:0.00130459):1e-08,Cor_leucanthema_LEU:0.00264533):0.00121514,((Cor_check_ML2006.38:0.00959099,Corydalis_sp_AY328203:0.00117959):0.00119682,(Cor_dongchuanensis_ML2007.10.11:0.0013474,((Cor_mairei_330533:1e-08,Cor_check_ML060419:1e-08):0.00393409,((((Cor_kokiana_ML2008.04.02:0.00131962,Cor_kokiana_ML2008.04.26:1e-08):1e-08,Cor_kokiana_33052:1e-08):0.00659535,(((Cor_oxypetala_ML2007.10.21:0.00136444,Cor_appendiculata_ML2007.10.18:0.00142489):1e-08,Cor_enantiophylla_ML2007.10.53:0.00132626):0.00264897,((((((Cor_melanochlora_31435:1e-08,Cor_cytisiflora_ML2004.22:1e-08):1e-08,Cor_cytisflora_330553:0.00284932):1e-08,(Cor_aeditua_ML2006.72:0.00419415,Cor_schistostigma_ML2006.7:1e-08):0.00124144):0.00245556,Cor_anthocrene_ML2007.10.25:1e-08):1e-08,(Cor_heterothylax_330557:0.00403196,Cor_hendersonii_33054:0.00392169):1e-08):0.00122792,(Cor_pseudoadoxa_ML2008.04.01:0.00541231,(((Cor_myriophylla_ML2008.04.24:1e-08,Cor_melanochlora_ML2007.10.17:1e-08):0.00385542,(Cor_chamdoensis_31515:0.00133142,Cor_fangshanensis_CW07026:1e-08):1e-08):0.00256617,Cor_cashmeriana_ML060409:0.00283236):1e-08):1e-08):1e-08):1e-08):0.00132034,((Cor_aeaeae_ML2006.10:2e-08,((Cor_stolonifera_ML2007.10.29:1e-08,(Cor_barbisepala_ML2006.32:0.00294271,Cor_stolonifera_ML2007.10.27:1e-08):1e-08):0.00572386,Cor_panda_yw23:1e-08):1e-08):0.00242596,(Cor_tapaishanica_ML2008.04.09:1e-08,Cor_ellipticarpa_ML060416:1e-08):0.00346201):0.0030868):1e-08):1e-08):1e-08):1e-08):1e-08):1e-08,(Cor_balsamiflora_yw21:0.00130274,(Cor_balsamiflora_ML2007.10.02:1e-08,(((Cor_mucronipetala_ML2007.10.26:1e-08,Cor_mucronipetala_ML2007.10.24:1e-08):1e-08,Cor_calycosa_ML2007.10.01:1e-08):1e-08,(Cor_mucronipetala_ML2007.10.30:1e-08,(Cor_C.capitata_ML060411:1e-08,Cor_capitata_ML2006.17:1e-08):0.00127153):1e-08):1e-08):1e-08):0.00126571):0.00190654):1e-08):0.01783135):0.00619633):0.00316843):0.0052156):0.01269517):0.01777571):0.00888142):0.02183108):0.00394631):0.00394631;"
    t = newick.parse(s)
    node, mapping = traverse(t, opts)
    d = draw(node, opts)
    #render(d, opts)
    render_multipage(d, opts)
