import applications.tred.modules.phylo as phylo
import applications.tred.modules.newick as newick
import applications.tred.modules.layout as layout

def tree_upload_form():
    form = FORM(TABLE(
        TR(DIV("Newick string:",
               DIV(INPUT(_type="button", _value="Preview",
                         _onclick="ajax('%s', ['newick'], 'preview')" %\
                         URL(r=request,f="newick_preview")),
                   _style="padding-top:1ex",
                   )),
           TEXTAREA(_name="newick", _rows=6, _cols=80, _id="newick",
                    requires=[IS_NOT_EMPTY()])),
        TR(DIV(_id="nodeclick"),
           DIV(_id="preview",
               _style="position:relative;width:100%;border-style:solid; border-width:1px; border-color:lightgray;")),
        TR("",
           INPUT(_type="submit"))
        ))
    return form

def upload():
    form = tree_upload_form()
    if not session.collapsed:
        session.collapsed = {}
    if form.accepts(request.vars, session):
        try:
            n = newick.parse(form.vars.newick)
        except newick.ParseError, e:
            response.flash = e

    elif form.errors:
        response.flash = "Unable to upload tree, see below"
    else:
        pass
    return dict(form=form)

def newick2css(s):
    root = newick.parse(s)
    for i, n in enumerate(root.iternodes()):
        n.id = i
    return nodes2css(root, interactive=False, wscale=1.0)

def nodeclick_options():
    node_id = int(request.vars.n or -1)
    if node_id > 0:
        a = A("node %s" % node_id, _href="foo")
        return a
    else:
        return A("")

def expandall():
    session.collapsed = {}
    return render()

def render():
    node_id = int(request.vars.n or -1)
    tree_id = int(request.vars.t or -1)
    if node_id > -1:
        session.selected_node_id = node_id
    else:
        session.selected_node_id = None

    if not session.collapsed:
        session.collapsed = {}

    if session.clickaction == "collapse_view" and session.selected_node_id:
        print "1", session.collapsed
        session.collapsed[session.selected_node_id] = 1
        print "2", session.collapsed
    elif session.clickaction == "expand_view" and \
         session.selected_node_id in session.collapsed:
        del session.collapsed[session.selected_node_id]
        
    if tree_id != session.selected_tree_id and tree_id > -1:
        root = restore_tree(tree_id)
    else:
        rec = db(db.snode.id==session.root_node_id).select()[0]
        root = restore_tree(rec.stree_id)
    return nodes2css(root)

def style_nodes(root, wscale=1.0):
    return style_nodes(root, collapsed=session.collapsed,
                       wscale=wscale,
                       selected_node_id=session.selected_node_id)
## def style_nodes(root, wscale=1.0):
##     bgcolor = "black"
##     selcolor = "red"
##     session.collapsed = session.collapsed or {}
##     leaves = root.leaves(collapsed=session.collapsed)
##     l2d = root.leaf_distances(measure=phylo.INTERNODES,
##                               collapsed=session.collapsed)[root]
##     width = max([ l2d[lf.id] for lf in leaves ]) * 3 * wscale
##     rpad = max([ len(lf.label or "") for lf in leaves ]) * 0.7
##     lpad = max(1, len(root.label or []) * 0.7)
##     width += rpad+2 + lpad
##     height = len(leaves)*3
##     branchwidth = 0.75
##     n2c = layout.calc_node_positions(
##         root, width, height,
##         lpad=lpad+1, tpad=1, bpad=2.5, rpad=rpad+1,
##         collapsed=session.collapsed,
##         scaled=False
##         )
##     n2c[root].px = 1
##     for node in root.iternodes(collapsed=session.collapsed):
##         coords = n2c[node]
##         w = coords.x-coords.px
## ##         onclick = "ajax('%s', [], 'treecss')" % \
## ##                   URL(r=request,f="render?t=%s&n=%s" % \
## ##                       (node.stree_id, node.id))
##         node.hbranch_style["width"] = w
##         node.hbranch_style["height"] = branchwidth
##         node.hbranch_style["top"] = coords.y+0.5
##         node.hbranch_style["left"] = coords.px
##         node.hbranch_style["background-color"] = bgcolor
##         if coords.py is None:
##             coords.py = coords.y
##         if coords.py < coords.y:
##             h = coords.y-coords.py
##             y = coords.py
##         else:
##             h = coords.py-coords.y
##             y = coords.y
##         node.vbranch_style["width"] = 0.5 * branchwidth
##         node.vbranch_style["height"] = h
##         node.vbranch_style["top"] = y+0.5
##         node.vbranch_style["left"] = coords.px
##         node.vbranch_style["background-color"] = bgcolor
##         if node.istip or node.id in session.collapsed:
##             node.label_style["top"] = coords.y-0.5
##             node.label_style["left"] = coords.x+0.25
##         else:
##             node.label_style["text-align"] = "right"
##             node.label_style["width"] = len(node.label or "")
##             node.label_style["top"] = coords.y-0.5
##             node.label_style["left"] = coords.x-len(node.label or "")

##     if session.selected_node_id:
##         for n in root.iternodes(collapsed=session.collapsed):
##             if n.id == session.selected_node_id:
##                 for m in n.iternodes():
##                     m.vbranch_style["background-color"] = selcolor
##                     m.hbranch_style["background-color"] = selcolor
##                 break
                
##     return width, height

def clipboard():
    if not session.clipboard:
        session.clipboard = []
    if request.vars.e:
        session.clipboard = []
    tree_id = request.vars.t or -1
    node_id = request.vars.n or -1
    if tree_id > -1 and node_id > -1 and session.clickaction == "copy":
        tlab = db(db.stree.id==tree_id).select()[0].tree_title or ""
        nrec = db(db.snode.id==node_id).select()[0]
        nlab = nrec.label or ""
        if not nlab and not nrec.parent_id:
            nlab = "root"
        x = ("stree", tree_id, tlab, node_id, nlab)
        if x not in session.clipboard:
            session.clipboard.insert(0, x)
    rv = [DIV("Clipboard ",
              A("[Empty]",
                _onclick="ajax2('%s','e=1','clipboard');return true" \
                % URL(r=request,f="clipboard")),
              _class="sidemenu_header")]
    for ttype, t, tlab, n, nlab in session.clipboard:
        rv.append(
            DIV("%s:%s" % (tlab or t, nlab or n),
                A("[X]", _title="delete",
                  _href=URL(r=request, f="clipdel",
                            vars=dict(t=t, n=n, ttype=ttype))),
                _style="padding-top:0.25em")
            )
    return DIV(_class="sidemenu", *rv)

def clipdel():
    ttype = request.vars.ttype
    t = request.vars.t
    n = request.vars.n
##     tlab = db(db.stree.id==int(t)).select()[0].tree_title or ""
##     nlab = db(db.snode.id==int(n)).select()[0].label or ""
    for tt, ct, tlab, cn, nlab in session.clipboard:
        if tt == ttype and ct == t and cn == n:
            session.clipboard.remove((ttype, t, tlab, n, nlab))
    redirect(URL(r=request,f="view/%s" % session.selected_tree_id))

## def clipsel():
##     t = request.vars.t
##     n = request.vars.n
##     tlab = db(db.stree.id==int(t)).select()[0].tree_title or ""
##     nlab = db(db.snode.id==int(n)).select()[0].label or ""

def nodes2css(root, interactive=True, wscale=1.0):
    width, height = style_nodes(root, wscale=wscale)
    divs = []
    for node in root.iternodes(phylo.PREORDER,
                               collapsed=session.collapsed or {}):
        if interactive is True:
            onclick = "ajax3(['%s','%s'], ['t=%s&n=%s','t=%s&n=%s'],"\
                      " ['treecss', 'clipboard'], 0);" % \
                      (URL(r=request,f="render"), URL(r=request,f="clipboard"),
                       node.stree_id, node.id, node.stree_id, node.id)
        else:
            onclick = ""
        divs.append(DIV(
            _style="position:absolute; "\
            "width:%(width)sem; height:%(height)sex; "\
            "background-color:%(background-color)s; "\
            "top:%(top)sex; left:%(left)sem" % node.hbranch_style,
            _onclick=onclick, _id="hbranch%s" % node.id
            ))
        divs.append(DIV(
            _style="position:absolute; height:%(height)sex; "\
            "width:%(width)sem; background-color:%(background-color)s; "\
            "top:%(top)sex; left:%(left)sem" % node.vbranch_style,
            _onclick=onclick, _id="vbranch%s" % node.id
            ))
        if node.istip or node.id in (session.collapsed or []):
            if session.clickaction == "edit_label" and \
               node.id == session.selected_node_id:
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
                if node.id in session.collapsed:
                    style="background-color:yellow"
                divs.append(
                    DIV(SPAN(node.label or "[collapsed]", _style=style,
                             _onclick=onclick),
                        _style="position:absolute; top:%(top)sex; "\
                        "left:%(left)sem" % node.label_style,
                        _id="label%s" % node.id)
                    )
        else:
            if session.clickaction == "edit_label" and \
               node.id == session.selected_node_id:
                style = node.label_style.copy()
                if not node.label:
                    style["left"] = style["left"] - 6
                divs.append(
                    DIV(FORM(INPUT(_type="hidden", _name="edit_node_id",
                                   _value=str(node.id)),
                             INPUT(_type="text", _name="edit_node_label",
                                   _size=8, value=node.label or "")),
                        _style="position:absolute; width:%(width)sem; "\
                        "text-align:%(text-align)s; top:%(top)sex; "\
                        "left:%(left)sem" % style,
                        _id="label%s" % node.id)
                    )
            else:
                divs.append(
                    DIV(SPAN(node.label or "", _style="background-color:yellow",
                             _onclick=onclick),
                        _style="position:absolute; width:%(width)sem; "\
                        "text-align:%(text-align)s; top:%(top)sex; "\
                        "left:%(left)sem" % node.label_style,
                        _id="label%s" % node.id)
                    )
##             divs.append(
##                 DIV(SPAN(node.label or "", _style="background-color:yellow",
##                          _onclick="ajax2('%s','n=%s','label%s')" % \
##                          (URL(r=request,f="editlabel"), node.id, node.id)),
##                     _style="position:absolute; width:%(width)sem; "\
##                     "text-align:%(text-align)s; top:%(top)sex; "\
##                     "left:%(left)sem" % node.label_style,
##                     _id="label%s" % node.id)
##                 )
    d = DIV(_style="width:%sem; height:%sex;"\
            % (width, height),
            *divs)
    return d

def editlabel():
    node_id = int(request.vars.n or 0)
    rec = db(db.snode.id==node_id).select(db.snode.ALL)[0]
    return FORM(
        INPUT(_type="hidden", _name="edit_node_id", _value=request.vars.n),
        INPUT(_type="text", _name="edit_node_label", _size=10,
              value=rec.label or "")
        )

## def edit_support():
##     node_id = int(request.vars.n or 0)
##     rec = db(db.snode.id==node_id).select(db.snode.ALL)[0]
##     return FORM(
##         INPUT(_type="hidden", _name="edit_node_id", _value=request.vars.n),
##         INPUT(_type="text", _name="edit_node_support", _size=10,
##               value=rec.support or "")
##         )

def newick_preview():
    if request.vars.newick:
        d = newick2css(request.vars.newick)
        return d.xml()
    return ""

def dbnodes2tree(tree_id):
    nodes = db(db.snode.stree_id==tree_id).select(
        orderby=db.snode.id
        )
    nodes = list(nodes)
    root = [ n for n in nodes if n.parent_id is None ]
    assert root and len(root) == 1
    root = root[0]
    nodes.remove(root)
    r = phylo.Node()
    r.stree_id = tree_id
    r.label = root.label
    r.length = root.length
    r.bootstrap_support = root.bootstrap_support
    r.posterior_support = root.posterior_support
    r.other_support = root.other_support
    r.other_support_type = root.other_support_type
    r.id = root.id
    r.parent_id = root.parent_id
    v = {r.id: r}
    while nodes:
        node = nodes.pop(0)
        n = phylo.Node()
        n.stree_id = tree_id
        n.label = node.label
        n.istip = node.istip
        n.length = node.length
        n.bootstrap_support = node.bootstrap_support
        n.posterior_support = node.posterior_support
        n.other_support = node.other_support
        n.other_support_type = node.other_support_type
        n.id = node.id
        n.parent_id = node.parent_id
        v[n.id] = n
        assert n.parent_id in v, "%s" % n.parent_id
        p = v[n.parent_id]
        p.add_child(n)
    return r

def restore_tree(tree_id):
    rec = db(db.stree.id==tree_id).select()[0]
    r = db((db.snode.stree_id==rec.id)&
           (db.snode.parent_id==None)).select()
    assert len(r) == 1
    root = dbnodes2tree(r[0].stree_id)
    session.selected_tree_id = tree_id
    session.root_node_id = root.id
    #session.selected_node_id = None
    return root

## def restore_node(node_id):
##     rec = db(db.snode.id==node_id).select()[0]
##     return rec

def delete_confirm():
    request.subapp = A("source trees", _href=URL(a=request.application,
                                                 c=request.controller,
                                                 f="index"))
    response.menu = [
        ["Source trees", False, URL(r=request, f="index")],
        ["Grafted trees", False,
         URL(a=request.application,c="gtree",f="index")],
        ]
    tree_id = int(request.args[0])
    rec = db(db.stree.id==tree_id).select()[0]
    assert rec
    rows = db((db.gnode.snode_id==db.snode.id) & \
              (db.gtree.id==db.gnode.gtree_id) & \
              (db.snode.stree_id==tree_id)).select(
        db.gtree.id, db.gtree.title, db.gtree.contributor,
        groupby=db.gnode.gtree_id
        )
    gtrees = []
    delete_link = ""
    if rows:
        w = "trees"
        if len(rows) == 1:
            w = "tree"
        response.flash = "This source tree cannot be deleted because it is "\
                         "currently referenced in %s grafted %s" % \
                         (len(rows), w)
        for r in rows:
            url = URL(a=request.application, c="gtree", f="view/%s" % r.id)
            gtrees.append(A("[%s by %s]" % (r.title, r.contributor), _href=url))
        gtrees = OL(*gtrees)
    else:
        url = URL(r=request, f="delete/%s" % tree_id)
        response.flash = "You are about to permanently delete this "\
                         "source tree, contributed by %s" % rec.contributor
        delete_link = A("[I'm ok with that]", _href=url)

    return dict(gtrees=gtrees or "", delete_link=delete_link)
    
def delete():
    if request.args and int(request.args[0]):
        treeid = int(request.args[0])
        rec = db(db.stree.id==treeid).select()[0]
        assert rec
        db(db.stree.id==treeid).delete()
        db(db.snode.stree_id==treeid).delete()
        for x in (session.recently_viewed_strees or []):
            if x[0] == treeid:
                session.recently_viewed_strees.remove(x)
                
    response.flash = "Tree deleted."
    session.flash = response.flash
    redirect(URL(r=request,f="index"))

def view():
    request.subapp = A("source trees", _href=URL(a=request.application,
                                                 c=request.controller,
                                                 f="index"))
##     response.menu = [
##         ["Search", False, URL(a=request.application,c=request.controller,
##                               f="index")],
##         ["Upload", False, URL(r=request, f="upload")],
##         ]
    response.menu = [
        ["Source trees", False, URL(r=request, f="index")],
        ["Grafted trees", False,
         URL(a=request.application,c="gtree",f="index")],
        ]
    session.clickaction = session.clickaction or "copy"
    session.collapsed = session.collapsed or {}

    #print request.form
    if request.vars.edit_node_id:
        i = int(request.vars.edit_node_id)
        db(db.snode.id==i).update(label=request.vars.edit_node_label or None,
                                  mtime=datetime.datetime.now())
        session.selected_node_id = None

##     if session.selected_node_id:
##         print "view: selected node", session.selected_node_id
##     else:
##         print "view: no selected node"

    if request.vars.id:
        i = int(request.vars.id)
    elif request.args:
        i = int(request.args[0])
    else:
        session.root_node_id = None
        session.selected_node_id = None
        raise ValueError, "id required"

    if (not session.root_node_id) or \
           (session.root_node_id and session.selected_tree_id != i):
        root = restore_tree(i)
    else:
        root = restore_tree(session.selected_tree_id)
##     print "view: root node", session.root_node_id
    pre = nodes2css(root)

    rec = db(db.stree.id==i).select()[0]
    if not session.recently_viewed_strees:
        session.recently_viewed_strees = []
    s = treerec2str(rec)
    v = (i, s)
    try:
        session.recently_viewed_strees.remove(v)
    except:
        pass
    session.recently_viewed_strees.insert(0, v)

    cb = clipboard()
    tm = treemenu()
    nwk = "%s;" % newick.tostring(root)
    return dict(pre=pre,rec=rec,root=root,clickoptions=clickoptions(),
                treerecstr=s, newick=nwk,
                clipboard=cb, treemenu=tm)

def iframe():
    if request.vars.id:
        i = int(request.vars.id)
    elif request.args:
        i = int(request.args[0])
    else:
        session.root_node_id = None
        session.selected_node_id = None
        raise ValueError, "id required"

    if (not session.root_node_id) or \
           (session.root_node_id and session.selected_tree_id != i):
        root = restore_tree(i)
    else:
        root = restore_tree(session.selected_tree_id)
    pre = nodes2css(root)
    return dict(pre=pre)

def treemenu():
    rv = [
        DIV("Tree menu", _class="sidemenu_header"),
        DIV(A("[Copy]",
              _onclick="ajax2('%s', 't=%s&n=%s', 'clipboard')" % \
              (URL(r=request,f="clipboard"),
               session.selected_tree_id,
               session.root_node_id))),
        DIV(A("[Expand all]",
              _onclick="ajax2('%s','expandall=1','treecss')" % \
              URL(r=request,f="expandall"))),
        DIV(A("[Toggle tree/newick]",
              _href=URL(r=request,f='toggle_view')),
            _id="newick_toggle"),
        HR(_style="padding:0.25em; border:0px"),
        DIV(A("[Create grafted tree]",
              _href=URL(a=request.application,
                        c="gtree",
                        f="new_gtree/%s" % session.root_node_id)))
        ]
    return DIV(_class="sidemenu", *rv)

def toggle_view():
    if (not session.stree_view) or session.stree_view == "tree":
        session.stree_view = "newick"
    else:
        session.stree_view = "tree"
    redirect(URL(r=request,f="view/%s" % session.selected_tree_id))

def clickoptions():
    clickoptions = DIV(
        DIV("Click action:", _class="sidemenu_header"),
        DIV(INPUT(_name="clickoption", _type="radio", _value="copy",
                  _onclick="ajax2('%s', 'a=copy', 'clickoptions')" % \
                  URL(r=request,f="set_clickaction"),
                  value=session.clickaction or "copy"), "Copy to clipboard"),
        DIV(INPUT(_name="clickoption", _type="radio", _value="collapse_view",
                  _onclick="ajax2('%s', 'a=collapse_view', 'clickoptions')" % \
                  URL(r=request,f="set_clickaction"),
                  value=session.clickaction or "copy"), "Collapse view"),
        DIV(INPUT(_name="clickoption", _type="radio", _value="expand_view",
                  _onclick="ajax2('%s', 'a=expand_view', 'clickoptions')" % \
                  URL(r=request,f="set_clickaction"),
                  value=session.clickaction or "copy"), "Expand view"),
        DIV(INPUT(_name="clickoption", _type="radio", _value="edit_label",
                  _onclick="ajax2('%s', 'a=edit_label', 'clickoptions')" % \
                  URL(r=request,f="set_clickaction"),
                  value=session.clickaction or "copy"), "Edit label"),
        DIV(nodeclick_options(), _id="nodeclick"),
        _class="sidemenu")
    return clickoptions

def set_clickaction():
    session.clickaction = request.vars.a
    return clickoptions()

def index():
    request.subapp = A("source trees", _href=URL(a=request.application,
                                                 c=request.controller,
                                                 f="index"))
##     response.menu = [
##         ["Search", True, URL(a=request.application,c="default",f="index")],
##         ["Upload", False, URL(r=request, f="upload")],
##         ]
    response.menu = [
        ["Source trees", False, URL(r=request, f="index")],
        ["Grafted trees", False,
         URL(a=request.application,c="gtree",f="index")],
        ]
    form = FORM(TABLE(TR(TD(INPUT(_name="t", _size=20),
                            " (search in title, newick, citation)"),
                         TD("Uploaded by: ", INPUT(_name="u", _size=12))),
                      TR(INPUT(_type="Submit", _value="Submit")),
                      _style="width:95%"),
                )

    results = []; recent_uploads = []
    if form.accepts(request.vars, session):
        t = None
        if form.vars.t:
            t = db.stree.tree_title.like("%"+form.vars.t+"%")|\
                db.stree.citation.like("%"+form.vars.t+"%")|\
                db.stree.newick.like("%"+form.vars.t+"%")
        if form.vars.u:
            u = db.stree.contributor.like("%"+form.vars.u+"%")
            if t: t = t&u
            else: t = u
        rows = db(t).select(db.stree.ALL)
        if rows:
            if form.vars.t and (not form.vars.u):
                response.flash = "%s matches for '%s'" % \
                                 (len(rows), form.vars.t)
            if (not form.vars.t) and form.vars.u:
                response.flash = "%s trees uploaded by '%s'" % \
                                 (len(rows), form.vars.u)
            if form.vars.t and form.vars.u:
                response.flash = "%s matches for '%s' uploaded by '%s'" % \
                                 (len(rows), form.vars.t, form.vars.u)
                
            for row in rows:
                s = treerec2str(row)
                results.append(
                    LI(A(s, _href=URL(r=request, f="view", args=[row.id])))
                    )
            results = OL(*results)
        else:
            response.flash = "No matches for '%s'" % form.vars.t

    recently_viewed = []
    if session.recently_viewed_strees:
        rv = []
        for i, s in session.recently_viewed_strees[:10]:
            rv.append(A(s, _href=URL(r=request, f="view", args=[i])))
        recently_viewed = OL(*rv)
    return dict(form=form, results=results,
                recently_viewed=recently_viewed,
                recent_uploads=recent_uploads_OL())


def recent_uploads_OL():
    v = []
    rows = db().select(db.stree.ALL,
                       limitby=(0,10),
                       orderby=~db.stree.upload_date)
    for row in rows:
        s = treerec2str(row)
        v.append(
            LI(A(s, _href=URL(r=request, f="view", args=[row.id])))
            )
    return OL(*v)    

def style_nodes(root, collapsed={}, selected_node_id=None, wscale=1.0):
    bgcolor = "black"
    selcolor = "red"
    leaves = root.leaves(collapsed=collapsed)
    l2d = root.leaf_distances(measure=phylo.INTERNODES,
                              collapsed=collapsed)[root]
    width = max([ l2d[lf.id] for lf in leaves ]) * 3 * wscale
    rpad = max([ len(lf.label or "") for lf in leaves ]) * 0.7
    lpad = max(1, len(root.label or []) * 0.7)
    width += rpad+2 + lpad
    height = len(leaves)*3
    branchwidth = 0.75
    n2c = layout.calc_node_positions(
        root, width, height,
        lpad=lpad+1, tpad=1, bpad=2.5, rpad=rpad+1,
        collapsed=collapsed,
        scaled=False
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
        else:
            node.label_style["text-align"] = "right"
            node.label_style["width"] = len(node.label or "")
            node.label_style["top"] = coords.y-0.5
            node.label_style["left"] = coords.x-len(node.label or "")

    if selected_node_id:
        for n in root.iternodes(collapsed=collapsed):
            if n.id == selected_node_id:
                for m in n.iternodes():
                    m.vbranch_style["background-color"] = selcolor
                    m.hbranch_style["background-color"] = selcolor
                break
                
    return width, height
