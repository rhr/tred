import sys
from array import array
import phylo, newick

class AsciiBuffer:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self._b = [ array('c', ' '*width) for line in range(height) ]

    def putstr(self, r, c, s):
        assert r < self.height
        assert c+len(s) <= self.width, "%s %s %s '%s'" % (self.width, r, c, s)
        self._b[r][c:c+len(s)] = array('c', s)

    def __str__(self):
        return "\n".join([ b.tostring() for b in self._b ])

def sum_to_root(node, internodes=True, length=False):
    i = 0
    n = node
    while 1:
        if not n.parent:
            break
        else:
            n = n.parent
            i += 1
    return i

def depth_length_preorder_traversal(node):
    if not node.parent:
        node.depth = 0
        node.length_to_root = 0.0
    else:
        p = node.parent
        node.depth = p.depth + 1
        node.length_to_root = p.length_to_root + (node.length or 0.0)

##     if node.label:
##         print node.label, node.depth

    for ch in node.children:
        depth_length_preorder_traversal(ch)

def smooth_cpos(node):
    for ch in node.children:
        smooth_cpos(ch)
        
    if node.parent and not node.istip:
        px = node.parent.c
        cx = min([ ch.c for ch in node.children ])
        dxp = node.c - px
        cxp = cx - node.c
        node.c = int(px + (cx - px)*0.5)

def scale_cpos(node, scalef, root_offset):
    if node.parent:
        node.c = node.parent.c + int(node.length * scalef)
    else:
        node.c = root_offset

    for ch in node.children:
        scale_cpos(ch, scalef, root_offset)

def tree2ascii(tree, unitlen=3, minwidth=50, maxwidth=None, scaled=False,
               show_internal_labels=True):
    depth_length_preorder_traversal(tree)

    leaves = tree.leaves(); nleaves = len(leaves)

    maxdepth = max([ lf.depth for lf in leaves ])

    max_labelwidth = max([ len(lf.label) for lf in leaves ]) + 1

    root_offset = 0
    if tree.label and show_internal_labels:
        root_offset = len(tree.label)
        
    width = maxdepth*unitlen + max_labelwidth + 2 + root_offset
    #print width

    height = 2*nleaves - 1

    if width < minwidth:
        unitlen = (minwidth - max_labelwidth - 2 - root_offset)/maxdepth
        width = maxdepth*unitlen + max_labelwidth + 2 + root_offset

    buf = AsciiBuffer(width, height)

    for i, lf in enumerate(leaves):
        lf.c = width - max_labelwidth - 2
        lf.r = i*2

    for node in tree.iternodes(phylo.POSTORDER):
        if node.children:
            children = node.children
            rmin = children[0].r; rmax = children[-1].r
            node.r = int(rmin + (rmax-rmin)/2.0)
            node.c = min([ ch.c for ch in children ]) - unitlen

    if not scaled:
        smooth_cpos(tree)
    else:
        maxlen = max([ lf.length_to_root for lf in leaves ])
        scalef = (leaves[0].c + 1 - root_offset)/maxlen
        scale_cpos(tree, scalef, root_offset)

    for node in tree.iternodes(phylo.POSTORDER):
        if node.parent:
            for r in range(min([node.r, node.parent.r]),
                           max([node.r, node.parent.r])):
                buf.putstr(r, node.parent.c, ":")

            sym = getattr(node, "hchar", "-")
            vbar = sym*(node.c-node.parent.c)
            buf.putstr(node.r, node.parent.c, vbar)

        if node.istip:
            buf.putstr(node.r, node.c+1, " "+node.label)
        else:
            if node.label and show_internal_labels:
                buf.putstr(node.r, node.c-len(node.label), node.label)

        buf.putstr(node.r, node.c, "+")
        
    return str(buf)

render = tree2ascii

if __name__ == "__main__":
    import random
    rand = random.Random()
    
    t = newick.parse("(foo,((bar,(dog,cat)dc)dcb,(shoe,(fly,(cow, bowwow)cowb)cbf)X)Y)Z;")
    
    #t = newick.parse("(((foo:4.6):5.6, (bar:6.5, baz:2.3):3.0):3.0);")
    #t = newick.parse("(foo:4.6, (bar:6.5, baz:2.3)X:3.0)Y:3.0;")
    i = 1
##     for n in t.descendants():
##         #n.length = rand.random()
##         if not n.istip:
##             n.label = "n%s" % i
##             print n, n.label
##             i += 1
    print tree2ascii(t, scaled=0, show_internal_labels=1)
    r = t.find_descendant("cat").parent
    phylo.reroot(t, r)
    tp = t.parent
    tp.remove_child(t)
    c = t.children[0]
    t.remove_child(c)
    tp.add_child(c)
##     s = newick.to_string(r)
##     print tree2ascii(newick.parse(s))
##     for node in r.children:
##         print node.label, node.parent.label
    print tree2ascii(r, scaled=0, show_internal_labels=1)
