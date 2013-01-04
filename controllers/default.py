import som
from som import newick, phylo, treeio, drawtree
from cStringIO import StringIO
import os, commands, glob, subprocess

reload(som)
for m in newick, phylo, treeio, drawtree:
    reload(m)
    
## def get_treelist():
##     key = response.session_id + ".treelist"
##     tlist = cache.ram(
##         key,
##         lambda: session.treelist or som.TreeList(),
##         time_expire=300
##         )
##     if (not tlist.trees) and session.treelist and session.treelist.trees:
##         return session.treelist
##     session.treelist = tlist
##     return tlist

def get_treelist():
    if not session.treelist:
        session.treelist = som.TreeList()
    return session.treelist

def index():
    return dict(treelist = get_treelist())

def labelsort_changed():
    tlist = get_treelist()
    try:
        i = int(request.vars.treenum)
        t = tlist.trees[i]
        t.labelsort = request.vars.labelsort
        return t.labelselect()
    except:
        pass
    return ""

def labelfilter_changed():
    tlist = get_treelist()
    try:
        i = int(request.vars.treenum)
        t = tlist.trees[i]
        t.labelfilter = request.vars.labelfilter
        return t.labelselect()
    except:
        pass
    return ""

def printer_reroot():
    tlist = get_treelist()
    try:
        i = int(request.vars.i)
        t = tlist.trees[i]
    except:
        session.flash = "no tree '%s'" % i
        redirect("index")
    v = request.vars.nodeselect
    if v:
        nodes = [ n for n in t.root.iternodes() if str(n.id) in v ]
        newroot = t.root.mrca([ n.label for n in nodes ])
        if newroot:
            newroot = phylo.reroot(t.root, newroot)
            t.newick = newick.tostring(newroot)+";"
            t.parse()
    redirect(URL(r=request,f="printer",vars=dict(i=i)))

def printer_prune_taxa():
    tlist = get_treelist()
    try:
        i = int(request.vars.i)
        t = tlist.trees[i]
    except:
        session.flash = "no tree '%s'" % i
        redirect("index")
    v = request.vars.nodeselect
    if v:
        nodes = [ n for n in t.root.iternodes() if str(n.id) in v ]
        ## for n in nodes:
        while nodes:
            n = nodes[0]
            if n.parent:
                p = n.parent
                p.children.remove(n)
                if p.parent and len(p.children) == 1:
                    gp = p.parent
                    c = p.children[0]
                    if p.length:
                        c.length += p.length
                    c.parent = gp
                    gp.children.insert(gp.children.index(p), c)
                    gp.children.remove(p)
            nodes = [ n for n in t.root.iternodes() if str(n.id) in v ]
        t.newick = newick.tostring(t.root)+";"
        t.count_nodes()
    redirect(URL(r=request,f="printer",vars=dict(i=i)))

def hyper():
    tlist = get_treelist()
    i = int(request.vars.i)
    try:
        t = tlist.trees[i]
    except:
        session.flash = "no tree '%s'" % i
        redirect("index")
    return dict(tree=t)

def spacetree():
    return hyper()

def view():
    tlist = get_treelist()
    try:
        i = int(request.vars.i)
        t = tlist.trees[i]
        return dict(tree=t)
    except:
        session.flash = "no tree '%s'" % i
        redirect("index")

def newickstr():
    tlist = get_treelist()
    try:
        i = int(request.vars.i)
        t = tlist.trees[i]
    except:
        session.flash = "no tree '%s'" % i
        redirect("index")

    fname = "%s-%s.newick" % (t.source, t.name)
    if t.printopts.title:
        fname = "_".join(t.printopts.title.split())
        if not fname.endswith("newick"):
            fname = fname + ".newick"
    response.headers["Content-Type"] = "text/plain"
    s = "attachment; filename=%s" % fname
    response.headers["Content-Disposition"] = s
    return t.newick

def printout():
    tlist = get_treelist()
    try:
        i = int(request.vars.i)
        t = tlist.trees[i]
    except:
        session.flash = "no tree '%s'" % i
        redirect("index")

    fname = "/tmp/tred-%s.pdf" % response.session_id
    title = "%s-%s" % (t.source, t.name)
    if t.printopts.title:
        title = t.printopts.title.replace(" ", "_")
    if os.path.isfile(fname):
        response.headers["Content-Type"] = "application/x-pdf"
        s = "attachment; filename=%s.pdf" % (title)
        response.headers["Content-Disposition"] = s
        return file(fname).read()

def png_preview():
    f = "/tmp/%s" % request.args[0]
    if os.path.isfile(f):
        response.headers["Content-Type"] = "image/png"
        s = "attachment; filename=%s" % f
        response.headers["Content-Disposition"] = s
        return file(f).read()

def thicken_branches(drawing_node):
    node = drawing_node
    label_numbers = {}
    for n in node.iternodes():
        if n.intlabel:
            try:
                label_numbers[n] = float(n.intlabel)
            except:
                pass
    if label_numbers:
        m = max(label_numbers.values())
        lim = None
        if  0 <= m <= 1.0:
            # posterior support
            lim = 0.95
        elif  0 <= m <= 100:
            # bootstrap values
            lim = 70
        else:
            pass
        if lim:
            for k, v in label_numbers.items():
                if v >= lim:
                    k.thicken = True
    
def pdfsingle():
    tlist = get_treelist()
    try:
        i = int(request.vars.i)
        t = tlist.trees[i]
        if request.vars.ladderize:
            t.root.order_subtrees_by_size(
                recurse=True,reverse=bool(request.vars.rev)
                )
    except:
        session.flash = "no tree '%s'" % i
        redirect("index")

    fname = "tred-"+response.session_id
    opts = t.printopts
    v = request.vars

    if v.parsevars:
        t.labelfilter = v.labelfilter or ""
        t.labeltype = v.labeltype or t.labeltype
        t.labelsort = v.labelsort or t.labelsort

        opts.title = v.title or opts.title or "%s-%s" % (t.source, t.name)
        opts.pagesize = v.pagesize or opts.pagesize or "letter"
        #print opts.pagesize
        opts.draw_phylogram = v.draw_phylogram and t.phylogram
        opts.baseheight = float(v.baseheight or 0) or opts.baseheight
        opts.unitwidth = float(v.unitwidth or 0) or opts.unitwidth
        opts.border = float(v.border or 0) or opts.border
        opts.vpad = float(v.vpad or 1.1)
        if v.draw_intlabels and "intlabel" not in opts.visible:
            opts.visible.append("intlabel")
        if (not v.draw_intlabels) and "intlabel" in opts.visible:
            opts.visible.remove("intlabel")

    node, mapping = drawtree.traverse(t.root, opts)
    thicken_branches(node)

    node.set_attr("vpad", opts.vpad, 1)
    d = drawtree.draw(node, opts)
    t.drawing = d
    buf = drawtree.render_pdf(d, opts)

    response.headers["Content-Type"] = "application/x-pdf"
    f = t.printopts.title + ".pdf"
    s = "attachment; filename=%s" % f
    response.headers["Content-Disposition"] = s
    return buf.getvalue()


def pdf2svg():
    tlist = get_treelist()
    try:
        i = int(request.vars.i)
        t = tlist.trees[i]
        if request.vars.ladderize:
            t.root.order_subtrees_by_size(
                recurse=True,reverse=bool(request.vars.rev)
                )
    except:
        session.flash = "no tree '%s'" % i
        redirect("index")

    fname = "tred-"+response.session_id
    opts = t.printopts
    v = request.vars

    if v.parsevars:
        t.labelfilter = v.labelfilter or ""
        t.labeltype = v.labeltype or t.labeltype
        t.labelsort = v.labelsort or t.labelsort

        opts.title = v.title or opts.title or "%s-%s" % (t.source, t.name)
        opts.pagesize = v.pagesize or opts.pagesize or "letter"
        #print opts.pagesize
        opts.draw_phylogram = v.draw_phylogram and t.phylogram
        opts.baseheight = float(v.baseheight or 0) or opts.baseheight
        opts.unitwidth = float(v.unitwidth or 0) or opts.unitwidth
        opts.border = float(v.border or 0) or opts.border
        opts.vpad = float(v.vpad or 1.1)
        if v.draw_intlabels and "intlabel" not in opts.visible:
            opts.visible.append("intlabel")
        if (not v.draw_intlabels) and "intlabel" in opts.visible:
            opts.visible.remove("intlabel")

    node, mapping = drawtree.traverse(t.root, opts)
    thicken_branches(node)

    node.set_attr("vpad", opts.vpad, 1)
    d = drawtree.draw(node, opts)
    t.drawing = d
    buf = drawtree.render_pdf(d, opts)
    
    proc = subprocess.Popen(("/usr/bin/pstoedit", "-f", "plot-svg"),
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    out, err = proc.communicate(buf.getvalue())
    out = out.split("\n")
    out[2] = '<svg version="1.1" baseProfile="full" id="body" '\
             'width="%s" height="%s" viewBox="0 0 1 1" '\
             'preserveAspectRatio="none" '\
             'xmlns="http://www.w3.org/2000/svg" '\
             'xmlns:xlink="http://www.w3.org/1999/xlink" '\
             'xmlns:ev="http://www.w3.org/2001/xml-events">' \
             % (d.width, d.height)
    out[5] = ""
    response.headers["Content-Type"] = "image/svg"
    f = t.printopts.title + ".svg"
    s = "attachment; filename=%s" % f
    response.headers["Content-Disposition"] = s
    return "\n".join(out)

def printer():
    tlist = get_treelist()
    try:
        i = int(request.vars.i)
    except TypeError:
        redirect("index")
    try:
        t = tlist.trees[i]
    except IndexError:
        session.flash = "no tree '%s'" % i
        redirect("index")

    if request.vars.ladderize:
        t.root.order_subtrees_by_size(
            recurse=True,reverse=bool(request.vars.rev)
            )
        t.newick = newick.tostring(t.root)+";"

    fname = "tred-"+response.session_id
    opts = t.printopts
    v = request.vars

    if v.parsevars:
        t.labelfilter = v.labelfilter or ""
        t.labeltype = v.labeltype or t.labeltype
        t.labelsort = v.labelsort or t.labelsort

        opts.title = v.title or opts.title or "%s-%s" % (t.source, t.name)
        opts.pagesize = v.pagesize or opts.pagesize or "letter"
        #print opts.pagesize
        opts.draw_phylogram = v.draw_phylogram and t.phylogram
        opts.baseheight = float(v.baseheight or 0) or opts.baseheight
        opts.unitwidth = float(v.unitwidth or 0) or opts.unitwidth
        opts.border = float(v.border or 0) or opts.border
        opts.vpad = float(v.vpad or 1.1)
        if v.draw_intlabels and "intlabel" not in opts.visible:
            opts.visible.append("intlabel")
        if (not v.draw_intlabels) and "intlabel" in opts.visible:
            opts.visible.remove("intlabel")

    node, mapping = drawtree.traverse(t.root, opts)
    thicken_branches(node)

    node.set_attr("vpad", opts.vpad, 1)
    d = drawtree.draw(node, opts)
    t.drawing = d
    buf = StringIO()
    npages, scalefact = drawtree.render_multipage(d, opts, buf)
    f = file("/tmp/%s.pdf" % fname, "w")
    f.write(buf.getvalue())
    f.close()
    commands.getoutput("rm /tmp/%s*.png" % fname)
    cmd = "convert /tmp/%s.pdf /tmp/%s.png" % (fname, fname)
    exit, out = commands.getstatusoutput(cmd)
    pngs = glob.glob("/tmp/%s*.png" % fname)
    if pngs:
        pngs = [ os.path.split(x)[1] for x in pngs ]
        pngs.sort()
    if scalefact < 1.0:
        response.flash = "To fit the page width, "\
                         "the drawing has been scaled by %0.2f" % scalefact
    return dict(tree=t, pngs=pngs)

def svg():        
    tlist = get_treelist()
    try:
        i = int(request.vars.i)
        t = tlist.trees[i]
    except:
        session.flash = "no tree '%s'" % i
        redirect("index")

    opts = t.printopts
    node, mapping = drawtree.traverse(t.root, opts)
    thicken_branches(node)
    node.set_attr("vpad", opts.vpad, 1)
    off = t.printopts.border
    node.translate(off,off)
    d = drawtree.draw(node, opts)
    #d.scale(1.9,1.9)
    x1, y1, x2, y2 = d.getBounds()
    d.width = (x2-x1)*0.63
    d.height = (y2-y1)*0.598
    response.headers["Content-Type"] = "image/svg"
    f = t.printopts.title + ".svg"
    s = "attachment; filename=%s" % f
    response.headers["Content-Disposition"] = s
    return drawtree.render_svg(d, opts)

def hypertree():
    tlist = get_treelist()
    try:
        i = int(request.vars.i)
        t = tlist.trees[i]
        return dict(tree=t)
    except:
        session.flash = "no tree '%s'" % i
        redirect("index")
    return dict(tree=t)

def delete_all():
    cache.ram.clear()
    session.treelist = None
    redirect(request.vars.f or "index")

def delsrc():
    tlist = get_treelist()
    s = request.vars.s
    v = []
    if s:
        for t in tlist.trees:
            if t.source == s:
                v.append(t)
        for t in v:
            tlist.trees.remove(t)
    redirect("index")
                

def delete():
    tlist = get_treelist()
    try:
        i = int(request.vars.i)
        del tlist.trees[i]
    except:
        session.flash = "no tree '%s'" % i
    redirect("index")

def select_tree():
    if request.vars.i != None:
        try:
            session.treelist.select_single(int(request.vars.i))
        except:
            session.flash = "unable to select tree", request.vars.i
    redirect(request.vars.f or "index")

def select_multiple():
    redirect("index")

def upload_example():
    s = request.vars.s
    fname = "applications/%s/static/%s.newick" % (request.application,s)
    if os.path.exists(fname):
        treelist = get_treelist()
        t = som.Tree(s, file(fname).read(), "Example")
        treelist.add(t)
    redirect("index")

def upload_trees():
    buf = request.vars.s
    #print request.vars.f
    source = "Pasted"
    if buf:
        buf = StringIO(buf)
    elif request.vars.f not in (None, ""):
        buf = request.vars.f.file
        source = request.vars.f.filename
    else:
        session.flash = "Paste trees into text box or upload file"
        redirect("index")
    treelist = get_treelist()
    for name, newick in treeio.extract_newicks_from_buffer(buf):
        t = som.Tree(name, newick, source)
        treelist.add(t)
    ## treelist.trees.extend([
    ##     som.Tree(x[0], x[1], source)
    ##     for x in treeio.extract_newicks_from_buffer(buf)
    ##     ])
    redirect("index")

