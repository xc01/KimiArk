from run_handoffs import *

def main():
    # Effective two-action group restored #21/#27/#29/#33. Inspect #19: only one Melantha hit@4155, no block. Move her return interception downstream first, then earlier legal handoff.
    for tile,d in [([3,4],'RIGHT'),([3,4],'UP'),([3,3],'RIGHT'),([3,3],'UP'),([3,5],'RIGHT')]:
        edits=[change(FANG,'DEPLOY',0,tile=[4,5],direction='RIGHT'),change(MEL,'DEPLOY',4155,tile=tile,direction=d)]
        r=variant('FRONTIER_MEL'+str(tile[0])+str(tile[1])+d,edits,'Best complementary branch #19 has only one return hit and no block. A downstream interception tile tests genuine block/kill while frozen opening, shell bait and DP remain identical; regressions on armors/#29/civilians recorded.')
        if r.get('observed',{}).get('complete_win'):return
    for retreat in [1967,1994,2010,2030,2045]:
        edits=[change(FANG,'DEPLOY',0,tile=[4,5],direction='RIGHT'),change(MEL,'RETREAT',2054,frame=retreat),change(MEL,'DEPLOY',4155,frame=retreat+2101,tile=[3,5],direction='UP')]
        r=variant('FRONTIER_EARLY_RETURN'+str(retreat),edits,'After observed roadblock4 destruction@1966, earlier live withdrawal advances legal Melantha upper return. Test #19 actual contact rather than leakage delay; cannon locks change if withdrawal precedes later projectile birth, not assumed safe.')
        if r.get('observed',{}).get('complete_win'):return

if __name__=='__main__':main()
