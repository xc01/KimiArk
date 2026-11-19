from driver import *
if __name__=='__main__':
 round_record(1,'Sustain extra upper Friston using verified medic coverage and Fang DOWN support.','Eight full battles: correct DOWN coverage heals Friston1321/1407 and closes early #1/#6, but cannon splash kills support as early2111-2593; no cannon kill. Other healer tiles do not cover Friston or expose medics.','Rather than add more load to two medics, round2 tests merging two upper damage/blocking roles. Earlier Midnight purchase need not delay Melantha: DP is sufficient before and after Fang income.')
 round_record(2,'Midnight deploys before runner1 crosses a downstream middle tile; DOWN range covers outer upper row1 while self-blocking row3. Preserve Melantha841 and her roadblock4 timing, unlike old coupled delay attempts.','PENDING','If upper compression changes contact, inspect blocked-enemy priority and roadblock3 before retaining it.')
 for tile,d,frame in [([3,4],'DOWN',481),([3,5],'DOWN',451),([3,5],'DOWN',481),([3,3],'DOWN',481),([2,4],'DOWN',481),([2,4],'RIGHT',481),([2,4],'UP',481),([3,4],'DOWN',511)]:
  edits=[set_(MID,'DEPLOY',571,frame=frame,tile=tile,direction=d)]
  if tile==[3,5]:edits.append(set_(MEL,'DEPLOY',4148,tile=[3,4],direction='UP'))
  variant('R2_MID'+''.join(map(str,tile))+d+str(frame),'complementary',edits,'Earlier Midnight middle interception can compress upper two lanes while outer lower Melantha841 clearance stays frozen. Actual self-block priority, top outer kills, lower Fang survival, cannon and both protection routes observed; no exact-position guarantee.',2)
