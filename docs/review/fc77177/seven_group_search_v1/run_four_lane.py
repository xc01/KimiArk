from run_handoffs import *
STEWARD='char_210_stward'

def four_lane(outer='char_500_noirc'):
    # Move Midnight's three-tile DOWN axis to the center, so it can hit the top guard's blocked enemies.
    edits=[{'type':'replace','operator':SPOT,'replacement':outer},{'type':'replace','operator':MEL,'replacement':'char_502_nblade'},change(outer,'DEPLOY',2341,frame=721,tile=[1,5],direction='RIGHT'),remove(outer,'ACTIVATE_SKILL',3330),remove(outer,'ACTIVATE_SKILL',6500),change(MID,'DEPLOY',571,tile=[4,5],direction='DOWN'),change('char_502_nblade','DEPLOY',841,frame=931,tile=[6,3],direction='RIGHT'),remove('char_502_nblade','RETREAT',2054),remove('char_502_nblade','DEPLOY',4155),remove('char_502_nblade','ACTIVATE_SKILL',6350),change(ANSEL,'DEPLOY',1321,tile=[5,3],direction='RIGHT'),change(HIBISC,'DEPLOY',1681,frame=1741),change(STEWARD,'DEPLOY',2071,frame=2131)]
    edits +=[change(HIBISC,'ACTIVATE_SKILL',f,frame=f+60) for f in [2582,4083,6100,7601]]
    return edits

def main():
    for bottom in [[6,3],[6,4],[6,5]]:
        r=variant('FOUR_LANE_NOIR_YATO6'+str(bottom[1]),four_lane()+[change('char_502_nblade','DEPLOY',931,tile=bottom)],'A complete four-lane role replacement: Midnight lower-middle DOWN supports top Noir, Fang original upper-middle, cheap Yato lower outer with relocated Ansel. Explicit DP/cooldown paid; roadblock clearance and artillery healing remain risks, not assumed.')
        if r.get('observed',{}).get('complete_win'):return

if __name__=='__main__':main()
