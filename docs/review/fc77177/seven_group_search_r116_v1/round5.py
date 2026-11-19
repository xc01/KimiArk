from driver import *
def sustained(hphase=3140,afirst=2147,mfirst=2102):
 edits=[replace(SPOT,FRIS),set_(FRIS,'DEPLOY',2341,frame=91,tile=[4,5],direction='RIGHT'),rm(FRIS,'ACTIVATE_SKILL',3330),rm(FRIS,'ACTIVATE_SKILL',6500),set_(MEL,'DEPLOY',841,frame=901),rm(MEL,'RETREAT',2054),rm(MEL,'DEPLOY',4155),rm(MEL,'ACTIVATE_SKILL',6350),set_(ANSEL,'DEPLOY',1321,frame=1396,tile=[5,5],direction='RIGHT'),set_(HIBI,'DEPLOY',1681,frame=1740),set_(STEW,'DEPLOY',2071,frame=2131),set_(STEW,'DEPLOY',6381,tile=[2,5],direction='UP')]
 edits +=[set_(ANSEL,'ACTIVATE_SKILL',old,frame=new) for old,new in zip([2072,3873,5900,7701],[afirst,afirst+1801,afirst+3602,afirst+5403])]
 edits +=[set_(HIBI,'ACTIVATE_SKILL',old,frame=hphase+i*1501) for i,old in enumerate([2582,4083,6100,7601])]
 edits +=[add(MEL,'ACTIVATE_SKILL',f) for f in [mfirst,mfirst+1801,mfirst+3602,mfirst+5403]]
 return edits
if __name__=='__main__':
 round_record(4,'Exchange outer Melantha and Midnight tasks to compress support geometry with both middle holders intact.','Five full corrected variants: upper roadblock3 clears1696 and lower roadblock4 clears2422, but Friston dies937 and Fang1209 before medics; blocking survives locally without adequate early damage. No role-union gain.','Final hypothesis retains original early damage assistance and all four lanes, changes sustained Melantha skill load plus source-backed Hibiscus timing rather than shifting the outer guards.')
 round_record(5,'Retain Fang upper all the way through #19/armor21, Friston lower, original outer Midnight, sustained-skilled Melantha lower. A Hibiscus phase covering the actual3311/3970 damage sequence may retain both support and artillery without sacrificing upper interception.','PENDING','This is round5; after its parameter tests, stop and independently verify the most valuable complete new branch or an attained WIN.')
 for hp in [3040,3140,3240,3340]:
  variant('R5_SUSTAIN_H'+str(hp),'baseline',sustained(hp),'Full seven-role persistent blockade with Melantha repeated attack skills and actual Hibiscus phase from known artillery-surviving R112. Fang remains deployed to retain #19/21 upper roles; actual healing competition and shell lock damage determine survival. No net-HP guarantee.',5)
