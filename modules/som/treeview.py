import layout
import phylo
import newick
from gluon.html import *

def node2css(root, request, wscale=1.0, scaled=False):
    width, height = style_nodes(root, request, wscale=wscale,
                                scaled=bool(scaled))
    divs = []
    for node in root.iternodes(phylo.PREORDER):
        divs.append(DIV(
            _style="position:absolute; "\
            "width:%(width)sem; height:%(height)sex; "\
            "background-color:%(background-color)s; "\
            "top:%(top)sex; left:%(left)sem" % node.hbranch_style,
            _id="hbranch%s" % node.id,
            _title="node_id = %s" % node.id
            ))
        divs.append(DIV(
            _style="position:absolute; height:%(height)sex; "\
            "width:%(width)sem; background-color:%(background-color)s; "\
            "top:%(top)sex; left:%(left)sem" % node.vbranch_style,
            _id="vbranch%s" % node.id,
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
                _id="singlechild%s" % node.id
                )
            divs.append(d)

        if node.istip:
            ## if session.snode_clickaction == "edit_label" and \
               ## node.id == session.selected_snode_id:
            if False:
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
                    style="background-color:yellow"
                if node.istip:
                    span = SPAN(node.label or "[collapsed]", _style=style)
                else:
                    span = SPAN(node.label or "[collapsed]", _style=style,
                                _title="%s leaves" % node.ntips)
                divs.append(
                    DIV(span, _style="position:absolute; top:%(top)sex; "\
                        "left:%(left)sem" % node.label_style,
                        _id="label%s" % node.id)
                    )
        else:
            divs.append(
                DIV(SPAN(node.label or "",
                         _style="background-color:yellow"),
                    _style="position:absolute; width:%(width)sem; "\
                    "text-align:%(text-align)s; top:%(top)sex; "\
                    "left:%(left)sem" % node.label_style,
                    _id="label%s" % node.id)
                )
    d = DIV(_style="width:%sem; height:%sex;" % (width, height), *divs)
    return d


def style_nodes(root, request, selected_node_id=None, wscale=1.0, scaled=True):
    bgcolor = "black"
    selcolor = "red"
    leaves = root.leaves()
    l2d = root.leaf_distances(measure=phylo.INTERNODES)[root.id]
    height = len(leaves)*3
    unit = 3.0
    width = max([ l2d[lf.id] for lf in leaves ]) * unit * wscale
    width = min(width, 65)
    rpad = max([ len(lf.label or "") for lf in leaves ]) * 0.7
    lpad = max(1, len(root.label or []) * 0.7)
    width += rpad+2 + lpad
    branchwidth = 0.75
    n2c = layout.calc_node_positions(
        root, width, height,
        lpad=lpad+1, tpad=1, bpad=2.5, rpad=rpad+1,
        scaled=scaled
        )
    n2c[root].px = 1
    for node in root.iternodes():
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
        if node.istip:
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
        for n in root.iternodes():
            if n.id == selected_node_id:
                for m in n.iternodes():
                    m.vbranch_style["background-color"] = selcolor
                    m.hbranch_style["background-color"] = selcolor
                break
                
    return width, height
