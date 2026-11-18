from run_handoffs import *

def main():
    # Prior Friston run killed #1 but blocker died@787. Advance actual ranged support and pay DP by delaying Melantha, still before her observed #5 contact.
    for replacement,early,mel_frame in [('char_4093_frston',91,931),('char_502_nblade',211,1051)]:
        for mid_frame in [481,511]:
            edits=SWAP+[{'type':'replace','operator':SPOT,'replacement':replacement},change(replacement,'DEPLOY',2341,frame=early,tile=[3,5],direction='UP'),remove(replacement,'ACTIVATE_SKILL',3330),remove(replacement,'ACTIVATE_SKILL',6500),change(MID,'DEPLOY',571,frame=mid_frame),change(MEL,'DEPLOY',841,frame=mel_frame),remove(MEL,'RETREAT',2054),remove(MEL,'DEPLOY',4155),remove(MEL,'ACTIVATE_SKILL',6350)]
            r=variant('CHEAP_SUPPORT_'+replacement+'_MID'+str(mid_frame),edits,'Earlier Midnight attacks should let cheap upper blocker survive #1; Melantha deployment pays DP delay before #5 contact and keeps row6. Check actual survival, #6 treatment, both middle lanes and later armor.')
            if r.get('observed',{}).get('complete_win'):return
    # Original Fang guards upper; cheap replacement holds lower instead. Earlier support can now favor Fang #1 or lower #2 by proximity, exact damage decides.
    for mid_frame in [481,511,571]:
        edits=[{'type':'replace','operator':SPOT,'replacement':'char_4093_frston'},change('char_4093_frston','DEPLOY',2341,frame=91,tile=[4,5],direction='RIGHT'),remove('char_4093_frston','ACTIVATE_SKILL',3330),remove('char_4093_frston','ACTIVATE_SKILL',6500),change(MID,'DEPLOY',571,frame=mid_frame),change(MEL,'DEPLOY',841,frame=931),remove(MEL,'RETREAT',2054),remove(MEL,'DEPLOY',4155),remove(MEL,'ACTIVATE_SKILL',6350)]
        r=variant('FRISTON_LOWER_MID'+str(mid_frame),edits,'Keep baseline Fang upper and cheap Friston lower, Melantha continuously holds outer bottom; actual ranged support must close lower and survive until healing.')
        if r.get('observed',{}).get('complete_win'):return

if __name__=='__main__':main()
