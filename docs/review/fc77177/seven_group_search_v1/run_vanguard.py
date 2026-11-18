from run_handoffs import *
VAN='char_240_wyvern'

def vanilla_group(first=421,second=1322):
    return [{'type':'replace','operator':FANG,'replacement':VAN}]+[add(VAN,'ACTIVATE_SKILL',f) for f in [first,second,2600,4200,5101,6002,6903]]

def main():
    for first in [421,451,481]:
        for second in [1322,1352]:
            r=variant(f'VAN_UP_F{first}_S{second}',vanilla_group(first,second),'Replace Fang responsibility group with Vanilla same blocking and stronger attack/manual DP skill. Boost during first runner to test freeing upper-range attacks before lower runner passes, while preserving original outer and cannon roles.')
            if r.get('observed',{}).get('complete_win'):return
    # Same explicit higher-output group on complementary branch; late Melantha covers upper handoff.
    for first in [421,571,621]:
        edits=SWAP+vanilla_group(first,1322)
        r=variant('VAN_SWAP_F'+str(first),edits,'Apply complete Vanilla vanguard group to complementary branch; test actual lower-middle retention, upper leakage and both medical/artillery regressions, no eighth ID.')
        if r.get('observed',{}).get('complete_win'):return

if __name__=='__main__':main()
