#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
# (c) Valik mailto:vasnake@gmail.com

'''
Created on 2011-04-30
@author: Valik

AutoCAD ActiveX objects wrapper and misc. utilities.

Discovered problems
    negative coords; it can be transformed from OCS to WCS by:
        (trans '(-3195.939915040071400 1786.635070675984300) (handent "7598") 0)
    to perform OCS2UCS:
        (trans '(-3195.939915040071400 1786.635070675984300) (handent "7598") 1)

In given DWG several coord. systems was used (OCS, UCS, WCS) and all these coord. systems was rotated in
different ways. It cause a big trouble to detect true rotation angle for misc. entities.
For blocks, for example.
The worse thing is that AutoCAD ActiveX API didn't have methods for transformation from
one CS to another. Beside that API give us only WCS coordinates (except for polylines) and OCS angles only.
Don't use AutoCAD ActiveX API, use AutoLISP.

From docs

c:\Program Files\Common Files\Autodesk Shared\acadauto.chm
Coordinate
    Variant (three-element or two-element array of doubles); read-write
    The array of X, Y, and Z coordinates for the specified vertex.
    LightweightPolyline object: The variant has two elements representing the X and Y coordinates in OCS.
    Polyline object: The variant has three elements, representing the X and Y coordinates in OCS. The Z coordinate is present in the variant but ignored.
    All other objects: The variant has three elements, representing the X and Y coordinates in WCS; the Z coordinate will default to 0 on the active UCS.
Coordinates
    Variant (array of doubles); read-write
    The array of points.
    LightweightPolyline objects: The variant is an array of 2D points in OCS.
    Polyline objects: The variant is an array of 3D points: the X and Y coordinates are in OCS; the Z coordinate is ignored.
    All other objects: The variant is an array of 3D points in WCS.

http://exchange.autodesk.com/autocadarchitecture/enu/online-help/browse#WS73099cc142f4875516d84be10ebc87a53f-79d0.htm
OCS
    Object coordinate system—point values returned by entget are expressed in this coordinate system,
    relative to the object itself.
    These points are usually converted into the WCS, current UCS, or current DCS, according to the intended use of the object.
    Conversely, points must be translated into an OCS before they are written to the database by means of the entmod or entmake
    unctions. This is also known as the entity coordinate system.
WCS
    World coordinate system: The reference coordinate system. All other coordinate systems are
    defined relative to the WCS, which never changes. Values measured relative to the WCS are stable
    across changes to other coordinate systems. All points passed in and out of
    ActiveX methods and properties are expressed in the WCS unless otherwise specified.
UCS
    User coordinate system (UCS): The working coordinate system. The user specifies a UCS to make drawing
    tasks easier. All points passed to AutoCAD commands, including those returned from AutoLISP routines
    and external functions, are points in the current UCS (unless the user precedes them
    with an * at the Command prompt). If you want your application to send coordinates in the
    WCS, OCS, or DCS to AutoCAD commands, you must first convert them to the UCS by calling the
    TranslateCoordinates method.

http://exchange.autodesk.com/autocadarchitecture/enu/online-help/search#WS73099cc142f4875516d84be10ebc87a53f-7a23.htm
    IAcadUCS_Impl GetUCSMatrix

http://www.kxcad.net/autodesk/autocad/Autodesk_AutoCAD_ActiveX_and_VBA_Developer_Guide/ws1a9193826455f5ff1a32d8d10ebc6b7ccc-6d46.htm
    util = doc.Utility # def TranslateCoordinates(self, Point, FromCoordSystem, ToCoordSystem, Displacement, OCSNormal):
    coordinateWCS = ThisDrawing.Utility.TranslateCoordinates(firstVertex, acOCS, acWorld[acUCS], False, plineNormal)
'''

import math, array
import trig


def getModule(sModuleName):
    import comtypes.client
    sLibPath = GetLibPath()
    comtypes.client.GetModule(sLibPath +'\\'+ sModuleName)

def GetLibPath():
    """Return location of Autocad type libraries as string
    c:\Program Files\Common Files\Autodesk Shared\
    c:\ObjectARX2011\inc-win32\
    """
    import winreg, os, sys
    key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,
        "TypeLib\\{D32C213D-6096-40EF-A216-89A3A6FB82F7}\\1.0\\0\\win32")
    res = winreg.QueryValueEx(key, '')[0]
    # print >> sys.stderr, ('lib [%s]' % (res))
    print('lib [%s]' % (res))
    return os.path.dirname(res)

def NewObj(MyClass, MyInterface):
    """Creates a new comtypes POINTER object where
    MyClass is the class to be instantiated,
    MyInterface is the interface to be assigned
    """
    from comtypes.client import CreateObject
    try:
        ptr = CreateObject(MyClass, interface=MyInterface)
        return ptr
    except:
        return None

def CType(obj, interface):
    """Casts obj to interface and returns comtypes POINTER or None"""
    try:
        newobj = obj.QueryInterface(interface)
        return newobj
    except:
        return None

def point2str(xyz):
    return '%0.16f, %0.16f' % (xyz[0], xyz[1])


class VacEntity (object):
    ''' EntityType adapter (c:\program...\Autodesk Topobase Client 2011\Help\acadauto.chm)
    Basic class for entity coordinates and properties.
    Coords in WCS except for some rare cases
    '''
    def __init__(self, item=''):
        super(VacEntity, self).__init__()
        self.coords = ''
        self.angle = ''
        self.name = ''
        self.closed = ''
        self.radius = ''

    def toStr(self):
        return '%s;%s;%s;%s;%s' % (self.coords, self.angle, self.name, self.closed, self.radius)

    def __str__(self):
        return self.toStr()

    def __repr__(self):
        return self.toStr()

    def description(self):
        s = (
            "This export tool have a major CS (coordinate system) problem. \n"
            "  We have coordinates in WCS (mostly) and angles in OCS (mostly). \n"
            "  Plus, API didn't have methods for angle transformation from one CS to another. \n"
            "  You can see examples of importing data back to AutoCAD in tests code. \n"
            "Fields meaning: \n"
            "coords: list of entity coordinates in WCS in form 'x, y[, ...]' \n"
            "  block coords contains insertion point, rotation vector point, zero angle vector point, \n"
            "    90 grad vector point. \n"
            "  line coords: list of points. \n"
            "  polyline: list of points and bulges. \n"
            "  text: insertion point, text alignment point, rotation vector point, \n"
            "    zero angle vector point, 90 grad vector point. \n"
            "  circle: center point. \n"
            "  arc: center point, start point, end point, middle point. \n"
            "Comments for coords: \n"
            "Rotation vector point needed for detect rotation angle in WCS. \n"
            "  That point with insertion point give us a vector with certain angle toward X axis, \n"
            "  rotation angle. Insertion point and zero angle poing give us an X axis direction in OCS. \n"
            "Polyline point may be preceded by bulge in form '(bulge f) x, y, ...'. \n"
            "  It means that next two points make a bulge segment of polyline. Bulge value given for WCS. \n"
            "Arc always drawn counterclockwise, from start to end point. \n"
            "  But because it's true only in OCS I save a middle point. \n"
            "Other fields: \n"
            "angle: rotation angle for block, text. Start and end angles for arc. \n"
            "  Measured in radians for OCS. \n"
            "text: block name; text for text. \n"
            "closed: for polyline - if true then polyline closed and form a polygon. \n"
            "  For text it's a style name. \n"
            "radius: for arc and circle it is a radius. For block it's a \n"
            "  X scale factor, Y scale factor. For text it is a set of parameters: \n"
            "  Alignment, VerticalAlignment, HorizontalAlignment, Height, ScaleFactor, Backward."
        )
        return s

    def heads(self):
        return 'coords, angle, text, closed, radius'

    def values(self):
        return '%s//%s//%s//%s//%s' % (self.coords, self.angle, self.name, self.closed, self.radius)

    def getWCSpointsFromOCSangle(self, pnt, norm, angle=0.0):
        '''Returns tuple with three points (sp, cx, cy)
        cx: point in WCS, vector [pnt, cx] give us direction for OCS X axis.
        cy: point in WCS, vector [pnt, cy] give us direction for OCS Y axis.
        sp: point in WCS, vector [pnt, sp] give us rotation angle.

        Used for rotation angle transformation from one CS to another.
        '''
        p = VAcad.trans(pnt, AutoCAD.acWorld, AutoCAD.acOCS, norm)
        sp = trig.AutoLISP.polarP(p, angle, 100)
        cx = trig.AutoLISP.polarP(p, 0.0, 100)
        cy = trig.AutoLISP.polarP(p, math.pi/2.0, 100)
        sp = VAcad.trans(sp, AutoCAD.acOCS, AutoCAD.acWorld, norm)
        cx = VAcad.trans(cx, AutoCAD.acOCS, AutoCAD.acWorld, norm)
        cy = VAcad.trans(cy, AutoCAD.acOCS, AutoCAD.acWorld, norm)

        return (sp, cx, cy)
#    def getWCSpointsFromOCSangle(self, pnt, norm, angle=0.0):
#class VacEntity


class VacBlock (VacEntity):
    '''IAcadBlockReference wrapper
    acBlockReference = 7

    extra attribs:
        HasAttributes,GetAttributes,GetConstantAttributes,IsDynamicBlock,
        GetDynamicBlockProperties, InsUnitsFactor,X(Y)ScaleFactor,
        X(Y)EffectiveScaleFactor,InsUnits,EffectiveName
    coords: InsertionPoint, SecondPoint, X-axis, Y-axis
        SecondPoint, X-axis, Y-axis: three points that defines rotation angle, OCS X,Y axis in WCS
    '''
    def __init__(self, item=''):
        super(VacBlock, self).__init__(item)
        if not item: return
        o = CType(item, AutoCAD.IAcadBlockReference)
        self.coords = o.InsertionPoint # point2str(o.InsertionPoint)
        self.angle = o.Rotation
        self.name = o.Name
        self.radius = '%s, %s' % (o.XScaleFactor, o.YScaleFactor)

        norm = o.Normal
        sp,cx,cy = self.getWCSpointsFromOCSangle(self.coords, norm, self.angle)
        self.coords = '%s, %s, %s, %s' % (point2str(self.coords), point2str(sp), point2str(cx), point2str(cy))
        #~ self.angle = u'%s, %s' % (self.angle, VAcad.ocs2wcsAngle(self.angle, norm))
#class VacBlock (VacEntity)


class VacLWPolyline (VacEntity):
    '''IAcadLWPolyline wrapper
    acPolylineLight = 24

    extra attribs: Thickness,ConstantWidth
    coords: x, y[,...] in WCS
        or (bulge n) x1, y1, x2, y2[,...]

    bulge it's a two-point segment curvature, in OCS.

    AutoCAD coords transformation:
        coordinateWCS = ThisDrawing.Utility.TranslateCoordinates(firstVertex, acOCS, acWorld, False, plineNormal)
        coordinateUCS = ThisDrawing.Utility.TranslateCoordinates(firstVertex, acOCS, acUCS, False, plineNormal)
    '''
    def __init__(self, item=''):
        super(VacLWPolyline, self).__init__(item)
        if not item: return
        o = CType(item, AutoCAD.IAcadLWPolyline)
        self.closed = o.Closed
        self.coords = o.Coordinates
        if self.closed:
            # add closing point
            self.coords = self.coords + (self.coords[0], self.coords[1])

        # format WCS coords string with bulges
        llen = len(self.coords)
        norm = o.Normal
        bsign = self.getWCSBulgeSign(norm)
        s = ''
        for n,e in zip(list(range(llen)), self.coords):
            if n%2 == 0: # 0, 2, 4,...
                if s: s += ', '
                p = VAcad.trans((e, self.coords[n+1], 0.0), AutoCAD.acOCS, AutoCAD.acWorld, norm)
                if n < llen-2: # not last pair
                    ind = n/2
                    b = bsign * o.GetBulge(ind)
                    if not b == 0.0:
                        s += '(bulge %0.5f) ' % b
                        print(('  polyline [%s] have bulge [%0.3f] at segment [%u]' % (o.Handle, b, ind+1)))
                s += point2str(p)
        self.coords = s
#	def __init__(self, item=''):

    def getWCSBulgeSign(self, norm):
        '''Detect bulge sign in WCS using predefined vectors in OCS
        '''
        p0 = VAcad.trans((0.0, 0.0, 0.0), AutoCAD.acOCS, AutoCAD.acWorld, norm)
        p1 = VAcad.trans((2.0, 1.0, 0.0), AutoCAD.acOCS, AutoCAD.acWorld, norm)
        p2 = VAcad.trans((2.0, 2.0, 0.0), AutoCAD.acOCS, AutoCAD.acWorld, norm)
        return trig.getBulgeSign(p0, p1, p2)
#class VacLWPolyline (VacEntity)


class VacText (VacEntity):
    '''IAcadText wrapper
    acText = 32

    extra attribs: Thickness,Height,VerticalAlignment,ObliqueAngle,HorizontalAlignment,
        StyleName,ScaleFactor,Alignment
    coords: InsertionPoint, TextAlignmentPoint, SecondPoint, X-axis, Y-axis
        meanings same as for VacBlock
    closed: StyleName
    radius: Alignment, VerticalAlignment, HorizontalAlignment, Height, ScaleFactor, Backward

    To position text whose justification is other than left, aligned, or fit, use the TextAlignmentPoint.
    '''
    def __init__(self, item=''):
        super(VacText, self).__init__(item)
        if not item: return
        o = CType(item, AutoCAD.IAcadText)
        self.coords = (o.InsertionPoint, o.TextAlignmentPoint)
        self.name = o.TextString
        self.angle = o.Rotation
        self.radius = '%s, %s, %s, %s, %s, %s' % (
            o.Alignment, o.VerticalAlignment, o.HorizontalAlignment, o.Height, o.ScaleFactor, o.Backward)
        self.closed = o.StyleName

        norm = o.Normal
        sp,cx,cy = self.getWCSpointsFromOCSangle(self.coords[0], norm, self.angle)
        self.coords = '%s, %s, %s, %s, %s' % (
            point2str(self.coords[0]), point2str(self.coords[1]),
            point2str(sp), point2str(cx), point2str(cy))
        #~ self.angle = u'%s, %s' % (self.angle, VAcad.ocs2wcsAngle(self.angle, norm))
#class VacText (VacEntity)


class VacLine (VacEntity):
    '''IAcadLine wrapper
    acLine = 19

    extra attribs: Thickness
    '''
    def __init__(self, item=''):
        super(VacLine, self).__init__(item)
        if not item: return
        o = CType(item, AutoCAD.IAcadLine)
        self.coords = '%s, %s' % (point2str(o.StartPoint), point2str(o.EndPoint))
#class VacLine (VacEntity)


class VacCircle (VacEntity):
    '''IAcadCircle wrapper
    acCircle = 8

    extra attribs: Thickness
    '''
    def __init__(self, item=''):
        super(VacCircle, self).__init__(item)
        if not item: return
        o = CType(item, AutoCAD.IAcadCircle)
        self.coords = point2str(o.Center)
        self.radius = o.Radius
#class VacCircle (VacEntity)


class VacArc (VacEntity):
    '''IAcadArc wrapper
    acArc = 4

    extra attribs: Thickness
    coords: Center, StartPoint, EndPoint, MidPoint
        the reason why arc defined by four points in WCS is that
        angles can't be transformed from OCS to WCS directly.
        MidPoint is a point on the middle of the arc.

    c:\Program Files\Common Files\Autodesk Shared\acadauto.chm
        An arc is always drawn counterclockwise from the start point to the endpoint.
        The StartPoint and EndPoint properties of an arc are calculated through the
        StartAngle, EndAngle, and Radius properties.

    Arc direction given in UCS and coords in WCS.
    '''
    def __init__(self, item=''):
        super(VacArc, self).__init__(item)
        if not item: return
        o = CType(item, AutoCAD.IAcadArc)
        c,s,e = (o.Center, o.StartPoint, o.EndPoint)
        sa,ea = (o.StartAngle, o.EndAngle)
        # WCS
        self.coords = '%s, %s, %s' % (point2str(c), point2str(s), point2str(e))

        self.radius = o.Radius
        # radians
        self.angle = '%s, %s' % (sa, ea)

        # get midpoint
        norm = o.Normal
        c = VAcad.trans(c, AutoCAD.acWorld, AutoCAD.acOCS, norm)
        s = VAcad.trans(s, AutoCAD.acWorld, AutoCAD.acOCS, norm)
        e = VAcad.trans(e, AutoCAD.acWorld, AutoCAD.acOCS, norm)
        m = trig.getArcMidpointP(c, self.radius, s, e)
        m = VAcad.trans(m, AutoCAD.acOCS, AutoCAD.acWorld, norm)
        self.coords = '%s, %s' % (self.coords, point2str(m))
#class VacArc (VacEntity)


class VacPoint (VacEntity):
    '''IAcadPoint wrapper
    acPoint = 22

    extra attribs: Thickness
    '''
    def __init__(self, item=''):
        super(VacPoint, self).__init__(item)
        if not item: return
        o = CType(item, AutoCAD.IAcadPoint)
        self.coords = point2str(o.Coordinates)
#class VacPoint (VacEntity):


class VAcadServices:
    '''Tools and services for transformations, etc.
    '''
    def __init__(self):
        import comtypes.client
        self.acad = comtypes.client.GetActiveObject('AutoCAD.Application')
        self.ac = CType(self.acad, AutoCAD.IAcadApplication)
        self.docs = self.ac.Documents
        self.doc = self.ac.ActiveDocument
        self.ms = self.doc.ModelSpace
        self.u = self.doc.Utility
        self.bulgeSign = ''
        self.zeroAngle = ''
        self.norm = ''

    def openDWG(self, fname, ro=True):
        self.docs.Close()
        self.doc = self.docs.Open(fname, ro)
        self.ms = self.doc.ModelSpace
        self.u = self.doc.Utility

    def trans(self, point, csFrom, csTo, norm='', disp=False):
        if len(point) < 3:
            point = (point[0], point[1], 0.0)
        p = array.array('d', [point[0], point[1], point[2]])
        if norm:
            norm = array.array('d', [norm[0], norm[1], norm[2]])
            p = self.u.TranslateCoordinates(p, csFrom, csTo, disp, norm)
        else:
            p = self.u.TranslateCoordinates(p, csFrom, csTo, disp)
        return p

    def ocs2wcsAngle(self, angle, norm):
        ''' transform angle from OCS to WCS
        '''
        #~ if not (self.norm and self.bulgeSign) or self.norm != norm:
        p0 = self.trans((0.0, 0.0, 0.0), AutoCAD.acOCS, AutoCAD.acWorld, norm)
        p1 = self.trans((2.0, 1.0, 0.0), AutoCAD.acOCS, AutoCAD.acWorld, norm)
        p2 = self.trans((2.0, 2.0, 0.0), AutoCAD.acOCS, AutoCAD.acWorld, norm)
        p10 = self.trans((1.0, 0.0, 0.0), AutoCAD.acOCS, AutoCAD.acWorld, norm)
        self.bulgeSign = trig.getBulgeSign(p0, p1, p2)
        self.zeroAngle = trig.AutoLISP.angleP(p0, p10)
        self.norm = norm

        ta = (self.bulgeSign * self.zeroAngle) + (self.bulgeSign * angle)
        return trig.normAngle2pi(ta)

    def getUCSMatrix(self):
        ''' Autodesk Shared\acadauto.chm
        RetVal = object.GetUCSMatrix()
        Object
            UCS (Document.ActiveUCS)
            The object this method applies to.
        RetVal
            Variant (4x4 array of doubles)
            The UCS matrix.
        To transform an entity into a given UCS, use the TransformBy method, using the matrix returned by this method as the input for that method.
        http://exchange.autodesk.com/autocadarchitecture/enu/online-help/browse#WS73099cc142f4875516d84be10ebc87a53f-7a23.htm
            matrix: (a1,a2,a3) (b1,b2,b3), (c1,c2,c3), (d1,d2,d3)
            x' = x*a1 + y*b1 + z*c1 + d1
            y' = x*a2 + y*b2 + z*c2 + d2
            z' = x*a3 + y*b3 + z*c3 + d3
        Example:
            #~ UCSMatrix: ((0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
            #~ WCS (bulge 0.26052) 3195.9399150400714000, 1786.6350706759843000,
            #~ UCS at point  X=1786.6351  Y=3195.9399  Z=   0.0000
            a,b,c,d = (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
            x,y,z = 3195.9399150400714000, 1786.6350706759843000, 0.0
            xt = x*a[0] + y*b[0] + z*c[0] + d[0]
            yt = x*a[1] + y*b[1] + z*c[1] + d[1]
            zt = x*a[2] + y*b[2] + z*c[2] + d[2]
        '''
        m = None
        print('getUCSMatrix...')
        t = self.doc.GetVariable('UCSNAME')
        print(('UCSNAME: [%s]' % t))
        if t:
            t = self.doc.ActiveUCS
            print(('ActiveUCS: [%r]' % t))
        if t:
            ucs = CType(t, AutoCAD.IAcadUCS)
            print(('IAcadUCS: [%r]' % ucs))
            m = ucs.GetUCSMatrix()
            m = (self.doc.GetVariable('UCSNAME'), m[0], m[1], m[2], m[3])
        if not m:
            m = (self.doc.GetVariable('UCSNAME'), \
                self.doc.GetVariable('UCSXDIR'), self.doc.GetVariable('UCSYDIR'), \
                (0.0, 0.0, 0.0), self.doc.GetVariable('UCSORG'))
        return m
#class VAcadServices:


try:
    # c:\Python25\Lib\site-packages\comtypes\gen\_D32C213D_6096_40EF_A216_89A3A6FB82F7_0_1_0.py
    import comtypes.gen.AutoCAD as AutoCAD
except:
    getModule('acax18ENU.tlb') # comtypes.gen.AutoCAD
    import comtypes.gen.AutoCAD as AutoCAD

VAcad = VAcadServices()
