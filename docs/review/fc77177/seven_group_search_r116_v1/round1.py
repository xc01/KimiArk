from driver import *
def base():
 return [set_(FANG,'DEPLOY',0,tile=[4,5],direction='DOWN'),replace(SPOT,FRIS),set_(FRIS,'DEPLOY',2341,frame=91,tile=[3,5],direction='UP'),rm(FRIS,'ACTIVATE_SKILL',3330),rm(FRIS,'ACTIVATE_SKILL',6500),rm(MEL,'RETREAT',2054),rm(MEL,'DEPLOY',4155),rm(MEL,'ACTIVATE_SKILL',6350)]
if __name__=='__main__':
 round_record(1,'Friston upper blocker must survive officer6 and block #10/#12 after closing #1; Fang DOWN provides extra early damage. Medics must actually reach upper Friston and persistent Melantha.','PENDING','Use first actual lost support/output event to decide next hypothesis.')
 for at,ad,ht,hd in [([5,5],'DOWN',[5,6],'DOWN'),([5,5],'DOWN',[2,6],'UP'),([5,6],'DOWN',[2,5],'UP'),([5,3],'RIGHT',[2,6],'UP'),([5,5],'DOWN',[2,7],'UP')]:
  edits=base()+[set_(ANSEL,'DEPLOY',1321,tile=at,direction=ad),set_(HIBI,'DEPLOY',1681,tile=ht,direction=hd)]
  if at==[5,5]:edits.append(set_(STEW,'DEPLOY',6381,tile=[5,3],direction='RIGHT'))
  variant('R1_UPPER_FRI_A'+''.join(map(str,at))+ad+'_H'+''.join(map(str,ht))+hd,'baseline',edits,'Upper Friston receives actual ranged damage assistance from Fang DOWN, and medic geometry is tested for sustained officer block rather than assuming nearby equals covered; lower outer Melantha persists. Both shell/civilian/armor regressions observed.',1)
