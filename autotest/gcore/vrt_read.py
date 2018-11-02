#!/usr/bin/env python
# -*- coding: utf-8 -*-
###############################################################################
# $Id$
#
# Project:  GDAL/OGR Test Suite
# Purpose:  Test basic read support for a all datatypes from a VRT file.
# Author:   Frank Warmerdam <warmerdam@pobox.com>
#
###############################################################################
# Copyright (c) 2003, Frank Warmerdam <warmerdam@pobox.com>
# Copyright (c) 2008-2012, Even Rouault <even dot rouault at mines-paris dot org>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
###############################################################################

import os
import sys
import shutil
import struct

sys.path.append('../pymod')

import gdaltest
from osgeo import gdal
import test_cli_utilities

###############################################################################
# When imported build a list of units based on the files available.

gdaltest_list = []

init_list = [
    ('byte.vrt', 1, 4672, None),
    ('int16.vrt', 1, 4672, None),
    ('uint16.vrt', 1, 4672, None),
    ('int32.vrt', 1, 4672, None),
    ('uint32.vrt', 1, 4672, None),
    ('float32.vrt', 1, 4672, None),
    ('float64.vrt', 1, 4672, None),
    ('cint16.vrt', 1, 5028, None),
    ('cint32.vrt', 1, 5028, None),
    ('cfloat32.vrt', 1, 5028, None),
    ('cfloat64.vrt', 1, 5028, None),
    ('msubwinbyte.vrt', 2, 2699, None),
    ('utmsmall.vrt', 1, 50054, None),
    ('byte_nearest_50pct.vrt', 1, 1192, None),
    ('byte_averaged_50pct.vrt', 1, 1152, None),
    ('byte_nearest_200pct.vrt', 1, 18784, None),
    ('byte_averaged_200pct.vrt', 1, 18784, None)]

###############################################################################
# The VRT references a non existing TIF file


def vrt_read_1():

    gdal.PushErrorHandler('CPLQuietErrorHandler')
    ds = gdal.Open('data/idontexist.vrt')
    gdal.PopErrorHandler()

    if ds is None:
        return 'success'

    return 'fail'

###############################################################################
# The VRT references a non existing TIF file, but using the proxy pool dataset API (#2837)


def vrt_read_2():

    ds = gdal.Open('data/idontexist2.vrt')
    if ds is None:
        return 'fail'

    gdal.PushErrorHandler('CPLQuietErrorHandler')
    cs = ds.GetRasterBand(1).Checksum()
    gdal.PopErrorHandler()

    if cs != 0:
        return 'fail'

    ds.GetMetadata()
    ds.GetRasterBand(1).GetMetadata()
    ds.GetGCPs()

    ds = None
    return 'success'

###############################################################################
# Test init of band data in case of cascaded VRT (ticket #2867)


def vrt_read_3():

    driver_tif = gdal.GetDriverByName("GTIFF")

    output_dst = driver_tif.Create('tmp/test_mosaic1.tif', 100, 100, 3, gdal.GDT_Byte)
    output_dst.GetRasterBand(1).Fill(255)
    output_dst = None

    output_dst = driver_tif.Create('tmp/test_mosaic2.tif', 100, 100, 3, gdal.GDT_Byte)
    output_dst.GetRasterBand(1).Fill(127)
    output_dst = None

    ds = gdal.Open('data/test_mosaic.vrt')
    # A simple Checksum() cannot detect if the fix works or not as
    # Checksum() reads line per line, and we must use IRasterIO() on multi-line request
    data = ds.GetRasterBand(1).ReadRaster(90, 0, 20, 100)
    got = struct.unpack('B' * 20 * 100, data)
    for i in range(100):
        if got[i * 20 + 9] != 255:
            gdaltest.post_reason('at line %d, did not find 255' % i)
            return 'fail'
    ds = None

    driver_tif.Delete('tmp/test_mosaic1.tif')
    driver_tif.Delete('tmp/test_mosaic2.tif')

    return 'success'


###############################################################################
# Test complex source with complex data (#3977)

def vrt_read_4():

    try:
        import numpy as np
    except ImportError:
        return 'skip'

    data = np.zeros((1, 1), np.complex64)
    data[0, 0] = 1. + 3.j

    drv = gdal.GetDriverByName('GTiff')
    ds = drv.Create("/vsimem/test.tif", 1, 1, 1, gdal.GDT_CFloat32)
    ds.GetRasterBand(1).WriteArray(data)
    ds = None

    complex_xml = '''<VRTDataset rasterXSize="1" rasterYSize="1">
  <VRTRasterBand dataType="CFloat32" band="1">
    <ComplexSource>
      <SourceFilename relativeToVRT="1">/vsimem/test.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <ScaleOffset>3</ScaleOffset>
      <ScaleRatio>2</ScaleRatio>
    </ComplexSource>
  </VRTRasterBand>
</VRTDataset>
'''

    ds = gdal.Open(complex_xml)
    scaleddata = ds.GetRasterBand(1).ReadAsArray()
    ds = None

    gdal.Unlink("/vsimem/test.tif")

    if scaleddata[0, 0].real != 5.0 or scaleddata[0, 0].imag != 9.0:
        gdaltest.post_reason('did not get expected value')
        print('scaleddata[0, 0]: %f %f' % (scaleddata[0, 0].real, scaleddata[0, 0].imag))
        return 'fail'

    return 'success'

###############################################################################
# Test serializing and deserializing of various band metadata


def vrt_read_5():

    src_ds = gdal.Open('data/testserialization.asc')
    ds = gdal.GetDriverByName('VRT').CreateCopy('/vsimem/vrt_read_5.vrt', src_ds)
    src_ds = None
    ds = None

    ds = gdal.Open('/vsimem/vrt_read_5.vrt')

    gcps = ds.GetGCPs()
    if len(gcps) != 2 or ds.GetGCPCount() != 2:
        return 'fail'

    if ds.GetGCPProjection().find("WGS 84") == -1:
        print(ds.GetGCPProjection())
        return 'fail'

    ds.SetGCPs(ds.GetGCPs(), ds.GetGCPProjection())

    gcps = ds.GetGCPs()
    if len(gcps) != 2 or ds.GetGCPCount() != 2:
        return 'fail'

    if ds.GetGCPProjection().find("WGS 84") == -1:
        print(ds.GetGCPProjection())
        return 'fail'

    band = ds.GetRasterBand(1)
    if band.GetDescription() != 'MyDescription':
        print(band.GetDescription())
        return 'fail'

    if band.GetUnitType() != 'MyUnit':
        print(band.GetUnitType())
        return 'fail'

    if band.GetOffset() != 1:
        print(band.GetOffset())
        return 'fail'

    if band.GetScale() != 2:
        print(band.GetScale())
        return 'fail'

    if band.GetRasterColorInterpretation() != gdal.GCI_PaletteIndex:
        print(band.GetRasterColorInterpretation())
        return 'fail'

    if band.GetCategoryNames() != ['Cat1', 'Cat2']:
        print(band.GetCategoryNames())
        return 'fail'

    ct = band.GetColorTable()
    if ct.GetColorEntry(0) != (0, 0, 0, 255):
        print(ct.GetColorEntry(0))
        return 'fail'
    if ct.GetColorEntry(1) != (1, 1, 1, 255):
        print(ct.GetColorEntry(1))
        return 'fail'

    if band.GetMaximum() != 0:
        print(band.GetMaximum())
        return 'fail'

    if band.GetMinimum() != 2:
        print(band.GetMinimum())
        return 'fail'

    if band.GetMetadata() != {'STATISTICS_MEAN': '1', 'STATISTICS_MINIMUM': '2', 'STATISTICS_MAXIMUM': '0', 'STATISTICS_STDDEV': '3'}:
        print(band.GetMetadata())
        return 'fail'

    ds = None

    gdal.Unlink('/vsimem/vrt_read_5.vrt')

    return 'success'

###############################################################################
# Test GetMinimum() and GetMaximum()


def vrt_read_6():

    try:
        os.unlink('data/byte.tif.aux.xml')
        print('Removed data/byte.tif.aux.xml. Was not supposed to exist...')
    except OSError:
        pass

    src_ds = gdal.Open('data/byte.tif')
    mem_ds = gdal.GetDriverByName('GTiff').CreateCopy('/vsimem/vrt_read_6.tif', src_ds)
    vrt_ds = gdal.GetDriverByName('VRT').CreateCopy('/vsimem/vrt_read_6.vrt', mem_ds)

    if vrt_ds.GetRasterBand(1).GetMinimum() is not None:
        gdaltest.post_reason('got bad minimum value')
        print(vrt_ds.GetRasterBand(1).GetMinimum())
        return 'fail'
    if vrt_ds.GetRasterBand(1).GetMaximum() is not None:
        gdaltest.post_reason('got bad maximum value')
        print(vrt_ds.GetRasterBand(1).GetMaximum())
        return 'fail'

    # Now compute source statistics
    mem_ds.GetRasterBand(1).ComputeStatistics(False)

    if vrt_ds.GetRasterBand(1).GetMinimum() != 74:
        gdaltest.post_reason('got bad minimum value')
        print(vrt_ds.GetRasterBand(1).GetMinimum())
        return 'fail'
    if vrt_ds.GetRasterBand(1).GetMaximum() != 255:
        gdaltest.post_reason('got bad maximum value')
        print(vrt_ds.GetRasterBand(1).GetMaximum())
        return 'fail'

    mem_ds = None
    vrt_ds = None

    gdal.GetDriverByName('GTiff').Delete('/vsimem/vrt_read_6.tif')
    gdal.GetDriverByName('VRT').Delete('/vsimem/vrt_read_6.vrt')

    return 'success'

###############################################################################
# Test GDALOpen() anti-recursion mechanism


def vrt_read_7():

    filename = "/vsimem/vrt_read_7.vrt"

    content = """<VRTDataset rasterXSize="20" rasterYSize="20">
  <VRTRasterBand dataType="Byte" band="1">
    <SimpleSource>
      <SourceFilename relativeToVRT="1">%s</SourceFilename>
      <SourceBand>1</SourceBand>
      <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
      <DstRect xOff="0" yOff="0" xSize="20" ySize="20" />
    </SimpleSource>
  </VRTRasterBand>
</VRTDataset>""" % filename

    gdal.FileFromMemBuffer(filename, content)
    gdal.PushErrorHandler('CPLQuietErrorHandler')
    ds = gdal.Open(filename)
    gdal.PopErrorHandler()
    error_msg = gdal.GetLastErrorMsg()
    gdal.Unlink(filename)

    if ds is not None:
        return 'fail'

    if error_msg != 'GDALOpen() called with too many recursion levels':
        return 'fail'

    return 'success'

###############################################################################
# Test ComputeRasterMinMax()


def vrt_read_8():

    src_ds = gdal.Open('data/byte.tif')
    mem_ds = gdal.GetDriverByName('GTiff').CreateCopy('/vsimem/vrt_read_8.tif', src_ds)
    vrt_ds = gdal.GetDriverByName('VRT').CreateCopy('/vsimem/vrt_read_8.vrt', mem_ds)

    vrt_minmax = vrt_ds.GetRasterBand(1).ComputeRasterMinMax()
    mem_minmax = mem_ds.GetRasterBand(1).ComputeRasterMinMax()

    mem_ds = None
    vrt_ds = None

    gdal.GetDriverByName('GTiff').Delete('/vsimem/vrt_read_8.tif')
    gdal.GetDriverByName('VRT').Delete('/vsimem/vrt_read_8.vrt')

    if vrt_minmax != mem_minmax:
        print(vrt_minmax)
        print(mem_minmax)
        return 'fail'

    return 'success'

###############################################################################
# Test ComputeStatistics()


def vrt_read_9():

    src_ds = gdal.Open('data/byte.tif')
    mem_ds = gdal.GetDriverByName('GTiff').CreateCopy('/vsimem/vrt_read_9.tif', src_ds)
    vrt_ds = gdal.GetDriverByName('VRT').CreateCopy('/vsimem/vrt_read_9.vrt', mem_ds)

    vrt_stats = vrt_ds.GetRasterBand(1).ComputeStatistics(False)
    mem_stats = mem_ds.GetRasterBand(1).ComputeStatistics(False)

    mem_ds = None
    vrt_ds = None

    gdal.GetDriverByName('GTiff').Delete('/vsimem/vrt_read_9.tif')
    gdal.GetDriverByName('VRT').Delete('/vsimem/vrt_read_9.vrt')

    if vrt_stats != mem_stats:
        print(vrt_stats)
        print(mem_stats)
        return 'fail'

    return 'success'

###############################################################################
# Test GetHistogram() & GetDefaultHistogram()


def vrt_read_10():

    src_ds = gdal.Open('data/byte.tif')
    mem_ds = gdal.GetDriverByName('GTiff').CreateCopy('/vsimem/vrt_read_10.tif', src_ds)
    vrt_ds = gdal.GetDriverByName('VRT').CreateCopy('/vsimem/vrt_read_10.vrt', mem_ds)

    vrt_hist = vrt_ds.GetRasterBand(1).GetHistogram()
    mem_hist = mem_ds.GetRasterBand(1).GetHistogram()

    mem_ds = None
    vrt_ds = None

    f = gdal.VSIFOpenL('/vsimem/vrt_read_10.vrt', 'rb')
    content = gdal.VSIFReadL(1, 10000, f).decode('ascii')
    gdal.VSIFCloseL(f)

    if vrt_hist != mem_hist:
        gdaltest.post_reason('fail')
        print(vrt_hist)
        print(mem_hist)
        return 'fail'

    if content.find('<Histograms>') < 0:
        gdaltest.post_reason('fail')
        print(content)
        return 'fail'

    # Single source optimization
    for i in range(2):
        gdal.FileFromMemBuffer('/vsimem/vrt_read_10.vrt',
                               """<VRTDataset rasterXSize="20" rasterYSize="20">
    <VRTRasterBand dataType="Byte" band="1">
        <SimpleSource>
        <SourceFilename relativeToVRT="1">vrt_read_10.tif</SourceFilename>
        </SimpleSource>
    </VRTRasterBand>
    </VRTDataset>""")

        ds = gdal.Open('/vsimem/vrt_read_10.vrt')
        if i == 0:
            ds.GetRasterBand(1).GetDefaultHistogram()
        else:
            ds.GetRasterBand(1).GetHistogram()
        ds = None

        f = gdal.VSIFOpenL('/vsimem/vrt_read_10.vrt', 'rb')
        content = gdal.VSIFReadL(1, 10000, f).decode('ascii')
        gdal.VSIFCloseL(f)

        if content.find('<Histograms>') < 0:
            gdaltest.post_reason('fail')
            print(content)
            return 'fail'

    # Two sources general case
    for i in range(2):
        gdal.FileFromMemBuffer('/vsimem/vrt_read_10.vrt',
                               """<VRTDataset rasterXSize="20" rasterYSize="20">
    <VRTRasterBand dataType="Byte" band="1">
        <SimpleSource>
        <SourceFilename relativeToVRT="1">vrt_read_10.tif</SourceFilename>
        </SimpleSource>
        <SimpleSource>
        <SourceFilename relativeToVRT="1">vrt_read_10.tif</SourceFilename>
        </SimpleSource>
    </VRTRasterBand>
    </VRTDataset>""")

        ds = gdal.Open('/vsimem/vrt_read_10.vrt')
        if i == 0:
            ds.GetRasterBand(1).GetDefaultHistogram()
        else:
            ds.GetRasterBand(1).GetHistogram()
        ds = None

        f = gdal.VSIFOpenL('/vsimem/vrt_read_10.vrt', 'rb')
        content = gdal.VSIFReadL(1, 10000, f).decode('ascii')
        gdal.VSIFCloseL(f)

        if content.find('<Histograms>') < 0:
            gdaltest.post_reason('fail')
            print(content)
            return 'fail'

    gdal.GetDriverByName('GTiff').Delete('/vsimem/vrt_read_10.tif')
    gdal.GetDriverByName('VRT').Delete('/vsimem/vrt_read_10.vrt')

    return 'success'

###############################################################################
# Test resolving files from a symlinked vrt using relativeToVRT with an absolute symlink


def vrt_read_11():

    if not gdaltest.support_symlink():
        return 'skip'

    try:
        os.remove('tmp/byte.vrt')
        print('Removed tmp/byte.vrt. Was not supposed to exist...')
    except OSError:
        pass

    os.symlink(os.path.join(os.getcwd(), 'data/byte.vrt'), 'tmp/byte.vrt')

    ds = gdal.Open('tmp/byte.vrt')

    os.remove('tmp/byte.vrt')

    if ds is None:
        return 'fail'

    return 'success'

###############################################################################
# Test resolving files from a symlinked vrt using relativeToVRT
# with a relative symlink pointing to a relative symlink


def vrt_read_12():

    if not gdaltest.support_symlink():
        return 'skip'

    try:
        os.remove('tmp/byte.vrt')
        print('Removed tmp/byte.vrt. Was not supposed to exist...')
    except OSError:
        pass

    os.symlink('../data/byte.vrt', 'tmp/byte.vrt')

    ds = gdal.Open('tmp/byte.vrt')

    os.remove('tmp/byte.vrt')

    if ds is None:
        return 'fail'

    return 'success'

###############################################################################
# Test resolving files from a symlinked vrt using relativeToVRT with a relative symlink


def vrt_read_13():

    if not gdaltest.support_symlink():
        return 'skip'

    try:
        os.remove('tmp/byte.vrt')
        print('Removed tmp/byte.vrt. Was not supposed to exist...')
    except OSError:
        pass
    try:
        os.remove('tmp/other_byte.vrt')
        print('Removed tmp/other_byte.vrt. Was not supposed to exist...')
    except OSError:
        pass

    os.symlink('../data/byte.vrt', 'tmp/byte.vrt')
    os.symlink('../tmp/byte.vrt', 'tmp/other_byte.vrt')

    ds = gdal.Open('tmp/other_byte.vrt')

    os.remove('tmp/other_byte.vrt')
    os.remove('tmp/byte.vrt')

    if ds is None:
        return 'fail'

    return 'success'

###############################################################################
# Test ComputeStatistics() when the VRT is a subwindow of the source dataset (#5468)


def vrt_read_14():

    src_ds = gdal.Open('data/byte.tif')
    mem_ds = gdal.GetDriverByName('GTiff').CreateCopy('/vsimem/vrt_read_14.tif', src_ds)
    mem_ds.FlushCache()  # hum this should not be necessary ideally
    vrt_ds = gdal.Open("""<VRTDataset rasterXSize="4" rasterYSize="4">
  <VRTRasterBand dataType="Byte" band="1">
    <SimpleSource>
      <SourceFilename relativeToVRT="0">/vsimem/vrt_read_14.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
      <SrcRect xOff="2" yOff="2" xSize="4" ySize="4" />
      <DstRect xOff="0" yOff="0" xSize="4" ySize="4" />
    </SimpleSource>
  </VRTRasterBand>
</VRTDataset>""")

    vrt_stats = vrt_ds.GetRasterBand(1).ComputeStatistics(False)

    mem_ds = None
    vrt_ds = None

    gdal.GetDriverByName('GTiff').Delete('/vsimem/vrt_read_14.tif')

    if vrt_stats[0] != 115.0 or vrt_stats[1] != 173.0:
        print(vrt_stats)
        gdaltest.post_reason('fail')
        return 'fail'

    return 'success'

###############################################################################
# Test RasterIO() with resampling on SimpleSource


def vrt_read_15():

    vrt_ds = gdal.Open("""<VRTDataset rasterXSize="9" rasterYSize="9">
  <VRTRasterBand dataType="Byte" band="1">
    <SimpleSource>
      <SourceFilename relativeToVRT="0">data/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
      <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
      <DstRect xOff="0" yOff="0" xSize="9" ySize="9" />
    </SimpleSource>
    <SimpleSource>
      <SourceFilename relativeToVRT="0">data/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
      <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
      <DstRect xOff="0" yOff="0" xSize="9" ySize="9" />
    </SimpleSource>
  </VRTRasterBand>
</VRTDataset>""")

    cs = vrt_ds.GetRasterBand(1).Checksum()
    if cs != 1044:
        print(cs)
        return 'fail'

    return 'success'

###############################################################################
# Test RasterIO() with resampling on ComplexSource


def vrt_read_16():

    vrt_ds = gdal.Open("""<VRTDataset rasterXSize="9" rasterYSize="9">
  <VRTRasterBand dataType="Byte" band="1">
    <ComplexSource>
      <SourceFilename relativeToVRT="0">data/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
      <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
      <DstRect xOff="0" yOff="0" xSize="9" ySize="9" />
    </ComplexSource>
    <ComplexSource>
      <SourceFilename relativeToVRT="0">data/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
      <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
      <DstRect xOff="0" yOff="0" xSize="9" ySize="9" />
    </ComplexSource>
  </VRTRasterBand>
</VRTDataset>""")

    cs = vrt_ds.GetRasterBand(1).Checksum()
    if cs != 1044:
        print(cs)
        return 'fail'

    return 'success'

###############################################################################
# Test RasterIO() with resampling on AveragedSource


def vrt_read_17():

    vrt_ds = gdal.Open("""<VRTDataset rasterXSize="9" rasterYSize="9">
  <VRTRasterBand dataType="Byte" band="1">
    <AveragedSource>
      <SourceFilename relativeToVRT="0">data/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
      <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
      <DstRect xOff="0" yOff="0" xSize="9" ySize="9" />
    </AveragedSource>
  </VRTRasterBand>
</VRTDataset>""")

    # Note: AveragedSource with resampling does not give consistent results
    # depending on the RasterIO() request
    cs = vrt_ds.GetRasterBand(1).Checksum()
    if cs != 847:
        print(cs)
        return 'fail'

    return 'success'

###############################################################################
# Test that relative path is correctly VRT-in-VRT


def vrt_read_18():

    vrt_ds = gdal.Open('data/vrtinvrt.vrt')
    cs = vrt_ds.GetRasterBand(1).Checksum()
    if cs != 4672:
        print(cs)
        return 'fail'

    return 'success'

###############################################################################
# Test shared="0"


def vrt_read_19():

    vrt_ds = gdal.Open("""<VRTDataset rasterXSize="20" rasterYSize="20">
  <VRTRasterBand dataType="Byte" band="1">
    <AveragedSource>
      <SourceFilename relativeToVRT="0" shared="0">data/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
    </AveragedSource>
  </VRTRasterBand>
</VRTDataset>""")

    vrt2_ds = gdal.Open("""<VRTDataset rasterXSize="20" rasterYSize="20">
  <VRTRasterBand dataType="Byte" band="1">
    <AveragedSource>
      <SourceFilename relativeToVRT="0" shared="0">data/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
    </AveragedSource>
  </VRTRasterBand>
</VRTDataset>""")

    cs = vrt_ds.GetRasterBand(1).Checksum()
    if cs != 4672:
        print(cs)
        return 'fail'

    cs = vrt2_ds.GetRasterBand(1).Checksum()
    if cs != 4672:
        print(cs)
        return 'fail'

    return 'success'


###############################################################################
# Test 2 level of VRT with shared="0"

def vrt_read_20():

    if test_cli_utilities.get_gdalinfo_path() is None:
        return 'skip'

    shutil.copy('data/byte.tif', 'tmp')
    for i in range(3):
        open('tmp/byte1_%d.vrt' % (i + 1), 'wt').write("""<VRTDataset rasterXSize="20" rasterYSize="20">
    <VRTRasterBand dataType="Byte" band="1">
        <SimpleSource>
        <SourceFilename relativeToVRT="1">byte.tif</SourceFilename>
        <SourceBand>1</SourceBand>
        <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
        <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
        <DstRect xOff="0" yOff="0" xSize="20" ySize="20" />
        </SimpleSource>
    </VRTRasterBand>
    </VRTDataset>""")
    open('tmp/byte2.vrt', 'wt').write("""<VRTDataset rasterXSize="20" rasterYSize="20">
  <VRTRasterBand dataType="Byte" band="1">
    <SimpleSource>
      <SourceFilename relativeToVRT="1">byte1_1.vrt</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
      <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
      <DstRect xOff="0" yOff="0" xSize="20" ySize="20" />
    </SimpleSource>
    <SimpleSource>
      <SourceFilename relativeToVRT="1">byte1_2.vrt</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
      <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
      <DstRect xOff="0" yOff="0" xSize="20" ySize="20" />
    </SimpleSource>
    <SimpleSource>
      <SourceFilename relativeToVRT="1">byte1_3.vrt</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
      <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
      <DstRect xOff="0" yOff="0" xSize="20" ySize="20" />
    </SimpleSource>
  </VRTRasterBand>
</VRTDataset>""")
    ret = gdaltest.runexternal(test_cli_utilities.get_gdalinfo_path() + ' -checksum tmp/byte2.vrt --config VRT_SHARED_SOURCE 0 --config GDAL_MAX_DATASET_POOL_SIZE 3')
    if ret.find('Checksum=4672') < 0:
        gdaltest.post_reason('failure')
        print(ret)
        return 'fail'

    os.unlink('tmp/byte.tif')
    os.unlink('tmp/byte1_1.vrt')
    os.unlink('tmp/byte1_2.vrt')
    os.unlink('tmp/byte1_3.vrt')
    os.unlink('tmp/byte2.vrt')

    return 'success'

###############################################################################
# Test implicit virtual overviews


def vrt_read_21():

    ds = gdal.Open('data/byte.tif')
    data = ds.ReadRaster(0, 0, 20, 20, 400, 400)
    ds = None
    ds = gdal.GetDriverByName('GTiff').Create('/vsimem/byte.tif', 400, 400)
    ds.WriteRaster(0, 0, 400, 400, data)
    ds.BuildOverviews('NEAR', [2])
    ds = None

    gdal.FileFromMemBuffer('/vsimem/vrt_read_21.vrt', """<VRTDataset rasterXSize="800" rasterYSize="800">
  <VRTRasterBand dataType="Byte" band="1">
    <SimpleSource>
      <SourceFilename>/vsimem/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="400" RasterYSize="400" DataType="Byte" BlockXSize="400" BlockYSize="1" />
      <SrcRect xOff="100" yOff="100" xSize="200" ySize="250" />
      <DstRect xOff="300" yOff="400" xSize="200" ySize="250" />
    </SimpleSource>
  </VRTRasterBand>
</VRTDataset>""")
    ds = gdal.Open('/vsimem/vrt_read_21.vrt')
    if ds.GetRasterBand(1).GetOverviewCount() != 1:
        gdaltest.post_reason('failure')
        print(ds.GetRasterBand(1).GetOverviewCount())
        return 'fail'
    data_ds_one_band = ds.ReadRaster(0, 0, 800, 800, 400, 400)
    ds = None

    gdal.FileFromMemBuffer('/vsimem/vrt_read_21.vrt', """<VRTDataset rasterXSize="800" rasterYSize="800">
  <VRTRasterBand dataType="Byte" band="1">
    <SimpleSource>
      <SourceFilename>/vsimem/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="400" RasterYSize="400" DataType="Byte" BlockXSize="400" BlockYSize="1" />
      <SrcRect xOff="100" yOff="100" xSize="200" ySize="250" />
      <DstRect xOff="300" yOff="400" xSize="200" ySize="250" />
    </SimpleSource>
  </VRTRasterBand>
  <VRTRasterBand dataType="Byte" band="2">
    <ComplexSource>
      <SourceFilename>/vsimem/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="400" RasterYSize="400" DataType="Byte" BlockXSize="400" BlockYSize="1" />
      <SrcRect xOff="100" yOff="100" xSize="200" ySize="250" />
      <DstRect xOff="300" yOff="400" xSize="200" ySize="250" />
      <ScaleOffset>10</ScaleOffset>
    </ComplexSource>
  </VRTRasterBand>
</VRTDataset>""")
    ds = gdal.Open('/vsimem/vrt_read_21.vrt')
    if ds.GetRasterBand(1).GetOverviewCount() != 1:
        gdaltest.post_reason('failure')
        print(ds.GetRasterBand(1).GetOverviewCount())
        return 'fail'

    ds = gdal.Open('/vsimem/vrt_read_21.vrt')
    ovr_band = ds.GetRasterBand(1).GetOverview(-1)
    if ovr_band is not None:
        gdaltest.post_reason('failure')
        return 'fail'
    ovr_band = ds.GetRasterBand(1).GetOverview(1)
    if ovr_band is not None:
        gdaltest.post_reason('failure')
        return 'fail'
    ovr_band = ds.GetRasterBand(1).GetOverview(0)
    if ovr_band is None:
        gdaltest.post_reason('failure')
        return 'fail'
    cs = ovr_band.Checksum()
    cs2 = ds.GetRasterBand(2).GetOverview(0).Checksum()

    data = ds.ReadRaster(0, 0, 800, 800, 400, 400)

    if data != data_ds_one_band + ds.GetRasterBand(2).ReadRaster(0, 0, 800, 800, 400, 400):
        gdaltest.post_reason('failure')
        return 'fail'

    mem_ds = gdal.GetDriverByName('MEM').Create('', 400, 400, 2)
    mem_ds.WriteRaster(0, 0, 400, 400, data)
    ref_cs = mem_ds.GetRasterBand(1).Checksum()
    ref_cs2 = mem_ds.GetRasterBand(2).Checksum()
    mem_ds = None
    if cs != ref_cs:
        gdaltest.post_reason('failure')
        print(cs)
        print(ref_cs)
        return 'fail'
    if cs2 != ref_cs2:
        gdaltest.post_reason('failure')
        print(cs2)
        print(ref_cs2)
        return 'fail'

    ds.BuildOverviews('NEAR', [2])
    expected_cs = ds.GetRasterBand(1).GetOverview(0).Checksum()
    expected_cs2 = ds.GetRasterBand(2).GetOverview(0).Checksum()
    ds = None

    if cs != expected_cs:
        gdaltest.post_reason('failure')
        print(cs)
        print(expected_cs)
        return 'fail'
    if cs2 != expected_cs2:
        gdaltest.post_reason('failure')
        print(cs2)
        print(expected_cs2)
        return 'fail'

    gdal.Unlink('/vsimem/vrt_read_21.vrt')
    gdal.Unlink('/vsimem/vrt_read_21.vrt.ovr')
    gdal.Unlink('/vsimem/byte.tif')

    return 'success'

###############################################################################
# Test that we honour NBITS with SimpleSource and ComplexSource


def vrt_read_22():

    ds = gdal.Open('data/byte.tif')
    data = ds.ReadRaster()
    ds = None
    ds = gdal.GetDriverByName('GTiff').Create('/vsimem/byte.tif', 20, 20)
    ds.WriteRaster(0, 0, 20, 20, data)
    ds.GetRasterBand(1).ComputeStatistics(False)
    ds = None

    ds = gdal.Open("""<VRTDataset rasterXSize="20" rasterYSize="20">
  <VRTRasterBand dataType="Byte" band="1">
    <Metadata domain="IMAGE_STRUCTURE">
        <MDI key="NBITS">6</MDI>
    </Metadata>
    <SimpleSource>
      <SourceFilename>/vsimem/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
    </SimpleSource>
  </VRTRasterBand>
</VRTDataset>""")
    if ds.GetRasterBand(1).GetMinimum() != 63:
        gdaltest.post_reason('failure')
        return 'fail'

    if ds.GetRasterBand(1).GetMaximum() != 63:
        gdaltest.post_reason('failure')
        return 'fail'

    if ds.GetRasterBand(1).ComputeRasterMinMax() != (63, 63):
        gdaltest.post_reason('failure')
        return 'fail'

    if ds.GetRasterBand(1).ComputeStatistics(False) != [63.0, 63.0, 63.0, 0.0]:
        gdaltest.post_reason('failure')
        print(ds.GetRasterBand(1).ComputeStatistics(False))
        return 'fail'

    data = ds.ReadRaster()
    got = struct.unpack('B' * 20 * 20, data)
    if got[0] != 63:
        gdaltest.post_reason('failure')
        return 'fail'

    ds = gdal.Open("""<VRTDataset rasterXSize="20" rasterYSize="20">
  <VRTRasterBand dataType="Byte" band="1">
    <Metadata domain="IMAGE_STRUCTURE">
        <MDI key="NBITS">6</MDI>
    </Metadata>
    <ComplexSource>
      <SourceFilename>/vsimem/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
    </ComplexSource>
  </VRTRasterBand>
</VRTDataset>""")
    if ds.GetRasterBand(1).GetMinimum() != 63:
        gdaltest.post_reason('failure')
        return 'fail'

    if ds.GetRasterBand(1).GetMaximum() != 63:
        gdaltest.post_reason('failure')
        return 'fail'

    if ds.GetRasterBand(1).ComputeRasterMinMax() != (63, 63):
        gdaltest.post_reason('failure')
        return 'fail'

    if ds.GetRasterBand(1).ComputeStatistics(False) != [63.0, 63.0, 63.0, 0.0]:
        gdaltest.post_reason('failure')
        print(ds.GetRasterBand(1).ComputeStatistics(False))
        return 'fail'

    ds = gdal.Open("""<VRTDataset rasterXSize="20" rasterYSize="20">
  <VRTRasterBand dataType="Byte" band="1">
    <Metadata domain="IMAGE_STRUCTURE">
        <MDI key="NBITS">6</MDI>
    </Metadata>
    <ComplexSource>
      <SourceFilename>/vsimem/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <ScaleOffset>10</ScaleOffset>
    </ComplexSource>
  </VRTRasterBand>
</VRTDataset>""")
    if ds.GetRasterBand(1).GetMinimum() is not None:
        gdaltest.post_reason('failure')
        print(ds.GetRasterBand(1).GetMinimum())
        return 'fail'

    if ds.GetRasterBand(1).GetMaximum() is not None:
        gdaltest.post_reason('failure')
        return 'fail'

    if ds.GetRasterBand(1).ComputeRasterMinMax() != (63, 63):
        gdaltest.post_reason('failure')
        return 'fail'

    if ds.GetRasterBand(1).ComputeStatistics(False) != [63.0, 63.0, 63.0, 0.0]:
        gdaltest.post_reason('failure')
        print(ds.GetRasterBand(1).ComputeStatistics(False))
        return 'fail'

    gdal.Unlink('/vsimem/byte.tif')
    gdal.Unlink('/vsimem/byte.tif.aux.xml')

    return 'success'

###############################################################################
# Test non-nearest resampling on a VRT exposing a nodata value but with
# an underlying dataset without nodata


def vrt_read_23():

    try:
        from osgeo import gdalnumeric
        gdalnumeric.zeros
        import numpy
    except (ImportError, AttributeError):
        return 'skip'

    mem_ds = gdal.GetDriverByName('GTiff').Create('/vsimem/vrt_read_23.tif', 2, 1)
    mem_ds.GetRasterBand(1).WriteArray(numpy.array([[0, 10]]))
    mem_ds = None
    ds = gdal.Open("""<VRTDataset rasterXSize="2" rasterYSize="1">
  <VRTRasterBand dataType="Byte" band="1">
    <NoDataValue>0</NoDataValue>
    <SimpleSource>
      <SourceFilename>/vsimem/vrt_read_23.tif</SourceFilename>
    </SimpleSource>
  </VRTRasterBand>
</VRTDataset>""")
    got_ar = ds.GetRasterBand(1).ReadAsArray(0, 0, 2, 1, 4, 1, resample_alg=gdal.GRIORA_Bilinear)
    if list(got_ar[0]) != [0, 10, 10, 10]:
        gdaltest.post_reason('failure')
        print(list(got_ar[0]))
        return 'fail'
    if ds.ReadRaster(0, 0, 2, 1, 4, 1, resample_alg=gdal.GRIORA_Bilinear) != ds.GetRasterBand(1).ReadRaster(0, 0, 2, 1, 4, 1, resample_alg=gdal.GRIORA_Bilinear):
        gdaltest.post_reason('failure')
        return 'fail'
    ds = None

    gdal.Unlink('/vsimem/vrt_read_23.tif')

    # Same but with nodata set on source band too
    mem_ds = gdal.GetDriverByName('GTiff').Create('/vsimem/vrt_read_23.tif', 2, 1)
    mem_ds.GetRasterBand(1).SetNoDataValue(0)
    mem_ds.GetRasterBand(1).WriteArray(numpy.array([[0, 10]]))
    mem_ds = None
    ds = gdal.Open("""<VRTDataset rasterXSize="2" rasterYSize="1">
  <VRTRasterBand dataType="Byte" band="1">
    <NoDataValue>0</NoDataValue>
    <SimpleSource>
      <SourceFilename>/vsimem/vrt_read_23.tif</SourceFilename>
    </SimpleSource>
  </VRTRasterBand>
</VRTDataset>""")
    got_ar = ds.GetRasterBand(1).ReadAsArray(0, 0, 2, 1, 4, 1, resample_alg=gdal.GRIORA_Bilinear)
    if list(got_ar[0]) != [0, 10, 10, 10]:
        gdaltest.post_reason('failure')
        print(list(got_ar[0]))
        return 'fail'
    if ds.ReadRaster(0, 0, 2, 1, 4, 1, resample_alg=gdal.GRIORA_Bilinear) != ds.GetRasterBand(1).ReadRaster(0, 0, 2, 1, 4, 1, resample_alg=gdal.GRIORA_Bilinear):
        gdaltest.post_reason('failure')
        return 'fail'
    ds = None

    gdal.Unlink('/vsimem/vrt_read_23.tif')

    return 'success'

###############################################################################
# Test floating point rounding issues when the VRT does a zoom-in


def vrt_read_24():

    ds = gdal.Open('data/zoom_in.vrt')
    data = ds.ReadRaster(34, 5, 66, 87)
    ds = None

    ds = gdal.GetDriverByName('MEM').Create('', 66, 87)
    ds.WriteRaster(0, 0, 66, 87, data)
    cs = ds.GetRasterBand(1).Checksum()
    ds = None

    # Please do not change the expected checksum without checking that
    # the result image has no vertical black line in the middle
    if cs != 46612:
        gdaltest.post_reason('failure')
        print(cs)
        return 'fail'
    ds = None

    return 'success'

###############################################################################
# Test GetDataCoverageStatus()


def vrt_read_25():

    import ogrtest
    if not ogrtest.have_geos():
        return 'skip'

    ds = gdal.Open("""<VRTDataset rasterXSize="2000" rasterYSize="200">
  <VRTRasterBand dataType="Byte" band="1">
    <SimpleSource>
      <SourceFilename relativeToVRT="0">data/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
      <DstRect xOff="0" yOff="0" xSize="20" ySize="20" />
    </SimpleSource>
    <SimpleSource>
      <SourceFilename relativeToVRT="0">data/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
      <DstRect xOff="1000" yOff="30" xSize="10" ySize="20" />
    </SimpleSource>
    <SimpleSource>
      <SourceFilename relativeToVRT="0">data/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
      <DstRect xOff="1010" yOff="30" xSize="10" ySize="20" />
    </SimpleSource>
  </VRTRasterBand>
</VRTDataset>""")

    (flags, pct) = ds.GetRasterBand(1).GetDataCoverageStatus(0, 0, 20, 20)
    if flags != gdal.GDAL_DATA_COVERAGE_STATUS_DATA or pct != 100.0:
        gdaltest.post_reason('failure')
        print(flags)
        print(pct)
        return 'fail'

    (flags, pct) = ds.GetRasterBand(1).GetDataCoverageStatus(1005, 35, 10, 10)
    if flags != gdal.GDAL_DATA_COVERAGE_STATUS_DATA or pct != 100.0:
        gdaltest.post_reason('failure')
        print(flags)
        print(pct)
        return 'fail'

    (flags, pct) = ds.GetRasterBand(1).GetDataCoverageStatus(100, 100, 20, 20)
    if flags != gdal.GDAL_DATA_COVERAGE_STATUS_EMPTY or pct != 0.0:
        gdaltest.post_reason('failure')
        print(flags)
        print(pct)
        return 'fail'

    (flags, pct) = ds.GetRasterBand(1).GetDataCoverageStatus(10, 10, 20, 20)
    if flags != gdal.GDAL_DATA_COVERAGE_STATUS_DATA | gdal.GDAL_DATA_COVERAGE_STATUS_EMPTY or pct != 25.0:
        gdaltest.post_reason('failure')
        print(flags)
        print(pct)
        return 'fail'

    return 'success'


###############################################################################
# Test consistency of RasterIO() with resampling, that is extracting different
# sub-windows give consistent results

def vrt_read_26():

    vrt_ds = gdal.Open("""<VRTDataset rasterXSize="22" rasterYSize="22">
  <VRTRasterBand dataType="Byte" band="1">
    <SimpleSource>
      <SourceFilename relativeToVRT="0">data/byte.tif</SourceFilename>
      <SourceBand>1</SourceBand>
      <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
      <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
      <DstRect xOff="0" yOff="0" xSize="22" ySize="22" />
    </SimpleSource>
  </VRTRasterBand>
</VRTDataset>""")

    full_data = vrt_ds.GetRasterBand(1).ReadRaster(0, 0, 22, 22)
    full_data = struct.unpack('B' * 22 * 22, full_data)

    partial_data = vrt_ds.GetRasterBand(1).ReadRaster(1, 1, 1, 1)
    partial_data = struct.unpack('B' * 1 * 1, partial_data)

    if partial_data[0] != full_data[22 + 1]:
        gdaltest.post_reason('fail')
        print(full_data)
        print(partial_data[0])
        print(full_data[22 + 1])
        return 'fail'

    return 'success'

###############################################################################
# Test fix for https://bugs.chromium.org/p/oss-fuzz/issues/detail?id=1553


def vrt_read_27():

    gdal.Open('data/empty_gcplist.vrt')

    return 'success'

###############################################################################
# Test fix for https://bugs.chromium.org/p/oss-fuzz/issues/detail?id=1551


def vrt_read_28():

    with gdaltest.error_handler():
        ds = gdal.Open('<VRTDataset rasterXSize="1 "rasterYSize="1"><VRTRasterBand band="-2147483648"><SimpleSource></SimpleSource></VRTRasterBand></VRTDataset>')
    if ds is not None:
        return 'fail'

    return 'success'


###############################################################################
# Check VRT source sharing and non-sharing situations (#6949)

def vrt_read_29():

    f = open('data/byte.tif')
    lst_before = gdaltest.get_opened_files()
    if len(lst_before) == 0:
        return 'skip'
    f.close()
    lst_before = gdaltest.get_opened_files()

    gdal.Translate('tmp/vrt_read_29.tif', 'data/byte.tif')

    vrt_text = """<VRTDataset rasterXSize="20" rasterYSize="20">
    <VRTRasterBand dataType="Byte" band="1">
        <SimpleSource>
        <SourceFilename>tmp/vrt_read_29.tif</SourceFilename>
        <SourceBand>1</SourceBand>
        <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
        <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
        <DstRect xOff="0" yOff="0" xSize="20" ySize="20" />
        </SimpleSource>
    </VRTRasterBand>
    <VRTRasterBand dataType="Byte" band="2">
        <SimpleSource>
        <SourceFilename>tmp/vrt_read_29.tif</SourceFilename>
        <SourceBand>1</SourceBand>
        <SourceProperties RasterXSize="20" RasterYSize="20" DataType="Byte" BlockXSize="20" BlockYSize="20" />
        <SrcRect xOff="0" yOff="0" xSize="20" ySize="20" />
        <DstRect xOff="0" yOff="0" xSize="20" ySize="20" />
        </SimpleSource>
    </VRTRasterBand>
    </VRTDataset>"""

    ds = gdal.Open(vrt_text)
    # Just after opening, we shouldn't have read the source
    lst = gdaltest.get_opened_files()
    if lst.sort() != lst_before.sort():
        gdaltest.post_reason('fail')
        print(lst)
        print(lst_before)
        return 'fail'

    # Check that the 2 bands share the same source handle
    ds.GetRasterBand(1).Checksum()
    lst = gdaltest.get_opened_files()
    if len(lst) != len(lst_before) + 1:
        gdaltest.post_reason('fail')
        print(lst)
        print(lst_before)
        return 'fail'
    ds.GetRasterBand(2).Checksum()
    lst = gdaltest.get_opened_files()
    if len(lst) != len(lst_before) + 1:
        gdaltest.post_reason('fail')
        print(lst)
        print(lst_before)
        return 'fail'

    # Open a second VRT dataset handle
    ds2 = gdal.Open(vrt_text)

    # Check that it consumes an extra handle
    ds2.GetRasterBand(1).Checksum()
    lst = gdaltest.get_opened_files()
    if len(lst) != len(lst_before) + 2:
        gdaltest.post_reason('fail')
        print(lst)
        print(lst_before)
        return 'fail'

    gdal.Unlink('tmp/vrt_read_29.tif')

    return 'success'

###############################################################################
# Check VRT reading with DatasetRasterIO


def vrt_read_30():

    ds = gdal.Open("""<VRTDataset rasterXSize="2" rasterYSize="2">
  <VRTRasterBand dataType="Byte" band="1">
  </VRTRasterBand>
  <VRTRasterBand dataType="Byte" band="2">
  </VRTRasterBand>
  <VRTRasterBand dataType="Byte" band="3">
  </VRTRasterBand>
</VRTDataset>""")

    data = ds.ReadRaster(0, 0, 2, 2, 2, 2, buf_pixel_space=3, buf_line_space=2 * 3, buf_band_space=1)
    got = struct.unpack('B' * 2 * 2 * 3, data)
    for i in range(2 * 2 * 3):
        if got[i] != 0:
            print(got)
            return 'fail'
    ds = None

    return 'success'

###############################################################################
# Check that we take into account intermediate data type demotion


def vrt_read_31():

    gdal.FileFromMemBuffer('/vsimem/in.asc',
                           """ncols        2
nrows        2
xllcorner    0
yllcorner    0
dx           1
dy           1
-255         1
254          256""")

    ds = gdal.Translate('', '/vsimem/in.asc', outputType=gdal.GDT_Byte, format='VRT')

    data = ds.GetRasterBand(1).ReadRaster(0, 0, 2, 2, buf_type=gdal.GDT_Float32)
    got = struct.unpack('f' * 2 * 2, data)
    if got != (0, 1, 254, 255):
        gdaltest.post_reason('fail')
        print(got)
        return 'fail'

    data = ds.ReadRaster(0, 0, 2, 2, buf_type=gdal.GDT_Float32)
    got = struct.unpack('f' * 2 * 2, data)
    if got != (0, 1, 254, 255):
        gdaltest.post_reason('fail')
        print(got)
        return 'fail'

    ds = None

    gdal.Unlink('/vsimem/in.asc')

    return 'success'


###############################################################################
# Test reading a VRT where the NODATA & NoDataValue are slighly below the
# minimum float value (https://github.com/OSGeo/gdal/issues/1071)

def vrt_float32_with_nodata_slightly_below_float_min():

    shutil.copyfile('data/minfloat.tif', 'tmp/minfloat.tif')
    shutil.copyfile('data/minfloat_nodata_slightly_out_of_float.vrt',
                    'tmp/minfloat_nodata_slightly_out_of_float.vrt')
    gdal.Unlink('tmp/minfloat_nodata_slightly_out_of_float.vrt.aux.xml')

    ds = gdal.Open('tmp/minfloat_nodata_slightly_out_of_float.vrt')
    nodata = ds.GetRasterBand(1).GetNoDataValue()
    stats = ds.GetRasterBand(1).ComputeStatistics(False)
    ds = None

    vrt_content = open('tmp/minfloat_nodata_slightly_out_of_float.vrt', 'rt').read()

    gdal.Unlink('tmp/minfloat.tif')
    gdal.Unlink('tmp/minfloat_nodata_slightly_out_of_float.vrt')

    # Check that the values were 'normalized' when regenerating the VRT
    if vrt_content.find('-3.402823466385289') >= 0:
        gdaltest.post_reason('did not get expected nodata in rewritten VRT')
        print(vrt_content)
        return 'fail'

    if nodata != -3.4028234663852886e+38:
        gdaltest.post_reason('did not get expected nodata')
        print("%.18g" % nodata)
        return 'fail'

    if stats != [-3.0, 5.0, 1.0, 4.0]:
        gdaltest.post_reason('did not get expected stats')
        print(stats)
        return 'fail'

    return 'success'



for item in init_list:
    ut = gdaltest.GDALTest('VRT', item[0], item[1], item[2])
    if ut is None:
        print('VRT tests skipped')
        sys.exit()
    gdaltest_list.append((ut.testOpen, item[0]))

gdaltest_list.append(vrt_read_1)
gdaltest_list.append(vrt_read_2)
gdaltest_list.append(vrt_read_3)
gdaltest_list.append(vrt_read_4)
gdaltest_list.append(vrt_read_5)
gdaltest_list.append(vrt_read_6)
gdaltest_list.append(vrt_read_7)
gdaltest_list.append(vrt_read_8)
gdaltest_list.append(vrt_read_9)
gdaltest_list.append(vrt_read_10)
gdaltest_list.append(vrt_read_11)
gdaltest_list.append(vrt_read_12)
gdaltest_list.append(vrt_read_13)
gdaltest_list.append(vrt_read_14)
gdaltest_list.append(vrt_read_15)
gdaltest_list.append(vrt_read_16)
gdaltest_list.append(vrt_read_17)
gdaltest_list.append(vrt_read_18)
gdaltest_list.append(vrt_read_19)
gdaltest_list.append(vrt_read_20)
gdaltest_list.append(vrt_read_21)
gdaltest_list.append(vrt_read_22)
gdaltest_list.append(vrt_read_23)
gdaltest_list.append(vrt_read_24)
gdaltest_list.append(vrt_read_25)
gdaltest_list.append(vrt_read_26)
gdaltest_list.append(vrt_read_27)
gdaltest_list.append(vrt_read_28)
gdaltest_list.append(vrt_read_29)
gdaltest_list.append(vrt_read_30)
gdaltest_list.append(vrt_read_31)
gdaltest_list.append(vrt_float32_with_nodata_slightly_below_float_min)

if __name__ == '__main__':

    gdaltest.setup_run('vrt_read')

    gdaltest.run_tests(gdaltest_list)

    gdaltest.summarize()
