import phylo

class Coordinates:
    def __init__(self):
        pass

def smooth_xpos(node, n2coords):
    if not node.istip:
        children = node.children
        for ch in children:
            smooth_xpos(ch, n2coords)
        
        if node.parent:
            px = n2coords[node.parent].x
            cx = min([ n2coords[ch].x for ch in children ])
            n2coords[node].x = (px + cx)/2.0

    #print "scaled", node.label, node.x, node.y

def depth_length_preorder_traversal(node, n2coords=None):
    "calculate node depth (root = depth 0) and length to root"
    if n2coords is None:
        n2coords = {}
    coords = n2coords.get(node) or Coordinates()
    coords.node = node
    if not node.parent:
        coords.depth = 0
        coords.length_to_root = 0.0
    else:
        #print node.parent, node.parent.length
        try:
            p = n2coords[node.parent]
            coords.depth = p.depth + 1
            coords.length_to_root = p.length_to_root + (node.length or 0.0)
        except KeyError:
            print node.label, node.parent.label
        except AttributeError:
            coords.depth = 0
            coords.length_to_root = 0
    n2coords[node] = coords

    for ch in node.children:
        depth_length_preorder_traversal(ch, n2coords)

    return n2coords

def calc_node_positions(node, width, height,
                        lpad=0, rpad=0, tpad=0, bpad=0,
                        scaled=True, n2coords=None):
    "origin is at upper left"
    width -= (lpad + rpad)
    height -= (tpad + bpad)

    if n2coords is None:
        n2coords = {}
    depth_length_preorder_traversal(node, n2coords=n2coords)
    leaves = node.leaves()
    nleaves = len(leaves)
    maxdepth = max([ n2coords[lf].depth for lf in leaves ])
    unitwidth = width/float(maxdepth)
    unitheight = height/(nleaves-1.0)

    xoff = (unitwidth * 0.5)
    yoff = (unitheight * 0.5)

    if scaled:
        maxlen = max([ n2coords[lf].length_to_root for lf in leaves ])
        scale = width/maxlen

    #print "height is", height
    for i, lf in enumerate(leaves):
        c = n2coords[lf]
        c.y = i * unitheight
        #print lf.label, c.y
        if not scaled:
            c.x = width
        else:
            c.x = c.length_to_root * scale

    for n in node.iternodes(phylo.POSTORDER):
        c = n2coords[n]
        if (not n.istip) and n.children:
            children = n.children
            ymax = n2coords[children[0]].y
            ymin = n2coords[children[-1]].y
            c.y = (ymax + ymin)/2.0
            if not scaled:
                c.x = min([ n2coords[ch].x for ch in children ]) - unitwidth
            else:
                c.x = c.length_to_root * scale

        #print n.label, c.x, c.y

    if not scaled:
        for i in range(10):
            smooth_xpos(node, n2coords)

    for coords in n2coords.values():
        coords.x += lpad
        coords.y += tpad

    for n, coords in n2coords.items():
        if n.parent:
            p = n2coords[n.parent]
            coords.px = p.x; coords.py = p.y
        else:
            coords.px = None; coords.py = None

    return n2coords

def calc_node_positions_pdf(node, unitheight=12, unitwidth=12*5,
                            scaled=True, n2coords=None):
    """
    origin is at lower left
    unitheight is height of text, e.g 12 (points)
    """
    if n2coords is None:
        n2coords = {}
    
    depth_length_preorder_traversal(node, n2coords)
    leaves = node.leaves()
    nleaves = len(leaves)
    maxdepth = max([ n2coords[lf].depth for lf in leaves ])
    width = maxdepth * unitwidth

    if scaled:
        maxlen = max([ n2coords[lf].length_to_root for lf in leaves ])
        scale = width/maxlen

    #print "height is", height
    y = 0
    for i, lf in enumerate(leaves):
        c = n2coords[lf]
        try:
            c.y = y + lf.get_height()
        except AttributeError:
            c.y = y + i * unitheight
        y = c.y
        #print lf.label, c.y
        if not scaled:
            c.x = width
        else:
            c.x = c.length_to_root * scale

    for n in node.iternodes(phylo.POSTORDER):
        c = n2coords[n]
        if not n.istip:
            children = n.children
            ymax = n2coords[children[0]].y
            ymin = n2coords[children[-1]].y
            c.y = (ymax + ymin)/2.0
            if not scaled:
                c.x = min([ n2coords[ch].x for ch in children ]) - unitwidth
            else:
                c.x = c.length_to_root * scale

        #print n.label, c.x, c.y

    if not scaled:
        for i in range(10):
            smooth_xpos(node, n2coords)

    return n2coords

if __name__ == "__main__":
    import newick
    node = newick.parse("(a:3,(b:2,(c:4,d:5):1,(e:3,(f:1,g:1):2):2):2);")
    for i, n in enumerate(node.iternodes()):
        if not n.istip:
            n.label = "node%s" % i
    node.label = "root"
    calc_node_positions(node, width=10, height=10, scaled=True)
