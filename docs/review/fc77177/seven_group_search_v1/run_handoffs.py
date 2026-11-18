from search_batch import variant
from run_groups import *

def remove(op,kind,frame): return {'type':'remove','operator':op,'action':kind,'frame':frame}
def add(op,kind,frame,**fields): return {'type':'add','value':dict(action_type=kind,operator_id=op,frame=frame,**fields)}
SWAP=[change(FANG,'DEPLOY',0,tile=[4,5],direction='RIGHT'),change(MEL,'DEPLOY',4155,tile=[3,5],direction='UP')]

def main():
    # Ranged replacement compresses outer-upper and upper-middle coverage, leaving Fang on lower-middle.
    for tile,direction in [([2,5],'RIGHT'),([2,5],'LEFT'),([2,3],'RIGHT'),([2,3],'LEFT'),([2,6],'LEFT')]:
        edits=SWAP+[{'type':'replace','operator':MID,'replacement':'char_124_kroos'},change('char_124_kroos','DEPLOY',571,tile=tile,direction=direction),remove('char_124_kroos','ACTIVATE_SKILL',1772),remove('char_124_kroos','ACTIVATE_SKILL',5073)]
        r=variant('KROOS_MID'+''.join(map(str,tile))+'_'+direction,edits,'Replace Midnight group with Kroos multi-lane coverage; same seven IDs, Fang lower-middle and Melantha late upper-middle retained; test actual kills and roadblock3 clearance.')
        if r.get('observed',{}).get('complete_win'): return
    # Spot can cover upper middle until Melantha returns; Melantha must keep lower outer duty in the interim.
    for frame in [511,571,841,1261]:
        edits=SWAP+[change(SPOT,'DEPLOY',2341,frame=frame,tile=[3,5],direction='RIGHT'),remove(MEL,'RETREAT',2054),change(MEL,'DEPLOY',4155,frame=6500,tile=[3,5],direction='UP'),add(MEL,'RETREAT',4399),add(SPOT,'RETREAT',4400),add(SPOT,'DEPLOY',6501,tile=[6,5],direction='RIGHT'),change(MEL,'ACTIVATE_SKILL',6350,frame=7700)]
        r=variant('SPOT_UP_EARLY'+str(frame),edits,'Spot upper-middle intercepts new leaks while Melantha keeps lower outer; explicit retreats and cooldown-respecting return restore late duties. Observe DP and survival risk.')
        if r.get('observed',{}).get('complete_win'): return

if __name__=='__main__': main()
