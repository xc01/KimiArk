from run_handoffs import *

def main():
    # Preserve all role IDs; shift the two cooperating coverage axes as a group, then directions.
    for col in [4,3]:
        for fd in ['UP','RIGHT']:
            for mt in [[1,col],[1,5]]:
                edits=[change(FANG,'DEPLOY',0,tile=[3,col],direction=fd),change(MID,'DEPLOY',571,tile=mt,direction='UP')]
                r=variant(f'UPPER_GROUP_F{col}{fd}_MID{mt[1]}',edits,'Shift Fang blocking and Midnight long axis as a two-action coverage group; test whether earlier damage or later crossing permits lower-lane kills without abandoning upper blockers.')
                if r.get('observed',{}).get('complete_win'):return
    # Right facing starts damage on the incoming upper lane earlier, without roster change.
    variant('FANG35_RIGHT',[change(FANG,'DEPLOY',0,direction='RIGHT')],'Start upper-lane damage one tile earlier; check whether freed attacks reach lower-lane targets and preserve #29.')
    # Low-cost new blocker replaces Spot, preserving seven-ID union. The two outer guards stay in place.
    for replacement,frame in [('char_4093_frston',91),('char_502_nblade',211),('char_286_cast3',91)]:
        edits=SWAP+[{'type':'replace','operator':SPOT,'replacement':replacement},change(replacement,'DEPLOY',2341,frame=frame,tile=[3,5],direction='UP'),remove(replacement,'ACTIVATE_SKILL',3330),remove(replacement,'ACTIVATE_SKILL',6500),remove(MEL,'RETREAT',2054),remove(MEL,'DEPLOY',4155),remove(MEL,'ACTIVATE_SKILL',6350),add(replacement,'RETREAT',6700)]
        r=variant('CHEAP_UPPER_'+replacement,edits,'Replace Spot group with a low-cost early upper blocker; Melantha explicitly stays at lower outer rather than retreating, while Fang covers lower middle. New blocker must actually survive/kill until late; regressions observed.')
        if r.get('observed',{}).get('complete_win'):return

if __name__=='__main__':main()
