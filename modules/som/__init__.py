import types
from gluon.html import *
from gluon.sqlhtml import *
from gluon.storage import Storage
from . import newick, treeview, phylo, treeio, drawtree, svgfig

class PrintOpts:
    def __init__(self, **kwargs):
        self.title = ""
        self.visible = ["intlabel"]
        self.pagesize = "letter"
        self.landscape = False
        self.draw_phylogram = False
        self.baseheight = 10
        self.unitwidth = 30
        self.lengths_are_support = False
        self.thicken = False
        self.scale = False
        self.format = "pdf"
        self.verbose = False
        self.unitwidth = self.baseheight*3.0
        self.border = 20
        self.vpad = 1.1

    def pgsize_select_html(self):
        pgsize_opts = [
            OPTION(x, _value=x) for x in ("letter", "A4")
            ]
        return SELECT(
            _name = "pagesize",
            value = self.pagesize,
            _id = "pagesize_select",
            *pgsize_opts
            )

    def scalebranches_select_html(self):
        v = self.draw_phylogram
        return INPUT(
            _name = "draw_phylogram",
            _type = "checkbox",
            value = v,
            _id = "scalebranches_select"
            )

class Tree:
    def __init__(self, name, newick, source):
        self.name = name
        self.newick = newick
        self.source = source
        self.root = None
        self.phylogram = False
        self.printopts = PrintOpts()
        self.viewopts = Storage()
        self.viewopts.wscale = 1.0
        self.drawing = None
        self.labelfilter = None
        self.labelsort = "topological"
        self.labeltype = "tips_only"
        self.selected_nodes = set()
        self.parse()

    def labeltype_select(self, request):
        clades = False
        for n in self.root.iternodes():
            if (not n.istip) and n.label:
                clades = True
                break
        if clades:
            opts = [
                OPTION(s, _value=s.replace(" ", "_")) for s in \
                ("tips only", "clades only", "tips and clades")
                ]
        else:
            opts = [
                OPTION(s, _value=s.replace(" ", "_")) for s in \
                ("tips only",)
                ]
        u = URL(r=request, f="labelselect")
        js = "ajax('%s', ['labeltype'], 'nodeselect')" % u
        return SELECT(_id="labeltype", _onchange=js,
                      value=self.labeltype, *opts)

    def sortorder_select(self, request):
        opts = [
            OPTION(s, _value=s) for s in ("alphabetical", "topological")
            ]
        u = URL(r=request, f="labelsort_changed")
        js = "ajax('%s', ['treenum','labelsort'], 'nodelabels')" % u
        return SELECT(_id="labelsort", _onchange=js,
                      value=self.labelsort, *opts)

    def labelselect(self):
        if self.labeltype == "tips_only":
            nodes = [ (n.label, n.id) for n in self.root.leaves() ]
        elif self.labeltype == "clades_only":
            nodes = [ (n.label, n.id) for n in self.root.iternodes()
                      if (n.label and (not n.istip)) ]
        else:
            nodes = [
                (n.label, n.id) for n in self.root.iternodes() if n.label
                ]
        if self.labelfilter:
            nodes = [ (s, i) for s, i in nodes if self.labelfilter in s ]
        if self.labelsort == "alphabetical":
            nodes.sort()
        elif self.labelsort == "topological":
            nodes.reverse()
        opts = [
            OPTION(s, _value=i) for s, i in nodes
            ]
        return SELECT(
            _name="nodeselect", _id="nodeselect", _multiple=ON,
            #value=" ".join([ str(x) for x in self.selected_nodes ]),
            value=list(self.selected_nodes),
            *opts)

    def parse(self):
        self.root = newick.parse(self.newick)
        self.phylogram = True
        for i, n in enumerate(self.root.iternodes()):
            n.id = i
            if n.parent and n.length == None:
                self.phylogram = False
                break
        self.count_nodes()

    def count_nodes(self):
        for n in self.root.iternodes(phylo.POSTORDER):
            n.ntips = 0
        for lf in self.root.leaves():
            for n in lf.rootpath():
                n.ntips += 1

    def html(self, request, interactive=False):
        return treeview.node2css(self.root, request,# interactive,
                                 self.viewopts.wscale,
                                 self.viewopts.scaled)

class TreeList:
    def __init__(self):
        self.trees = []
        self.selected = None

    def sourcelist(self):
        s = []
        d = {}
        for t in self.trees:
            if t.source not in d:
                s.append(t.source)
                d[t.source] = [t]
            else:
                d[t.source].append(t)
        return [ (k, d[k]) for k in s ]

    def add(self, tree):
        if tree not in self.trees:
            self.trees.append(tree)

    def select_single(self, i):
        assert i < len(self.trees)
        self.selected = i

    def selected_single(self):
        if self.selected is not None:
            try:
                return self.trees[self.selected]
            except:
                return None

    def render_selected_html(self, request):
        if self.selected != None:
            try:
                t = self.trees[self.selected]
            except:
                return ""
            return t.html(request)
        return ""

    def namelinks(self, request, f="select_tree"):
        v = []
        for i, t in enumerate(self.trees):
            url = URL(r=request, f=f, vars=dict(i=i))
            a = A(t.name, _href=url)
            v.append(a)
        return v

    def upload_form(self, request):
        txtarea = TEXTAREA(
            _name="s", _rows=10, _cols=80, _id="newick"
            )
        submit = INPUT(_type="submit", _value="Submit")
        upload = INPUT(_type="file", _name="f")
        table = TABLE(
            TR(TD("Paste tree(s) in Newick or Nexus format:")),
            TR(TD(txtarea)),
            TR(TD("Or upload file: ", upload)),
            TR(TD(submit))
            )
        action = URL(r=request, f="upload_trees")
        form = FORM(table, _action=action)
        return form
