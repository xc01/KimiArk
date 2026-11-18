from run_medical_groups import *

def outer_defender(replacement):
    edits=[{'type':'replace','operator':SPOT,'replacement':FRIS},{'type':'replace','operator':MEL,'replacement':replacement},change(FRIS,'DEPLOY',2341,frame=91,tile=[4,5],direction='RIGHT'),remove(FRIS,'ACTIVATE_SKILL',3330),remove(FRIS,'ACTIVATE_SKILL',6500),change(replacement,'DEPLOY',841,frame=901),remove(replacement,'RETREAT',2054),remove(replacement,'DEPLOY',4155),remove(replacement,'ACTIVATE_SKILL',6350)]
    return edits

def main():
    # Low damage is accepted as a risk; defender armor can change the repeated shell survival, and all four lanes retain a holder.
    for replacement in [SPOT,'char_209_ardign','char_122_beagle']:
        edits=outer_defender(replacement)
        if replacement==SPOT: edits +=[add(replacement,'ACTIVATE_SKILL',1352),add(replacement,'ACTIVATE_SKILL',3330),add(replacement,'ACTIVATE_SKILL',6500)]
        elif replacement=='char_209_ardign': edits +=[add(replacement,'ACTIVATE_SKILL',1400),add(replacement,'ACTIVATE_SKILL',2100),add(replacement,'ACTIVATE_SKILL',2800),add(replacement,'ACTIVATE_SKILL',3500),add(replacement,'ACTIVATE_SKILL',4200),add(replacement,'ACTIVATE_SKILL',5000),add(replacement,'ACTIVATE_SKILL',6000),add(replacement,'ACTIVATE_SKILL',7000)]
        else:edits +=[add(replacement,'ACTIVATE_SKILL',2150),add(replacement,'ACTIVATE_SKILL',4300),add(replacement,'ACTIVATE_SKILL',6500)]
        r=variant('DEFENDER_OUTER_'+replacement,edits,'Replace persistent lower-outer Melantha with armored defender, and old Spot with Friston lower-middle. Preserve four-lane blocking instead of allowing Melantha second-shell death; check actual roadblock4 clearance and civilian safety, cannon output and armor.')
        if r.get('observed',{}).get('complete_win'):return
    for d in ['DOWN','RIGHT']:
        edits=outer_defender(SPOT)+[change(FANG,'DEPLOY',0,tile=[4,5],direction=d),change(FRIS,'DEPLOY',91,tile=[3,5],direction='UP'),add(SPOT,'ACTIVATE_SKILL',1352),add(SPOT,'ACTIVATE_SKILL',3330),add(SPOT,'ACTIVATE_SKILL',6500)]
        variant('DEFENDER_OUTER_UPFRIS_FANG'+d,edits,'Compare upper cheap blocker plus lower Fang with explicit armored outer handoff; facing down may add upper-runner damage before lower contact.')

if __name__=='__main__':main()
