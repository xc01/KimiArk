from run_defender_groups import *

def support_base():
    edits=outer_defender(SPOT)+[change(HIBISC,'DEPLOY',1681,frame=1741),change(STEWARD,'DEPLOY',2071,frame=2131),change(ANSEL,'DEPLOY',1321,tile=[5,5],direction='RIGHT',frame=1396),change(STEWARD,'DEPLOY',6381,tile=[5,3],direction='RIGHT')]
    edits += [change(HIBISC,'ACTIVATE_SKILL',f,frame=f+60) for f in [2582,4083,6100,7601]]
    edits += [change(ANSEL,'ACTIVATE_SKILL',f,frame=f+75) for f in [2072,3873,5900,7701]]
    return edits

def main():
    for first in [1352,1952,2102,2252,2402]:
        r=variant('SPOT_CLEAR_FIRST'+str(first),support_base()+[add(SPOT,'ACTIVATE_SKILL',f) for f in [first,first+1951,first+3902]],'Explicit four-holder branch; Ansel covers defended outer lane and cannon. Delay Spot healing stoppage to retain actual roadblock4 damage, checking whether its release changes while cannon output remains. Skill recovery is coupled legally.')
        if r.get('observed',{}).get('complete_win'):return

if __name__=='__main__':main()
