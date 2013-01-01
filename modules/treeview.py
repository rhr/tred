from gluon.sqlhtml import *
from gluon.sql import *
from gluon.storage import Storage
from som import layout, phylo, newick, ascii

class Tree:
    def __init__(self, name=None):
        self.name = name
        self.wscale = 2.0
        self.scaled = False
        self.scaled_view = False
        self.collapsed = {}
        self.newick = ""
        self.root = None            
        self.root_age = self.calibrate()
        self.interactive = False
        self.visible = True
        self.view = "html"
        self.bwu = "em"
        self.bhu = "ex"
        self.included = "__all__"

    def is_included(self, label):
        if self.included == "__all__":
            return True
        elif label in self.included:
            return True
        else:
            return False

    def set_included(self, label, value):
        if value:
            if self.included != "__all__" and label not in self.included:
                self.included.append(label)
        else:
            if self.included == "__all__":
                self.included = [ n.label for n in self.root.iternodes()
                                  if not n.istip ]
            self.included.remove(label)

    def calibrate(self, depth=None):
        if self.scaled:
            v = [ sum([ n.length for n in lf.rootpath() if n.parent ])
                  for lf in self.root.leaves() ]
            mx = max(v)
            depth = depth or mx
            scale = depth/mx
            for node in self.root.descendants(phylo.POSTORDER):
                if node.parent:
                    node.length *= scale
                else:
                    node.length = 0.0
            self.root_age = depth
            return depth

    def serialize(self):
        return dict(
            name = self.name,
            newick = self.newick,
            root_age = self.root_age,
            included = self.included
            )

    def is_ultrametric(self):
        if self.scaled:
            v = [ sum([ n.length for n in lf.rootpath() if n.parent ])
                  for lf in self.root.leaves() ]
            mx = max(v); mn = min(v)
            d = mx - mn
            if d > float(mx)/1000.0:
                return (False, d)
            else:
                return (True, d)

    def parse(self, s=None):
        if s:
            self.newick = s
        self.root = newick.parse(self.newick)
        scaled = True
        for i, n in enumerate(self.root.iternodes(phylo.POSTORDER)):
            n.number = i
            if (not n.istip) and (not n.label):
                n.label = "N%s" % n.number
            n.age = None
            if n.parent and (n.length is None):
                scaled = False
        self.newick = newick.tostring(self.root)+";"
        self.scaled = scaled

    def html(self, r, s):
        return DIV(
            self.render_controls(r, s),
            DIV(nodes2css(r, s, self), _style="position:relative;")
            )

    def render_controls(self, r, s):
        target = "treecss"
        cb = URL(r=r, f="tree_view_stretch")
        ajax="ajaxdirect('%s', '', '%s')" % (cb, target)
        w = A("[wider]", _onclick=ajax, _style="cursor:pointer;",
              _title="Stretch tree wider")
        cb = URL(r=r, f="tree_view_squeeze")
        ajax="ajaxdirect('%s', '', '%s')" % (cb, target)
        h = A("[narrower]", _onclick=ajax, _style="cursor:pointer;",
              _title="Squeeze tree narrower")
        cb = URL(r=r, f="tree_view_select_all")
        ajax="ajaxdirect('%s', '', '%s')" % (cb, target)
        sa = A("[select all]", _onclick=ajax, _style="cursor:pointer;",
               _title="Select all nodes")
        cb = URL(r=r, f="tree_view_select_none")
        ajax="ajaxdirect('%s', '', '%s')" % (cb, target)
        sn = A("[select none]", _onclick=ajax, _style="cursor:pointer;",
               _title="Deselect all nodes")
        return DIV("Branches drawn to scale: ", self.render_scaled(r, s),
                   XML("&nbsp;&nbsp;"), w,
                   XML("&nbsp;&nbsp;"), h,
                   XML("&nbsp;&nbsp;"), sa,
                   XML("&nbsp;&nbsp;"), sn)


    def render_scaled(self, request, session):
        target = "treecss"
        v = bool(self.scaled_view)
        cb = URL(r=request, f="tree_scaled_checkbox_clicked")
        ajax="ajaxdirect('%s', '', '%s')" % (cb, target)
        inp = INPUT(_type="checkbox", value=v, _onchange=ajax)
        return inp

    def render(self, r, s):
        if self.visible:
            if self.view == "html":
                return self.html(r, s)
            elif self.view == "ascii":
                return ascii.render(self.root, scaled=self.scaled_view)
            else:
                return self.newick
        else:
            return ""

def restore(d, m):
    t = Tree(m)
    t.name = d.get("name")
    t.newick = d.get("newick")
    t.root_age = d.get("root_age")
    t.included = d.get("included")
    t.parse()
    return t

def nodes2css(request, session, tree):
    root = tree.root
    interactive = tree.interactive
    wscale = tree.wscale
    width, height = style_nodes(tree)
    divs = []
    target = "treelist_cell"
    cb = URL(r=request, f="nodecheck_clicked")
    for node in root.iternodes(phylo.PREORDER):
        if interactive is True:
            onclick = "ajax3(['%s','%s'], ['t=%s&n=%s','t=%s&n=%s'],"\
                      " ['treecss', 'clipboard'], 0);" % \
                      (URL(r=request,f="render"), URL(r=request,f="clipboard"),
                       node.tree_id, node.id, node.tree_id, node.id)
        else:
            onclick = ""
        divs.append(DIV(
            _style="position:absolute; "\
            "width:%(width)sem; height:%(height)sex; "\
            "background-color:%(background-color)s; "\
            "top:%(top)sex; left:%(left)sem" % node.hbranch_style,
            _onclick=onclick, _id="hbranch%s" % node.id,
            _title="node_id = %s" % node.id
            ))
        divs.append(DIV(
            _style="position:absolute; height:%(height)sex; "\
            "width:%(width)sem; background-color:%(background-color)s; "\
            "top:%(top)sex; left:%(left)sem" % node.vbranch_style,
            _onclick=onclick, _id="vbranch%s" % node.id,
            _title="node_id = %s" % node.id
            ))

        if len(node.children) == 1 and node.parent:
            style = node.hbranch_style.copy()
            style["left"] = style["left"]+style["width"]-0.5
            style["width"] = 0.75
            style["top"] -= style["height"]*0.5
            style["height"] *= 1.75
            #style["background-color"] = "blue"
            d = DIV(
                _style="position:absolute; "\
                "width:%(width)sem; height:%(height)sex; "\
                "background-color:%(background-color)s; "\
                "top:%(top)sex; left:%(left)sem" % style,
                _onclick=onclick, _id="singlechild%s" % node.id
                )
            divs.append(d)

        if node.istip:
            if session.snode_clickaction == "edit_label" and \
               node.id == session.selected_snode_id:
                divs.append(
                    DIV(FORM(INPUT(_type="hidden", _name="edit_node_id",
                                   _value=str(node.id)),
                             INPUT(_type="text", _name="edit_node_label",
                                   _size=8, value=node.label or "")),
                        _style="position:absolute; top:%(top)sex; "\
                        "left:%(left)sem" % node.label_style,
                        _id="label%s" % node.id)
                    )
            else:
                style=""
                if node.id in {}:#session.snode_collapsed:
                    style="background-color:#ffff99"
                if node.istip:
                    span = SPAN(node.label or "[collapsed]", _style=style,
                                _onclick=onclick)
                else:
                    span = SPAN(node.label or "[collapsed]", _style=style,
                                _onclick=onclick,
                                _title="%s leaves" % node.ntips)
                divs.append(
                    DIV(span, _style="position:absolute; top:%(top)sex; "\
                        "left:%(left)sem" % node.label_style,
                        _id="label%s" % node.id)
                    )
        else:
            style = node.label_style.copy()
            style["left"] -= 1
            style["width"] += 1
            checkid = "nodecheck_%s" % node.label
            ajax = "ajax('%s',['%s'],'%s');" % (cb, checkid, target)
            divs.append(
                DIV(SPAN(node.label or "",
                         INPUT(_type="checkbox",
                               _id=checkid,
                               value=tree.is_included(node.label),
                               _onchange=ajax),
                         _style="background-color:#ffff99;padding:1px;",
                         _onclick=onclick),
                    _style="position:absolute;width:%(width)sem;"\
                    "text-align:%(text-align)s; top:%(top)sex; "\
                    "left:%(left)sem" % style,
                    _id="label%s" % node.id)
                )

    d = DIV(_style="width:%sem; height:%sex;" % (width, height),
            *divs)
    return d

def style_nodes(tree, selected_node_id=None):
    root = tree.root
    collapsed = tree.collapsed
    wscale = tree.wscale
    scaled = tree.scaled_view
    bgcolor = "gray"
    selcolor = "red"
    leaves = root.leaves(collapsed=collapsed)
    l2d = root.leaf_distances(measure=phylo.INTERNODES,
                              collapsed=collapsed)[root]
    height = len(leaves)*3
    unit = 5.0
    width = max([ l2d[lf.id] for lf in leaves ]) * unit * wscale
    width = min(width, 70)
    rpad = max([ len(lf.label or "") for lf in leaves ]) * 0.65
    lpad = max(1, len(root.label or []) * 0.7)
    width += rpad+2 + lpad
    branchwidth = 0.75
    n2c = layout.calc_node_positions(
        root, width, height,
        lpad=lpad+1, tpad=1, bpad=2.5, rpad=rpad+1,
        collapsed=collapsed,
        scaled=scaled
        )
    n2c[root].px = 1
    for node in root.iternodes(collapsed=collapsed):
        coords = n2c[node]
        w = coords.x-coords.px
        node.hbranch_style["width"] = w
        node.hbranch_style["height"] = branchwidth
        node.hbranch_style["top"] = coords.y+0.5
        node.hbranch_style["left"] = coords.px
        node.hbranch_style["background-color"] = bgcolor
        if coords.py is None:
            coords.py = coords.y
        if coords.py < coords.y:
            h = coords.y-coords.py
            y = coords.py
        else:
            h = coords.py-coords.y
            y = coords.y
        node.vbranch_style["width"] = 0.5 * branchwidth
        node.vbranch_style["height"] = h
        node.vbranch_style["top"] = y+0.5
        node.vbranch_style["left"] = coords.px
        node.vbranch_style["background-color"] = bgcolor
        if node.istip or node.id in collapsed:
            node.label_style["top"] = coords.y-0.5
            node.label_style["left"] = coords.x+0.25
            node.label_style["width"] = len(node.label or "")
            node.label_style["text-align"] = "left"
        else:
            node.label_style["text-align"] = "right"
            node.label_style["width"] = len(node.label or "")
            node.label_style["top"] = coords.y-0.5
            node.label_style["left"] = coords.x-len(node.label or "")

        node.ref_style["top"] = coords.y-0.5
        node.ref_style["left"] = coords.x+0.25
        
    if selected_node_id:
        for n in root.iternodes(collapsed=collapsed):
            if n.id == selected_node_id:
                for m in n.iternodes():
                    m.vbranch_style["background-color"] = selcolor
                    m.hbranch_style["background-color"] = selcolor
                break
                
    return width, height
