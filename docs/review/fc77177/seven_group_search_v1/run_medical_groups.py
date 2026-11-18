from run_handoffs import *

FRIS='char_4093_frston';STEWARD='char_210_stward'

def middle_robot_base():
    return [{'type':'replace','operator':SPOT,'replacement':FRIS},change(FRIS,'DEPLOY',2341,frame=91,tile=[4,5],direction='RIGHT'),remove(FRIS,'ACTIVATE_SKILL',3330),remove(FRIS,'ACTIVATE_SKILL',6500),remove(MEL,'RETREAT',2054),remove(MEL,'DEPLOY',4155),remove(MEL,'ACTIVATE_SKILL',6350)]

def main():
    for tile,d in [([5,5],'RIGHT'),([5,5],'UP'),([5,6],'LEFT')]:
        edits=middle_robot_base()+[change(ANSEL,'DEPLOY',1321,tile=tile,direction=d)]
        if tile==[5,5]: edits += [change(STEWARD,'DEPLOY',6381,tile=[5,3],direction='RIGHT')]
        r=variant(f'FRIS_BOTH_MED{tile[0]}{tile[1]}_{d}',edits,'Friston lower holds all four previous leaks; relocate Ansel to cover persistent Melantha before observed two-shell death@2143. Keep actual ranged support for Steward; explicit later-tile deconfliction. Cannon, armors and both civilians independently checked.')
        if r.get('observed',{}).get('complete_win'):return
    # Can an explicit retreat/redeployment avoid the death while retaining the two established middle blockers?
    for tile in [[6,5],[6,4],[6,3]]:
        edits=middle_robot_base()+[add(MEL,'RETREAT',1967),add(MEL,'DEPLOY',4068,tile=tile,direction='RIGHT'),add(MEL,'ACTIVATE_SKILL',6350)]
        r=variant('FRIS_MEL_RETURN6'+str(tile[1]),edits,'After observed roadblock4 destruction, living Melantha withdraws before second shell and returns on legal cooldown. Different lower outer interception tiles test #16/#18 handoff gap; upper Fang/robot persist.')
        if r.get('observed',{}).get('complete_win'):return
    # Low-cost rescue of upper robot: deploy Lancet before eighth runner hit; Ansel remains full medic.
    edits=SWAP+[{'type':'replace','operator':SPOT,'replacement':FRIS},change(FRIS,'DEPLOY',2341,frame=91,tile=[3,5],direction='UP'),remove(FRIS,'ACTIVATE_SKILL',3330),remove(FRIS,'ACTIVATE_SKILL',6500),{'type':'replace','operator':HIBISC,'replacement':'char_285_medic2'},change('char_285_medic2','DEPLOY',1681,frame=661),remove('char_285_medic2','ACTIVATE_SKILL',2582),remove('char_285_medic2','ACTIVATE_SKILL',4083),remove('char_285_medic2','ACTIVATE_SKILL',6100),remove('char_285_medic2','ACTIVATE_SKILL',7601),change(MEL,'DEPLOY',841,frame=931),remove(MEL,'RETREAT',2054),remove(MEL,'DEPLOY',4155),remove(MEL,'ACTIVATE_SKILL',6350),change(ANSEL,'DEPLOY',1321,tile=[5,5],direction='RIGHT'),change(STEWARD,'DEPLOY',6381,tile=[5,3],direction='RIGHT')]
    variant('FRIS_UP_LANCET_RESCUE',edits,'Lancet arrives before Friston eighth #1 hit to test survival until full medic; exact healing/output and late lower lane role are observed, not assumed.')

if __name__=='__main__':main()
