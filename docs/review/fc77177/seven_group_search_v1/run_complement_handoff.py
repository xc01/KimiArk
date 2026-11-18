from run_handoffs import *
STEWARD='char_210_stward'

def main():
    for hibi_tile,d in [([5,6],'LEFT'),([5,5],'UP'),([5,3],'RIGHT')]:
        edits=[change(FANG,'DEPLOY',0,tile=[4,5],direction='RIGHT'),change(SPOT,'DEPLOY',2341,frame=1321,tile=[3,5],direction='RIGHT'),change(ANSEL,'DEPLOY',1321,frame=2341,tile=[5,5],direction='RIGHT'),change(HIBISC,'DEPLOY',1681,tile=hibi_tile,direction=d),remove(MEL,'RETREAT',2054),remove(MEL,'DEPLOY',4155),change(STEWARD,'DEPLOY',6381,tile=[5,3],direction='RIGHT'),change(SPOT,'ACTIVATE_SKILL',3330,frame=1772),change(SPOT,'ACTIVATE_SKILL',6500,frame=5674),add(SPOT,'ACTIVATE_SKILL',3723),change(ANSEL,'ACTIVATE_SKILL',2072,frame=3092),change(ANSEL,'ACTIVATE_SKILL',3873,frame=4893),change(ANSEL,'ACTIVATE_SKILL',5900,frame=6694),change(ANSEL,'ACTIVATE_SKILL',7701,frame=8495)]
        if hibi_tile==[5,5]:edits[2]=change(ANSEL,'DEPLOY',1321,frame=2341,tile=[5,6],direction='LEFT')
        if hibi_tile==[5,3]:edits[6]=change(STEWARD,'DEPLOY',6381,tile=[2,5],direction='UP')
        r=variant('COMPLEMENT_SPOT_EARLY_HIBI'+str(hibi_tile)+d,edits,'Pay early upper Spot by swapping its purchase with Ansel, not adding an ID. Persistent Melantha keeps lower outer with geometric Hibiscus support before second shell; early Fang/Midnight lower kills retained. Only #1 is already past proposed upper blocker; all later regressions independently checked.')
        if r.get('observed',{}).get('complete_win'):return

if __name__=='__main__':main()
