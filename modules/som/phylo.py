import sets, types
#from gluon.storage import Storage
PREORDER = 0; POSTORDER = 1
BRANCHLENGTH = 0; INTERNODES = 1

class Node:
    def __init__(self):
        self.id = None
        self.data = {}
        self.isroot = False
        self.istip = False
        self.label = None
        self.length = None
        self.age = None
        self.parent = None
        self.children = []
        self.nchildren = 0
        self.hbranch_style = {}
        self.vbranch_style = {}
        self.label_style = {}
        self.ref_style = {}
        self.length_style = {}
        self.support_style = {}

    def emit_json(self):
        s = ",".join([ c.emit_json() for c in self.children ])
        return """{
            "id":"%s",
            "name":"%s",
            "data":{},
            "children":[%s]
        }""" % (self.id, self.label or "node%s"%self.id, s)


    def leafsets(self):
        d = {}
        leaves = self.leaves()
        for lf in leaves:
            for n in lf.parent.rootpath():
                if n not in d:
                    d[n] = [lf]
                else:
                    d[n].append(lf)
        return d

    def labelset_nodemap(self, d=None):
        if d is None:
            d = {}
        if not self.istip:
            s = set()
            for child in self.children:
                if child.istip:
                    s.add(child.label)
                else:
                    child.labelset_nodemap(d)
                    s = s | d[child]
            d[self] = s
            d[sets.ImmutableSet(s)] = self
        return d

    def leafset_nodemap(self, d=None):
        if d is None:
            d = {}
        if not self.istip:
            s = set()
            for child in self.children:
                if child.istip:
                    s.add(child)
                else:
                    child.leafset_nodemap(d)
                    s = s | d[child]
            d[self] = s
            d[sets.ImmutableSet(s)] = self
        return d

    def mrca(self, labels):
        if type(labels[0]) == types.StringType:
            s = set(labels)
            tipsets = self.labelset_nodemap()
            for n in [ x for x in self.iternodes(POSTORDER) if not x.istip ]:
                if s.issubset(tipsets[n]):
                    return n
        else:
            # labels are nodes
            v = [ list(n.rootpath()) for n in labels ]
            n = None
            while 1:
                s = set([ x.pop() for x in v ])
                if len(s) == 1:
                    n = list(s)[0]
                else:
                    break
            return n

    def order_subtrees_by_size(self, n2s=None, recurse=False, reverse=False):
        if n2s is None:
            n2s = node2size(self)
        if not self.istip:
            v = [ (n2s[c], c.label, c) for c in self.children ]
            v.sort()
            if reverse:
                v.reverse()
            self.children = [ x[-1] for x in v ]
            if recurse:
                for c in self.children:
                    c.order_subtrees_by_size(n2s, recurse=True, reverse=reverse)

    def add_child(self, child):
        assert child not in self.children
        self.children.append(child)
        child.parent = self
        self.nchildren += 1

    def bisect_branch(self):
        assert self.parent
        parent = self.prune()
        n = Node()
        if self.length:
            n.length = self.length/2.0
            self.length /= 2.0
        parent.add_child(n)
        n.add_child(self)
        return n

    def remove_child(self, child):
        assert child in self.children
        self.children.remove(child)
        child.parent = None
        self.nchildren -= 1

##     def leaves(self, v=None):
##         if v is None:
##             v = []
##         if not self.children:
##             v.append(self)
##         else:
##             for child in self.children:
##                 child.leaves(v)
##         return v

    def leaves(self):
        return [ n for n in self.iternodes() if n.istip ]

    def iternodes(self, order=PREORDER):
        """
        returns a list of nodes descendant from self - including self
        """
        if order == PREORDER:
            yield self
        for child in self.children:
            for d in child.iternodes(order):
                yield d
        if order == POSTORDER:
            yield self

    def descendants(self, order=PREORDER, v=None):
        """
        returns a list of nodes descendant from self - not including self!
        """
        if v is None:
            v = []
        assert order in (PREORDER, POSTORDER)
        for child in self.children:
            if order == PREORDER:
                v.append(child)
            else:
                v.insert(0, child)
            if child.children:
                child.descendants(order, v)
        return v

    def find_descendant(self, label):
        if label == self.label:
            return self
        else:
            for child in self.children:
                n = child.find_descendant(label)
                if n:
                    return n
        return None

    def prune(self):
        p = self.parent
        if p:
            p.remove_child(self)
        return p

    def graft(self, node):
        parent = self.parent
        parent.remove_child(self)
        n = Node()
        n.add_child(self)
        n.add_child(node)
        parent.add_child(n)

    def leaf_distances(self, store=None, measure=BRANCHLENGTH):
        """
        for each internal node, calculate the distance to each leaf,
        measured in branch length or internodes
        """
        if store is None:
            store = {}
        leaf2len = {}
        if self.children:
            for child in self.children:
                if measure == BRANCHLENGTH:
                    assert child.length is not None
                    dist = child.length
                elif measure == INTERNODES:
                    dist = 1
                else:
                    raise "InvalidMeasure"
                child.leaf_distances(store, measure)
                if child.istip:
                    leaf2len[child.id] = dist
                else:
                    for k, v in store[child.id].items():
                        leaf2len[k] = v + dist
        else:
            leaf2len[self.id] = {self.id: 0}
        store[self.id] = leaf2len
        return store

    def rootpath(self):
        n = self
        while 1:
            yield n
            if n.parent:
                n = n.parent
            else:
                break
            
    def subtree_mapping(self, labels, clean=False):
        """
        find the set of nodes in 'labels', and create a new tree
        representing the subtree connecting them.  nodes are assumed to be
        non-nested.

        return value is a mapping of old nodes to new nodes and vice versa.
        """
        d = {}
        oldtips = [ x for x in self.leaves() if x.label in labels ]
        for tip in oldtips:
            path = list(tip.rootpath())
            for node in path:
                if node not in d:
                    newnode = Node()
                    newnode.istip = node.istip
                    newnode.length = node.length
                    newnode.label = node.label
                    d[node] = newnode
                    d[newnode] = node
                else:
                    newnode = d[node]

                for child in node.children:
                    if child in d:
                        newchild = d[child]
                        if newchild not in newnode.children:
                            newnode.add_child(newchild)
        d["oldroot"] = self
        d["newroot"] = d[self]
        if clean:
            n = d["newroot"]
            while 1:
                if n.nchildren == 1:
                    oldnode = d[n]
                    del d[oldnode]; del d[n]
                    child = n.children[0]
                    child.parent = None
                    child.isroot = True
                    d["newroot"] = child
                    d["oldroot"] = d[child]
                    n = child
                else:
                    break
                    
            for tip in oldtips:
                newnode = d[tip]
                while 1:
                    newnode = newnode.parent
                    oldnode = d[newnode]
                    if newnode.nchildren == 1:
                        child = newnode.children[0]
                        if newnode.length:
                            child.length += newnode.length
                        newnode.remove_child(child)
                        if newnode.parent:
                            parent = newnode.parent
                            parent.remove_child(newnode)
                            parent.add_child(child)
                        del d[oldnode]; del d[newnode]
                    if not newnode.parent:
                        break
            
        return d

    def ultrametricize_dumbly(self):
        assert not self.istip
        d = self.leaf_distances()
        import pprint
        pprint.pprint(d)

def node2size(node, d=None):
    "map node and descendants to number of descendant tips"
    if d is None:
        d = {}
    size = int(node.istip)
    if not node.istip:
        for child in node.children:
            node2size(child, d)
            size += d[child]
    d[node] = size
    return d

def reroot(oldroot, newroot):
    oldroot.isroot = False
    newroot.isroot = True
    v = []
    n = newroot
    while 1:
        v.append(n)
        if not n.parent: break
        n = n.parent
    #print [ x.label for x in v ]
    v.reverse()
    for i, cp in enumerate(v[:-1]):
        node = v[i+1]
        # node is current node; cp is current parent
        #print node.label, cp.label
        cp.remove_child(node)
        node.add_child(cp)
        cp.length = node.length
    return newroot

def reduce_unlabeled(root):
    marked = set()
    for lf in root.leaves():
        [ marked.add(n) for n in lf.rootpath() if n.parent and (not n.label) ]
    for n in marked:
        length = n.length
        i = n.parent.children.index(n)
        j = i+1
        for c in n.children:
            ## if length:
            ##     c.length += length
            c.parent = n.parent
            n.parent.children.insert(j, c)
            j += 1
        n.parent.children.remove(n)
    return marked
        
if __name__ == "__main__":
    import newick, ascii, os, sys

    s = "(Pteridophyta,((Cycadaceae,((Pinaceae,Gnetaceae),((Araucaria,Agathis)Araucariaceae,(Dacrydium,Podocarpus)Podocarpaceae))),(Amborella,(Nymphaea,((Austrobaileya,(Trimenia,(Schizandra,Illicium)))Austrobaileyales,(((Araceae,Zosteraceae)Alismatales,((Orchidaceae,(Iridaceae,(Amaryllidaceae,Agavaceae)))Asparagales,(Burmanniaceae,(Taccaceae,Dioscoreaceae))Dioscoreales,(Liliaceae,Smilacaeae)Liliales,(Pandanaceae,Cyclanthaceae)Pandanales,((((Calamus,Eugeissona),Mauritia),(Nypa,((Arenga,Borassodendron),(Chelyocarpus,(Licuala,Livistona),(Phytelephas,((Wettinia,Iriartea),(Reinhardtia,(Synechanthus,Chamaedorea),(Aiphanes,Elaeis),Attalea,(Orania,((Geonoma,(Hyospathe,Euterpe)),(Iguanura,Areca))))))))))Arecaceae,(((Poaceae,(Cyperaceae,Juncaceae)),Bromeliaceae)Poales,((Haemodoraceae,Commelinaceae)Commelinales,(Zingiberaceae,Costaceae,Musaceae,Marantaceae,Cannaceae,Heliconiaceae)Zingiberales)))Commelinids))Monocots,(Chloranthus,(((Myristicaceae,((Annona,Powpowia)Annonaceae,(Liriodendron,(Kmeria,Manglietia,(Pachylarnax,(Elmerrillia,Michelia))))Magnoliaceae))Magnoliales,(Calycanthus,(Hernandia,((Litsea,Cryptocaria)Lauraceae,(Kibara,Siparuna)Monimiaceae)))Laurales),((Canellaceae,(Takhtajania,Drimys)Winteraceae)Canellales,(Aristolochia,(Peperomia,Piper)Piperaceae)Piperales))ranalean,((Sabia,Meliosma)Sabiaceae,(Papaveraceae,((Boquila,Akebia)Lardizabalaceae,(Menispermaceae,Ranunculaceae)))Ranunculales,((Buxus,Pachysandra)Buxaceae,(Platanus,(Protea,Helicia)Proteaceae)Proteales,(Gunnera,(((Tetracera,Dillenia)Dilleniaceae,(((Amaranthaceae,Caryophyllaceae),((Nyctaginaceae,Phytolaccaceae),(Portulacaceae,Cactaceae))),(Polygonaceae,Ancistrocladaceae,Nepenthaceae))Caryophyllales),(Balanophoraceae3,Olacaceae,(Opiliaceae,(Santalaceae,Loranthaceae)))Santalales,(((Altingia,Liquidambar)Altingiaceae,(Fothergilla,Hammamelis)Hamamelidaceae,Saxifragaceae,Daphniphyllaceae)Saxifragales,((Vitis,Leea)Vitaceae,((Turpinia,Staphylea)Staphyleaceae,(Geraniales-gen2,(Monsonia,Geranium)Geraniaceae)Geraniales,((Combretaceae,(Onagraceae,(Lythrum,Lagerstroemia)Lythraceae)),((Vochysiaceae,((Eugenia,Syzygium),Rhodamnia)Myrtaceae,(Axinandra,Crypteronia)Crypteroniaceae),((Memecylon,Mouriri),(Pternandra,(Astronia,((((Maieta,Tococa),(Leandra,Clidemia)),(Adelobotrys,Graffenrieda)),(Triolena,(Tropobea,((Macrolenes,Dissochaeta),(Medinilla,Blastus))),(Arthrostemma,(Centradenia,(Tibouchina,Melastoma))))))))Melastomataceae))Myrtales,(Zygophyllaceae,(((Perrottetia,(Quetzalia,((Hippocratea,Salacia),((Gymnosporia,Maytenus),((Crossopetalum,Wimmeria),(Siphonodon,(Euonymus,Celastrus)))))))Celastraceae,(((Lepidobotrys,Oxalis)Oxalidaceae,Connaraceae),(Sloanea,(Elaeocarpus,(Cunonia,Weinmannia)Cunoniaceae)))Oxalidales),(Ctenolophon,((Drypetes,Humiria),(Quiinaceae,Ochnaceae),(Chrysobalanaceae,((Tripura,Dichapetalum)Dichapetalaceae,(Trigoniastrum,Trigonia)Trigoniaceae)),((Caryocaraceae,Irvingia),(Malpighiaceae,(Hypericaceae,Clusiaceae))),(Phyllanthus,(Erythroxylum,(Cassipourea,((Bruguiera,(Rhizophora,(Ceriops,Kandelia))),(Carallia,(Gynotroches,Pellacalyx))))Rhizophoraceae)),(((Hydnocarpus,Ixonanthes),Pangium),(((Viola,Hymenanthera)Violaceae,(Turneraceae,Passifloraceae)),((Casearia,Flacourtia)Flacourtiaceae,(Lacistemataceae,(Salix,Populus)Salicaceae)))),(Neoscortechinia,((Pimelodendron,(Euphorbia,Hura)),((Croton,Hevea),(Trigonostemon,(Acalypha,Ricinus)))))Euphorbiaceae))Malpighiales),(((Polygala,Xanthophyllum)Polygalaceae,((Cercis,Bauhinia)Cercideae,((Prioria,((Copaifera,Sindora),Hymenaea)DetarieaeSS,((Endertia,Saraca),(Intsia,Tamarindus,(Brownea,Macrolobium),Crudia,Cynometra,(Macrolobieae-gen2,Gilbertiodendron)Macrolobieae))Amherstieae)DetarieaeSL,((Dialium,Koompassia)Dialiinae,(((Gleditsia,Gymnocladus),((Senna,Cassia),Caesalpinia,((Delonix,(Peltophorum,Schizolobium)),Tachigalia,(((Mimosa,Adenanthera),(Calliandra,Inga,Archidendron,Albizia,Pithecelobium,Enterolobium)),Acacia,(Parkia,Pentaclethra))Mimosoideae))),(Swartzia,((Dipteryx,(Myrospermum,Aldina)),(Andira,(Ormosia,(Sophora,(Crotolaria,(Ulex,Lupinus))))genistoid,((Aeschynomene,Dalbergia),(Pterocarpus,(Centrolobium,Inocarpus)),Platypodium,Platymiscium)dalbergioid,(Wisteria,(Robinia,Lotus)),(Indigofera,(Fordia,(Canavalia,(Millettia,(Lonchocarpus,Derris)))millettioid,(Clitoria,(Desmodium,(Erythrina,(Spatholobus,(Phaseolus,Vigna)))))phaseoloid)))))Papilionideae))))Fabaceae)Fabales,((Rosaceae,(Rhamnaceae,Elaeagnus,(Ulmaceae,(Urticaceae,(Cecropiaceae,(Moraceae,(Trema,Celtis,Humulus)))))))Rosales,(((Datiscaceae,Begoniaceae),((Cucurbitaceae,Anisophyllea),Octomeles))Cucurbitales,(Nothofagus,((Fagus,(Trigonobalanus,(Castanea,Castanopsis,(Lithocarpus,Quercus))))Fagaceae,((Carya,Juglans)Juglandaceae,(Myrica,(Casuarinaceae,(Betula,Alnus,Carpinus,Corylus,Ostrya)Betulaceae)))))Fagales))))Eurosid1,((Caricaceae,((Arabidopsis,Brassica)Brassicaceae,(Cadaba,Capparis)Capparidaceae)),(((Muntingia,((Dipterocarpus,(Dryobalanops,(Hopea,Shorea,Parashorea))),(Vatica,Cotylelobium),(Upuna,Vateria),Anisoptera)Dipterocarpaceae),((Gonystylus,(Aquilaria,(Daphne,(Phaleria,Dirca))))Thymelaeaceae,(Bixaceae,Cochlospermaceae),((((Grewia,Luehea),Apeiba),(Kleinhovia,Byttneria)),((Neesia,Durio),(Pentace,(Heretiera,Sterculia,Scaphium),(Tilia,Pterospermum),Ceiba)))Malvaceae))Malvales,((((Ailanthus,(Simarouba,Quassia))Simaroubaceae,((Zanthoxylum,Acronychia),(Ruta,Murraya))Rutaceae),(Aglaia,Dysoxylum)Meliaceae),(((Spondias,Mangifera)Anacardiaceae,(Santiria,Bursera)Burseraceae),((Koelreueria,Dodonaea)Sapindaceae,(Acer,Aesculus))))Sapindales))Eurosid2)Rosids))sub-rosids,(((Cornus,Mastixia)Cornaceae,Alangium)Cornales,((((Tetramerista,Pellicieraceae),Marcgraviaceae),Balsaminaceae),((Fouquieriaceae,Polemoniaceae),((Sladeniaceae,Ternstroemia),(Schima,Gordonia)Theaceae,Diospyros,Symplocaceae,(Maesaceae,(Theophrastaceae,(Primulaceae,(Myrsine,Ardisia)Myrsinaceae))),(Diapensiaceae,Styrax),(Sapotaceae,(Barringtonia,Gustavia)Lecythidaceae),(((Ericaceae,Cyrillaceae),Clethra),(Sarraceniaceae,(Actinidia,Saurauia)Actinidiaceae)))))Ericales,(((Platea,Icacina)Icacinaceae,(Boraginaceae,(Rubiaceae,((Gentiana,Fragraea)Gentianaceae,((Logania,Strychnos)Loganiaceae,(Alstonia,(Kopsia,((Rauvolfia,Tabernaemontana),((Thevetia,(Allamanda,Plumeria)),(Apocynum,(Hoya,Asclepias,Dischidia)Asclepiadaceae)))))Apocynaceae)))Gentianales,(((Fraxinus,Chionanthus)Oleaceae,((Bignonia,Catalpa)Bignoniaceae,Gesneriaceae,(Lamiaceae,((Vitex,Teijsmanniodendron)Verbenaceae,(Acanthaceae,Scrophulariaceae)))))Lamiales,(Solanaceae,Convolvulaceae)Solanales)))Euasterid1,((((Stemonurus,Gomphandra)Stemonuraceae,Cardiopteridaceae),(Phyllonomaceae,(Helwingiaceae,(Nemopanthus,Ilex)Aquifoliaceae)))Aquifoliales,(Polyosma,(Pennantiaceae,((Torricelliaceae,Griseliniaceae),(Pittosporaceae,(Apiaceae,(Osmoxylon,((Gastonia,(Aralia,Panax,Sciadodendron)),(Schefflera,(Kalopanax,(Dendropanax,(Oreopanax,(Trevesia,Hedera)))))))Araliaceae))))Apiales,(Adoxaceae,(Diervillaceae,(Caprifoliaceae,(Linnaeaceae,(Morinaceae,(Dipsacaceae,Valerianaceae))))))Dipsacales,(Rousseaceae,Pentaphragmataceae,Campanulaceae,(((Argophyllaceae,Phelliniaceae),Stylidiaceae),Alseuosmiaceae,(Menyanthaceae,((Goodenia,Scaveola)Goodeniaceae,(Calyceraceae,Asteraceae)))))Asterales))Euasterid2))Asterids))Core-eudicots))Eudicots)))))));"
    n = newick.parse(s)
    marked = reduce_unlabeled(n)
    print newick.tostring(n)
    sys.exit()
    
    from numpy import array
    #tree = newick.parse("(a,(b,(c,(d,e))));")
    f = os.path.expanduser("~/Projects/pedic-sympatry/matrices/")
    tree = eval(file(f+"garli-ml.tree").read())
    treespp = tree["species"]
    root = newick.parse(tree["newick"])
    spp = ['alaschanica', 'cheilanthifolia', 'dichotoma', 'kansuensis',
           'oederi', 'plicata', 'przewalskii', 'remotiloba',
           'rhinanthoides', 'roylei', 'rupicola', 'scolopax']
    print root.subtree_mapping(spp, clean=1)
