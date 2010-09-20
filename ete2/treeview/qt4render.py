import math
import types
import copy

from PyQt4  import QtCore, QtGui
from PyQt4.QtGui import QPrinter

from qt4gui import _PropertiesDialog
import layouts

_MIN_NODE_STYLE = {
    "fgcolor": "#0030c1",
    "bgcolor": "#FFFFFF",
    "vt_line_color": "#000000",
    "hz_line_color": "#000000",
    "line_type": 0,
    "vlwidth": 1,
    "hlwidth": 1,
    "size":6,
    "shape": "sphere",
    "faces": None,
    "faces_": None, # A dist must be initialized by node
    "draw_descendants": 1,
    "ymargin": 0
}


class _NodeItem(QtGui.QGraphicsRectItem):
    def __init__(self, node):
        self.node = node
        self.radius = node.img_style["size"]/2
        QtGui.QGraphicsRectItem.__init__(self,0,0,self.radius*2,self.radius*2)

    def paint(self, p, option, widget):
        #QtGui.QGraphicsRectItem.paint(self, p, option, widget)
        if self.node.img_style["shape"] == "sphere":
            r = self.radius
            gradient = QtGui.QRadialGradient(r, r, r,(r*2)/3,(r*2)/3)
            gradient.setColorAt(0.05, QtCore.Qt.white);
            gradient.setColorAt(0.9, QtGui.QColor(self.node.img_style["fgcolor"]));
            p.setBrush(QtGui.QBrush(gradient))
            p.setPen(QtCore.Qt.NoPen)
            p.drawEllipse(self.rect())
        elif self.node.img_style["shape"] == "square":
            p.fillRect(self.rect(),QtGui.QBrush(QtGui.QColor(self.node.img_style["fgcolor"])))
        elif self.node.img_style["shape"] == "circle":
            p.setBrush(QtGui.QBrush(QtGui.QColor(self.node.img_style["fgcolor"])))
            p.setPen(QtGui.QPen(QtGui.QColor(self.node.img_style["fgcolor"])))
            p.drawEllipse(self.rect())

    def hoverEnterEvent (self,e):
        width = self.parentItem().mapFromScene(self.scene().i_width, 0).x()
        height = self.parentItem().rect().height()
        self.scene().highlighter.setRect(QtCore.QRectF(0, 0, \
                                                           width, height))
        self.scene().highlighter.setParentItem(self.parentItem())
        self.scene().highlighter.setVisible(True)

    def hoverLeaveEvent (self,e):
        self.scene().highlighter.setVisible(False)

    def mousePressEvent(self,e):
        pass

    def mouseReleaseEvent(self,e):
        if e.button() == QtCore.Qt.RightButton:
            self.showActionPopup()
        elif e.button() == QtCore.Qt.LeftButton:
            self.scene().propertiesTable.update_properties(self.node)

    def showActionPopup(self):
        contextMenu = QtGui.QMenu()
        if self.node.collapsed:
            contextMenu.addAction( "Expand"           , self.toggle_collapse)
        else:
            contextMenu.addAction( "Collapse"         , self.toggle_collapse)

        contextMenu.addAction( "Set as outgroup"      , self.set_as_outgroup)
        contextMenu.addAction( "Swap branches"        , self.swap_branches)
        contextMenu.addAction( "Delete node"          , self.delete_node)
        contextMenu.addAction( "Delete partition"     , self.detach_node)
        contextMenu.addAction( "Add childs"           , self.add_childs)
        contextMenu.addAction( "Populate partition"   , self.populate_partition)
        if self.node.up is not None and\
                self.scene().startNode == self.node:
            contextMenu.addAction( "Back to parent", self.back_to_parent_node)
        else:
            contextMenu.addAction( "Extract"              , self.set_start_node)

        if self.scene().buffer_node:
            contextMenu.addAction( "Paste partition"  , self.paste_partition)

        contextMenu.addAction( "Cut partition"        , self.cut_partition)
        contextMenu.addAction( "Show newick"        , self.show_newick)
        contextMenu.exec_(QtGui.QCursor.pos())

    def show_newick(self):
        d = NewickDialog(self.node)
        d._conf = _show_newick.Ui_Newick()
        d._conf.setupUi(d)
        d.update_newick()
        d.exec_()
        return False

    def delete_node(self):
        self.node.delete()
        self.scene().draw()

    def detach_node(self):
        self.node.detach()
        self.scene().draw()

    def swap_branches(self):
        self.node.swap_childs()
        self.scene().draw()

    def add_childs(self):
        n,ok = QtGui.QInputDialog.getInteger(None,"Add childs","Number of childs to add:",1,1)
        if ok:
            for i in xrange(n):
                ch = self.node.add_child()
            self.scene().set_style_from(self.scene().startNode,self.scene().layout_func)

    def void(self):
        return True

    def set_as_outgroup(self):
        self.scene().startNode.set_outgroup(self.node)
        self.scene().set_style_from(self.scene().startNode, self.scene().layout_func)
        self.scene().draw()

    def toggle_collapse(self):
        self.node.collapsed ^= True
        self.scene().draw()

    def cut_partition(self):
        self.scene().buffer_node = self.node
        self.node.detach()
        self.scene().draw()

    def paste_partition(self):
        if self.scene().buffer_node:
            self.node.add_child(self.scene().buffer_node)
            self.scene().set_style_from(self.scene().startNode,self.scene().layout_func)
            self.scene().buffer_node= None
            self.scene().draw()

    def populate_partition(self):
        n, ok = QtGui.QInputDialog.getInteger(None,"Populate partition","Number of nodes to add:",2,1)
        if ok:
            self.node.populate(n)
            self.scene().set_style_from(self.scene().startNode,self.scene().layout_func)
            self.scene().draw()

    def set_start_node(self):
        self.scene().startNode = self.node
        self.scene().draw()

    def back_to_parent_node(self):
        self.scene().startNode = self.node.up
        self.scene().draw()



class _ArcItem(QtGui.QGraphicsRectItem):
    def __init__(self, angle_start, angle_span, radius, *args):
        QtGui.QGraphicsRectItem.__init__(self, 0, 0, radius, radius)
        self.angle_start = angle_span
        self.angle_span = angle_span
        self.radius = radius

    def paint(self, painter, option, index):
        rect = QtCore.QRectF(-self.radius, -self.radius, self.radius*2, self.radius*2);
        painter.setPen(self.pen())
        painter.drawArc(rect, self.angle_start, self.angle_span*16)
        painter.drawRect(rect)

class _TextItem(QtGui.QGraphicsSimpleTextItem):
    """ Manage faces on Scene"""
    def __init__(self,face,node,*args):
        QtGui.QGraphicsSimpleTextItem.__init__(self,*args)
        self.node = node
        self.face = face

    def hoverEnterEvent (self,e):
        partition = self.parentItem().parentItem()
        width = partition.mapFromScene(self.scene().i_width, 0).x()
        height = partition.rect().height()
        self.scene().highlighter.setRect(QtCore.QRectF(0, 0, \
                                                           width, height))
        self.scene().highlighter.setParentItem(partition)
        self.scene().highlighter.setVisible(True)

    def hoverLeaveEvent (self,e):
        self.scene().highlighter.setVisible(False)

    def mousePressEvent(self,e):
        pass

    def mouseReleaseEvent(self,e):
        if e.button() == QtCore.Qt.RightButton:
            self.node._QtItem_.showActionPopup()
        elif e.button() == QtCore.Qt.LeftButton:
            self.scene().propertiesTable.update_properties(self.node)


class _FaceGroup(QtGui.QGraphicsItem): # I resisted to name this FaceBook :) 
    def __init__(self, faces, node, *args):
        QtGui.QGraphicsItem.__init__(self, *args)
        self.node = node
        self.column2faces = {}
        for c, column_faces in enumerate(faces):
            self.column2faces[c] = column_faces

        self.w = 0
        self.h = 0
        # updates the size of this grid
        self.update_columns_size()

    def paint(self, painter, option, index):
        return

    def boundingRect(self):
        return QtCore.QRectF(0,0, self.w, self.h)

    def get_size():
        return self.w, self.h

    def update_columns_size(self):
        self.column2size = {}
        for c, faces in self.column2faces.iteritems():
            height = 0
            width = 0
            for f in faces:
                if f.type == "pixmap": 
                    f.update_pixmap()
                height += f._height()
                width = max(width, f._width())
            self.column2size[c] = (width, height)
        self.w = sum([0]+[size[0] for size in self.column2size.itervalues()])
        self.h = max([0]+[size[1] for size in self.column2size.itervalues()])

    def render(self):
        x = 0
        for c, faces in self.column2faces.iteritems():
            w, h = self.column2size[c]
            # Starting y position. Center columns
            y = (self.h / 2) - (h/2)
            for f in faces:
                if f.type == "text":
                    obj = _TextItem(f, self.node, f.get_text())
                    obj.setFont(f.font)
                    obj.setBrush(QtGui.QBrush(f.fgcolor))
                    obj.setParentItem(self)
                    obj.setAcceptsHoverEvents(True)
                else:
                    # Loads the pre-generated pixmap
                    obj = _FaceItem(f, self.node, pixmap)
                    obj.setAcceptsHoverEvents(True)
                    obj.setParentItem(self)
                obj.setPos(x, y)
                # Y position is incremented by the height of last face
                # in column
                y += f._height()
            # X position is incremented by the max width of the last
            # processed column.
            x += w

class _FaceItem(QtGui.QGraphicsPixmapItem):
    """ Manage faces on Scene"""
    def __init__(self, face, node, *args):
        QtGui.QGraphicsPixmapItem.__init__(self,*args)
        self.node = node
        self.face = face

    def hoverEnterEvent (self,e):
        partition = self.parentItem().parentItem()
        width = partition.mapFromScene(self.scene().i_width, 0).x()
        height = partition.rect().height()
        self.scene().highlighter.setRect(QtCore.QRectF(0, 0, \
                                                           width, height))
        self.scene().highlighter.setParentItem(partition)
        self.scene().highlighter.setVisible(True)

    def hoverLeaveEvent (self,e):
        self.scene().highlighter.setVisible(False)

    def mousePressEvent(self,e):
        pass

    def mouseReleaseEvent(self,e):
        if e.button() == QtCore.Qt.RightButton:
            self.node._QtItem_.showActionPopup()
        elif e.button() == QtCore.Qt.LeftButton:
            self.scene().propertiesTable.update_properties(self.node)

class _PartitionItem(QtGui.QGraphicsRectItem):
    def __init__(self, node, *args):
        QtGui.QGraphicsRectItem.__init__(self, *args)
        self.node = node

    def paint(self, painter, option, index):
        return QtGui.QGraphicsRectItem.paint(self, painter, option, index)

class _SelectorItem(QtGui.QGraphicsRectItem):
    def __init__(self):
        self.Color = QtGui.QColor("blue")
        self._active = False
        QtGui.QGraphicsRectItem.__init__(self,0,0,0,0)

    def paint(self, p, option, widget):
        p.setPen(self.Color)
        p.drawRect(self.rect().x(),self.rect().y(),self.rect().width(),self.rect().height())
        return
        # Draw info text
        font = QtGui.QFont("Arial",13)
        text = "%d selected."  % len(self.get_selected_nodes())
        textR = QtGui.QFontMetrics(font).boundingRect(text)
        if  self.rect().width() > textR.width() and \
                self.rect().height() > textR.height()/2 and 0: # OJO !!!!
            p.setPen(QtGui.QPen(self.Color))
            p.setFont(QtGui.QFont("Arial",13))
            p.drawText(self.rect().bottomLeft().x(),self.rect().bottomLeft().y(),text)

    def get_selected_nodes(self):
        selPath = QtGui.QPainterPath()
        selPath.addRect(self.rect())
        self.scene().setSelectionArea(selPath)
        return [i.node for i in self.scene().selectedItems()]

    def setActive(self,bool):
        self._active = bool

    def isActive(self):
        return self._active

class _HighlighterItem(QtGui.QGraphicsRectItem):
    def __init__(self):
        self.Color = QtGui.QColor("red")
        self._active = False
        QtGui.QGraphicsRectItem.__init__(self,0,0,0,0)

    def paint(self, p, option, widget):
        p.setPen(self.Color)
        p.drawRect(self.rect().x(),self.rect().y(),self.rect().width(),self.rect().height())
        return




class _TreeScene(QtGui.QGraphicsScene):
    def __init__(self, rootnode=None, style=None, *args):
        QtGui.QGraphicsScene.__init__(self,*args)

        self.view = None
        # Config variables
        self.buffer_node = None        # Used to copy and paste
        self.layout_func = None        # Layout function
        self.startNode   = rootnode    # Node to start drawing
        self.scale       = 0           # Tree branch scale used to draw
        self.max_w_aligned_face = 0    # Stores the max width of aligned faces
        self.min_real_branch_separation = 0
        self.selectors  = []
        self._highlighted_nodes = {}

        self.node2faces = {}
        self.node2item = {}

        # Qt items
        self.selector = None
        self.mainItem = None        # Qt Item which is parent of all other items
        self.propertiesTable = _PropertiesDialog(self)

    def initialize_tree_scene(self, tree, style, tree_properties):
        self.tree        = tree        # Pointer to original tree
        self.startNode   = tree        # Node to start drawing
        self.max_w_aligned_face = 0    # Stores the max width of aligned faces

        # Load image attributes
        self.props = tree_properties

        # Validates layout function
        if type(style) == types.FunctionType or\
                type(style) == types.MethodType:
            self.layout_func = style
        else:
            try:
                self.layout_func = getattr(layouts,style)
            except:
                raise ValueError, "Required layout is not a function pointer nor a valid layout name."

        # Set the scene background
        self.setBackgroundBrush(QtGui.QColor("white"))

        # Set nodes style
        self.set_style_from(self.startNode,self.layout_func)

        self.propertiesTable.update_properties(self.startNode)

    def highlight_node(self, n):
        self.unhighlight_node(n)
        r = QtGui.QGraphicsRectItem(self.mainItem)
        self._highlighted_nodes[n] = r

        R = n.fullRegion.getRect()
        width = self.i_width-n._x
        r.setRect(QtCore.QRectF(n._x,n._y,width,R[3]))
 
        #r.setRect(0,0, n.fullRegion.width(), n.fullRegion.height())

        #r.setPos(n.scene_pos)
        # Don't know yet why do I have to add 2 pixels :/
        #r.moveBy(0,0)
        r.setZValue(-1)
        r.setPen(QtGui.QColor(self.props.search_node_fg))
        r.setBrush(QtGui.QColor(self.props.search_node_bg))

        # self.view.horizontalScrollBar().setValue(n._x)
        # self.view.verticalScrollBar().setValue(n._y)

    def unhighlight_node(self, n):
        if n in self._highlighted_nodes and \
                self._highlighted_nodes[n] is not None:
            self.removeItem(self._highlighted_nodes[n])
            del self._highlighted_nodes[n]


    def mousePressEvent(self,e):
        self.selector.setRect(e.scenePos().x(),e.scenePos().y(),0,0)
        self.selector.startPoint = QtCore.QPointF(e.scenePos().x(),e.scenePos().y())
        self.selector.setActive(True)
        self.selector.setVisible(True)
        QtGui.QGraphicsScene.mousePressEvent(self,e)

    def mouseReleaseEvent(self,e):
        curr_pos = e.scenePos()
        x = min(self.selector.startPoint.x(),curr_pos.x())
        y = min(self.selector.startPoint.y(),curr_pos.y())
        w = max(self.selector.startPoint.x(),curr_pos.x()) - x
        h = max(self.selector.startPoint.y(),curr_pos.y()) - y
        if self.selector.startPoint == curr_pos:
            self.selector.setVisible(False)
        self.selector.setActive(False)
        QtGui.QGraphicsScene.mouseReleaseEvent(self,e)

    def mouseMoveEvent(self,e):

        curr_pos = e.scenePos()
        if self.selector.isActive():
            x = min(self.selector.startPoint.x(),curr_pos.x())
            y = min(self.selector.startPoint.y(),curr_pos.y())
            w = max(self.selector.startPoint.x(),curr_pos.x()) - x
            h = max(self.selector.startPoint.y(),curr_pos.y()) - y
            self.selector.setRect(x,y,w,h)
        QtGui.QGraphicsScene.mouseMoveEvent(self, e)

    def mouseDoubleClickEvent(self,e):
        QtGui.QGraphicsScene.mouseDoubleClickEvent(self,e)

    def save(self, imgName, w=None, h=None, header=None, \
                 dpi=150, take_region=False):
        ext = imgName.split(".")[-1].upper()

        root = self.startNode
        aspect_ratio = root.fullRegion.height() / root.fullRegion.width()

        # auto adjust size
        if w is None and h is None:
            w = dpi * 6.4
            h = w * aspect_ratio
            if h>dpi * 11:
                h = dpi * 11
                w = h / aspect_ratio

        elif h is None:
            h = w * aspect_ratio
        elif w is None:
            w = h / aspect_ratio

        if ext == "PDF" or ext == "PS":
            format = QPrinter.PostScriptFormat if ext == "PS" else QPrinter.PdfFormat
            printer = QPrinter(QPrinter.HighResolution)
            printer.setResolution(dpi)
            printer.setOutputFormat(format)
            printer.setPageSize(QPrinter.A4)
            
            pageTopLeft = printer.pageRect().topLeft()
            paperTopLeft = printer.paperRect().topLeft()
            # For PS -> problems with margins
            # print paperTopLeft.x(), paperTopLeft.y()
            # print pageTopLeft.x(), pageTopLeft.y()
            # print  printer.paperRect().height(),  printer.pageRect().height()
            topleft =  pageTopLeft - paperTopLeft

            printer.setFullPage(True);
            printer.setOutputFileName(imgName);
            pp = QtGui.QPainter(printer)
            if header:
                pp.setFont(QtGui.QFont("Verdana",12))
                pp.drawText(topleft.x(),20, header)
                targetRect =  QtCore.QRectF(topleft.x(), 20 + (topleft.y()*2), w, h)
            else:
                targetRect =  QtCore.QRectF(topleft.x(), topleft.y()*2, w, h)

            if take_region:
                self.selector.setVisible(False)
                self.render(pp, targetRect, self.selector.rect())
                self.selector.setVisible(True)
            else:
                self.render(pp, targetRect, self.sceneRect())
            pp.end()
            return
        else:
            targetRect = QtCore.QRectF(0, 0, w, h)
            ii= QtGui.QImage(w, \
                                 h, \
                                 QtGui.QImage.Format_ARGB32)
            pp = QtGui.QPainter(ii)
            pp.setRenderHint(QtGui.QPainter.Antialiasing )
            pp.setRenderHint(QtGui.QPainter.TextAntialiasing)
            pp.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
            if take_region:
                self.selector.setVisible(False)
                self.render(pp, targetRect, self.selector.rect())
                self.selector.setVisible(True)
            else:
                self.render(pp, targetRect, self.sceneRect())
            pp.end()
            ii.save(imgName)

    def draw(self):
        # Clean previous items from scene by removing the main parent
        if self.mainItem:
            self.removeItem(self.mainItem)

        self.node2faces = {}
        self.node2item = {}

        #Clean_highlighting rects
        for n in self._highlighted_nodes:
            self._highlighted_nodes[n] = None

        # Recreates main parent and add it to scene
        self.mainItem = QtGui.QGraphicsRectItem()
        self.addItem(self.mainItem)
        # Recreates selector item (used to zoom etc...)
        self.selector = _SelectorItem()
        self.selector.setParentItem(self.mainItem)
        self.selector.setVisible(False)
        self.selector.setZValue(2)

        self.highlighter   = _HighlighterItem()
        self.highlighter.setParentItem(self.mainItem)
        self.highlighter.setVisible(False)
        self.highlighter.setZValue(2)
        self.min_real_branch_separation = 0

        # Get branch scale
        fnode, max_dist = self.startNode.get_farthest_leaf(topology_only=\
            self.props.force_topology)

        if max_dist>0:
            self.scale =  self.props.tree_width / max_dist
        else:
            self.scale =  1

        #self.update_node_areas(self.startNode)
        self.update_node_areas_rectangular(self.startNode)

        # Get picture dimensions
        self.i_width  = self.startNode.fullRegion.width()
        self.i_height = self.startNode.fullRegion.height()

        # Place aligned faces
        # ...

        # Place faces around tree
        # ...

        # size correcton for aligned faces
        self.i_width += self.max_w_aligned_face
        # New pos for tree when inverse orientation
        if self.props.orientation == 1:
            self.startNode._QtItem_.moveBy(self.max_w_aligned_face,0)

        # Tree border
        # border = self.addRect(0,0,self.i_width, self.i_height)
        # border = self.addRect(0,0,self.i_width-self.max_w_aligned_face,self.i_height)
        # border = self.addRect(0,0, self.sceneRect().width(), self.sceneRect().height())
        # border.setParentItem(self.mainItem)

        # Draw scale
        self.add_scale(1 ,self.i_height+4)

        #Re-establish node marks
        for n in self._highlighted_nodes:
            self.highlight_node(n)

        self.setSceneRect(-2,-2,self.i_width+4,self.i_height+50)


    def add_scale(self,x,y):
        size = 50
        customPen  = QtGui.QPen(QtGui.QColor("black"),1)

        line = QtGui.QGraphicsLineItem(self.mainItem)
        line2 = QtGui.QGraphicsLineItem(self.mainItem)
        line3 = QtGui.QGraphicsLineItem(self.mainItem)
        line.setPen(customPen)
        line2.setPen(customPen)
        line3.setPen(customPen)

        line.setLine(x,y+20,size,y+20)
        line2.setLine(x,y+15,x,y+25)
        line3.setLine(size,y+15,size,y+25)

        scale_text = "%0.2f" % float(size/ self.scale)
        scale = QtGui.QGraphicsSimpleTextItem(scale_text)
        scale.setParentItem(self.mainItem)
        scale.setPos(x,y+20)

        if self.props.force_topology:
            wtext = "Force topology is enabled!\nBranch lengths does not represent original values."
            warning_text = QtGui.QGraphicsSimpleTextItem(wtext)
            warning_text.setFont( QtGui.QFont("Arial", 8))
            warning_text.setBrush( QtGui.QBrush(QtGui.QColor("darkred")))
            warning_text.setPos(x, y+32)
            warning_text.setParentItem(self.mainItem)

    def set_style_from(self,node,layout_func):
        for n in [node]+node.get_descendants():
            n.img_style = copy.copy(_MIN_NODE_STYLE)
            n.img_style["faces"] = []
            n.img_style["faces_"] = {}
            layout_func(n)

    def update_node_faces(self, node):
        # Organize all faces of this node in FaceGroups objects
        # (tables of faces)
        faceblock = {}
        self.node2faces[node] = faceblock
        for position in ["branch-right", "aligned", "branch-top", "branch-bottom"] :
            if position in node.img_style["faces_"]:
                # The value of this is expected to be list of columns of faces
                # c2f = [ [f1, f2, f3], 
                #         [f4, f4]
                #       ]
                if position=="aligned" and not node.is_leaf():
                    faceblock[position] = _FaceGroup([], node)
                    continue # aligned on internal node don't make sense
                faceblock[position] = _FaceGroup(node.img_style["faces_"][position], node)
            else:
                faceblock[position] = _FaceGroup([], node)
        return faceblock

    def update_node_areas_rectangular(self,root_node):
        """ """
        ## General scheme on how nodes size are handled
        ## |==========================================================================================================================|
        ## |                                                fullRegion                                                                |       
        ## |             nodeRegion                  |================================================================================|
        ## |                                         |                                fullRegion                                     || 
        ## |                                         |        nodeRegion                     |=======================================||
        ## |                                         |                                       |         fullRegion                   |||
        ## |                                         |                                       |         nodeRegion                   ||| 
        ## |                                         |                         |             | xdist_offset | nodesize | facesRegion|||
        ## |                                         | xdist_offset | nodesize |facesRegion  |=======================================||
        ## |                                         |                         |             |=======================================||
        ## |                                         |                                       |             fullRegion                ||
        ## |                                         |                                       |             nodeRegion                ||
        ## |  branch-top     |          |            |                                       | xdist_offset | nodesize | facesRegion ||
        ## | xdist_offset    | nodesize |facesRegion |                                       |=======================================||
        ## |  branch-bottom  |          |            |================================================================================|
        ## |                                         |=======================================|                                        |
        ## |                                         |             fullRegion                |                                        |
        ## |                                         |        nodeRegion                     |                                        |
        ## |                                         | xdist_offset | nodesize | facesRegion |                                        |
        ## |                                         |=======================================|                                        |
        ## |==========================================================================================================================|
        ##
        ## Rendering means to create all QGraphicsItems that represent
        ## all node features. For this, I use an iterative function
        ## that creates a rectangleItem for each node in which all its
        ## features are included. The same tree node hierarchy is
        ## maintained for setting the parents items of partitions.
        ## Once a node has its partitionItem, elements are added to
        ## such partitionItem, and are positioned relative to the
        ## coordinate system of the parent.
        ## 
        ## A node partition contains the branch to its parent, the
        ## node circle, faces and the vertical line connecting childs

        n2i = self.node2item = {}
        visited = set()
        nodeStack = []
        nodeStack.append(root_node)
        while nodeStack:
            node = nodeStack[-1]
            finished = True
            if node.img_style["draw_descendants"]:
                for c in node.children:
                    if c not in visited:
                        nodeStack.append(c)
                        finished = False
            # Here you have the preorder position of the node. 
            # node.visited_preorder
            if not finished:
                continue

            # Here you have the postorder position of the node. Now is
            # when I want to visit the node
            nodeStack.pop(-1)
            visited.add(node)

            # Branch length converted to pixels
            if self.props.force_topology:
                node.dist_xoffset = 60
            else:
                node.dist_xoffset = float(node.dist * self.scale)

            # Organize faces by groups
            faceblock = self.update_node_faces(node)

            # Total height required by the node
            h = node.__img_height__ = max(node.img_style["size"] + faceblock["branch-top"].h + faceblock["branch-bottom"].h, 
                                          node.img_style["hlwidth"] + faceblock["branch-top"].h + faceblock["branch-bottom"].h, 
                                          faceblock["branch-right"].h, 
                                          faceblock["aligned"].h, 
                                          self.props.min_branch_separation,
                                          )    

            # Total width required by the node
            w = node.__img_width__ = sum([max(node.dist_xoffset + node.img_style["size"], 
                                              faceblock["branch-top"].w + node.img_style["size"],
                                              faceblock["branch-bottom"].w + node.img_style["size"],
                                              ), 
                                          faceblock["branch-right"].w]
                                         )

            # Updates the max width spent by aligned faces
            if faceblock["aligned"].w > self.max_w_aligned_face:
                self.max_w_aligned_face = faceblock["aligned"].w

            # Rightside faces region
            node.facesRegion = QtCore.QRectF(0, 0, faceblock["branch-right"].w, faceblock["branch-right"].h)

            # Node region 
            node.nodeRegion = QtCore.QRectF(0, 0, w, h)
            if self.min_real_branch_separation < h:
                self.min_real_branch_separation = h

            if not node.is_leaf() and node.img_style["draw_descendants"]:
                widths, heights = zip(*[[c.fullRegion.width(),c.fullRegion.height()] \
                                          for c in node.children])
                w += max(widths)
                h = max(node.nodeRegion.height(), sum(heights))

            # This is the node total region covered by the node
            node.fullRegion = QtCore.QRectF(0, 0, w, h)

            # ------------------ RENDERING ---------------------------
            # Creates a rectItem representing the node partition. Its
            # size was calculate in update_node_areas. This partition
            # groups all its child partitions
            partition = self.node2item[node] = \
                _PartitionItem(node, 0, 0, node.fullRegion.width(), node.fullRegion.height())

            # Draw virtual partition grid (for debugging)
            # partition.setPen(QtGui.QColor("yellow"))
            # color = QtGui.QColor("#cccfff")
            # color = QtGui.QColor("#ffffff")
            # partition.setBrush(color)
            # partition.setPen(color)

            if node.is_leaf() or not node.img_style["draw_descendants"]:
                # Leafs will be processed from parents
                partition.center = self.get_partition_center(node)
                continue
            else:
                parent_partition = partition
                # set position of child partitions
                x = node.nodeRegion.width()
                y = 0
                all_childs_height = sum([c.fullRegion.height() for c in node.children])
                if node.fullRegion.height() > all_childs_height:
                    y += ((node.fullRegion.height() - all_childs_height))/2
                for c in node.children:
                    cpart = n2i[c]
                    # Sets x and y position of child within parent
                    # partition (relative positions)
                    cpart.setParentItem(parent_partition)
                    cpart.start_y = y 
                    cpart.start_x = x
                    cpart.setPos(x, y)

                    # Increment y for the next child within partition
                    y += c.fullRegion.height()
                    # Build all node associated items
                    self.render_node_partition(c, cpart)
                # set partition center that will be used for parent nodes
                partition.center = self.get_partition_center(node)

        # Render root node and set its positions
        partition = n2i[root_node]
        partition.setParentItem(self.mainItem)
        partition.center = self.get_partition_center(root_node)
        self.render_node_partition(root_node, partition)
        for part in self.node2item.values():
            # save absolute position in scene (used for maps and
            # highlighting)
            abs_pos = part.mapToScene(0, 0)
            part.abs_startx = abs_pos.x()
            part.abs_starty = abs_pos.y()

    def update_node_areas_radial(self,root_node):
        """ UNFINISHED! """

        center_item = QtGui.QGraphicsRectItem(0,0,3,3)
        center_item.setPen(QtGui.QColor("#ff0000"))
        center_item.setBrush(QtGui.QColor("#ff0000"))
        n2a = {}
        angle_step = 360./len(root_node)
        next_angle = 0
        n2i = self.node2item = {}
        visited = set()
        nodeStack = []
        nodeStack.append(root_node)
        while nodeStack:
            node = nodeStack[-1]
            finished = True
            if node.img_style["draw_descendants"]:
                for c in node.children:
                    if c not in visited:
                        nodeStack.append(c)
                        finished = False

            ## Here you have the preorder position of the node. 
            # ... node.before_go_for_childs = blah ...
            if not finished:
                continue

            # Here you have the postorder position of the node. Now is
            # when I want to visit the node
            nodeStack.pop(-1)
            visited.add(node)

            # Branch length converted to pixels
            if self.props.force_topology:
                node.dist_xoffset = 60
            else:
                node.dist_xoffset = float(node.dist * self.scale)

            # Organize faces by groups
            faceblock = self.update_node_faces(node)

            # Total height required by the node
            h = node.__img_height__ = max(node.img_style["size"] + faceblock["branch-top"].h + faceblock["branch-bottom"].h, 
                                          node.img_style["hlwidth"] + faceblock["branch-top"].h + faceblock["branch-bottom"].h, 
                                          faceblock["branch-right"].h, 
                                          faceblock["aligned"].h, 
                                          self.props.min_branch_separation,
                                          )    

            # Total width required by the node
            w = node.__img_width__ = sum([max(node.dist_xoffset + node.img_style["size"], 
                                              faceblock["branch-top"].w + node.img_style["size"],
                                              faceblock["branch-bottom"].w + node.img_style["size"],
                                              ), 
                                          faceblock["branch-right"].w]
                                         )

            # Updates the max width spend by aligned faces
            if faceblock["aligned"].w > self.max_w_aligned_face:
                self.max_w_aligned_face = faceblock["aligned"].w

            # Rightside faces region
            node.facesRegion = QtCore.QRectF(0, 0, faceblock["branch-right"].w, faceblock["branch-right"].h)

            # Node region 
            node.nodeRegion = QtCore.QRectF(0, 0, w, h)
            if self.min_real_branch_separation < h:
                self.min_real_branch_separation = h

            if not node.is_leaf() and node.img_style["draw_descendants"]:
                widths, heights = zip(*[[c.fullRegion.width(),c.fullRegion.height()] \
                                          for c in node.children])
                w += max(widths)
                h = max(node.nodeRegion.height(), sum(heights))

            # This is the node total region covered by the node
            node.fullRegion = QtCore.QRectF(0, 0, w, h)
            
            # ------------------ RENDERING ---------------------------
            # Creates a rectItem representing the node partition. Its
            # size was calculate in update_node_areas. This partition
            # groups all its child partitions
           
            partition = self.node2item[node] = \
                _PartitionItem(node, 0, 0, node.fullRegion.width(), node.fullRegion.height())
                #QtGui.QGraphicsRectItem(0, 0, node.fullRegion.width(), node.fullRegion.height())

            # Draw virtual partition grid (for debugging)
            #color = QtGui.QColor("#cccfff")
            #color = QtGui.QColor("#ffffff")
            #partition.setBrush(color)
            #partition.setPen(color)

            if node.is_leaf() or not node.img_style["draw_descendants"]:
                # Leafs will be processed from parents
                partition.angle = next_angle
                partition.angle_start = next_angle
                partition.angle_span = partition.angle_start + angle_step
                next_angle+= angle_step
            else:
                p1 = n2i[node.children[0]]
                p2 = n2i[node.children[-1]]
                partition.angle = p2.angle_start + p2.angle_span - p1.angle_start
                partition.angle_start = p1.angle_start - (p1.angle_span/2)
                partition.angle_span = p2.angle_start - (p2.angle_span/2) - partition.angle_start
    
            #partition.setParentItem(center_item)
            b = node.nodeRegion.height()
            a = node.nodeRegion.width()
            A = partition.angle
            radius = math.sqrt( (b/2*math.atan(A))**2 + a**2  + (b/2)**2 )
            print radius, partition.angle_start

            arc = _ArcItem(partition.angle_start, partition.angle_span, radius)

            n2a[node] = arc            

            for c in node.children:
                cpart = n2i[c]
                cpart.setParentItem(arc)
                carc = n2a[c]
                carc.setParentItem(arc)
                self.render_node_partition(node, cpart)
            
        arc.setParentItem(center_item)
        arc.setPen(QtGui.QColor("#0000ff"))
        center_item.setParentItem(self.mainItem)
        center_item.setPos(200,200)
        # Render root node and set its positions

    def rotate_node(self,node,angle,x=None,y=None):
        if x and y:
            x = node.fullRegion.width()/2
            y = node.fullRegion.height()/2
            node._QtItem_.setTransform(QtGui.QTransform().translate(x, y).rotate(angle).translate(-x, -y));
        else:
            node._QtItem_.rotate(angle)

    def get_partition_center(self, n):
        down = self.node2faces[n]["branch-bottom"].h
        up = self.node2faces[n]["branch-top"].h

        if n.is_leaf() or not n.img_style["draw_descendants"]:
            center = n.fullRegion.height()/2
        else:
            first_child_part = self.node2item[n.children[0]]
            last_child_part = self.node2item[n.children[-1]]
            c1 = first_child_part.start_y + first_child_part.center
            c2 = last_child_part.start_y + last_child_part.center
            center = c1+ (c2-c1)/2

        if up > center:
            center = up
        elif down > n.fullRegion.height()-center:
            center = n.fullRegion.height()-down
        return center
            
    def render_node_partition(self, node, partition):

        if node.img_style["bgcolor"].upper() not in set(["#FFFFFF", "white"]): 
            color = QtGui.QColor(node.img_style["bgcolor"])
            partition.setBrush(color)
            partition.setPen(color)
        else:
            partition.setPen(QtGui.QColor("#FFFFFF"))

        # Draw partition components 
        # Draw node balls in the partition centers
        ball_size = node.img_style["size"] 
        ball_start_x = node.nodeRegion.width() - node.facesRegion.width() - ball_size
        node_ball = _NodeItem(node)
        node_ball.setParentItem(partition)            
        node_ball.setPos(ball_start_x, partition.center-(ball_size/2))
        node_ball.setAcceptsHoverEvents(True)
        # Hz line
        hz_line = QtGui.QGraphicsLineItem(partition)
        hz_line.setLine(0, partition.center, 
                        node.dist_xoffset, partition.center)

        # Attach branch-right faces to child 
        fblock = self.node2faces[node]["branch-right"]
        fblock.setParentItem(partition)
        fblock.render()
        fblock.setPos(node.nodeRegion.width()-node.facesRegion.width(), \
                              partition.center-node.facesRegion.height()/2)
                
        # Attach branch-bottom faces to child 
        fblock = self.node2faces[node]["branch-bottom"]
        fblock.setParentItem(partition)
        fblock.render()
        fblock.setPos(0, partition.center)
        
        # Attach branch-top faces to child 
        fblock = self.node2faces[node]["branch-top"]
        fblock.setParentItem(partition)
        fblock.render()
        fblock.setPos(0, partition.center-fblock.h)

        # Vt Line
        if not node.is_leaf() and node.img_style["draw_descendants"]==1:
            vt_line = QtGui.QGraphicsLineItem(partition)
            first_child_part = self.node2item[node.children[0]]
            last_child_part = self.node2item[node.children[-1]]
            c1 = first_child_part.start_y + first_child_part.center
            c2 = last_child_part.start_y + last_child_part.center
            vt_line.setLine(node.nodeRegion.width(), c1,\
                                node.nodeRegion.width(), c2)            

        # STYLES
        line_pen = QtGui.QPen(QtGui.QColor(node.img_style["hz_line_color"])) 
        line_pen.setWidth(node.img_style["hlwidth"])
        if node.img_style["line_type"] == 0:
            line_pen.setStyle(QtCore.Qt.SolidLine)
        elif node.img_style["line_type"] == 1:
            line_pen.setStyle(QtCore.Qt.DashLine)
        hz_line.setPen(line_pen)

        try:
            line_pen = QtGui.QPen(QtGui.QColor(node.img_style["vt_line_color"])) 
            line_pen.setWidth(node.img_style["vlwidth"])
            if node.img_style["line_type"] == 0:
                line_pen.setStyle(QtCore.Qt.SolidLine)
            elif node.img_style["line_type"] == 1:
                line_pen.setStyle(QtCore.Qt.DashLine)
            vt_line.setPen(line_pen)
        except UnboundLocalError:
            pass




    def render_node_OLD(self,node , x, y,level=0):
        """ Traverse the tree structure and render each node using the
        regions, sizes, and faces previously loaded. """

        # Node's stuff
        orientation = self.props.orientation
        r = node.img_style["size"]/2
        fh = node.facesRegion.width()

        node._QtItem_ = _NodeItem(node)
        node._QtItem_.setAcceptsHoverEvents(True)

        # RIGHT TO LEFT
        if orientation == 1:
            if node == self.startNode:
                x = self.i_width-x

        # Add main node QGItem. Each node item has as parent the
        # parent node item
        if node==self.startNode:
            node._QtItem_.setParentItem(self.mainItem)
            scene_pos = node._QtItem_.pos()
            node.scene_pos = scene_pos

        # node x,y starting positions
        node._x = x
        node._y = y

        # colour rect as node background
        if  node.img_style["bgcolor"].upper() != "#FFFFFF":
            background = QtGui.QGraphicsRectItem(self.mainItem)
            background.setZValue(-1000+level)
            color = QtGui.QColor(node.img_style["bgcolor"])
            background.setBrush(color)
            background.setPen(color)
            if orientation == 0:
                background.setRect(node._x,node._y,self.i_width-node._x+self.max_w_aligned_face,node.fullRegion.height())
            elif orientation == 1:
                background.setRect(node._x-node.fullRegion.width(),node._y,self.i_width,node.fullRegion.height())
        # Draw node and lines
        if not node.is_leaf() and node.img_style["draw_descendants"]==1:
            # Corrections ... say something else, don't you think?
#            node_height = 0
#            for ch in node.get_children():
#                node_height += ch.fullRegion.height()

#            if node.fullRegion.height() >= node_height:
#                y_correction = node.fullRegion.height() - node_height
#            else:
#               y_correction = 0

#           y_correction = node._y_correction
            # recursivity: call render function for every child
            next_y = y + node._y_correction#/2
            for ch in node.get_children():
                dist_to_child = ch.dist * self.scale
                if orientation == 0:
                    next_x = x+node.nodeRegion.width()
                elif orientation == 1:
                    next_x = x-node.nodeRegion.width()

                self.render_node(ch, next_x, next_y,level+1)
                next_y += ch.fullRegion.height()

            node._centered_y = ((node.children[0]._centered_y + node.children[-1]._centered_y)/2)
            # Draw an internal node. Take global pos.

            # Place node at the correct pos in Scene
            ch._QtItem_.setParentItem(node._QtItem_)
            if orientation == 0:
                node._QtItem_.setPos(x+node.dist_xoffset,node._centered_y-node.img_style["size"]/2)
            elif orientation == 1:
                node._QtItem_.setPos(x-node.dist_xoffset-node.img_style["size"],node._centered_y-node.img_style["size"]/2)
            for ch in node.children:
                scene_pos = ch._QtItem_.pos()
                ch.scene_pos = scene_pos
                ch._QtItem_.setParentItem(node._QtItem_)
                ch._QtItem_.setPos(node._QtItem_.mapFromScene(scene_pos) )

            # Draws the startNode branch when it is not the absolute root
            if node == self.startNode:
                y = node._QtItem_.pos().y()+ node.img_style["size"]/2
                self.add_branch(self.mainItem,0,y,node.dist_xoffset,y,node.dist,node.support, node.img_style["hz_line_color"], node.img_style["hlwidth"], node.img_style["line_type"])

            # RECTANGULAR STYLE
            if self.props.style == 0:
                vt_line = QtGui.QGraphicsLineItem(node._QtItem_)
                customPen = QtGui.QPen(QtGui.QBrush(QtGui.QColor(node.img_style["vt_line_color"])), node.img_style["vlwidth"])
                if node.img_style["line_type"]==1:
                    customPen.setStyle(QtCore.Qt.DashLine)
                vt_line.setPen(customPen)

                ch1_y = node._QtItem_.mapFromScene(0,node.children[0]._centered_y).y()
                ch2_y = node._QtItem_.mapFromScene(0,node.children[-1]._centered_y).y()

                # Draw hz lines of childs
                for ch in node.children:
                    ch_pos = node._QtItem_.mapFromScene(ch._x, ch._centered_y)
                    if orientation == 0:
                        self.add_branch(node._QtItem_,fh+r*2,ch_pos.y(),fh+r*2+ch.dist_xoffset ,ch_pos.y(),ch.dist, ch.support, ch.img_style["hz_line_color"], ch.img_style["hlwidth"], ch.img_style["line_type"])
                    elif orientation == 1:
                        self.add_branch(node._QtItem_,-fh,ch_pos.y(),-fh-ch.dist_xoffset ,ch_pos.y(),ch.dist,ch.support,ch.img_style["hz_line_color"], ch.img_style["hlwidth"], ch.img_style["line_type"])
                # Draw vertical line
                if orientation == 0:
                    vt_line.setLine(fh+r*2,ch1_y,fh+(r*2),ch2_y)
                elif orientation == 1:
                    vt_line.setLine(-fh,ch1_y,-fh,ch2_y)

            # DIAGONAL STYLE
            elif self.props.style == 1:
                # Draw lines from node to childs
                for ch in node.children:
                    if orientation == 0:
                        ch_x = ch._QtItem_.x()
                        ch_y = ch._QtItem_.y()+ch.img_style["size"]/2
                        self.add_branch(node._QtItem_,fh+node.img_style["size"],r,ch_x,ch_y,ch.dist,ch.support, ch.img_style["hz_line_color"], 1, ch.img_style["line_type"])
                    elif orientation == 1:
                        ch_x = ch._QtItem_.x()
                        ch_y = ch._QtItem_.y()+ch.img_style["size"]/2
                        self.add_branch(node._QtItem_,-fh,r,ch_x+(r*2),ch_y,ch.dist,ch.support, ch.img_style["hz_line_color"], 1, ch.img_style["line_type"])

            self.add_faces(node,orientation)

        else:
            # Draw terminal node
            node._centered_y = y+node.fullRegion.height()/2
            if orientation == 0:
                node._QtItem_.setPos(x+node.dist_xoffset, node._centered_y-r)
            elif orientation == 1:
                node._QtItem_.setPos(x-node.dist_xoffset-node.img_style["size"], node._centered_y-r)

            self.add_faces(node,orientation)

    def add_branch(self,parent_item,x1,y1,x2,y2,dist,support,color,width,line_type):
        hz_line = QtGui.QGraphicsLineItem(parent_item)
        customPen  = QtGui.QPen(QtGui.QBrush(QtGui.QColor(color)), width)
        if line_type == 1:
            customPen.setStyle(QtCore.Qt.DashLine)
        hz_line.setPen(customPen)
        hz_line.setLine(x1,y1,x2,y2)

        if self.props.draw_branch_length:
            distText = "%0.3f" % dist
            if support is not None:
                distText += "(%0.2f)" % support
            font = QtGui.QFont(self.props.general_font_type,self.props.branch_length_font_size)
            rect = QtGui.QFontMetrics(font).boundingRect(0,0,0,0,QtCore.Qt.AlignTop,distText)
            b_length = QtGui.QGraphicsSimpleTextItem(distText)
            b_length.setFont(font)
            b_length.setBrush(QtGui.QColor(self.props.branch_length_font_color))
            b_length.setParentItem(hz_line)
            b_length.setPos(x1,y1)
            if y1 != y2:
                offset = 0
                angle = math.atan((y2-y1)/(x2-x1))*360/ (2*math.pi)
                if y1>y2:
                    offset = rect.height()
                b_length.setTransform(QtGui.QTransform().translate(0, y1-offset).rotate(angle).translate(0,-y1));

    def add_faces(self, node, orientation):
        for fblock in  node.__faces__.values():
            fblock.setParentItem(node._QtItem_)

        if orientation==0:
            aligned_start_x = node._QtItem_.mapFromScene(self.i_width,0).x()
            start_x = node.img_style["size"]
        elif orientation==1:
            start_x = 0
            aligned_start_x = node._QtItem_.mapFromScene(0,0).x()
        
        node.__faces__["aligned"].render()
        node.__faces__["aligned"].setPos(aligned_start_x, 0)
        node.__faces__["branch-right"].render()
        node.__faces__["branch-right"].setPos(start_x, -node.nodeRegion.height())


