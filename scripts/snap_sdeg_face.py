# -*- coding: utf-8 -*-
"""按 cohesive 面分别截图 (env: ODB, TAG, OUTDIR, OUTLOG)
一次会话输出三张: snap_<TAG>_hz4.png / _hz21.png / _xz.png
方法: LeafFromElementLabels(partInstanceName, labels) + DisplayGroup.add 合并"""
import os
from odbAccess import openOdb
from abaqusConstants import *

LOG = open(os.environ['OUTLOG'], 'w')
def log(*a):
    LOG.write(' '.join(str(x) for x in a) + '\n')
    LOG.flush()

from caeModules import *
import displayGroupOdbToolset as dgo

odb = openOdb(os.environ['ODB'], readOnly=True)
TAG = os.environ['TAG']
OUTDIR = os.environ['OUTDIR']
log('ODB opened, TAG =', TAG)

# XZ 相关 elset (UPPER instance 内, 排除水平层)
xz_upper_sets = set()
for sn in odb.rootAssembly.instances['UPPER-GEOM-1'].elementSets.keys():
    if 'COHESIVE_XZ' in sn or 'COH_CONT' in sn:
        xz_upper_sets.add(sn)
xz_upper_sets = tuple(sorted(xz_upper_sets))
log('XZ upper elsets:', xz_upper_sets)

# 三个面的 leaf 列表: (名称, [leaf...], 视角)
def labels_leaf(inst_name, elsets):
    inst = odb.rootAssembly.instances[inst_name]
    labs = set()
    for sn in elsets:
        if sn in inst.elementSets:
            for e in inst.elementSets[sn].elements:
                if e.type.startswith('COH'):
                    labs.add(e.label)
    labs = tuple(sorted(labs))
    log('  leaf %s n=%d' % (inst_name, len(labs)))
    return dgo.LeafFromElementLabels(inst_name, labs)

faces = [
    ('hz4', [labels_leaf('M5-GEOM-1', ('CELL_COHESIVE_H_Z4',))],
     (200.0, 200.0, 800.0), (200.0, 200.0, 3.95), (0.0, 1.0, 0.0)),
    ('hz21', [labels_leaf('M4-GEOM-1', ('CELL_COHESIVE_H_Z21',))],
     (200.0, 200.0, 800.0), (200.0, 200.0, 20.95), (0.0, 1.0, 0.0)),
    ('xz', [labels_leaf('M5-GEOM-1', ('CELL_COHESIVE_XZ',)),
            labels_leaf('M4-GEOM-1', ('CELL_COHESIVE_XZ',)),
            labels_leaf('UPPER-GEOM-1', xz_upper_sets)],
     (200.0, 900.0, 11.0), (200.0, 200.0, 11.0), (0.0, 0.0, 1.0)),
]

vp = session.viewports['Viewport: 1']
vp.setValues(displayedObject=odb)
step_idx = len(list(odb.steps.keys())) - 1
nf = len(list(odb.steps.values())[-1].frames)
vp.setValues(width=420, height=315)

# 逐面截图 (每个面完整渲染序列)
for name, leaves, cam, tgt, up in faces:
    log('FACE', name)
    vp.odbDisplay.displayGroup.replace(leaf=leaves[0])
    for lf in leaves[1:]:
        try:
            vp.odbDisplay.displayGroup.add(leaf=lf)
        except Exception:
            try:
                vp.odbDisplay.displayGroup.add(lf)
            except Exception as e:
                log('  add leaf err:', str(e)[:60])
    vp.odbDisplay.setPrimaryVariable(variableLabel='SDEG',
                                     outputPosition=INTEGRATION_POINT)
    vp.odbDisplay.setFrame(step=step_idx, frame=nf - 1)
    vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
    vp.odbDisplay.contourOptions.setValues(
        minAutoCompute=False, maxAutoCompute=False,
        minValue=0.01, maxValue=1.0,
        numIntervals=9, intervalType=UNIFORM,
        outsideLimitsMode=SPECTRUM)
    vp.odbDisplay.commonOptions.setValues(
        deformationScaling=UNIFORM, uniformScaleFactor=1.0, visibleEdges=ALL)
    vp.viewportAnnotationOptions.setValues(triad=OFF, title=OFF, state=OFF,
                                           legendTitle=ON, legendBox=ON)
    try:
        vp.viewportAnnotationOptions.setValues(
            legendFont='-*-verdana-bold-r-normal-*-*-240-*-*-p-*-*-*')
    except Exception as e:
        log('  legend font warn:', str(e)[:60])
    vp.view.setValues(projection=PARALLEL,
                      cameraPosition=cam,
                      cameraUpVector=up,
                      cameraTarget=tgt)
    vp.view.fitView()
    out = os.path.join(OUTDIR, 'snap_%s_%s.png' % (TAG, name))
    session.printToFile(fileName=out, format=PNG, canvasObjects=(vp,))
    log('SNAP %s -> %s' % (name, out))

log('ALL DONE')
LOG.close()
