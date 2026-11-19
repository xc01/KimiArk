from driver import *
KROOS='char_124_kroos';ADN='char_211_adnach';ORCHID='char_278_orchid'
def edits(op,frame,tile,d):
 out=[replace(MID,op),set_(op,'DEPLOY',571,frame=frame,tile=tile,direction=d),rm(op,'ACTIVATE_SKILL',1772),rm(op,'ACTIVATE_SKILL',5073)]
 if op==ADN:out +=[add(op,'ACTIVATE_SKILL',frame+2101),add(op,'ACTIVATE_SKILL',frame+4802)]
 if op==ORCHID:out +=[add(op,'ACTIVATE_SKILL',frame+1351),add(op,'ACTIVATE_SKILL',frame+3452),add(op,'ACTIVATE_SKILL',frame+5553)]
 return out
if __name__=='__main__':
 round_record(2,'Earlier Midnight middle deployment with unchanged Melantha should retain outer-upper output while adding actual upper-middle blocks.','Seven full variants: [3,4]DOWN481 blocks #1@506 and kills, but #4/#8 and further outer-upper enemies leak; shifted geometry excludes or cannot prioritize those targets. Several keep artillery and #14, but #3 fails independently.','Round3 tests ranged multi-lane coverage without SELF_BLOCKED target priority, paying earlier legal deployment rather than previous Kroos571 that misses the first damage opportunity.')
 round_record(3,'Kroos or other legal ranged substitute covers row1 and row3 from [2,5]RIGHT before #1 arrives, while Fang retains row4; no self-block target monopolization.','PENDING','Trace actual hits before a first leak, then change coverage or damage mechanism only if warranted.')
 for parent,op,frame,tile,d in [('complementary',KROOS,331,[2,5],'RIGHT'),('complementary',KROOS,331,[2,6],'LEFT'),('complementary',KROOS,331,[2,3],'RIGHT'),('complementary',ADN,331,[2,5],'RIGHT'),('complementary',ORCHID,361,[2,5],'RIGHT'),('baseline',KROOS,331,[2,5],'RIGHT'),('complementary',KROOS,361,[2,5],'RIGHT')]:
  changes=edits(op,frame,tile,d)
  if tile==[2,6]:changes += [set_(HIBI,'DEPLOY',1681,tile=[2,7],direction='UP')]
  variant('R3_'+parent+'_'+op+'_'+''.join(map(str,tile))+d+str(frame),parent,changes,'Early legal ranged replacement tests simultaneous upper outer/middle damage without self-block priority; parent opening lower route, Melantha roadblock4 and seven-ID budget retained. Actual cannon targeting and civilian clearance independently observed.',3)
