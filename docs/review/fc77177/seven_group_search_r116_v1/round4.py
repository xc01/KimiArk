from driver import *
def outer_swap(hd='LEFT',at=(5,5),ad='RIGHT'):
 # Fang and cheap Friston retain their original two middle lanes; exchange full outer deployment duties.
 changes=[replace(SPOT,FRIS),set_(FRIS,'DEPLOY',2341,frame=91,tile=[4,5],direction='RIGHT'),rm(FRIS,'ACTIVATE_SKILL',3330),rm(FRIS,'ACTIVATE_SKILL',6500),set_(MID,'DEPLOY',571,frame=901,tile=[6,5],direction='RIGHT'),set_(MEL,'DEPLOY',841,frame=571,tile=[1,5],direction='RIGHT'),rm(MEL,'RETREAT',2054),rm(MEL,'DEPLOY',4155),set_(ANSEL,'DEPLOY',1321,frame=1396,tile=list(at),direction=ad),set_(HIBI,'DEPLOY',1681,frame=1741,direction=hd),set_(STEW,'DEPLOY',2071,frame=2131),set_(STEW,'DEPLOY',6381,tile=[2,5],direction='UP')]
 changes += [set_(ANSEL,'ACTIVATE_SKILL',f,frame=f+75) for f in [2072,3873,5900,7701]]
 changes += [set_(HIBI,'ACTIVATE_SKILL',f,frame=f+60) for f in [2582,4083,6100,7601]]
 changes +=[set_(MID,'ACTIVATE_SKILL',1772,frame=2102)]
 changes +=[add(MEL,'ACTIVATE_SKILL',1772),add(MEL,'ACTIVATE_SKILL',3573)]
 return changes
if __name__=='__main__':
 round_record(3,'Earlier Kroos/Adnach/Orchid coverage removes self-block monopoly and should kill first upper runner before escape.','Seven full variants. Kroos damages #1 for1950 but no kill; without blocking its crossing remains too short. Other substitutions likewise leak outer routes; several later die in splash. No parent role union improved.','Round4 exchanges two melee outer duties: preserve actual blocking while moving the long-range guard to the lower clearance/support corridor; inspect exact healer recipients and cannon lock windows.')
 round_record(4,'Melantha upper outer holds runners/officers while Midnight lower outer clears roadblock4 and handles lower queue; original Fang/Friston cover both middle lanes.','PENDING','Use actual earliest split to choose the final round; no additive eighth operator.')
 for hd,at,ad in [('LEFT',(5,5),'RIGHT'),('UP',(5,5),'RIGHT'),('LEFT',(5,6),'DOWN'),('LEFT',(5,5),'UP'),('DOWN',(5,5),'RIGHT')]:
  changes=outer_swap(hd,at,ad)
  variant('R4_SWAP_H'+hd+'_A'+''.join(map(str,at))+ad,'baseline',changes,'Exchange upper/lower outer guards with full DP and skill-linked deployment changes. Melantha blocking must retain upper kills; Midnight range clears lower barricade. Hibi LEFT explicitly covers top guard and both middles while Ansel covers lower/caster; shell exposure, medical capacity and armor regressions observed.',4)
